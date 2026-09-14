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
"""

import requests
import config
import database

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramNotifier:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)

    def send_message(self, text: str) -> bool:
        """یک پیام متنی به چت مشخص‌شده می‌فرسته. اگه توکن/چت‌آیدی ست نشده باشه، فقط False برمی‌گردونه."""
        if not self.enabled:
            return False

        url = f"{TELEGRAM_API_BASE.format(token=self.token)}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, data=payload, timeout=15)
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"خطا در ارسال پیام تلگرام: {e}")
            return False

    def format_signal_message(self, coin: dict) -> str:
        """پیام قابل‌خوندن برای یک سیگنال کوین می‌سازه (بدون فرمت خاص، پرهیز از دردسر escape کردن Markdown)."""
        risk = coin.get("risk", {})
        tier = coin.get("tier", {})
        lines = [
            f"{tier.get('emoji', '🚨')} سیگنال جدید شکار کوین [رده {tier.get('tier', '?')}]",
            "",
            f"نماد: {coin['symbol']}",
            f"نام: {coin.get('name', '-')}",
            f"رده: {tier.get('label', '-')}",
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
            lines.append(f"هشدارها: {' | '.join(risk['warning_flags'])}")
        lines.append(f"توضیح رده: {tier.get('explanation', '-')}")
        lines.append("")
        lines.append(f"لینک: https://www.coingecko.com/en/coins/{coin['coin_id']}")
        lines.append("")
        lines.append("⚠️ این توصیه‌ی خرید نیست. فقط یک فیلتر آماریه. با سرمایه‌ی مازاد و حجم کم تصمیم بگیر.")
        return "\n".join(lines)

    def notify_signals(self, coins: list[dict]):
        """
        روی لیست کوین‌های واجد شرایط پیمایش می‌کنه و برای هرکدوم پیام می‌فرسته.
        قبل از ارسال چک می‌کنه که این کوین اخیراً (تو بازه‌ی cooldown) نوتیفیکیشن
        نگرفته باشه - وگرنه هر اجرا (هر ۱۰ دقیقه) دوباره همون کوین رو گزارش می‌ده.
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
            if self.send_message(msg):
                database.record_notification(coin["coin_id"])
