"""
feature_engineering.py -- Modul Kalkulasi Fitur Kuantitatif
==========================================================
Mengimplementasikan indikator teknikal sebagai fitur untuk model ML:

1. Volatility Contraction (Bollinger Bandwidth di persentil rendah)
2. Momentum Extreme (RSI oversold < 25)
3. Bandarmology VWAP (rasio Close/VWAP > 1)
4. IDX Foreign Flow (aliran dana asing dari data IDX riil)
5. IDX Bid/Offer Sentiment (rasio bid/offer dari orderbook IDX)

Setiap indikator menghasilkan kolom sinyal True/False.
"""

import pandas as pd
import numpy as np
import ta
from config import (
    ROLLING_WINDOW_DAYS, BB_PERCENTILE_THRESHOLD, SMA_PERIOD,
    BB_PERIOD, BB_STD_DEV, RSI_PERIOD, RSI_OVERSOLD_THRESHOLD,
    VWAP_RATIO_THRESHOLD, VMA_PERIOD
)


class FeatureEngineer:
    """
    Kelas untuk menghitung semua fitur kuantitatif per saham.
    Setiap method menambahkan kolom baru ke DataFrame.
    """

    def __init__(self):
        """Inisialisasi FeatureEngineer."""
        pass

    def calc_volatility_contraction(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Menghitung Volatility Contraction menggunakan Bollinger Bandwidth.

        LOGIKA:
        - Bollinger Bandwidth = (Upper Band - Lower Band) / Middle Band
        - Jika Bandwidth berada di persentil 10 terbawah dalam 6 bulan terakhir
          DAN harga Close berada di atas SMA 20, maka sinyal = True.
        - Ini menandakan pasar sedang "compressed" (volatilitas rendah) yang
          sering mendahului pergerakan besar (breakout).

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame OHLCV yang sudah diurutkan per saham per tanggal.

        Returns
        -------
        pd.DataFrame
            DataFrame dengan kolom tambahan:
            - bb_bandwidth: Nilai Bollinger Bandwidth
            - sma_20: Simple Moving Average 20 hari
            - signal_volatility_contraction: True/False
        """
        result_frames = []

        for ticker, group in df.groupby("ticker"):
            group = group.copy().sort_values("date").reset_index(drop=True)

            # Hitung Bollinger Bands menggunakan library `ta`
            bb_indicator = ta.volatility.BollingerBands(
                close=group["close"],
                window=BB_PERIOD,
                window_dev=BB_STD_DEV
            )

            # Bollinger Bandwidth = (Upper - Lower) / Middle
            group["bb_bandwidth"] = bb_indicator.bollinger_wband()

            # SMA 20 untuk filter tren
            group["sma_20"] = ta.trend.sma_indicator(
                close=group["close"], window=SMA_PERIOD
            )

            # Hitung persentil rolling 6 bulan dari Bandwidth
            group["bb_pct"] = group["bb_bandwidth"].rolling(
                window=ROLLING_WINDOW_DAYS, min_periods=30
            ).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100,
                raw=False
            )

            # SINYAL: Bandwidth di persentil 10 terbawah DAN Close > SMA 20
            group["signal_volatility_contraction"] = (
                (group["bb_pct"] <= BB_PERCENTILE_THRESHOLD) &
                (group["close"] > group["sma_20"])
            )

            result_frames.append(group)

        return pd.concat(result_frames, ignore_index=True)

    def calc_momentum_extreme(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Menghitung Momentum Extreme menggunakan RSI (Relative Strength Index).

        LOGIKA:
        - RSI < 25 menandakan saham dalam kondisi OVERSOLD (terjual berlebihan).
        - Secara statistik, saham oversold memiliki probabilitas lebih tinggi
          untuk mengalami mean reversion (bounce back) di hari berikutnya.

        Returns: DataFrame dengan kolom rsi_14, signal_momentum_extreme
        """
        result_frames = []

        for ticker, group in df.groupby("ticker"):
            group = group.copy().sort_values("date").reset_index(drop=True)

            # Hitung RSI menggunakan library `ta`
            group["rsi_14"] = ta.momentum.rsi(
                close=group["close"], window=RSI_PERIOD
            )

            # SINYAL: RSI di bawah threshold oversold
            group["signal_momentum_extreme"] = (
                group["rsi_14"] < RSI_OVERSOLD_THRESHOLD
            )

            result_frames.append(group)

        return pd.concat(result_frames, ignore_index=True)

    def calc_bandarmology_vwap(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Menghitung VWAP (Volume Weighted Average Price) dan rasio Close/VWAP.

        LOGIKA:
        - VWAP = cumsum(Close * Volume) / cumsum(Volume) per saham
        - Rasio > 1.0 berarti harga Close LEBIH TINGGI dari rata-rata harga
          yang diboboti volume — mengindikasikan akumulasi oleh pihak bermodal
          besar (bandar).
        - Semakin tinggi rasio, semakin kuat indikasi akumulasi.

        Returns: DataFrame dengan kolom vwap, vwap_ratio, signal_bandarmology
        """
        result_frames = []

        for ticker, group in df.groupby("ticker"):
            group = group.copy().sort_values("date").reset_index(drop=True)

            # VWAP kumulatif = sum(Close × Volume) / sum(Volume)
            group["_cv"] = (group["close"] * group["volume"]).cumsum()
            group["_v"] = group["volume"].cumsum()
            group["vwap"] = group["_cv"] / group["_v"]

            # Rasio Close terhadap VWAP
            group["vwap_ratio"] = group["close"] / group["vwap"]

            # SINYAL: Harga bertahan di atas VWAP (akumulasi bandar)
            group["signal_bandarmology"] = (
                group["vwap_ratio"] > VWAP_RATIO_THRESHOLD
            )

            # Bersihkan kolom sementara
            group.drop(columns=["_cv", "_v"], inplace=True)

            result_frames.append(group)

        return pd.concat(result_frames, ignore_index=True)

    def calc_momentum_spikes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Menghitung fitur Momentum dan Volume Spike.
        1. volume_spike_ratio: rasio volume hari ini dibanding Volume Moving Average.
        2. close_to_high_ratio: kedekatan penutupan dengan harga tertinggi hari ini.
        """
        result_frames = []

        for ticker, group in df.groupby("ticker"):
            group = group.copy().sort_values("date").reset_index(drop=True)

            # Volume Moving Average
            group["vma_20"] = group["volume"].rolling(window=VMA_PERIOD, min_periods=1).mean()
            
            # Volume Spike Ratio
            # Handle division by zero
            group["volume_spike_ratio"] = np.where(
                group["vma_20"] > 0, 
                group["volume"] / group["vma_20"], 
                1.0
            )

            # Close vs High Ratio: (Close - Low) / (High - Low)
            range_val = group["high"] - group["low"]
            group["close_to_high_ratio"] = np.where(
                range_val > 0,
                (group["close"] - group["low"]) / range_val,
                1.0 # Jika tidak ada pergerakan, asumsikan kuat di penutupan jika close==high
            )

            result_frames.append(group)

        return pd.concat(result_frames, ignore_index=True)

    def calc_idx_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Menghitung fitur tambahan dari data IDX API.

        LOGIKA:
        - foreign_net > 0: Investor asing NET BELI (bullish signal)
        - bid_offer_ratio > 1.2: Lebih banyak bid daripada offer (demand tinggi)

        Fitur ini berasal dari data riil IDX, bukan simulasi.
        Kolom yang diharapkan sudah ada di df: foreign_net, bid_offer_ratio

        Returns: DataFrame dengan kolom signal_foreign_inflow, signal_strong_bid
        """
        df = df.copy()

        # -- Sinyal Foreign Inflow --
        # True jika investor asing net beli (foreign_net > 0)
        if "foreign_net" in df.columns:
            df["signal_foreign_inflow"] = df["foreign_net"] > 0
        else:
            df["signal_foreign_inflow"] = False

        # -- Sinyal Bid Kuat --
        # True jika bid/offer ratio > 1.2 (demand melebihi supply di orderbook)
        if "bid_offer_ratio" in df.columns:
            df["signal_strong_bid"] = df["bid_offer_ratio"] > 1.2
        else:
            df["signal_strong_bid"] = False

        return df

    def calc_stock_profiles(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Menghitung profil saham historis untuk keperluan clustering (Heterogeneity).
        
        Fitur yang dihitung:
        - `hist_volatility`: Standar deviasi pergerakan harga harian.
        - `avg_volume`: Rata-rata volume harian jangka panjang.
        """
        df["daily_return"] = df.groupby("ticker")["close"].pct_change()
        
        profile_stats = df.groupby("ticker").agg(
            hist_volatility=("daily_return", "std"),
            avg_volume=("volume", "mean")
        ).reset_index()
        
        df = df.merge(profile_stats, on="ticker", how="left")
        
        df["hist_volatility"] = df["hist_volatility"].fillna(df["hist_volatility"].median())
        df["avg_volume"] = df["avg_volume"].fillna(df["avg_volume"].median())
        
        # Log-Transform pada volume untuk mencegah outlier mendominasi K-Means
        df["avg_volume"] = np.log1p(df["avg_volume"])
        
        df.drop(columns=["daily_return"], inplace=True)
        
        return df

    def build_features(self, df_ohlcv: pd.DataFrame) -> pd.DataFrame:
        """
        Orkestrasi: jalankan semua kalkulasi fitur secara berurutan.

        Parameters
        ----------
        df_ohlcv : pd.DataFrame
            Data OHLCV harian (sudah diperkaya dengan data IDX jika tersedia).

        Returns
        -------
        pd.DataFrame
            DataFrame lengkap dengan semua fitur dan sinyal.
        """
        print("\n[>] Memulai Feature Engineering...")

        # 1. Volatility Contraction
        print("   -> Menghitung Bollinger Bandwidth & Volatility Contraction...")
        df = self.calc_volatility_contraction(df_ohlcv)

        # 2. Momentum Extreme (RSI)
        print("   -> Menghitung RSI & Momentum Extreme...")
        df = self.calc_momentum_extreme(df)

        # 3. Bandarmology VWAP
        print("   -> Menghitung VWAP & Rasio Bandarmologi...")
        df = self.calc_bandarmology_vwap(df)

        # 4. Momentum Spikes
        print("   -> Menghitung Momentum Spikes & Price Action...")
        df = self.calc_momentum_spikes(df)

        # 5. IDX Features (Foreign Flow + Bid/Offer Sentiment)
        print("   -> Menghitung fitur IDX (Foreign Flow, Bid/Offer)...")
        df = self.calc_idx_features(df)

        # 5. Stock Profiles (Untuk Clustering)
        print("   -> Membangun Profil Saham (Heterogeneity)...")
        df = self.calc_stock_profiles(df)

        print("[OK] Feature Engineering selesai!\n")
        return df
