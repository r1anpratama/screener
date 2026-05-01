"""
idx_client.py -- Klien API IDX (Indonesian Stock Exchange)
==========================================================
Modul ini mengadaptasi endpoint dari:
- NeaByteLab/IDX-API  (endpoint HTTP)
- nichsedge/idx-bei   (teknik curl_cffi impersonate)

KUNCI PENTING:
Situs idx.co.id menggunakan Cloudflare yang mem-block request
dari library standar (requests/urllib) jika diakses dari luar
Indonesia. Library `curl_cffi` dengan parameter impersonate="chrome"
meniru TLS fingerprint Chrome asli sehingga BYPASS restriksi ini.

Ini memungkinkan akses data IDX dari MANA SAJA di dunia.

Data yang bisa diambil:
1. Stock Summary — OHLCV + foreign flow + orderbook per tanggal
2. Broker Summary — Aktivitas trading per broker per tanggal
3. Trading Info Daily — Snapshot harga terkini per saham
4. Top Gainers / Losers — Saham naik/turun terbesar
5. Foreign Trading — Aliran dana asing
6. Financial Ratio — PER, PBV, ROE, DER, dll.
"""

import time
import json
import base64
from datetime import datetime, timedelta

from curl_cffi import requests as curl_requests
import pandas as pd


