"""
فاز ۱-B: ردیابی سریع چند-چین با DexScreener API (رسمی، رایگان، بدون کلید).
دلیل اضافه‌شدن این فاز: CoinGecko کوین‌ها رو معمولاً بعد از این‌که مقداری رشد
کردن و شناخته شدن لیست می‌کنه - یعنی ممکنه فاز اولیه‌ی انفجاری از دست بره.
DexScreener pool های تازه‌ساخته‌شده روی DEX ها رو تقریباً بلادرنگ نشون می‌ده.

فاز ۱-E (گسترش چند-چین): علاوه بر سولانا، BSC (لانچ‌پد four.meme) و Base
(لانچ‌پد Virtuals) رو هم پوشش می‌ده تا فرصت‌های خارج از اکوسیستم سولانا از دست نره.

مستندات رسمی: https://docs.dexscreener.com/api/reference
"""

import time
import requests
from datetime import datetime, timezone

import config

HEADERS = {"Accept": "application/json"}


class DexScreenerClient:
    def __init__(self):
        self.base_url = config.DEXSCREENER_BASE_URL
        self.session = requests.Session()

    def _get(self, path: str, params: dict = None, retries: int = 3):
        url = f"{self.base_url}{path}"
        for attempt in range(retries):
            resp = self.session.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"درخواست به {url} با rate limit مواجه شد")

    def get_boosted_tokens(self) -> list:
        """
        توکن‌هایی که اخیراً 'boost' (تبلیغ) شدن رو برمی‌گردونه - این یه سیگنال هایپ
        هست (توجه: پول خرج‌شده برای تبلیغ لزوماً به معنی امن بودن نیست. باید حتماً
        از فیلتر ریسک قرارداد رد بشه قبل از هر تصمیمی).
        """
        try:
            data = self._get("/token-boosts/latest/v1")
        except Exception:
            return []
        if isinstance(data, list):
            return data
        return []

    def get_pairs_for_tokens(self, token_addresses: list) -> list:
        """جزئیات کامل pair (قیمت، حجم، نقدینگی، سن، تراکنش‌ها) رو برای لیستی از آدرس توکن می‌گیره."""
        if not token_addresses:
            return []
        # DexScreener حداکثر ۳۰ آدرس در هر درخواست رو قبول می‌کنه
        all_pairs = []
        for i in range(0, len(token_addresses), 30):
            batch = token_addresses[i:i + 30]
            addresses_str = ",".join(batch)
            try:
                data = self._get(f"/latest/dex/tokens/{addresses_str}")
            except Exception:
                continue
            pairs = data.get("pairs") or []
            all_pairs.extend(pairs)
            time.sleep(1)
        return all_pairs

    def fetch_multichain_candidates(self) -> list:
        """
        جریان کامل: توکن‌های boosted روی همه‌ی چین‌های config.DEX_TARGET_CHAINS
        رو پیدا می‌کنه، جزئیات pair هرکدوم رو می‌گیره، و فقط pool های تازه با
        نقدینگی کافی رو برمی‌گردونه.
        """
        boosted = self.get_boosted_tokens()
        target_chains = set(config.DEX_TARGET_CHAINS)
        addresses = [
            b["tokenAddress"] for b in boosted
            if b.get("chainId") in target_chains and b.get("tokenAddress")
        ]
        addresses = list(dict.fromkeys(addresses))  # حذف تکراری با حفظ ترتیب

        if not addresses:
            return []

        pairs = self.get_pairs_for_tokens(addresses)
        relevant_pairs = [p for p in pairs if p.get("chainId") in target_chains]

        candidates = []
        now_ms = datetime.now(timezone.utc).timestamp() * 1000
        for pair in relevant_pairs:
            liquidity_usd = (pair.get("liquidity") or {}).get("usd") or 0
            created_at = pair.get("pairCreatedAt")
            age_hours = None
            if created_at:
                age_hours = (now_ms - created_at) / (1000 * 60 * 60)

            if liquidity_usd < config.MIN_LIQUIDITY_USD:
                continue
            if age_hours is not None and age_hours > config.MAX_PAIR_AGE_HOURS:
                continue

            candidates.append(self.normalize_pair(pair, age_hours))

        return candidates

    def normalize_pair(self, pair: dict, age_hours) -> dict:
        """داده‌ی خام pair رو به همون فرمت داخلی سیستم (مثل normalize_coin) تبدیل می‌کنه."""
        base_token = pair.get("baseToken") or {}
        price_change = pair.get("priceChange") or {}
        volume = pair.get("volume") or {}
        txns = pair.get("txns") or {}

        try:
            price_usd = float(pair.get("priceUsd") or 0)
        except (TypeError, ValueError):
            price_usd = None

        market_cap = pair.get("marketCap") or pair.get("fdv")

        txns_h24 = txns.get("h24") or {}
        txns_h1 = txns.get("h1") or {}

        chain_id_str = pair.get("chainId")
        chain_info = config.DEXSCREENER_CHAIN_MAP.get(chain_id_str, {})

        return {
            "coin_id": f"dex-{base_token.get('address', pair.get('pairAddress'))}",
            "symbol": (base_token.get("symbol") or "?").upper(),
            "name": base_token.get("name") or base_token.get("symbol") or "Unknown",
            "price_usd": price_usd,
            "market_cap_usd": market_cap,
            "volume_24h_usd": volume.get("h24"),
            "change_24h_percent": price_change.get("h24"),
            "change_1h_percent": price_change.get("h1"),
            "change_7d_percent": None,  # DexScreener بازه‌ی ۷ روزه نمی‌ده
            "age_hours": round(age_hours, 1) if age_hours is not None else None,
            "liquidity_usd": (pair.get("liquidity") or {}).get("usd"),
            "buys_24h": txns_h24.get("buys"),
            "sells_24h": txns_h24.get("sells"),
            "buys_1h": txns_h1.get("buys"),
            "sells_1h": txns_h1.get("sells"),
            # این فیلدها رو مستقیم داریم - در فاز ریسک مستقیم استفاده می‌شن، بدون
            # نیاز به فراخوانی اضافه به CoinGecko/resolve_chain
            "chain_type": chain_info.get("chain_type"),
            "goplus_chain_id": chain_info.get("goplus_chain_id"),
            "contract_address": base_token.get("address"),
            "source": chain_id_str or "dexscreener",
        }
