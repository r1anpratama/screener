"""
config.py — Konfigurasi Global & Hyperparameter
=================================================
File ini berisi semua konstanta, parameter, dan konfigurasi yang digunakan
di seluruh pipeline screening saham. Pisahkan konfigurasi dari logika agar
mudah diubah tanpa menyentuh kode utama.
"""

import numpy as np

# =============================================================================
# UNIVERSE SAHAM — Semua Saham Potensial di IHSG
# =============================================================================
# Daftar ticker mencakup seluruh spektrum kapitalisasi:
# Large-cap, Mid-cap, dan Small-cap untuk analisis komprehensif.
# Dalam produksi, daftar ini sebaiknya diambil dari API IDX secara dinamis.

TICKERS = [
    # === Large Cap (Blue Chip) ===
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNVR", "HMSP",
    "ICBP", "INDF", "KLBF", "GGRM", "PGAS", "SMGR", "ANTM",

    # === Mid Cap ===
    "BSDE", "CPIN", "ERAA", "EXCL", "INCO", "INKP", "ITMG", "JPFA",
    "JSMR", "MAPI", "MDKA", "MEDC", "MIKA", "MNCN", "PTBA",
    "PWON", "SCMA", "SIDO", "SRIL", "TBIG", "TINS", "TKIM",
    "TOWR", "UNTR", "WIKA",

    # === Small Cap (Potensi Tinggi, Risiko Tinggi) ===
    "ACES", "AGII", "AKRA", "AMRT", "ARNA", "BATA", "BIRD", "BJTM",
    "BRIS", "BRPT", "BTPS", "CLEO", "CTRA", "DMAS", "DSNG",
    "ELSA", "EMTK", "ESSA", "FILM", "GJTL", "HEAL", "HERO",
    "HOKI", "HRTA", "ISAT", "KAEF", "KIJA", "LINK", "LPPF",
    "MAPA", "MARK", "MEGA", "MLBI", "MYOR", "PNLF", "PTPP",
    "RAJA", "RALS", "RANC", "SMSM", "SPTM", "SSMS", "STTP",
    "TAPG", "TAXI", "TELE", "TOBA", "TPIA", "TSPC", "ULTJ",
    "VIVA", "WSBP", "WSKT", "WTON",

    # === Saham Lapis 3 (Spekulatif) ===
    "AALI", "ADHI", "ADMR", "AGRO", "ALTO", "APLN", "ASRI", "ASGR",
    "BALI", "BAYU", "BBKP", "BBMD", "BBTN", "BCAP", "BCIC",
    "BDMN", "BEKS", "BGTG", "BINA", "BKSL", "BMTR", "BNBR",
    "BNGA", "BNLI", "BRAM", "BUMI", "DILD", "DKFT", "DNET",
    "DOID", "DSFI", "ELTY", "ENRG", "FREN", "GEMS", "GIAA",
    "GPRA", "GWSA", "HRUM", "IBST", "INDY", "IPCM", "IRRA",
]


# =============================================================================
# PARAMETER DATA SIMULASI
# =============================================================================

# Jumlah hari trading untuk data historis (~1 tahun = ~250 hari)
N_TRADING_DAYS = 250

# Seed untuk reproduktifitas hasil simulasi
RANDOM_SEED = 42


# =============================================================================
# PARAMETER FEATURE ENGINEERING
# =============================================================================

# --- Volatility Contraction (Bollinger Bandwidth) ---
# Rolling window 6 bulan (~120 hari trading) untuk persentil
ROLLING_WINDOW_DAYS = 120

# Persentil batas bawah Bollinger Bandwidth (semakin rendah = semakin kontraksi)
BB_PERCENTILE_THRESHOLD = 10

# Periode SMA untuk filter tren (Close harus di atas SMA ini)
SMA_PERIOD = 20

# Periode Bollinger Bands
BB_PERIOD = 20

# Standard deviasi Bollinger Bands
BB_STD_DEV = 2


# --- Momentum Extreme (RSI) ---
# Periode RSI
RSI_PERIOD = 14

# Threshold RSI oversold (di bawah nilai ini = potensi reversal)
RSI_OVERSOLD_THRESHOLD = 25


# --- Bandarmology (VWAP) ---
# Rasio minimum Close/VWAP untuk menandakan akumulasi bandar
VWAP_RATIO_THRESHOLD = 1.0


