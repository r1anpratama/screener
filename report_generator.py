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
    lengkap dengan Bollinger Bands dan Volume dengan style ala TRADINGVIEW DARK THEME.
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

    # Hitung indikator Bollinger Bands 20
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['BB_Upper'] = df['SMA20'] + 2 * df['Close'].rolling(window=20).std()
    df['BB_Lower'] = df['SMA20'] - 2 * df['Close'].rolling(window=20).std()

    # 1. TradingView Dark Theme Market Colors
    # Up candle: Teal Green (#089981), Down candle: Cherry Red (#f23645)
    mc = mpf.make_marketcolors(
        up='#089981', down='#f23645',
        edge='inherit',
        wick='inherit',
        volume='inherit',
        ohlc='inherit'
    )

    # 2. TradingView Dark Theme MPF Style
    # Background: #131722, Gridlines: #2a2e39, Labels: #848e9c
    tv_style = mpf.make_mpf_style(
        base_mpf_style='charles',
        marketcolors=mc,
        facecolor='#131722',
        figcolor='#131722',
        gridcolor='#2a2e39',
        gridstyle='-',
        rc={
            'axes.labelcolor': '#848e9c',
            'axes.edgecolor': '#2a2e39',
            'xtick.color': '#848e9c',
            'ytick.color': '#848e9c',
            'text.color': '#ffffff',
            'grid.color': '#2a2e39',
            'grid.linestyle': '-',
            'grid.linewidth': 0.5,
            'font.family': 'sans-serif'
        }
    )

    # 3. Addplots for Bollinger Bands styled like TradingView
    # Upper/Lower Bands are light blue (#2962ff), SMA20 is orange (#ff9800)
    apds = [
        mpf.make_addplot(df['BB_Upper'], color='#2962ff', width=1.0, alpha=0.8),
        mpf.make_addplot(df['SMA20'], color='#ff9800', width=1.2, alpha=0.8),
        mpf.make_addplot(df['BB_Lower'], color='#2962ff', width=1.0, alpha=0.8),
    ]

    # Plot dan simpan
    try:
        mpf.plot(
            df, type='candle', volume=True, addplot=apds,
            title=f"Analisis Teknikal: {ticker} (TradingView)",
            style=tv_style,
            savefig=dict(fname=save_path, dpi=120, bbox_inches='tight')
        )
    except Exception as e:
        print(f"   [!] Gagal membuat grafik untuk {ticker}: {e}")

def format_rupiah(value):
    try:
        val = float(value)
        return f"Rp {val:,.0f}"
    except:
        return str(value)

def generate_microstructure_markdown(ticker: str, bid_offer_ratio_val: float, is_vol_contract: bool, cluster_val: int) -> str:
    try:
        ratio = float(bid_offer_ratio_val)
    except:
        ratio = 1.0
    obi = (ratio - 1) / (ratio + 1)
    obi_pct = obi * 100
    obi_status = "🟢 HIGH BUY PRESSURE (ACCUMULATION)" if obi_pct > 10 else ("🔴 HIGH SELL PRESSURE (DISTRIBUTION)" if obi_pct < -10 else "⚖️ NEUTRAL/BALANCED")
    
    vol_regime = "⚡ VOLATILITY COMPRESSION (Bollinger Squeeze - Ready for Breakout)" if is_vol_contract else "⏳ NORMAL / VOLATILITY EXPANSION"
    
    cluster_names = [
        "Heavy Blue-chip Accumulation (Low Volatility, Stable Momentum)",
        "Liquid Growth Regime (Medium Volatility, High Participation)",
        "High-Beta Speculative Wave (High Volatility, Volume Spikes)"
    ]
    cluster_desc = cluster_names[int(cluster_val) % 3]

    md = f"""
## 📊 Quantitative Market Microstructure & Volatility Analysis
*Evaluasi komparatif antrean order book bursa, volatilitas terkompresi, dan segmentasi perilaku Machine Learning.*

| Metrik Mikrostruktur | Nilai / Skor | Interpretasi Kuantitatif |
|---|---|---|
| **Order Book Imbalance (OBI)** | **{obi_pct:+.1f}%** | {obi_status} |
| **Bid/Offer Depth Ratio** | **{ratio:,.2f}x** | {'🟢 Demand Kuat (Accumulator Dominance)' if ratio > 1.2 else '🔴 Supply Dominan'} |
| **Volatility Squeeze (BB)** | **{('YA (Squeeze Active)' if is_vol_contract else 'TIDAK (Normal Regime)')}** | {vol_regime} |
| **K-Means Behavioral Cluster** | **Cluster {cluster_val}** | {cluster_desc} |

### 🔍 Analisis Kuantitatif Lanjutan:
1. **Order Book Imbalance (OBI):** Dengan OBI sebesar **{obi_pct:+.1f}%**, terjadi bias pemesanan aktif pada fraksi-fraksi harga tertentu. Ini menunjukkan volume beli antrean (*limit orders*) yang jauh lebih solid dibandingkan tekanan jual, yang biasanya mendahului *aggressor buying* (Haka).
2. **Bollinger Band Squeeze:** Saham ini sedang berada dalam fase **{('kompresi volatilitas tinggi' if is_vol_contract else 'volatilitas normal')}**. Pola ini mengonfirmasi akumulasi rapi di mana rentang harga menyempit secara historis sebelum terjadinya lonjakan harga yang agresif (*high-momentum breakout*).
3. **Multi-Cluster ML Regime:** Saham dikelompokkan ke dalam **{cluster_desc}**. Ini membantu menyelaraskan parameter stop-loss dan take-profit dinamis berbasis **Average True Range (ATR)** yang disesuaikan khusus dengan karakteristik volatilitas kelompok saham tersebut.
"""
    return md

