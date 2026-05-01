"""
main.py — Entry Point Pipeline Screening Saham IHSG
====================================================
Jalankan file ini untuk memulai seluruh pipeline:

    python main.py

Pipeline akan:
1. Men-generate data simulasi (OHLCV, tick intraday, broker summary)
2. Menghitung fitur kuantitatif (Bollinger, RSI, VWAP, anomali)
3. Melatih model XGBoost
4. Menampilkan hasil screening saham potensial
"""

import warnings
warnings.filterwarnings("ignore")  # Suppress warning agar output bersih

from screener import StockScreener
from tabulate import tabulate
from report_generator import generate_reports


def main():
    """Fungsi utama untuk menjalankan pipeline screening."""

    # Inisialisasi dan jalankan pipeline
    screener = StockScreener()
    df_screened = screener.run()

    # ======================================================================
    # TAMPILKAN HASIL SCREENING
    # ======================================================================
    if len(df_screened) == 0:
        print("[!] Tidak ada saham yang memenuhi kriteria screening hari ini.")
        print("   Coba turunkan threshold di config.py atau periksa data.")
        return

    # Format tabel output
    df_display = screener.format_output(df_screened)

    print("=" * 80)
    print("  HASIL SCREENING SAHAM -- Top Picks T+1 Trading")
    print("=" * 80)
    print()
    print(tabulate(
        df_display,
        headers="keys",
        tablefmt="grid",
        showindex=False,
        stralign="center",
        numalign="center",
    ))
    print()
    print(f"  Total saham terfilter: {len(df_screened)}")
    print(f"  Diurutkan berdasarkan: Probabilitas T+1 (tertinggi -> terendah)")
    print()

    # ======================================================================
    # RINGKASAN STATISTIK
    # ======================================================================
    print("-" * 60)
    print("  RINGKASAN STATISTIK")
    print("-" * 60)
    
    signal_cols = [
        "signal_volatility_contraction",
        "signal_momentum_extreme",
        "signal_bandarmology",
        "signal_foreign_inflow",
        "signal_strong_bid",
    ]

    for col in signal_cols:
        if col in df_screened.columns:
            count = df_screened[col].sum()
            label = col.replace("signal_", "").replace("_", " ").title()
            print(f"  * {label:30s}: {count} saham")

    print()
    print("-" * 60)
    print("  [!] DISCLAIMER")
    print("-" * 60)
    print("  Data OHLCV dari Yahoo Finance, data tambahan dari IDX API.")
    print("  Seluruh data riil. Hasil bukan rekomendasi")
    print("  investasi. Selalu lakukan analisis mandiri dan manajemen")
    print("  risiko. Past performance does not guarantee future results.")
    print("-" * 60)
    print()

    # ======================================================================
    # PEMBUATAN LAPORAN OTOMATIS
    # ======================================================================
    generate_reports(df_display, screener.df_ohlcv)

if __name__ == "__main__":
    main()
