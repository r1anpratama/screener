"""
portfolio_optimizer.py — Manajemen Risiko & Alokasi Kelly Criterion
===================================================================
Modul ini mengimplementasikan Kelly Criterion untuk menentukan alokasi
modal yang optimal secara matematis guna memaksimalkan compounding profit
sekaligus membatasi risiko drawdown menggunakan dynamic ATR-based stops.
"""

import pandas as pd
import numpy as np
from config import (
    KELLY_FRACTION, SL_ATR_MULTIPLIER, TP_ATR_MULTIPLIER
)

class PortfolioOptimizer:
    """
    Kelas untuk mengoptimalkan alokasi portofolio menggunakan formula Kelly Criterion.
    """

    def __init__(self, kelly_fraction: float = KELLY_FRACTION):
        """
        Parameters
        ----------
        kelly_fraction : float
            Faktor pengali Kelly (default: 0.5 = Half-Kelly).
            Membantu mengurangi volatilitas portfolio sambil mempertahankan
            sebagian besar tingkat pertumbuhan geometris.
        """
        self.kelly_fraction = kelly_fraction

    def calculate_single_kelly(
        self, win_probability: float, risk_reward_ratio: float
    ) -> float:
        """
        Menghitung alokasi Kelly untuk satu saham.
        
        Formula: f* = p - (q / R) = (p * (R + 1) - 1) / R
        di mana:
        - p = probabilitas menang (win_probability dalam desimal)
        - q = probabilitas kalah (1 - p)
        - R = risk-reward ratio (TP_pct / SL_pct)
        """
        p = win_probability / 100.0
        q = 1.0 - p
        R = risk_reward_ratio

        if R <= 0:
            return 0.0

        # Formula Kelly standar
        f_star = p - (q / R)

        # Kalikan dengan Kelly Fraction (misal: Half-Kelly)
        allocation = f_star * self.kelly_fraction

        # Batasi alokasi agar tidak negatif (hanya buy/long saja)
        return max(0.0, allocation)

    def optimize_allocations(
        self, df_picks: pd.DataFrame, max_single_allocation: float = 0.25, market_regime: str = "BULLISH"
    ) -> pd.DataFrame:
        """
        Menghitung alokasi optimal untuk sekeranjang saham pilihan hasil screening.
        
        Langkah-langkah:
        1. Hitung tingkat Volatilitas Relatif menggunakan ATR (Average True Range)
        2. Tentukan Stop Loss (SL) dan Take Profit (TP) dinamis berbasis ATR:
           - SL = SL_ATR_MULTIPLIER * ATR
           - TP = TP_ATR_MULTIPLIER * ATR
        3. Hitung Risk-Reward Ratio (R) = TP / SL
        4. Tentukan alokasi Kelly untuk masing-masing saham
        5. Lakukan diversifikasi dengan membatasi alokasi maksimal per saham (default: 25%)
        6. Kurangi alokasi Kelly sebesar 50% jika tren IHSG Bearish (Market Regime Overlay)
        7. Normalisasi alokasi jika total alokasi melebihi 100% modal (tanpa leverage)

        Parameters
        ----------
        df_picks : pd.DataFrame
            DataFrame berisi saham-saham hasil screening harian.
            Wajib memiliki kolom: 'ticker', 'close', 'atr', 'win_probability'
        max_single_allocation : float
            Batas maksimal alokasi modal pada satu ticker saham (default: 25%).
            Mencegah konsentrasi berlebih yang melanggar prinsip manajemen risiko.
        market_regime : str
            Kondisi tren pasar saat ini ('BULLISH' atau 'BEARISH').

        Returns
        -------
        pd.DataFrame
            DataFrame yang dilengkapi kolom kalkulasi risiko dan alokasi modal.
        """
        df = df_picks.copy()
        if df.empty:
            return df

        # Pastikan kolom-kolom penting tersedia
        for col in ["close", "atr", "win_probability"]:
            if col not in df.columns:
                if col == "atr":
                    df["atr"] = df["close"] * 0.02  # fallback jika tidak ada ATR
                elif col == "win_probability":
                    df["win_probability"] = 50.0  # fallback koin seimbang

        # 1. Hitung SL & TP dinamis berbasis rupiah & persentase
        df["sl_rupiah"] = (df["atr"] * SL_ATR_MULTIPLIER).round(0)
        df["tp_rupiah"] = (df["atr"] * TP_ATR_MULTIPLIER).round(0)

        # Harga batas bawah dan atas
        df["entry_price"] = df["close"]
        df["stop_loss"] = df["entry_price"] - df["sl_rupiah"]
        df["take_profit"] = df["entry_price"] + df["tp_rupiah"]

        # Persentase jarak SL & TP
        df["sl_pct"] = df["sl_rupiah"] / df["entry_price"]
        df["tp_pct"] = df["tp_rupiah"] / df["entry_price"]

        # 2. Risk-Reward Ratio (R)
        # R = TP_pct / SL_pct = tp_rupiah / sl_rupiah
        df["risk_reward_ratio"] = df["tp_rupiah"] / df["sl_rupiah"]

        # 3. Hitung Kelly Allocation mentah
        raw_kellys = []
        for _, row in df.iterrows():
            k = self.calculate_single_kelly(
                row["win_probability"], row["risk_reward_ratio"]
            )
            raw_kellys.append(k)
        
        df["raw_kelly"] = raw_kellys

        # 4. Batasi alokasi maksimal per saham (diversifikasi)
        df["optimized_kelly"] = df["raw_kelly"].apply(lambda x: min(x, max_single_allocation))

        # --- RISIKO REGIME PASAR (BARU) ---
        # Jika IHSG sedang bearish, kurangi alokasi Kelly sebesar 50% untuk mengamankan modal (Capital Preservation Overlay)
        if market_regime == "BEARISH":
            df["optimized_kelly"] = df["optimized_kelly"] * 0.5
            print("   [OVERLAY] Tren IHSG BEARISH! Memotong alokasi Kelly sebesar 50% untuk manajemen risiko modal.")

        # 5. Normalisasi jika total alokasi melampaui 100% modal (tanpa leverage)
        total_alloc = df["optimized_kelly"].sum()
        if total_alloc > 1.0:
            df["portfolio_weight"] = df["optimized_kelly"] / total_alloc
        else:
            df["portfolio_weight"] = df["optimized_kelly"]

        # Konversi alokasi ke persentase tampilan
        df["kelly_pct"] = (df["portfolio_weight"] * 100).round(2)

        # 6. Hitung Composite Profit Score
        # Mengombinasikan Probabilitas Win, Orderbook Demand, Volume Spike, dan Aliran Asing
        # untuk menyeleksi emiten dengan probabilitas tertinggi yang didukung oleh "Bandar"
        bid_offer = df["bid_offer_ratio"] if "bid_offer_ratio" in df.columns else 1.0
        vol_spike = df["volume_spike_ratio"] if "volume_spike_ratio" in df.columns else 1.0
        foreign = df["signal_foreign_inflow"] if "signal_foreign_inflow" in df.columns else False
        
        # Normalkan rasio orderbook dan volume spike agar tidak mendistorsi skor jika ada anomali ekstrem
        norm_bid_offer = np.minimum(bid_offer, 3.0) / 3.0
        norm_vol_spike = np.minimum(vol_spike, 5.0) / 5.0
        
        df["profit_score"] = (
            (df["win_probability"] * 0.4) +
            (norm_bid_offer * 20.0) +
            (norm_vol_spike * 20.0) +
            (foreign.astype(float) * 20.0)
        ).round(1)

        # Urutkan berdasarkan profit_score tertinggi (lebih valid dibanding probabilitas mentah saja)
        df.sort_values("profit_score", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df
