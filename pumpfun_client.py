"""
فاز ۱-C: رادار فارغ‌التحصیلی Pump.fun (از طریق Moralis API، رایگان با ثبت‌نام).

یافته‌ی کلیدی از تحقیق (داده‌ی واقعی اوایل سپتامبر ۲۰۲۶):
  - فقط ۲.۷٪ از توکن‌های pump.fun اصلاً فارغ‌التحصیل می‌شن؛ ۹۷.۳٪ بقیه روی
    bonding curve به صفر می‌میرن.
  - از اون ۲.۷٪ فارغ‌التحصیل‌شده، ۸۷٪ در همون ساعت اول اتفاق می‌افته - یعنی
    گرفتن لحظه‌ی دقیق فارغ‌التحصیلی با polling هر ۳۰ دقیقه عملاً غیرممکنه.
  - نکته‌ی مهم‌تر: لحظه‌ی فارغ‌التحصیلی خودش یه موج فروش از خریدارهای اولیه‌ی
    bonding curve راه می‌اندازه (چون اون‌ها خیلی ارزون‌تر خریده بودن).

نتیجه‌ی استراتژیک: به‌جای شکار در لحظه‌ی فارغ‌التحصیلی (که هم غیرممکنه هم پرریسک‌تره)،
دنبال توکن‌هایی می‌گردیم که از فارغ‌التحصیلی‌شون چند ساعت گذشته (MIN_GRADUATION_AGE_HOURS)
و از موج فروش اولیه جون سالم به در بردن - یعنی هنوز نقدینگی/قیمت معقولی دارن.

ثبت‌نام رایگان: https://admin.moralis.io -> بخش API Keys
"""

import requests
from datetime import datetime, timezone
import config

BASE_URL = "https://solana-gateway.moralis.io"


class MoralisPumpFunClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.MORALIS_API_KEY
        self.session = requests.Session()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict = None):
        if not self.enabled:
            return None
        headers = {"accept": "application/json", "X-API-Key": self.api_key}
        resp = self.session.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_graduated_tokens(self, exchange: str = None, limit: int = 100) -> list:
        """لیست توکن‌هایی که فارغ‌التحصیل شدن (به همراه زمان فارغ‌التحصیلی)."""
        exchange = exchange or config.PUMPFUN_EXCHANGE
        try:
            data = self._get(f"/token/mainnet/exchange/{exchange}/graduated", params={"limit": limit})
        except requests.RequestException as e:
            print(f"خطا در دریافت لیست فارغ‌التحصیل‌شده‌ها از Moralis: {e}")
            return []
        if not data:
            return []
        return data.get("result", [])

    def get_recent_graduation_candidates(self) -> list:
        """
        از بین همه‌ی فارغ‌التحصیل‌شده‌ها، فقط اون‌هایی که سنشون تو بازه‌ی
        امن (بعد از موج فروش اولیه، ولی هنوز به اندازه‌ی کافی تازه) هست رو برمی‌گردونه.
        خروجی: لیستی از dict شامل آدرس قرارداد و سن (ساعت) از لحظه‌ی فارغ‌التحصیلی.
        """
        tokens = self.get_graduated_tokens()
        now = datetime.now(timezone.utc)
        candidates = []
        for t in tokens:
            graduated_at = t.get("graduatedAt")
            address = t.get("tokenAddress")
            if not graduated_at or not address:
                continue
            try:
                grad_time = datetime.fromisoformat(graduated_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            age_hours = (now - grad_time).total_seconds() / 3600
            if config.MIN_GRADUATION_AGE_HOURS <= age_hours <= config.MAX_GRADUATION_AGE_HOURS:
                candidates.append({
                    "address": address,
                    "graduated_at": graduated_at,
                    "age_hours": round(age_hours, 1),
                })
        return candidates
