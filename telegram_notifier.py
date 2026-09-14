"""
فاز ۴ - اعلان تلگرام.
از Telegram Bot API مستقیم (بدون کتابخونه‌ی سنگین) استفاده می‌کنیم چون فقط
نیاز به ارسال پیام داریم، نه دریافت/polling. این باعث می‌شه روی محیط‌های
cron-based مثل GitHub Actions (که اسکریپت اجرا و بلافاصله خارج می‌شه) بی‌دردسر کار کنه.

راه‌اندازی (یک‌بار):
  1. تو تلگرام به @BotFather پیام بده و /newbot رو بزن، اسم دلخواه بده.
     در جواب یه توکن می‌گیری شبیه: 123456789:ABCdefGhIJKlmNoPQRstuVwxyz
  2. با ربات تازه‌ساخته‌شده‌ت یه پیام (مثلاً /start) بفرست تا چتت باهاش باز بشه.
  3. برای گرفتن chat_id، این آدرس رو تو مرورگر باز کن (TOKEN رو جایگزین کن):
     https://api.telegram.org/bot<TOKEN>/getUpdates
     تو جواب JSON دنبال "chat":{"id": ...} بگرد، همون chat_id تو هست.
  4. این دو مقدار رو در config.py یا به‌عنوان GitHub Secret ست کن.
     برای فرستادن به چند اکانت هم‌زمان، آیدی‌ها رو با ویرگول جدا کن:
     TELEGRAM_CHAT_ID = "111111,222222"
"""