# --- Pre-Closing Anomaly ---
# Multiplier untuk mendeteksi lonjakan volume abnormal
# Jika volume per menit di pre-closing > (rata-rata normal × multiplier),
# maka dianggap anomali
PRECLOSING_VOLUME_MULTIPLIER = 2.0

# Jam perdagangan normal IHSG: 09:00 - 15:49
# Sesi pre-closing: 15:50 - 16:00
TRADING_START = "09:00"
TRADING_END_NORMAL = "15:49"
PRECLOSING_START = "15:50"
PRECLOSING_END = "16:00"


# =============================================================================
# HYPERPARAMETER XGBOOST
# =============================================================================
# Dokumentasi lengkap: https://xgboost.readthedocs.io/en/stable/parameter.html

XGBOOST_PARAMS = {
    # -------------------------------------------------------------------------
    # learning_rate (eta) — Parameter KUNCI untuk mencegah overfitting
    # -------------------------------------------------------------------------
    # Nilai default: 0.3 (terlalu agresif untuk data saham Indonesia)
    #
    # PENJELASAN NARATIF:
    # learning_rate mengontrol seberapa besar kontribusi setiap pohon keputusan
    # (tree) terhadap prediksi akhir. Bayangkan setiap tree sebagai "pendapat"
    # seorang analis — learning_rate menentukan seberapa besar kita percaya
    # pada setiap pendapat tersebut.
    #
    # - learning_rate RENDAH (0.01 - 0.05):
    #   Model belajar SANGAT perlahan. Setiap tree hanya memberikan koreksi
    #   kecil. Ini membuat model lebih ROBUST terhadap noise dan jebakan
    #   volatilitas bandar seperti SPOOFING (order palsu yang dipasang lalu
    #   dicabut untuk mengelabui algoritma). Model tidak akan "terjebak"
    #   menghafal pola acak dari manipulasi orderbook.
    #   TRADE-OFF: Butuh lebih banyak trees (n_estimators tinggi) = lebih lambat.
    #
    # - learning_rate TINGGI (0.1 - 0.3):
    #   Model belajar CEPAT. Setiap tree memberikan koreksi besar. Ini
    #   berisiko OVERFITTING — model bisa menghafal pola spoofing/manipulasi
    #   yang sebenarnya hanya noise sementara, bukan sinyal trading valid.
    #   Akibatnya, model tampak bagus di backtesting tapi gagal di live trading.
    #
    # REKOMENDASI untuk pasar IHSG:
    # Gunakan 0.05 sebagai titik awal. Pasar Indonesia memiliki likuiditas
    # lebih rendah dibanding pasar global, sehingga lebih rentan terhadap
    # manipulasi. Learning rate rendah membantu model "menyaring" noise
    # dari aksi bandar dan fokus pada pola fundamental yang konsisten.
    # -------------------------------------------------------------------------
    "learning_rate": 0.05,

    # Jumlah pohon keputusan (boosting rounds)
    # Semakin banyak = semakin kompleks, tapi bisa overfitting
    "n_estimators": 300,

    # Kedalaman maksimum setiap pohon
    # 4-6 optimal untuk dataset saham (mencegah overfitting)
    "max_depth": 5,

    # Minimum jumlah sampel di leaf node
    # Nilai lebih tinggi = model lebih konservatif
    "min_child_weight": 10,

    # Subsample ratio dari training data per tree
    # 0.8 = 80% data dipakai per iterasi (mencegah overfitting)
    "subsample": 0.8,

    # Subsample ratio dari fitur per tree
    # 0.8 = 80% fitur dipakai per iterasi (menambah diversitas)
    "colsample_bytree": 0.8,

    # Regularisasi L1 (Lasso) — mendorong sparsity fitur
    "reg_alpha": 0.1,

    # Regularisasi L2 (Ridge) — mengurangi magnitude bobot
    "reg_lambda": 1.0,

    # Fungsi objektif untuk klasifikasi biner
    "objective": "binary:logistic",

    # Metrik evaluasi
    "eval_metric": "logloss",

    # Seed untuk reproduktifitas
    "random_state": RANDOM_SEED,

    # Gunakan histogram-based algorithm (lebih cepat)
    "tree_method": "hist",
}


# =============================================================================
# PARAMETER OUTPUT
# =============================================================================

# Jumlah maksimum saham yang ditampilkan di hasil screening
MAX_DISPLAY_STOCKS = 10

# Minimum probabilitas win untuk ditampilkan (dalam persen)
MIN_WIN_PROBABILITY = 0.0  # Tampilkan semua yang lolos filter sinyal
