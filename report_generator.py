import os
from datetime import datetime
import pandas as pd
import mplfinance as mpf

def create_daily_folder(base_dir: str = "analisa") -> str:
    """
    Membuat folder harian (misal: analisa/2026-04-30)
    dan menghapus isi file lama jika ada (agar fresh).
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    folder_path = os.path.join(base_dir, date_str)
    os.makedirs(folder_path, exist_ok=True)
    
    # Hapus file lama di dalam folder jika ada
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Gagal menghapus file {file_path}: {e}")
            
    return folder_path

def plot_stock_chart(df_ohlcv: pd.DataFrame, ticker: str, save_path: str):
    """
    Plot grafik candlestick (sekitar 3-6 bulan terakhir) menggunakan mplfinance,
    lengkap dengan Bollinger Bands dan Volume.
    """
    df = df_ohlcv[df_ohlcv["ticker"] == ticker].copy()
    if df.empty:
        print(f"   [!] Data OHLCV tidak ditemukan untuk {ticker}, skip grafik.")
        return

    # Set date sebagai index (syarat mplfinance)
    df.set_index("date", inplace=True)
    df.sort_index(inplace=True)

    # Ambil 100 hari trading terakhir agar grafik tidak terlalu padat
    df = df.tail(100)

    # Kolom harus sesuai standar mplfinance: Open, High, Low, Close, Volume
    df.rename(columns={
        "open": "Open", "high": "High", "low": "Low", 
        "close": "Close", "volume": "Volume"
    }, inplace=True)

    # Hitung indikator sederhana untuk diplot
    # Bollinger Bands 20
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['BB_Upper'] = df['SMA20'] + 2 * df['Close'].rolling(window=20).std()
    df['BB_Lower'] = df['SMA20'] - 2 * df['Close'].rolling(window=20).std()

    # Siapkan subplot indikator
    apds = [
        mpf.make_addplot(df['BB_Upper'], color='g', alpha=0.5),
        mpf.make_addplot(df['SMA20'], color='b', alpha=0.5),
        mpf.make_addplot(df['BB_Lower'], color='r', alpha=0.5),
    ]

    # Plot dan simpan
    try:
        mpf.plot(
            df, type='candle', volume=True, addplot=apds,
            title=f"Analisis Teknikal: {ticker}",
            style='yahoo',
            savefig=dict(fname=save_path, dpi=100, bbox_inches='tight')
        )
    except Exception as e:
        print(f"   [!] Gagal membuat grafik untuk {ticker}: {e}")

def format_rupiah(value):
    try:
        val = float(value)
        return f"Rp {val:,.0f}"
    except:
        return str(value)

def generate_ticker_report(row: pd.Series, chart_path: str, save_path: str):
    """
    Menghasilkan file markdown analisis mengapa saham ini direkomendasikan.
    """
    ticker = row.get("Saham", row.get("ticker", "UNKNOWN"))
    price = row.get("Harga", "-")
    prob = row.get("Prob. T+1", "-")
    rsi = row.get("RSI(14)", "-")
    foreign_net = row.get("Foreign Net", "-")
    bid_offer = row.get("Bid/Offer", "-")
    
    # Deteksi sinyal (Y/N)
    is_bandar = row.get("Bandar") == "[Y]"
    is_asing = row.get("Asing Beli") == "[Y]"
    is_bid_kuat = row.get("Bid Kuat") == "[Y]"
    is_rsi_oversold = row.get("RSI Oversold") == "[Y]"
    is_vol_contract = row.get("Vol.Contract") == "[Y]"

    # Bangun narasi alasan
    reasons = []
    if is_bandar:
        reasons.append(f"- **Akumulasi Bandar:** Harga penutupan berada di atas rata-rata VWAP, mengindikasikan adanya akumulasi kuat.")
    if is_asing:
        reasons.append(f"- **Aliran Dana Asing:** Terjadi *Net Foreign Buy* sebesar {foreign_net} lembar.")
    if is_bid_kuat:
        reasons.append(f"- **Sentimen Orderbook (Antrean):** Rasio Bid vs Offer mencapai {bid_offer}x lipat, menunjukkan minat beli (demand) yang sangat tinggi di pasar.")
    if is_rsi_oversold:
        reasons.append(f"- **Momentum Reversal:** Indikator RSI berada di level {rsi} (Oversold), berpotensi teknikal *rebound*.")
    if is_vol_contract:
        reasons.append(f"- **Kontraksi Volatilitas:** Bollinger Band sedang menyempit, biasanya menjadi fase konsolidasi sebelum *breakout* harga.")

    md_content = f"""# 📈 INSTITUTIONAL RESEARCH REPORT
