"""
تنظیمات مرکزی سیستم شکار کوین
همه‌ی آستانه‌ها و پارامترهای قابل تغییر اینجا هستند تا بدون دست‌زدن به منطق اصلی
بتونیم استراتژی رو تیون کنیم.

نکته‌ی امنیتی: مقادیر حساس (توکن تلگرام، کلید Moralis) از environment variable
خونده می‌شن (برای GitHub Actions: از GitHub Secrets تزریق می‌شن) تا هیچ‌وقت
مستقیم تو کد یا ریپوی public قرار نگیرن. برای تست محلی، می‌تونی یا این
متغیرهای محیطی رو ست کنی، یا موقتاً همین‌جا مقدار بدی (ولی هرگز commit نکن).
"""

import os

# --- منابع داده ---
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
# اگر بعداً کلید CoinMarketCap گرفتی اینجا ست کن (اختیاری، فعلاً استفاده نمی‌شه)
CMC_API_KEY = ""
CMC_BASE_URL = "https://pro-api.coinmarketcap.com/v1"

# --- فیلترهای فاز ۲ (Screening) - ردیابی میکروکپ (کوین‌های خیلی کوچیک و تازه) ---
MAX_MARKET_CAP_USD = 5_000_000
MIN_MARKET_CAP_USD = 20_000
MIN_VOLUME_TO_MCAP_RATIO = 0.05
MIN_24H_CHANGE_PERCENT = 15.0
MAX_COIN_AGE_DAYS = 365

# --- فاز ۱-E: ردیابی میان‌کپ / شتاب‌گیری موج دوم ---
# چرا این تیر لازم بود: کوین‌های اسکرین‌شات اولیه‌ی کاربر مارکت‌کپ ۲ تا ۲۷ میلیون
# دلار داشتن - یعنی فیلتر میکروکپ بالا (سقف ۵ میلیون) این‌ها رو کامل رد می‌کرد.
# این تیر به‌طور جداگانه کوین‌هایی که از میکروکپ گذشتن ولی دوباره دارن شتاب
# می‌گیرن (موج دوم پامپ) رو هم پوشش می‌ده.
MID_CAP_MIN_USD = 5_000_000
MID_CAP_MAX_USD = 60_000_000
MID_CAP_MIN_VOLUME_TO_MCAP_RATIO = 0.03
MID_CAP_MIN_24H_CHANGE_PERCENT = 8.0

# --- مدیریت سرمایه (فاز ۵) ---
MAX_POSITION_SIZE_PERCENT = 2.0
MAX_CONCURRENT_POSITIONS = 10

# --- دیتابیس ---
DB_PATH = "coin_hunter.db"

# --- زمان‌بندی ---
# نکته‌ی صادقانه: GitHub Actions به‌طور رسمی زیر ۵ دقیقه رو پشتیبانی نمی‌کنه و
# حتی روی ۵-۱۰ دقیقه هم ممکنه به‌خاطر صف بار سرور چند دقیقه تأخیر داشته باشه.
# ۱۰ دقیقه یه تعادل واقع‌بینانه بین سرعت و پایداریه؛ زیر این عملاً غیرقابل‌اتکاست.
FETCH_INTERVAL_MINUTES = 10

# --- فاز ۱-B: ردیابی سریع چند-چین (DexScreener) ---
DEXSCREENER_BASE_URL = "https://api.dexscreener.com"
MAX_PAIR_AGE_HOURS = 72
MIN_LIQUIDITY_USD = 5000
# چین‌هایی که این فاز پوشش می‌ده - سولانا (pump.fun/LetsBonk) + BSC (four.meme) +
# Base (Virtuals) چون این‌ها هم لانچ‌پدهای پرحجم برای memecoin دارن
DEX_TARGET_CHAINS = ["solana", "bsc", "base", "robinhood"]
# نگاشت chainId تو DexScreener به فرمت مورد نیاز GoPlus برای بررسی ریسک قرارداد
DEXSCREENER_CHAIN_MAP = {
    "solana": {"chain_type": "solana", "goplus_chain_id": "solana"},
    "bsc": {"chain_type": "evm", "goplus_chain_id": "56"},
    "base": {"chain_type": "evm", "goplus_chain_id": "8453"},
    "ethereum": {"chain_type": "evm", "goplus_chain_id": "1"},
    # Robinhood Chain: لانچ شده در ۱ جولای ۲۰۲۶، یه Arbitrum Orbit L2 با
    # chainId=4663، کاملاً EVM-compatible. یه لانچ‌پد bonding-curve به اسم
    # PheraDEX داره (شبیه pump.fun) - دقیقاً همون الگوی انفجاری memecoin.
    # ⚠️ نکته‌ی مهم: GoPlus ممکنه هنوز این چین خیلی‌جدید رو پشتیبانی نکنه؛
    # اگه GoPlus جواب ندی، سیستم به‌جای کرش، risk_score خنثی (۵۰) می‌ده
    # و هشدار "داده‌ی امنیتی موجود نیست" رو نشون می‌ده (رفتار امن پیش‌فرض).
    "robinhood": {"chain_type": "evm", "goplus_chain_id": "4663"},
}

