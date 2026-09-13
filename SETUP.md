# سیستم شکار کوین — راهنمای کامل راه‌اندازی

این ریپو دو بخش داره:
- **موتور اصلی (پایتون)** — هر ۱۰ دقیقه روی GitHub Actions اجرا می‌شه، بازار رو اسکن می‌کنه، و نتیجه رو به تلگرام می‌فرسته
- **ربات تعاملی (`telegram_bot/`، جاوااسکریپت)** — روی Telegram Serverless (رایگان) اجرا می‌شه و به دستورات `/status` و `/top` جواب می‌ده

هیچ‌کدوم نیاز به سرور یا کامپیوتر همیشه‌روشن ندارن.

## مرحله ۱ — ساخت ریپو در گیت‌هاب

1. یه ریپوی **public** بساز (این حیاتیه: روی ریپوی private فقط ۲۰۰۰ دقیقه در ماه Actions رایگانه که با اجرای هر ۱۰ دقیقه خیلی زود تموم می‌شه؛ روی public کاملاً نامحدود و رایگانه)
2. همه‌ی فایل‌های این پروژه (`.py`، `.github/`، `telegram_bot/`، `requirements.txt`) رو توش آپلود کن

> نگران نباش: توکن‌ها و کلیدها هیچ‌وقت داخل کد نیستن (در ادامه به‌عنوان Secret جدا اضافه می‌شن)، پس public بودن ریپو مشکلی برای امنیت حساب‌هات ایجاد نمی‌کنه.

## مرحله ۲ — ساخت ربات تلگرام و گرفتن توکن‌ها

1. به [@BotFather](https://t.me/BotFather) پیام بده، `/newbot` بزن، رباتت رو بساز
2. توکنی که می‌ده رو نگه دار (این `TELEGRAM_BOT_TOKEN` هست)
3. برای گرفتن `TELEGRAM_CHAT_ID`: با ربات تازه‌ساخته‌ت `/start` بزن، بعد این آدرس رو تو مرورگر باز کن (TOKEN رو جایگزین کن):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   تو جواب دنبال `"chat":{"id": ...}` بگرد

## مرحله ۳ — اضافه‌کردن Secrets به گیت‌هاب

تو ریپو برو به: **Settings → Secrets and variables → Actions → New repository secret**

این‌ها رو اضافه کن:
| اسم Secret | مقدار | اجباری؟ |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | توکن مرحله‌ی ۲ | بله |
| `TELEGRAM_CHAT_ID` | چت‌آیدی مرحله‌ی ۲ | بله |
| `MORALIS_API_KEY` | از [admin.moralis.io](https://admin.moralis.io) (رایگان، برای رادار فارغ‌التحصیلی Pump.fun) | اختیاری |
| `TGCLOUD_TOKEN` | از BotFather → رباتت → Serverless → CLI Access → Access token (فقط اگه ربات تعاملی رو هم می‌خوای) | اختیاری |

## مرحله ۴ — فعال‌سازی

1. تب **Actions** ریپو رو باز کن، workflow های `Coin Hunter Scan` و `Deploy Telegram Bot` رو ببین
2. اگه پیام "workflows aren't running" اومد، دکمه‌ی فعال‌سازی رو بزن
3. برای تست فوری (بدون منتظر موندن ۱۰ دقیقه): `Coin Hunter Scan` → `Run workflow` رو بزن

## مرحله ۵ (اختیاری) — فعال‌سازی ربات تعاملی

1. تو BotFather: `Bot → Serverless → روشنش کن`
2. فایل `telegram_bot/lib/signals.js` رو ویرایش کن و `SIGNALS_URL` رو با آدرس واقعی ریپوی خودت جایگزین کن:
   `https://raw.githubusercontent.com/USERNAME/REPO/main/latest_signals.json`
3. همین که این تغییر رو commit/push کنی، workflow دوم (`Deploy Telegram Bot`) خودکار ربات رو دیپلوی می‌کنه

## بعدش چی؟

- هر ۱۰ دقیقه یه اسکن جدید اجرا می‌شه؛ اگه سیگنال واجد شرایطی پیدا بشه، پیام تلگرام می‌گیری
- می‌تونی هر وقت خواستی به رباتت `/status` یا `/top` بزنی
- برای دیدن جزئیات هر اجرا (خطاها، آمار)، تب Actions → روی هر اجرا کلیک کن → لاگ‌ها رو ببین

## هزینه

همه‌چیز رایگانه، به شرطی که:
- ریپو **public** باشه (وگرنه GitHub Actions محدود و بعدش پولی می‌شه)
- از APIهای رایگان (CoinGecko, DexScreener, GoPlus) استفاده کنیم که همین الان استفاده می‌کنیم
