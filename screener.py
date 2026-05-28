"""
screener.py -- Orchestrator Utama Pipeline Screening Saham
==========================================================
Kelas StockScreener mengoordinasikan seluruh proses:
1. Pengumpulan data (Yahoo Finance + IDX API)
2. Enrichment data OHLCV dengan data IDX (foreign flow, orderbook)
3. Feature engineering (indikator teknikal + IDX features)
4. Training model ML (XGBoost)
5. Prediksi probabilitas T+1
6. Filter & ranking saham potensial
"""

import pandas as pd
import numpy as np
from data_ingestion import (
    fetch_ohlcv_yfinance,
    fetch_idx_stock_summary,
    fetch_idx_broker_summary,
    enrich_ohlcv_with_idx,
)
from idx_client import IDXClient
from feature_engineering import FeatureEngineer
from ml_model import T1ProbabilityModel, SelfLearningMetaFilter
from config import MAX_DISPLAY_STOCKS, MIN_WIN_PROBABILITY


class StockScreener:
    """
    Pipeline screening saham harian untuk T+1 trading.

    Pipeline ini mengintegrasikan data OHLCV, tick intraday, dan
    broker summary untuk menghasilkan daftar saham potensial yang
    diurutkan berdasarkan probabilitas kenaikan harga.

    Attributes
    ----------
    feature_engineer : FeatureEngineer
        Instance modul feature engineering.
    model : T1ProbabilityModel
        Instance model ML.
    df_ohlcv : pd.DataFrame
        Data OHLCV harian.
    df_tick : pd.DataFrame
        Data tick intraday.
    df_broker : pd.DataFrame
        Data broker summary.
    df_features : pd.DataFrame
        DataFrame dengan semua fitur.
    df_result : pd.DataFrame
        Hasil screening akhir.
    """

    def __init__(self):
        """Inisialisasi pipeline screening."""
        self.feature_engineer = FeatureEngineer()
        self.model = T1ProbabilityModel()
        self.meta_filter = SelfLearningMetaFilter()
        self.idx_client = IDXClient()
        self.df_ohlcv = None
        self.df_tick = None
        self.df_idx_summary = None
        self.df_broker = None
        self.df_features = None
        self.df_result = None

    def ingest_data(self) -> None:
        """
        Tahap 1: Pengumpulan data dari semua sumber.

        Sumber data:
        - Yahoo Finance: Data OHLCV historis 1 tahun
        - IDX API: Stock Summary harian (foreign flow, orderbook)
        - IDX API: Broker Summary
        - Mock: Tick intraday (simulasi, API gratis tidak tersedia)
        """
        print("=" * 60)
        print("[>] TAHAP 1: PENGUMPULAN DATA (Yahoo Finance + IDX API)")
        print("=" * 60)

        # 1a. OHLCV historis dari Yahoo Finance
        self.df_ohlcv = fetch_ohlcv_yfinance()

        # 1b. Stock Summary dari IDX API (foreign flow, orderbook, frequency)
        self.df_idx_summary = fetch_idx_stock_summary(
            idx_client=self.idx_client, n_days=3
        )

        # 1c. Broker Summary dari IDX API
        self.df_broker = fetch_idx_broker_summary(
            idx_client=self.idx_client
        )

        # 1d. (Dihapus: Data tick intraday simulasi)

        # 1e. Perkaya OHLCV dengan data IDX
        print("   -> Menggabungkan data Yahoo Finance + IDX API...")
        self.df_ohlcv = enrich_ohlcv_with_idx(
            self.df_ohlcv, self.df_idx_summary
        )
        print("   [OK] Data enrichment selesai")

    def engineer_features(self) -> None:
        """
        Tahap 2: Kalkulasi fitur kuantitatif.

        Menghitung indikator teknikal:
        - Volatility Contraction (Bollinger Bandwidth)
        - Momentum Extreme (RSI)
        - Bandarmology VWAP
        - IDX Foreign Flow
        - IDX Bid/Offer Sentiment
        """
        print("=" * 60)
        print("[>] TAHAP 2: FEATURE ENGINEERING")
        print("=" * 60)

        self.df_features = self.feature_engineer.build_features(
            self.df_ohlcv
        )

    def train_model(self) -> dict:
        """
        Tahap 3: Persiapan target dan training model ML.

        Menggunakan data historis untuk melatih XGBoost classifier
        memprediksi probabilitas kenaikan harga T+1.

        Returns
        -------
        dict
            Metrik evaluasi model (AUC-ROC, accuracy, dll.)
        """
        print("=" * 60)
        print("[>] TAHAP 3: TRAINING MODEL ML")
        print("=" * 60)

        # Siapkan target (label 0/1 berdasarkan pergerakan harga T+1)
        df_with_target = self.model.prepare_target(self.df_features)

        # Latih model
        metrics = self.model.train(df_with_target)

        # Tampilkan feature importance
        print("[*] Feature Importance:")
        fi = self.model.get_feature_importance()
        for _, row in fi.iterrows():
            bar = "#" * int(row["importance"] * 50)
            print(f"   {row['feature']:25s} {row['importance']:.4f} {bar}")
        print()

        return metrics

    def get_market_regime(self) -> str:
        """
        Mengecek tren jangka menengah IHSG (^JKSE) menggunakan SMA 50 hari.
        Mengmengembalikan 'BULLISH' jika harga penutupan di atas SMA 50, dan 'BEARISH' jika di bawahnya.
        """
        print("[>] Menghitung tren market regime IHSG...")
        try:
            import yfinance as yf
            df_ihsg = yf.download("^JKSE", period="1y", interval="1d", progress=False)
            if isinstance(df_ihsg.columns, pd.MultiIndex):
                df_ihsg.columns = df_ihsg.columns.get_level_values(0)
            
            df_ihsg = df_ihsg.dropna(subset=["Close"])
            df_ihsg['sma_50'] = df_ihsg['Close'].rolling(50).mean()
            
            latest_close = float(df_ihsg['Close'].iloc[-1])
            latest_sma_50 = float(df_ihsg['sma_50'].iloc[-1])
            
            self.ihsg_close = latest_close
            self.ihsg_sma_50 = latest_sma_50
            
            if latest_close >= latest_sma_50:
                print(f"   [IHSG] Close: {latest_close:,.2f} >= SMA 50: {latest_sma_50:,.2f} -> BULLISH REGIME")
                self.market_regime = "BULLISH"
            else:
                print(f"   [IHSG] Close: {latest_close:,.2f} < SMA 50: {latest_sma_50:,.2f} -> BEARISH REGIME")
                self.market_regime = "BEARISH"
        except Exception as e:
            print(f"   [!] Gagal mendownload data IHSG: {e}. Menggunakan default BULLISH.")
            self.ihsg_close = 0.0
            self.ihsg_sma_50 = 0.0
            self.market_regime = "BULLISH"
        return self.market_regime

    def predict_and_screen(self) -> pd.DataFrame:
        """
        Tahap 4: Prediksi probabilitas T+1 dan screening.

        Proses:
        1. Hitung tren IHSG untuk market regime filter
        2. Ambil data HARI TERAKHIR (hari ini) untuk setiap saham
        3. Filter saham dengan likuiditas & volatilitas tinggi
        4. Prediksi probabilitas kenaikan menggunakan model
        5. Filter HANYA saham dengan minimal 1 sinyal True
        6. Urutkan berdasarkan win_probability (tertinggi ke terendah)
        """
        print("=" * 60)
        print("[>] TAHAP 4: SCREENING & PREDIKSI T+1")
        print("=" * 60)

        # Hitung tren IHSG untuk market regime filter
        self.get_market_regime()

        # Ambil data hari terakhir (terbaru) per saham
        latest_date = self.df_features["date"].max()
        df_latest = self.df_features[
            self.df_features["date"] == latest_date
        ].copy()

        print(f"   -> Tanggal screening: {latest_date.strftime('%Y-%m-%d')}")
        print(f"   -> Jumlah saham sebelum filter: {len(df_latest)}")

        # --- PRE-FILTER: LIKUIDITAS & VOLATILITAS (BARU) ---
        # Membatasi saham dengan rata-rata volume harian >= 1.000.000 dan volatilitas historis >= 2.5%
        df_latest["unlogged_avg_volume"] = np.expm1(df_latest["avg_volume"])
        df_latest = df_latest[
            (df_latest["unlogged_avg_volume"] >= 1000000) & 
            (df_latest["hist_volatility"] >= 0.025)
        ].copy()
        print(f"   -> Jumlah saham setelah filter likuiditas & volatilitas: {len(df_latest)}")

        # Prediksi probabilitas kenaikan T+1
        if not df_latest.empty:
            df_latest = self.model.predict_proba(df_latest)
        else:
            print("   [!] Tidak ada saham yang lolos filter likuiditas & volatilitas.")
            self.df_result = pd.DataFrame()
            return self.df_result

        # ------------------------------------------------------------------
        # FILTER: Hanya saham dengan sinyal True dari indikator teknikal
        # ------------------------------------------------------------------
        signal_columns = [
            "signal_volatility_contraction",
            "signal_momentum_extreme",
            "signal_bandarmology",
            "signal_foreign_inflow",
            "signal_strong_bid",
        ]

        # Hitung jumlah sinyal aktif per saham
        df_latest["total_signals"] = df_latest[signal_columns].sum(axis=1)

        # Filter: minimal 1 sinyal aktif
        df_screened = df_latest[df_latest["total_signals"] >= 1].copy()

        # FILTER MANDATORI (BANDARMOLOGY): Hanya masukkan saham yang sedang diakumulasi oleh bandar (tidak didistribusi)
        df_screened = df_screened[df_screened["signal_bandarmology"] == True].copy()

        # Filter: probabilitas minimum
        df_screened = df_screened[
            df_screened["win_probability"] >= MIN_WIN_PROBABILITY
        ]

        # --- SELF-LEARNING META-FILTER CORRECTION (BARU) ---
        if self.meta_filter.is_trained:
            print("   [META-FILTER] Menerapkan koreksi adaptif dari ML Self-Learning Hub...")
            meta_scores = []
            for _, row in df_screened.iterrows():
                score = self.meta_filter.predict_correction_score(row)
                meta_scores.append(score)
            df_screened["meta_filter_score"] = meta_scores
            
            # Terapkan koreksi: jika safety score < 0.45, potong win_probability drastis!
            # Dan sesuaikan win_probability secara halus jika di atas 0.45.
            for idx, row in df_screened.iterrows():
                score = row["meta_filter_score"]
                if score < 0.45:
                    print(f"      [META-FILTER] Saham {row['ticker']} ditolak oleh Meta-Filter (Skor Keselamatan: {score:.1%})!")
                    df_screened.at[idx, "win_probability"] = row["win_probability"] * 0.1
                else:
                    df_screened.at[idx, "win_probability"] = row["win_probability"] * (0.6 + 0.4 * score)
            
            # Filter ulang berdasarkan win_probability setelah koreksi
            df_screened = df_screened[df_screened["win_probability"] >= MIN_WIN_PROBABILITY].copy()

        # Urutkan berdasarkan win_probability (tertinggi dulu)
        df_screened.sort_values("win_probability", ascending=False, inplace=True)
        df_screened.reset_index(drop=True, inplace=True)

        # Batasi jumlah tampilan
        df_screened = df_screened.head(MAX_DISPLAY_STOCKS)

        # --- OPTIMASI ALOKASI PORTFOLIO KELLY CRITERION (BARU) ---
        print("   -> Menghitung alokasi portofolio optimal (Kelly)...")
        from portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer()
        df_screened = optimizer.optimize_allocations(df_screened, market_regime=self.market_regime)

        self.df_result = df_screened

        print(f"   -> Saham yang lolos filter & teroptimasi: {len(df_screened)}")
        print()

        return df_screened

    def format_output(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Format DataFrame hasil screening menjadi tabel yang rapi
        untuk ditampilkan ke pengguna.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame hasil screening.

        Returns
        -------
        pd.DataFrame
            DataFrame yang sudah diformat dengan kolom pilihan.
        """
        # Kolom yang ditampilkan di output final
        display_columns = [
            "ticker",
            "close",
            "volume",
            "win_probability",
            "profit_score",
            "kelly_pct",
            "stop_loss",
            "take_profit",
            "cluster_id",
            "rsi_14",
            "vwap_ratio",
            "foreign_net",
            "bid_offer_ratio",
            "signal_volatility_contraction",
            "signal_momentum_extreme",
            "signal_bandarmology",
            "signal_foreign_inflow",
            "signal_strong_bid",
            "total_signals",
        ]

        # Ambil kolom yang ada saja
        available = [c for c in display_columns if c in df.columns]
        df_display = df[available].copy()

        # Format angka
        if "close" in df_display.columns:
            df_display["close"] = df_display["close"].apply(
                lambda x: f"Rp {x:,.0f}" if isinstance(x, (int, float)) else str(x)
            )
        if "volume" in df_display.columns:
            df_display["volume"] = df_display["volume"].apply(
                lambda x: f"{x:,.0f}" if isinstance(x, (int, float)) else str(x)
            )
        if "win_probability" in df_display.columns:
            df_display["win_probability"] = df_display["win_probability"].apply(
                lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else str(x)
            )
        if "profit_score" in df_display.columns:
            df_display["profit_score"] = df_display["profit_score"].apply(
                lambda x: f"{x:.1f}" if isinstance(x, (int, float)) else str(x)
            )
        if "kelly_pct" in df_display.columns:
            df_display["kelly_pct"] = df_display["kelly_pct"].apply(
                lambda x: f"{x:.2f}%" if isinstance(x, (int, float)) else str(x)
            )
        if "stop_loss" in df_display.columns:
            df_display["stop_loss"] = df_display["stop_loss"].apply(
                lambda x: f"Rp {x:,.0f}" if isinstance(x, (int, float)) else str(x)
            )
        if "take_profit" in df_display.columns:
            df_display["take_profit"] = df_display["take_profit"].apply(
                lambda x: f"Rp {x:,.0f}" if isinstance(x, (int, float)) else str(x)
            )
        if "rsi_14" in df_display.columns:
            df_display["rsi_14"] = df_display["rsi_14"].round(1)
        if "bb_bandwidth" in df_display.columns:
            df_display["bb_bandwidth"] = df_display["bb_bandwidth"].round(4)
        if "vwap_ratio" in df_display.columns:
            df_display["vwap_ratio"] = df_display["vwap_ratio"].round(4)
        if "foreign_net" in df_display.columns:
            df_display["foreign_net"] = df_display["foreign_net"].apply(
                lambda x: f"{x:,.0f}" if pd.notna(x) else "0"
            )
        if "bid_offer_ratio" in df_display.columns:
            df_display["bid_offer_ratio"] = df_display["bid_offer_ratio"].round(2)

        # Ganti True/False dengan tanda Y/N
        for col in signal_cols_list(df_display):
            df_display[col] = df_display[col].map({True: "[Y]", False: "[N]"})

        # Rename kolom agar lebih mudah dibaca
        rename_map = {
            "ticker": "Saham",
            "close": "Harga",
            "volume": "Volume",
            "win_probability": "Prob. T+1",
            "profit_score": "Skor Profit",
            "kelly_pct": "Alokasi Kelly",
            "stop_loss": "Stop Loss",
            "take_profit": "Take Profit",
            "cluster_id": "Cluster",
            "rsi_14": "RSI(14)",
            "bb_bandwidth": "BB Width",
            "vwap_ratio": "VWAP Ratio",
            "foreign_net": "Foreign Net",
            "bid_offer_ratio": "Bid/Offer",
            "signal_volatility_contraction": "Vol.Contract",
            "signal_momentum_extreme": "RSI Oversold",
            "signal_bandarmology": "Bandar",
            "signal_foreign_inflow": "Asing Beli",
            "signal_strong_bid": "Bid Kuat",
            "total_signals": "Sinyal",
        }

        df_display.rename(columns=rename_map, inplace=True)

        return df_display

    def run(self) -> pd.DataFrame:
        """
        Jalankan seluruh pipeline screening dari awal hingga akhir.

        Returns
        -------
        pd.DataFrame
            DataFrame hasil screening saham potensial.
        """
        print("\n" + "=" * 60)
        print("  PIPELINE SCREENING SAHAM HARIAN IHSG")
        print("  -- Analisis T+1 Trading --")
        print("=" * 60 + "\n")

        # Tahap 1: Ingest Data
        self.ingest_data()
        print()

        # Tahap 2: Feature Engineering
        self.engineer_features()

        # Tahap 3: Training Model
        self.train_model()

        # Tahap 4: Screening & Prediksi
        df_screened = self.predict_and_screen()

        return df_screened


def signal_cols_list(df: pd.DataFrame) -> list:
    """Helper: ambil daftar kolom sinyal yang ada di DataFrame."""
    return [c for c in df.columns if c.startswith("signal_")]
