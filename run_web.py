"""
run_web.py — Server Web Launcher & Dependency Auto-Installer
============================================================
Skrip utilitas ini memastikan dependensi web server (FastAPI, Uvicorn)
sudah terinstal dalam virtual environment aktif, lalu menjalankan server.
"""

import os
import sys
import subprocess

def install_and_import(package, pip_name=None):
    if pip_name is None:
        pip_name = package
    try:
        __import__(package)
        print(f"   [OK] Dependensi '{package}' sudah terinstal.")
    except ImportError:
        print(f"   [!] Dependensi '{package}' tidak ditemukan. Menginstal otomatis via pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            print(f"   [OK] Berhasil menginstal '{package}'!")
        except Exception as e:
            print(f"   [❌] Gagal menginstal '{package}': {e}")
            print(f"   Silakan instal secara manual: pip install {pip_name}")
            sys.exit(1)

def main():
    print("=" * 60)
    print("  IDX QUANT ML Stock Screener Dashboard Web Launcher")
    print("=" * 60)

    # 1. Pastikan folder analisa, static, dan templates tersedia
    os.makedirs("analisa", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    print("   [OK] Folder struktur 'analisa', 'static', 'templates' siap.")

    # 2. Verifikasi dan instal dependensi FastAPI & Uvicorn jika belum ada
    install_and_import("fastapi", "fastapi")
    install_and_import("uvicorn", "uvicorn")
    
    # 3. Opsional: periksa dependensi inti pendaftaran
    try:
        import xgboost
        import sklearn
        import optuna
        import curl_cffi
        import yfinance
        print("   [OK] Dependensi Machine Learning (XGBoost, Sklearn, Optuna, Yfinance, Curl_cffi) terdeteksi.")
    except ImportError as e:
        print(f"   [⚠️] Peringatan: Dependensi core ML tidak lengkap ({e}).")
        print("        Silakan aktifkan virtual environment Anda dan jalankan:")
        print("        pip install -r requirements.txt")
        print("-" * 60)

    # 4. Menjalankan server web Uvicorn
    print("\n[>] Booting Uvicorn ASGI Server...")
    print("    URL Akses: http://127.0.0.1:8000")
    print("    Tekan Ctrl+C untuk menghentikan server web.")
    print("=" * 60 + "\n")

    try:
        import uvicorn
        # Jalankan server
        uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=True)
    except KeyboardInterrupt:
        print("\n[✔] Server dihentikan oleh pengguna.")
    except Exception as e:
        print(f"\n[❌] Kegagalan server: {e}")

if __name__ == "__main__":
    main()
