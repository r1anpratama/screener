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
from ml_model import T1ProbabilityModel
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

    def predict_and_screen(self) -> pd.DataFrame:
        """
        Tahap 4: Prediksi probabilitas T+1 dan screening.

        Proses:
        1. Ambil data HARI TERAKHIR (hari ini) untuk setiap saham
        2. Prediksi probabilitas kenaikan menggunakan model
        3. Filter HANYA saham dengan minimal 1 sinyal True
        4. Urutkan berdasarkan win_probability (tertinggi ke terendah)

        Returns
        -------
        pd.DataFrame
            DataFrame hasil screening.
        """
        print("=" * 60)
        print("[>] TAHAP 4: SCREENING & PREDIKSI T+1")
        print("=" * 60)

        # Ambil data hari terakhir (terbaru) per saham
        latest_date = self.df_features["date"].max()
        df_latest = self.df_features[
            self.df_features["date"] == latest_date
        ].copy()

        print(f"   -> Tanggal screening: {latest_date.strftime('%Y-%m-%d')}")
        print(f"   -> Jumlah saham dianalisis: {len(df_latest)}")

        # Prediksi probabilitas kenaikan T+1
        df_latest = self.model.predict_proba(df_latest)

        # ------------------------------------------------------------------
        # FILTER: Hanya saham dengan sinyal True dari indikator teknikal
        # ------------------------------------------------------------------
        # Saham harus memenuhi MINIMAL SATU kondisi berikut:
        # - Volatility Contraction = True
        # - Momentum Extreme (RSI oversold) = True
        # - Bandarmology (VWAP ratio > 1) = True
        # - Pre-Closing Anomaly = True
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

        # Filter: probabilitas minimum
        df_screened = df_screened[
            df_screened["win_probability"] >= MIN_WIN_PROBABILITY
        ]

        # Urutkan berdasarkan win_probability (tertinggi dulu)
        df_screened.sort_values("win_probability", ascending=False, inplace=True)
        df_screened.reset_index(drop=True, inplace=True)

        # Batasi jumlah tampilan
        df_screened = df_screened.head(MAX_DISPLAY_STOCKS)

        self.df_result = df_screened

        print(f"   -> Saham yang lolos filter: {len(df_screened)}")
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
                lambda x: f"Rp {x:,.0f}"
            )
        if "volume" in df_display.columns:
            df_display["volume"] = df_display["volume"].apply(
                lambda x: f"{x:,.0f}"
            )
        if "win_probability" in df_display.columns:
            df_display["win_probability"] = df_display["win_probability"].apply(
                lambda x: f"{x:.1f}%"
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
