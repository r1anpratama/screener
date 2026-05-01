"""
data_ingestion.py — Modul Pengumpulan Data Multi-Source
========================================================
Mengambil data dari DUA sumber:

1. Yahoo Finance (yfinance) — Data OHLCV historis 1 tahun
2. IDX API (idx.co.id) — Data tambahan riil:
   - Stock Summary harian (foreign flow, orderbook, frequency)
   - Broker Summary (aktivitas per broker)
   - Top Gainers/Losers

Data IDX digunakan untuk memperkaya fitur ML:
- foreign_net_flow: aliran dana asing (beli - jual)
- bid_offer_ratio: rasio bid/offer volume (sentimen orderbook)
- trade_frequency: frekuensi transaksi (likuiditas)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

from idx_client import IDXClient
from config import (
    TICKERS, N_TRADING_DAYS, RANDOM_SEED
)


# =====================================================================
# SUMBER 1: Yahoo Finance — Data OHLCV Historis
# =====================================================================

def fetch_ohlcv_yfinance(
    tickers: list = TICKERS,
) -> pd.DataFrame:
    """
    Download data riil OHLCV harian dari Yahoo Finance (1 tahun terakhir).
    Menggunakan suffix .JK untuk saham yang terdaftar di BEI.

    Returns: DataFrame[date, ticker, open, high, low, close, volume]
    """
    print(f"   -> Mendownload OHLCV dari Yahoo Finance ({len(tickers)} saham)...")
    all_data = []

    for ticker in tickers:
        try:
            df = yf.download(
                f"{ticker}.JK", period="3y", interval="1d", progress=False
            )
            if df.empty:
                continue

            # Handle MultiIndex columns (yfinance v0.2+)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.reset_index()
            df = df.rename(columns={
                "Date": "date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume"
            })
            df["ticker"] = ticker
            df = df.dropna(subset=["close", "volume"])
            df = df[df["volume"] > 0]

            all_data.append(
                df[["date", "ticker", "open", "high", "low", "close", "volume"]]
            )
        except Exception:
            pass

    if not all_data:
        print("   [!] Gagal mendownload data OHLCV apapun dari Yahoo Finance.")
        return pd.DataFrame()

    df_result = pd.concat(all_data, ignore_index=True)
    df_result["date"] = pd.to_datetime(df_result["date"]).dt.tz_localize(None)
    df_result.sort_values(["date", "ticker"], inplace=True)
    df_result.reset_index(drop=True, inplace=True)

    n_stocks = len(df_result["ticker"].unique())
    print(f"   [OK] Yahoo Finance: {n_stocks} saham berhasil didownload")
    return df_result


# =====================================================================
# SUMBER 2: IDX API — Data Trading Riil dari BEI
# =====================================================================

def fetch_idx_stock_summary(
    idx_client: IDXClient = None, n_days: int = 3
) -> pd.DataFrame:
    """
    Ambil Stock Summary dari API IDX untuk beberapa hari terakhir.

    Data yang diambil per saham:
    - Foreign Buy/Sell (aliran dana asing)
    - Bid/Offer Volume (sentimen orderbook)
    - Frequency (frekuensi transaksi)
    - Non-regular volume

    Parameters
    ----------
    idx_client : IDXClient
        Instance klien IDX.
    n_days : int
        Jumlah hari trading terakhir yang diambil.

    Returns
    -------
    pd.DataFrame
        DataFrame stock summary dari IDX.
    """
    if idx_client is None:
        idx_client = IDXClient()

    print(f"   -> Mengambil Stock Summary dari IDX API ({n_days} hari terakhir)...")
    df = idx_client.get_stock_summary_multiday(n_days=n_days)

    if df.empty:
        print("   [!] Gagal mengambil Stock Summary dari IDX. Menggunakan data kosong.")
        return pd.DataFrame()

    n_stocks = len(df["ticker"].unique())
    print(f"   [OK] IDX Stock Summary: {n_stocks} saham, {len(df):,} baris")
    return df


def fetch_idx_broker_summary(
    idx_client: IDXClient = None, date_str: str = None
) -> pd.DataFrame:
    """
    Ambil Broker Summary dari API IDX untuk tanggal tertentu.

    Returns: DataFrame[date, broker_code, broker_name, volume, value, frequency]
    """
    if idx_client is None:
        idx_client = IDXClient()

    if date_str is None:
        # Gunakan hari ini atau hari kerja terakhir
        now = datetime.now()
        while now.weekday() >= 5:  # Skip weekend
            from datetime import timedelta
            now -= timedelta(days=1)
        date_str = now.strftime("%Y%m%d")

    print(f"   -> Mengambil Broker Summary dari IDX API ({date_str})...")
    df = idx_client.get_broker_summary(date_str)

    if df.empty:
        print("   [!] Gagal mengambil Broker Summary dari IDX.")
        return pd.DataFrame()

    print(f"   [OK] IDX Broker Summary: {len(df):,} entri broker")
    return df


# =====================================================================
# FUNGSI GABUNGAN: Merge Data yfinance + IDX
# =====================================================================

def enrich_ohlcv_with_idx(
    df_ohlcv: pd.DataFrame, df_idx_summary: pd.DataFrame
) -> pd.DataFrame:
    """
    Perkaya data OHLCV (dari yfinance) dengan data IDX Stock Summary.

    Fitur tambahan yang di-merge:
    - foreign_net: Net foreign flow (ForeignBuy - ForeignSell)
    - bid_offer_ratio: BidVolume / OfferVolume (sentimen)
    - trade_frequency: Frekuensi transaksi
    - nr_volume_ratio: Non-regular volume / total volume

    Parameters
    ----------
    df_ohlcv : pd.DataFrame
        Data OHLCV dari Yahoo Finance.
    df_idx_summary : pd.DataFrame
        Stock Summary dari IDX API.

    Returns
    -------
    pd.DataFrame
        DataFrame OHLCV yang diperkaya dengan data IDX.
    """
    if df_idx_summary.empty:
        # Jika tidak ada data IDX, isi dengan default values
        # (0 untuk foreign_net, 1.0 untuk bid_offer_ratio = netral)
        df_ohlcv["foreign_net"] = 0.0
        df_ohlcv["bid_offer_ratio"] = 1.0
        df_ohlcv["trade_frequency"] = 0.0
        df_ohlcv["nr_volume_ratio"] = 0.0
        return df_ohlcv

    # Siapkan data IDX untuk merge
    df_idx = df_idx_summary.copy()

    # Hitung fitur tambahan dari data IDX
    df_idx["foreign_net"] = df_idx["foreign_buy"] - df_idx["foreign_sell"]

    # Bid/Offer ratio: > 1 berarti lebih banyak pembeli (bullish)
    df_idx["bid_offer_ratio"] = np.where(
        df_idx["offer_volume"] > 0,
        df_idx["bid_volume"] / df_idx["offer_volume"],
        1.0
    )

    df_idx["trade_frequency"] = df_idx["frequency"]

    # Non-regular volume ratio: tinggi = banyak transaksi di luar bursa
    df_idx["nr_volume_ratio"] = np.where(
        df_idx["volume"] > 0,
        df_idx["nr_volume"] / df_idx["volume"],
        0.0
    )

    # Konversi tanggal IDX ke format yang sama dengan OHLCV
    df_idx["date"] = pd.to_datetime(df_idx["date"], format="%Y%m%d", errors="coerce")

    # Pilih kolom yang akan di-merge
    idx_features = df_idx[[
        "date", "ticker", "foreign_net", "bid_offer_ratio",
        "trade_frequency", "nr_volume_ratio"
    ]].copy()

    # Ambil data IDX TERBARU per saham (untuk hari terakhir)
    idx_latest = idx_features.sort_values("date").groupby("ticker").last().reset_index()

    # Merge: setiap baris OHLCV mendapat data IDX terbaru per ticker
    # (merge on ticker saja, karena IDX data hanya beberapa hari terakhir)
    df_result = df_ohlcv.merge(
        idx_latest.drop(columns=["date"]),
        on="ticker",
        how="left"
    )

    # Isi NaN untuk saham yang tidak ada di IDX
    for col in ["foreign_net", "bid_offer_ratio", "trade_frequency", "nr_volume_ratio"]:
        df_result[col] = df_result[col].fillna(0.0)

    return df_result