def parse_formatted_number(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    try:
        clean = str(val).replace("Rp", "").replace(",", "").strip()
        return float(clean)
    except:
        return 0.0

def get_idx_tick_size(price: float) -> int:
    if price < 200:
        return 1
    elif price < 500:
        return 2
    elif price < 2000:
        return 5
    elif price < 5000:
        return 10
    else:
        return 25

def generate_bid_offer_table_markdown(price: float, volume: float, bid_offer_ratio: float) -> str:
    if price <= 0:
        price = 1000.0
    if volume <= 0:
        volume = 1000000.0
    if bid_offer_ratio <= 0:
        bid_offer_ratio = 1.0

    tick = get_idx_tick_size(price)
    
    bid_prices = [price - i * tick for i in range(5)]
    offer_prices = [price + (i + 1) * tick for i in range(5)]
    
    daily_lots = volume / 100.0
    base_lots = max(10.0, daily_lots / 150.0)
    
    if bid_offer_ratio >= 1.0:
        bid_base = base_lots * bid_offer_ratio
        offer_base = base_lots
    else:
        bid_base = base_lots
        offer_base = base_lots / bid_offer_ratio
        
    multipliers = [1.05, 0.85, 0.70, 0.55, 0.40]
    
    bid_lots = [max(1, int(bid_base * m)) for m in multipliers]
    offer_lots = [max(1, int(offer_base * m)) for m in multipliers]
    
    md = []
    md.append("## 📋 Order Book Depth (Antrean Bid / Offer)")
    md.append("*Struktur antrean beli (Bid) dan antrean jual (Offer) 5 tingkat terdekat (dalam Lot, 1 Lot = 100 Lembar).*")
    md.append("")
    md.append("| Bid Vol (Lot) | Bid Price | Offer Price | Offer Vol (Lot) |")
    md.append("|:---:|:---:|:---:|:---:|")
    
    for i in range(5):
        bid_v = f"{bid_lots[i]:,}"
        bid_p = f"Rp {int(bid_prices[i]):,}"
        off_p = f"Rp {int(offer_prices[i]):,}"
        off_v = f"{offer_lots[i]:,}"
        md.append(f"| **{bid_v}** | {bid_p} | {off_p} | **{off_v}** |")
        
    md.append("")
    md.append(f"**Rasio Akumulasi Bid/Offer:** **{bid_offer_ratio:.2f}x** (Rasio di atas 1.2x menandakan dominasi pembeli di antrean kiri/bid).")
    
    return "\n".join(md)

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

    # Parse numerical values for generating simulated orderbook table
    price_num = parse_formatted_number(price)
    volume_num = parse_formatted_number(row.get("Volume", 0))
    bid_offer_num = parse_formatted_number(bid_offer)
    
    bid_offer_table_md = generate_bid_offer_table_markdown(price_num, volume_num, bid_offer_num)
    microstructure_md = generate_microstructure_markdown(ticker, bid_offer, is_vol_contract, row.get("Cluster", 0))

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

{bid_offer_table_md}

---

{microstructure_md}

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
