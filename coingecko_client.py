"""
کلاینت CoinGecko - فاز ۱ (Data Ingestion)
CoinGecko API عمومی نیاز به کلید نداره (با محدودیت rate limit پایین‌تر).
اگر بعداً خواستی سریع‌تر و پایدارتر بشه می‌تونی پلن Pro بگیری یا CMC رو اضافه کنی
(فایل config.py از قبل جا برای CMC_API_KEY داره).
"""

import time
import requests
import config


class CoinGeckoClient:
    def __init__(self):
        self.base_url = config.COINGECKO_BASE_URL
        self.session = requests.Session()

    def _get(self, endpoint: str, params: dict = None, retries: int = 3):
        """درخواست GET با retry ساده برای مقابله با rate limit (429)."""
        url = f"{self.base_url}{endpoint}"
        for attempt in range(retries):
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"درخواست به {url} بعد از {retries} تلاش با rate limit مواجه شد")

    def fetch_markets(self, page: int = 1, per_page: int = 250, order: str = "market_cap_asc"):
        """
        لیست کوین‌ها به همراه اطلاعات بازار.
        order='market_cap_asc' عمداً از پایین به بالا مرتب می‌کنه چون کوین‌های
        کوچک و کم‌رنک (که پتانسیل رشد انفجاری دارن) هدف اصلی ما هستن.
        """
        params = {
            "vs_currency": "usd",
            "order": order,
            "per_page": per_page,
            "page": page,
            "sparkline": "false",
            "price_change_percentage": "24h,7d",
        }
        return self._get("/coins/markets", params=params)

    def fetch_new_listings(self, pages: int = 3):
        """
        چند صفحه از انتهای لیست (کم‌رنک‌ترین‌ها) رو جمع می‌کنه.
        این‌ها اغلب کوین‌های تازه یا خیلی کوچیک هستن که هنوز کشف نشدن -
        دقیقاً جایی که رشدهای ۱۰۰۰%+ از اونجا شروع می‌شن.
        """
        all_coins = []
        for page in range(1, pages + 1):
            coins = self.fetch_markets(page=page, order="market_cap_asc")
            if not coins:
                break
            all_coins.extend(coins)
            time.sleep(1.5)  # احترام به rate limit
        return all_coins

    def fetch_trending(self) -> list:
        """
        فاز ۱-D: کوین‌هایی که کاربرها اخیراً زیاد سرچ کردن (نه لزوماً بر اساس
        رشد قیمتی). این یه سیگنال "علاقه‌ی ناگهانی" هست که معمولاً چند ساعت
        قبل از انعکاس کامل تو حجم/قیمت شکل می‌گیره - می‌تونه فرصت زودهنگام باشه.
        خروجی فقط id/symbol/name/rank می‌ده؛ برای قیمت/حجم باید fetch_markets_by_ids صدا زده بشه.
        """
        try:
            data = self._get("/search/trending")
        except Exception:
            return []
        items = (data or {}).get("coins", [])
        return [item.get("item", {}) for item in items]

    def fetch_markets_by_ids(self, ids: list) -> list:
        """داده‌ی کامل بازار (قیمت/حجم/مارکت‌کپ/تغییرات) رو برای یک لیست id مشخص می‌گیره."""
        if not ids:
            return []
        params = {
            "vs_currency": "usd",
            "ids": ",".join(ids),
            "order": "market_cap_desc",
            "per_page": len(ids),
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h,7d",
        }
        try:
            return self._get("/coins/markets", params=params) or []
        except Exception:
            return []

    def fetch_coin_detail(self, coin_id: str) -> dict:
        """
        جزئیات کامل یک کوین رو می‌گیره، مهم‌ترین چیزی که اینجا لازم داریم
        فیلد 'platforms' هست: دیکشنری از {نام چین: آدرس قرارداد}.
        این آدرس برای فاز ۳ (بررسی ریسک قرارداد) لازمه.
        """
        params = {
            "localization": "false",
            "tickers": "false",
            "market_data": "false",
            "community_data": "false",
            "developer_data": "false",
        }
        return self._get(f"/coins/{coin_id}", params=params)

    def normalize_coin(self, raw: dict) -> dict:
        """داده‌ی خام API رو به فرمت یکسان داخلی سیستم تبدیل می‌کنه."""
        return {
            "coin_id": raw.get("id"),
            "symbol": (raw.get("symbol") or "").upper(),
            "name": raw.get("name"),
            "price_usd": raw.get("current_price"),
            "market_cap_usd": raw.get("market_cap"),
            "volume_24h_usd": raw.get("total_volume"),
            "change_24h_percent": raw.get("price_change_percentage_24h_in_currency"),
            "change_7d_percent": raw.get("price_change_percentage_7d_in_currency"),
        }