import html
import requests
import config
import database

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramNotifier:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or config.TELEGRAM_BOT_TOKEN
        raw_chat_ids = chat_id or config.TELEGRAM_CHAT_ID
        # پشتیبانی از چند چت‌آیدی هم‌زمان با جداکننده‌ی ویرگول
        self.chat_ids = [c.strip() for c in (raw_chat_ids or "").split(",") if c.strip()]
        self.enabled = bool(self.token and self.chat_ids)

    def send_message(self, text: str, chat_id: str, use_html: bool = False) -> bool:
        """یک پیام متنی به یک چت مشخص می‌فرسته."""
        url = f"{TELEGRAM_API_BASE.format(token=self.token)}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if use_html:
            payload["parse_mode"] = "HTML"
        try:
            resp = requests.post(url, data=payload, timeout=15)
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"خطا در ارسال پیام تلگرام (چت {chat_id}): {e}")
            return False

    def send_to_all(self, text: str, use_html: bool = False) -> bool:
        """پیام رو به تمام چت‌آیدی‌های تنظیم‌شده می‌فرسته. اگه حداقل یکی موفق بود True برمی‌گردونه."""
        if not self.enabled:
            return False
        any_success = False
        for chat_id in self.chat_ids:
            if self.send_message(text, chat_id, use_html=use_html):
                any_success = True
        return any_success

    @staticmethod
    def _esc(text) -> str:
        """متن آزاد (اسم/نماد/هشدارها) رو برای درج امن داخل HTML تلگرام escape می‌کنه."""
        return html.escape(str(text), quote=True)

    def _build_links(self, coin: dict) -> list[tuple[str, str]]:
        """
        لیستی از (برچسب, آدرس) برمی‌گردونه - برای کوین‌های DexScreener/Pump.fun
        از لینک مستقیم DexScreener + جستجوی DexTools استفاده می‌کنه (چون DexTools
        آدرس pair مستقیم نداریم که بسازیم، ولی جستجوش با آدرس قرارداد همیشه کار می‌کنه).
        برای کوین‌های خام CoinGecko فقط لینک coingecko رو می‌ده.
        """
        dex_chain = coin.get("dex_chain")
        address = coin.get("contract_address")
        links = []

        if dex_chain and address:
            links.append(("DexScreener", f"https://dexscreener.com/{dex_chain}/{address}"))
            links.append(("DexTools", f"https://www.dextools.io/app/en/search?query={address}"))
        elif address:
            links.append(("DexScreener", f"https://dexscreener.com/search?q={address}"))
            links.append(("DexTools", f"https://www.dextools.io/app/en/search?query={address}"))
        else:
            links.append(("CoinGecko", f"https://www.coingecko.com/en/coins/{coin['coin_id']}"))

        if coin.get("twitter_url"):
            links.append(("توییتر", coin["twitter_url"]))
        if coin.get("website_url"):
            links.append(("وبسایت", coin["website_url"]))

        return links

    def format_signal_message(self, coin: dict) -> str:
        """
        پیام رو با HTML تلگرام می‌سازه: لینک‌ها به‌جای آدرس کامل، فقط با اسم
        کوتاه (مثل DexScreener) نمایش داده می‌شن و کانترکت با تگ <code> با یک
        لمس قابل‌کپیه. HTML امن‌تر از Markdown‌ه چون فقط &, <, > نیاز به
        escape دارن (نه _ که تو لینک‌های توییتر/وبسایت خیلی رایجه).
        """
        risk = coin.get("risk", {})
        tier = coin.get("tier", {})
        symbol = self._esc(coin.get("symbol", "?"))
        name = self._esc(coin.get("name", "-"))
        address = coin.get("contract_address")

        lines = [
            f"{tier.get('emoji', '🚨')} سیگنال جدید شکار کوین [رده {self._esc(tier.get('tier', '?'))}]",
            "",
            f"نماد: #{symbol}",
            f"نام: {name}",
            f"رده: {self._esc(tier.get('label', '-'))}",
            f"امتیاز نهایی: {coin['final_score']} / 100",
            f"مارکت‌کپ: ${coin['market_cap_usd']:,.0f}",
            f"رشد ۲۴ساعته: {coin['change_24h_percent']:.1f}%",
            f"امتیاز ریسک قرارداد: {risk.get('risk_score', '?')}/100 (پایین‌تر بهتره)",
        ]
        if risk.get("holder_concentration_percent") is not None:
            lines.append(f"تمرکز ۱۰ کیف‌پول برتر: {risk['holder_concentration_percent']}%")
        if risk.get("liquidity_locked_percent") is not None:
            lines.append(f"نقدینگی قفل‌شده: {risk['liquidity_locked_percent']}%")
        if risk.get("warning_flags"):
            lines.append(f"هشدارها: {self._esc(' | '.join(risk['warning_flags']))}")
        lines.append(f"توضیح رده: {self._esc(tier.get('explanation', '-'))}")
        lines.append("")

        if address:
            lines.append(f"کانترکت: <code>{self._esc(address)}</code>")

        link_parts = [
            f'<a href="{self._esc(url)}">{self._esc(label)}</a>'
            for label, url in self._build_links(coin)
        ]
        lines.append("لینک‌ها: " + " | ".join(link_parts))

        lines.append("")
        lines.append("⚠️ این توصیه‌ی خرید نیست. فقط یک فیلتر آماریه. با سرمایه‌ی مازاد و حجم کم تصمیم بگیر.")
        return "\n".join(lines)

    def notify_signals(self, coins: list[dict]):
        """
        روی لیست کوین‌های واجد شرایط پیمایش می‌کنه و برای هرکدوم (به همه‌ی
        چت‌آیدی‌های تنظیم‌شده) پیام می‌فرسته. قبل از ارسال چک می‌کنه که این
        کوین اخیراً (تو بازه‌ی cooldown) نوتیفیکیشن نگرفته باشه.
        """
        if not self.enabled:
            print("توکن/چت‌آیدی تلگرام ست نشده - نوتیفیکیشن رد شد (فقط در کنسول چاپ می‌شه).")
            return
        for coin in coins:
            if coin["final_score"] < config.NOTIFY_MIN_SCORE:
                continue
            if coin.get("tier", {}).get("tier") == "REJECTED":
                continue
            if not database.should_notify(coin["coin_id"], config.NOTIFY_COOLDOWN_HOURS):
                continue
            msg = self.format_signal_message(coin)
            if self.send_to_all(msg, use_html=True):
                database.record_notification(coin["coin_id"])
