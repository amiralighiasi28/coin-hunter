"""
فاز ۲-C - تشخیص Wash Trading و فشار خرید/فروش.
خیلی از پامپ‌های مصنوعی با ردوبدل کردن پول بین چند کیف‌پول، حجم معاملات
رو بزرگ‌تر از واقعیت نشون می‌دن تا کاربرها فکر کنن یه چیزی داره اتفاق می‌افته.
دو نشونه‌ی اصلی wash trading:
  ۱. حجم دلاری بالا ولی تعداد تراکنش خیلی کم (یعنی چند معامله‌ی درشت مصنوعی)
  ۲. نسبت خرید به فروش خیلی نزدیک به ۵۰/۵۰ (چرخوندن پول بین دو کیف‌پول)
     در مقابل، یک پامپ ارگانیک واقعی معمولاً فشار خرید غالب داره.

این تحلیل فقط برای کوین‌هایی که از DexScreener اومدن قابل انجامه، چون
CoinGecko تعداد تراکنش رو نمی‌ده. برای بقیه، امتیاز خنثی برمی‌گردونیم.
"""

# میانگین حجم هر تراکنش که بالاتر از این باشه، مشکوک به معاملات مصنوعی/نهنگ‌های محدوده
SUSPICIOUS_AVG_TRADE_SIZE_USD = 5000
# اگه نسبت خرید به کل تراکنش‌ها بین این بازه باشه (خیلی متوازن)، مشکوکه
BALANCED_RATIO_LOW = 0.45
BALANCED_RATIO_HIGH = 0.55
# حداقل تعداد تراکنش در ۲۴ ساعت که برای اطمینان از فعالیت واقعی لازمه
MIN_TXN_COUNT_24H = 20


def analyze_trading_pattern(coin: dict) -> dict:
    """
    خروجی: dict شامل wash_trading_score (0 امن -> 100 خیلی مشکوک)،
    buy_pressure_ratio (نسبت خرید)، و توضیح.
    """
    buys = coin.get("buys_24h")
    sells = coin.get("sells_24h")
    volume = coin.get("volume_24h_usd")

    if buys is None or sells is None:
        return {
            "wash_trading_score": 50,  # خنثی - داده نداریم (مثلاً منبع CoinGecko بوده)
            "buy_pressure_ratio": None,
            "note": "داده‌ی تراکنش در دسترس نیست (این کوین از CoinGecko اومده)",
        }

    total_txns = buys + sells
    score = 0
    notes = []

    if total_txns < MIN_TXN_COUNT_24H:
        score += 30
        notes.append(f"فقط {total_txns} تراکنش در ۲۴ ساعت - فعالیت واقعی کم")

    if volume and total_txns > 0:
        avg_trade_size = volume / total_txns
        if avg_trade_size > SUSPICIOUS_AVG_TRADE_SIZE_USD:
            score += 35
            notes.append(f"میانگین سایز هر تراکنش ${avg_trade_size:,.0f} - مشکوک به معاملات مصنوعی/بزرگ")

    buy_ratio = (buys / total_txns) if total_txns > 0 else 0.5
    if BALANCED_RATIO_LOW <= buy_ratio <= BALANCED_RATIO_HIGH and total_txns >= MIN_TXN_COUNT_24H:
        score += 25
        notes.append(f"نسبت خرید/فروش خیلی متوازنه ({buy_ratio:.0%}) - ممکنه چرخوندن پول باشه")
    elif buy_ratio > 0.65:
        notes.append(f"فشار خرید قوی ({buy_ratio:.0%}) - نشونه‌ی سالم برای پامپ ارگانیک")

    note = " | ".join(notes) if notes else "الگوی معاملاتی طبیعی به نظر می‌رسه"

    return {
        "wash_trading_score": min(score, 100),
        "buy_pressure_ratio": round(buy_ratio, 2),
        "note": note,
    }