# --- فاز ۱-C: رادار فارغ‌التحصیلی Pump.fun (Moralis API) ---
# این کلید رایگانه ولی نیاز به ثبت‌نام داره: https://admin.moralis.io (بخش API Keys)
MORALIS_API_KEY = os.environ.get("MORALIS_API_KEY", "")
PUMPFUN_EXCHANGE = "pumpfun"
# طبق تحقیق: فارغ‌التحصیلی موج فروش اولیه رو راه می‌اندازه - این ساعت‌های اول رو نادیده بگیر
MIN_GRADUATION_AGE_HOURS = 2
MAX_GRADUATION_AGE_HOURS = 48

# --- فاز ۱-D: رادار ترندهای CoinGecko (Trending Search) ---
# این endpoint کوین‌هایی که کاربرها اخیراً زیاد سرچ کردن رو نشون می‌ده - یه سیگنال
# "علاقه‌ی ناگهانی" که معمولاً قبل از انعکاس کامل تو قیمت/حجم شکل می‌گیره.
ENABLE_TRENDING_RADAR = True

# --- فاز ۱-F: واچ‌لیست پایدار (حافظه‌ی بین اجراها) ---
# کوین‌هایی که این دور فیلترهای فاز ۲ رو رد کردن (نزدیک بودن ولی نه کامل)، تا
# این تعداد روز دوباره تو اجراهای بعدی چک می‌شن - حتی اگه دیگه تو boosted/trending نباشن.
# این جلوی از دست رفتن کوینی که "نزدیک بود ولی هنوز آماده نبود" رو می‌گیره.
WATCHLIST_MAX_AGE_DAYS = 14
# چقدر امتیازش باید نزدیک به آستانه‌ی قبول‌شدن باشه تا وارد واچ‌لیست بشه
WATCHLIST_SCORE_MARGIN = 20.0

# --- فاز ۲-D: برچسب‌گذاری روایت/ترند (Narrative Tagging) ---
# این لیست رو خودت به‌روز نگه‌دار - هر وقت یه ترند جدید دیدی (مثل مشاهده‌ی خودت
# درباره‌ی ROBINHOOD)، کلیدواژه‌ش رو اینجا اضافه کن. حروف کوچک/بزرگ مهم نیست.
TRENDING_KEYWORDS = [
    "robinhood", "robin", "trump", "elon", "musk", "pepe", "doge",
    "tiktok", "brainrot", "ai", "openai", "chatgpt", "grok",
    "coinbase", "binance", "vitalik", "satoshi", "nasa", "spacex", "tesla",
]
# چند امتیاز به کوین‌هایی که اسمشون با ترند مطابقت داره اضافه بشه
NARRATIVE_SCORE_BONUS = 8.0

# --- تلگرام (فاز ۴) ---
# این دو مقدار رو باید خودت پر کنی، راهنما در پیام چت هست
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
# فقط کوین‌هایی که امتیاز نهایی‌شون از این بیشتره نوتیفیکیشن می‌گیرن
NOTIFY_MIN_SCORE = 60.0
# بعد از اینکه یه کوین نوتیفیکیشن گرفت، تا این تعداد ساعت دوباره براش پیام
# نمی‌فرستیم حتی اگه همچنان واجد شرایط باشه - جلوگیری از اسپم شدن هر ۱۰ دقیقه
NOTIFY_COOLDOWN_HOURS = 6

# --- رصد نتیجه (Outcome Tracking) ---
# مدت زمانی که هر سیگنال رصد می‌شه (روز) - دقیقاً همون بازه‌ی هدف اصلی پروژه
OUTCOME_TRACKING_MAX_DAYS = 30
# رشد ۱۰۰۰% یعنی قیمت ۱۱ برابر بشه (قیمت اولیه + ۱۰۰۰٪ = ۱۱ برابر)
OUTCOME_HIT_MULTIPLIER = 11.0