class IDXClient:
    """
    Klien Python untuk mengakses API resmi IDX (idx.co.id).

    Menggunakan curl_cffi (dari pola repo nichsedge/idx-bei) untuk
    bypass Cloudflare protection. Bisa diakses dari luar Indonesia.

    Teknik:
    - curl_cffi.requests.get(..., impersonate="chrome")
    - Header Referer yang sesuai halaman IDX
    - Rate limiting antar request
    """

    BASE_URL = "https://www.idx.co.id/primary"

    # Header minimal (curl_cffi menangani User-Agent via impersonate)
    HEADERS = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9,id;q=0.8",
        "Referer": "https://www.idx.co.id/",
    }

    def __init__(self, max_retries: int = 3, retry_delay: float = 2.0):
        """
        Inisialisasi klien IDX.

        Parameters
        ----------
        max_retries : int
            Jumlah maksimum percobaan ulang jika request gagal.
        retry_delay : float
            Delay awal antar retry (detik, bertambah eksponensial).
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        # curl_cffi session dengan impersonation Chrome
        self.session = curl_requests.Session(impersonate="chrome")
        self.session.headers.update(self.HEADERS)
        self._session_initialized = False

    def _ensure_session(self) -> None:
        """
        Inisialisasi session dari halaman utama IDX.
        curl_cffi + impersonate="chrome" bypass Cloudflare.
        """
        if self._session_initialized:
            return

        try:
            # Kunjungi halaman utama untuk cookie
            resp = self.session.get(
                "https://www.idx.co.id/id",
                timeout=15
            )
            if resp.status_code == 200:
                time.sleep(1)
                self._session_initialized = True
                print("   [OK] Session IDX berhasil diinisialisasi (curl_cffi)")
            else:
                print(f"   [!] IDX returned status {resp.status_code}")
        except Exception as e:
            print(f"   [!] Gagal inisialisasi session IDX: {e}")

    def _fetch(self, url: str) -> dict | list | None:
        """
        Fetch data dari URL dengan retry logic + curl_cffi impersonate.

        Returns
        -------
        dict | list | None
            Response JSON yang sudah di-parse, atau None jika gagal.
        """
        self._ensure_session()

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=30)

                if resp.status_code == 429:
                    # Rate limit — tunggu lebih lama
                    print(f"   [!] Rate limit (429), menunggu 30 detik...")
                    time.sleep(30)
                    continue

                if resp.status_code >= 500:
                    raise Exception(f"Server error {resp.status_code}")

                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception:
                        return None

                # Status lain (403, 404, dll.)
                return None

            except Exception as e:
                if attempt >= self.max_retries:
                    return None
                delay = min(
                    self.retry_delay * (2 ** (attempt - 1)), 15
                )
                time.sleep(delay)

        return None

    # ==================================================================
    # TRADING DATA
    # ==================================================================

    def get_stock_summary(self, date_str: str) -> pd.DataFrame:
        """
        Ambil ringkasan trading saham harian dari IDX.

        Endpoint: /TradingSummary/GetStockSummary?date=YYYYMMDD

        Data: OHLC, Volume, Value, Frequency, Foreign Buy/Sell,
        Bid/Offer, Listed Shares, dll.
        """
        url = f"{self.BASE_URL}/TradingSummary/GetStockSummary?date={date_str}"
        data = self._fetch(url)

        if not data or "data" not in data:
            return pd.DataFrame()

        records = []
        for item in data["data"]:
            records.append({
                "date": date_str,
                "ticker": item.get("StockCode", ""),
                "stock_name": item.get("StockName", ""),
                "open": item.get("OpenPrice", 0),
                "high": item.get("High", 0),
                "low": item.get("Low", 0),
                "close": item.get("Close", 0),
                "previous": item.get("Previous", 0),
                "change": item.get("Change", 0),
                "volume": item.get("Volume", 0),
                "value": item.get("Value", 0),
                "frequency": item.get("Frequency", 0),
                # Orderbook
                "bid": item.get("Bid", 0),
                "bid_volume": item.get("BidVolume", 0),
                "offer": item.get("Offer", 0),
                "offer_volume": item.get("OfferVolume", 0),
                # Foreign flow
                "foreign_buy": item.get("ForeignBuy", 0),
                "foreign_sell": item.get("ForeignSell", 0),
                "foreign_net": item.get("ForeignBuy", 0) - item.get("ForeignSell", 0),
                # Shares info
                "listed_shares": item.get("ListedShares", 0),
                "tradable_shares": item.get("TradebleShares", 0),
                # Non-regular market
                "nr_volume": item.get("NonRegularVolume", 0),
                "nr_value": item.get("NonRegularValue", 0),
            })

        return pd.DataFrame(records)

    def get_broker_summary(
        self, date_str: str, start: int = 0, length: int = 9999
    ) -> pd.DataFrame:
        """
        Ambil ringkasan aktivitas broker pada tanggal tertentu.

        Endpoint: /TradingSummary/GetBrokerSummary
        """
        url = (
            f"{self.BASE_URL}/TradingSummary/GetBrokerSummary"
            f"?length={length}&start={start}&date={date_str}"
        )
        data = self._fetch(url)

        if not data or "data" not in data:
            return pd.DataFrame()

        records = []
        for item in data["data"]:
            records.append({
                "date": date_str,
                "broker_code": item.get("IDFirm", ""),
                "broker_name": item.get("FirmName", ""),
                "volume": item.get("Volume", 0),
                "value": item.get("Value", 0),
                "frequency": item.get("Frequency", 0),
            })

        return pd.DataFrame(records)

    def get_trading_info_daily(self, ticker: str) -> dict | None:
        """
        Ambil snapshot trading harian terkini untuk satu saham.

        Endpoint: /ListedCompany/GetTradingInfoDaily?code=XXXX
        """
        url = f"{self.BASE_URL}/ListedCompany/GetTradingInfoDaily?code={ticker}"
        data = self._fetch(url)

        if not data or not data.get("SecurityCode"):
            return None

        return {
            "ticker": data.get("SecurityCode", ""),
            "board": data.get("BoardCode", ""),
            "previous": data.get("PreviousPrice", 0),
            "open": data.get("OpeningPrice", 0),
            "high": data.get("HighestPrice", 0),
            "low": data.get("LowestPrice", 0),
            "close": data.get("ClosingPrice", 0),
            "change": data.get("Change", 0),
            "volume": data.get("TradedVolume", 0),
            "value": data.get("TradedValue", 0),
            "frequency": data.get("TradedFrequency", 0),
            "bid": data.get("BestBidPrice", 0),
            "bid_volume": data.get("BestBidVolume", 0),
            "offer": data.get("BestOfferPrice", 0),
            "offer_volume": data.get("BestOfferVolume", 0),
            "individual_index": data.get("IndividualIndex", 0),
            "foreign_shares": data.get("NumberForeigner", 0),
        }

    def get_top_gainers(self, year: int, month: int) -> pd.DataFrame:
        """
        Ambil daftar saham top gainer bulan tertentu.

        Endpoint: /DigitalStatistic/GetApiData?urlName=LINK_TOP_GAINER
        """
        query = json.dumps({
            "year": str(year), "month": str(month),
            "quarter": 0, "type": "monthly"
        })
        q64 = base64.b64encode(query.encode()).decode()
        url = (
            f"{self.BASE_URL}/DigitalStatistic/GetApiData"
            f"?urlName=LINK_TOP_GAINER&query={q64}"
            f"&isPrint=False&cumulative=false"
        )
        data = self._fetch(url)

        if not data or "data" not in data:
            return pd.DataFrame()

        records = []
        for item in data["data"]:
            records.append({
                "ticker": item.get("Code", ""),
                "name": item.get("StockName", ""),
                "previous": item.get("prevValue", 0),
                "close": item.get("closeValue", 0),
                "change": item.get("changePrice", 0),
                "change_pct": item.get("changePercentage", 0),
            })

        return pd.DataFrame(records)

    def get_top_losers(self, year: int, month: int) -> pd.DataFrame:
        """
        Ambil daftar saham top loser bulan tertentu.
        """
        query = json.dumps({
            "year": str(year), "month": str(month),
            "quarter": 0, "type": "monthly"
        })
        q64 = base64.b64encode(query.encode()).decode()
        url = (
            f"{self.BASE_URL}/DigitalStatistic/GetApiData"
            f"?urlName=LINK_TOP_LOSER&query={q64}"
            f"&isPrint=False&cumulative=false"
        )
        data = self._fetch(url)

        if not data or "data" not in data:
            return pd.DataFrame()

        records = []
        for item in data["data"]:
            records.append({
                "ticker": item.get("Code", ""),
                "name": item.get("StockName", ""),
                "previous": item.get("prevValue", 0),
                "close": item.get("closeValue", 0),
                "change": item.get("changePrice", 0),
                "change_pct": item.get("changePercentage", 0),
            })

        return pd.DataFrame(records)

    def get_foreign_trading(self, year: int, month: int) -> pd.DataFrame:
        """
        Ambil data aliran dana investor asing.

        Endpoint: /DigitalStatistic/GetApiData?urlName=LINK_TABLE_DAILY_TRADING_INVESTOR_FOREIGN
        """
        query = json.dumps({
            "year": str(year), "month": str(month),
            "quarter": 0, "type": "monthly"
        })
        q64 = base64.b64encode(query.encode()).decode()
        url = (
            f"{self.BASE_URL}/DigitalStatistic/GetApiData"
            f"?urlName=LINK_TABLE_DAILY_TRADING_INVESTOR_FOREIGN"
            f"&query={q64}&isPrint=False&cumulative=false"
        )
        data = self._fetch(url)

        if not data or "data" not in data:
            return pd.DataFrame()

        records = []
        for item in data["data"]:
            records.append({
                "date": item.get("date", ""),
                "foreign_buy_volume": item.get("foreignForeignVolume", 0),
                "foreign_buy_value": item.get("foreignForeignValue", 0),
                "foreign_sell_volume": item.get("foreignDomesticVolume", 0),
                "foreign_sell_value": item.get("foreignDomesticValue", 0),
            })

        return pd.DataFrame(records)

    # ==================================================================
    # FINANCIAL DATA (dari pola scrape_financial_ratio.py idx-bei)
    # ==================================================================

    def get_financial_ratios(
        self, year: int = 2024, quarter: int = 4
    ) -> pd.DataFrame:
        """
        Ambil data rasio keuangan seluruh emiten.

        Endpoint: /DigitalStatistic/GetApiDataPaginated
        urlName=LINK_FINANCIAL_DATA_RATIO

        Data: PER, PBV, ROE, ROA, DER, NPM, dll.

        Parameters
        ----------
        year : int
            Tahun laporan keuangan.
        quarter : int
            Kuartal (1-4).

        Returns
        -------
        pd.DataFrame
            DataFrame rasio keuangan seluruh emiten.
        """
        all_data = []
        page = 1

        print(f"   -> Mengambil Financial Ratios (Q{quarter}/{year})...")

        while True:
            url = (
                f"{self.BASE_URL}/DigitalStatistic/GetApiDataPaginated"
                f"?urlName=LINK_FINANCIAL_DATA_RATIO"
                f"&periodQuarter={quarter}&periodYear={year}"
                f"&type=yearly&isPrint=false&cumulative=false"
                f"&pageSize=100&pageNumber={page}"
                f"&orderBy=&search="
            )
            data = self._fetch(url)

            if not data or "data" not in data or len(data["data"]) == 0:
                break

            all_data.extend(data["data"])
            page += 1
            time.sleep(1)  # Rate limiting

        if not all_data:
            print("   [!] Gagal mengambil Financial Ratios dari IDX.")
            return pd.DataFrame()

        # Parse ke DataFrame
        records = []
        for item in all_data:
            records.append({
                "ticker": item.get("Code", ""),
                "name": item.get("StockName", item.get("Name", "")),
                "per": item.get("PER", None),
                "pbv": item.get("PBV", None),
                "roe": item.get("ROE", None),
                "roa": item.get("ROA", None),
                "der": item.get("DER", None),
                "npm": item.get("NPM", None),
                "eps": item.get("EPS", None),
                "bv": item.get("BV", None),
            })

        df = pd.DataFrame(records)
        print(f"   [OK] Financial Ratios: {len(df)} emiten")
        return df

    def get_stock_summary_multiday(
        self, n_days: int = 5
    ) -> pd.DataFrame:
        """
        Ambil stock summary untuk beberapa hari terakhir.

        Parameters
        ----------
        n_days : int
            Jumlah hari trading terakhir yang diambil.

        Returns
        -------
        pd.DataFrame
            Gabungan stock summary beberapa hari.
        """
        all_data = []
        current = datetime.now()

        days_fetched = 0
        days_tried = 0

        while days_fetched < n_days and days_tried < n_days + 10:
            date_str = current.strftime("%Y%m%d")
            # Lewati weekend
            if current.weekday() < 5:  # Senin=0, Jumat=4
                df = self.get_stock_summary(date_str)
                if not df.empty:
                    all_data.append(df)
                    days_fetched += 1
                    print(f"      -> IDX Stock Summary {date_str}: {len(df)} saham")

            current -= timedelta(days=1)
            days_tried += 1
            time.sleep(0.5)  # Rate limiting

        if not all_data:
            return pd.DataFrame()

        return pd.concat(all_data, ignore_index=True)
