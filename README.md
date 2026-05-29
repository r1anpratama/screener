# 📊 IDX QUANT — ML Stock Screener & Premium TradingView Terminal Dashboard

Pipeline kuantitatif tingkat lanjut untuk *screening* saham harian IHSG (T+1 trading) berdasarkan probabilitas machine learning, volatilitas dinamis, manajemen risiko Kelly Criterion, dan **Interactive TradingView Charting Terminal** yang premium.

Sistem ini mengombinasikan **Data Historis (Yahoo Finance)** dengan **Data Riil Bursa (IDX API)** untuk mendeteksi emiten berpotensi lonjakan tinggi (>5%) dengan pembobotan alokasi portofolio dinamis untuk meminimalkan risiko drawdown.

---

## 🌟 Fitur Utama (v5.0 TradingView Terminal Suite)

### 1. 📈 TradingView-Style Interactive Charting Terminal (Baru!)
Visualisasi data historis emiten diubah menjadi chart terminal profesional ala **TradingView** menggunakan sumbu ganda (*dual-axis*) interaktif:
* **🎨 Neon Purple Area Line**: Garis harga penutupan menggunakan kurva kelengkungan halus (`tension: 0.15`) berwarna ungu neon (`#a78bfa`) dengan gradien isi (*area gradient*) yang memudar anggun ke dasar chart.
* **📊 Dual-Axis Volume Underlay**: Batang volume diplot sebagai grafik batang transparan langsung di dasar chart utama menggunakan sumbu y sekunder (`yVolume`). Volume dikunci di 25% dasar chart agar tidak mengganggu garis harga, diwarnai hijau transparan (`Close >= Open`) atau merah transparan (`Close < Open`) secara otomatis.
* **⚡ Real-Time HUD Overlay**: Panel absolut **OHLCV HUD Bar** di sudut kiri atas chart mendeteksi kursor kursor Anda secara instan (mouseover), menampilkan harga Open, High, Low, Close, dan Volume harian terdekat secara dinamis dengan pewarnaan hijau/merah terarah.
* **🕒 Client-Side Timeframe Zooming**: Tombol rentang waktu (`7D`, `30D`, `90D`, `ALL`) mengiris (*slicing*) data historis pada sisi klien secara instan dengan efek transisi animasi Chart.js yang sangat responsif.
* **🔒 Dynamic Support Floors**: Menghitung secara otomatis garis harga batas Support 1 (S1) dan Resistance 1 (R1) dari rentang waktu terpilih secara dinamis.

### 2. 📋 Dynamic 5-Level Bid/Offer Order Book (Baru!)
Dokumen laporan analisis riset otomatis (`analisa/[TANGGAL]/`) kini dilengkapi dengan **Tabel Kedalaman Order Book 5 Tingkat** yang dinamis:
* **IDX Tick Rules Compliance**: Struktur tingkat harga antrean Bid dan Offer dihitung tepat mengikuti regulasi fraksi harga resmi BEI (Rp1, Rp2, Rp5, Rp10, dan Rp25 per tingkat harga).
* **Liquidity Scaling**: Volume antrean dihitung dalam satuan **Lot** (1 Lot = 100 lembar) dan diskalakan secara matematis terhadap volume transaksi harian riil emiten serta rasio Bid/Offer, memberikan profil antrean yang sangat realistis untuk saham *blue-chip* maupun *mid-cap*.

### 3. 🎯 High-Contrast Ticker Selector
Memperbaiki bug keterbacaan select option bawaan browser.
* **Crisp Option Text**: Memaksa elemen dropdown pilihan emiten untuk merender teks gelap pekat (`#111827`) di atas latar belakang putih solid (`#ffffff`).
* Menjamin keterbacaan tajam 100% pada seluruh platform (Chrome, Edge, Safari, Firefox) baik di bawah setelan OS *light-mode* maupun *dark-mode*.

### 4. 🧠 Dynamic IHSG Market Regime Indicator
* **Trend Tracker**: Menganalisis data IHSG (^JKSE) secara dinamis menggunakan rata-rata pergerakan 50 hari (SMA 50).
* **Live Display Header**: Menampilkan status indeks BEI harian secara real-time pada header:
  * **`🟢 IHSG BULLISH (Di atas SMA 50)`**: Indikasi tren naik (Alokasi Kelly penuh aktif).
  * **`🔴 IHSG BEARISH (Di bawah SMA 50)`**: Indikasi tren turun (Otomatis memotong alokasi Kelly sebesar 50% untuk mitigasi risiko).

### 5. 🤖 Core Machine Learning & Self-Learning Hub
* **K-Means & Multi-XGBoost**: Mengklasterkan saham IHSG berdasarkan karakteristik historis (Blue-chip, Growth, High-Beta Speculative) dan melatih model XGBoost spesifik per klaster.
* **Tuning Optuna**: Menemukan hyperparameter optimal secara dinamis menggunakan minimalis validasi silang (stratified splits).
* **Self-Learning Meta-Filter Loop**: Menyediakan antarmuka pelatihan ulang Neural Network meta-learner untuk membedah hasil realisasi T+1 yang gagal (False Positives) dan sukses (True Positives) guna mengompensasi bias algoritma di hari berikutnya.

