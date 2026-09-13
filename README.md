# ربات تعاملی Telegram Serverless — راهنمای راه‌اندازی

این پروژه یه ربات جانبیه که کنار موتور اصلی پایتون (روی GitHub Actions) کار
می‌کنه. موتور پایتون هر چند دقیقه اسکن می‌کنه و یه فایل `latest_signals.json`
تو ریپوی گیت‌هابت آپدیت می‌کنه؛ این ربات با دستور `/status` یا `/top` همون
فایل رو می‌خونه و به کاربر نشون می‌ده - کاملاً رایگان، بدون سرور جدا.

## مراحل راه‌اندازی

1. **ساخت/انتخاب ربات در BotFather و فعال‌سازی Serverless**
   - وارد @BotFather شو → رباتت رو انتخاب کن (یا با `/newbot` بساز)
   - `Bot → Serverless` رو باز کن و روشنش کن
   - از همون منو، `CLI Access → Access token` رو کپی کن (این با توکن معمولی
     API فرق داره - فقط برای دستورات CLI استفاده می‌شه)

2. **نصب Node.js** (نسخه ۱۸ به بالا) اگه از قبل نداری

3. **آماده‌سازی پروژه**
   ```bash
   cd telegram_bot
   npm create @tgcloud/bot .
   npx tgcloud login
   ```
   موقع `login` همون CLI Access token مرحله‌ی ۱ رو وارد کن.

4. **آدرس JSON رو تنظیم کن**
   فایل `lib/signals.js` رو باز کن و `SIGNALS_URL` رو با آدرس raw فایل
   `latest_signals.json` تو ریپوی خودت جایگزین کن. فرمتش این شکلیه:
   ```
   https://raw.githubusercontent.com/USERNAME/REPO/main/latest_signals.json
   ```

5. **تست محلی (بدون deploy)**
   ```bash
   npx tgcloud run handlers/message '{ chat: { id: 1 }, text: "/status" }'
   ```

6. **Deploy**
   ```bash
   npx tgcloud push
   ```
   همین. ربات الان زنده‌ست و به `/start`، `/status`، و `/top` جواب می‌ده.

## نکته‌ی مهم

این ربات هیچ داده‌ای خودش تولید نمی‌کنه - فقط خروجی سیستم پایتون رو نشون
می‌ده. برای این‌که `latest_signals.json` واقعاً به‌روز بمونه، باید تو
GitHub Actions workflow (که بعداً می‌سازیم) این فایل بعد از هر اجرای
`main.py` به‌صورت خودکار commit و push بشه.