**Date:** {datetime.now().strftime('%d %B %Y')} | **Ticker:** {ticker}
**Sector:** IHSG Equity | **Action:** **STRONG WATCH**

---

## 📌 Executive Summary
**{ticker}** telah lolos algoritma screening *Multi-Cluster Machine Learning* dengan probabilitas kenaikan T+1 sebesar **{prob}**. Saham ini diidentifikasi masuk dalam pengawasan prioritas berdasarkan aliran dana, tekanan orderbook, dan momentum teknikal.

| Metrik Kunci | Nilai | Status Sinyal |
|---|---|---|
| **Last Price** | {price} | - |
| **T+1 Win Probability** | **{prob}** | 🟢 **High** |
| **Foreign Flow** | {foreign_net} | {('🟢 Beli' if is_asing else '🔴 Jual/Netral')} |
| **Bid/Offer Ratio** | {bid_offer}x | {('🟢 Demand Kuat' if is_bid_kuat else '🔴 Supply Dominan')} |

---

## 📊 Technical & Flow Analysis

![Technical Chart {ticker}](./{os.path.basename(chart_path)})

### 💡 Rationale (Alasan Rekomendasi)
Katalis utama yang mendasari tingginya probabilitas historis saham ini adalah:

{chr(10).join(reasons)}

---

## 🛡️ Risk & Action Plan
*Catatan Pialang: Setup trading ini direkomendasikan untuk Fast Trade / Day Trading (T+1).*

* **Area Entry (Beli):** Beli pada harga {price} atau *Buy on Weakness* di area *support* terdekat.
* **Target Profit (TP):** 1.5% - 3.0% dari harga *entry* (Scalping). Jual jika momentum transaksi melambat.
* **Stop Loss (SL):** Strict Cut-Loss di 2% - 3% di bawah harga rata-rata pembelian untuk memitigasi *downside risk*.

> **🚨 DISCLAIMER PENTING:** 
> Laporan ini digenerate secara otomatis oleh model kuantitatif *XGBoost*. Informasi di atas bukan merupakan ajakan untuk membeli atau menjual efek. Keputusan investasi sepenuhnya berada di tangan investor. Lakukan *money management* dengan ketat.
"""
    try:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(md_content)
    except Exception as e:
        print(f"   [!] Gagal membuat file markdown untuk {ticker}: {e}")

def generate_reports(df_top10: pd.DataFrame, df_ohlcv: pd.DataFrame):
    """
    Fungsi utama untuk membuat folder dan men-generate laporan untuk Top 10 saham.
    """
    print("\n" + "=" * 60)
    print("[>] TAHAP 5: PEMBUATAN LAPORAN OTOMATIS (ANALISA)")
    print("=" * 60)
    
    if df_top10.empty:
        print("   [!] Tidak ada data saham untuk dibuatkan laporan.")
        return

    folder_path = create_daily_folder()
    print(f"   -> Folder analisis dibuat di: {folder_path}/")

    count = 0
    for _, row in df_top10.iterrows():
        ticker = row.get("Saham", row.get("ticker", "UNKNOWN"))
        if ticker == "UNKNOWN":
            continue
            
        # Path file
        chart_filename = f"{ticker}_chart.png"
        chart_path = os.path.join(folder_path, chart_filename)
        report_path = os.path.join(folder_path, f"{ticker}_analisa.md")

        print(f"   -> Men-generate laporan & grafik untuk {ticker}...")
        
        plot_stock_chart(df_ohlcv, ticker, chart_path)
        generate_ticker_report(row, chart_path, report_path)
        count += 1
        
    print(f"   [OK] Berhasil membuat {count} laporan analisis.")