### 6. 🛡️ Kelly Criterion Position Sizing & ATR Risk Control
* **Optimasi Portofolio Kelly Criterion**: Menghitung alokasi modal optimal (f*) per picks saham secara kuantitatif guna memaksimalkan laju pertumbuhan modal geometris jangka panjang:
  Formula Kelly: f* = Half-Kelly x [ (p x R - (1 - p)) / R ]
* **ATR stops & Trailing SL**: Menghitung stop-loss dinamis (1.5 x ATR) dan take-profit (3 x ATR) berbasis volatilitas Average True Range 14 hari, dilengkapi pelacakan Trailing Stop (2 x ATR) untuk mengejar gelombang breakout yang panjang.

---

## ⚙️ Setup Environment

Penggunaan virtual environment sangat disarankan agar dependensi tidak bentrok dengan sistem global sistem operasi Windows Anda.

```bash
# 1. Clone atau masuk ke direktori project
cd d:\code\screener

# 2. Buat virtual environment
python -m venv screener

# 3. Aktifkan Virtual Environment (PowerShell Windows)
.\screener\Scripts\Activate.ps1

# 4. Install seluruh dependensi utama
pip install -r requirements.txt
```

---

## 🚀 Cara Menjalankan (2 Cara Mudah)

### Cara 1: Jalankan Dashboard Interaktif Web (Sangat Direkomendasikan)
Cukup jalankan skrip launcher pintar. Skrip ini akan otomatis memeriksa virtual environment, menginstal FastAPI/Uvicorn jika belum ada, dan mem-boot server web:

```bash
python run_web.py
```

*   **Akses Browser**: Buka browser Anda dan masuk ke **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.
*   **Memulai**: Klik tombol **⚡ Run Screener** di bilah sisi. Pipeline machine learning akan berjalan di latar belakang, dan log tuning XGBoost akan dialirkan langsung ke terminal web Anda secara real-time. Setelah selesai, dashboard akan otomatis menampilkan sinyal, chart TradingView, dan alokasi Kelly terbaru!

### Cara 2: Jalankan Pipeline via Console CLI (Traditional Mode)
Jika Anda hanya ingin menjalankan pencetakan laporan riset harian di folder `analisa/` tanpa membuka web:

```bash
python main.py
```

Skrip CLI akan melatih model, menyajikan tabel ringkasan kuantitatif di konsol, dan men-generate 10 laporan riset serta grafik candlestick di direktori `analisa/[TANGGAL_HARI_INI]/`.

---

## 📁 Struktur Project Terbaru

| File / Folder | Deskripsi |
|---|---|
| **`run_web.py`** | *Launcher* utama server web yang mengotomatisasi pengecekan sistem. |
| **`web_app.py`** | Backend server web FastAPI, penanganan logs SSE, dan perutean API data. |
| **`static/app.js`** | Logika frontend SPA, penangan fetch JSON, dan penggambaran Chart.js interaktif. |
| **`static/style.css`** | Tema visual *Midnight Tech* custom premium, perbaikan kontras opsi select ticker. |
| **`templates/index.html`** | Halaman dashboard HTML5 modular dengan tab chart TradingView, ML hub, dan Backtester. |
| **`report_generator.py`** | Penulis otomatis Broker Report bergaya institusi, dilengkapi kalkulator 5-level Bid/Offer BEI. |
| **`portfolio_optimizer.py`** | Modul perhitungan Kelly alokasi portofolio, ATR stops, dan Skor Profit. |
| **`backtester.py`** | *Engine* simulasi trading historis lengkap dengan komisi transaksi. |
| `config.py` | Konvensi global, universe emiten, parameter ATR, dan host port web. |
| `idx_client.py` | Modul bypass Cloudflare IDX menggunakan impersonasi TLS Chrome (`curl_cffi`). |
| `data_ingestion.py` | Pengumpul data terpadu Yahoo Finance dan IDX Stock Summary. |
| `feature_engineering.py` | Pembangun fitur indikator teknikal harian dan kalkulasi ATR. |
| `ml_model.py` | Inti kecerdasan buatan: K-Means Clustering + Tuning Optuna + model XGBoost. |
| `screener.py` | Orchestrator utama pengumpul alur pipeline ML dan kalkulasi alokasi. |
| `main.py` | Entry point CLI konsol tradisional. |

---

## 🛡️ Analisis Risiko & Disclaimer

*   **Pencegahan Overfitting**: Model menggunakan *learning_rate* dinamis rendah (~0.05) dan Optuna validasi silang (Stratified Validation Split) untuk meredam kebisingan sinyal/jebakan manipulasi orderbook (*spoofing*) di pasar IHSG.
*   **Disclaimer Penting**: Seluruh keluaran probabilitas model, trading plan, stop-loss, dan porsi alokasi Kelly dari sistem ini bersifat **analitis kuantitatif probabilistik**, dan **bukan merupakan rekomendasi investasi atau saran keuangan**. Keputusan transaksi sepenuhnya tanggung jawab pribadi Anda. Selalu terapkan money management ketat. *Past performance does not guarantee future results.*
