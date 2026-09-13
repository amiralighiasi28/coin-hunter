"""
فاز ۲ - Screening: فیلتر کردن کوین‌ها بر اساس معیارهای اولیه.
هدف: از بین صدها/هزاران کوین، اون‌هایی که نشونه‌ی شروع یک حرکت غیرعادی
هستن رو پیدا کنیم. این فقط فیلتر اولیه است - فاز ۳ (ریسک‌اسکورینگ) بعداً
روی خروجی این ماژول کار می‌کنه تا rug pull ها رو حذف کنه.

فاز ۱-E: دو تیر جداگانه اجرا می‌شه -
  - میکروکپ: کوین‌های خیلی کوچیک و تازه (زیر ۵ میلیون دلار)
  - میان‌کپ: کوین‌هایی که از میکروکپ گذشتن ولی دارن دوباره شتاب می‌گیرن
    (موج دوم پامپ) - این تیر دقیقاً همون بازه‌ای رو پوشش می‌ده که تو
    اسکرین‌شات اولیه‌ی کاربر دیده شد (۲ تا ۲۷ میلیون دلار) و قبلاً فیلتر
    میکروکپ به‌تنهایی این‌ها رو کامل رد می‌کرد.
"""

import config

MICRO_CAP_PROFILE = {
    "name": "micro",
    "min_mcap": config.MIN_MARKET_CAP_USD,
    "max_mcap": config.MAX_MARKET_CAP_USD,
    "min_volume_ratio": config.MIN_VOLUME_TO_MCAP_RATIO,
    "min_24h_change": config.MIN_24H_CHANGE_PERCENT,
}

MID_CAP_PROFILE = {
    "name": "mid",
    "min_mcap": config.MID_CAP_MIN_USD,
    "max_mcap": config.MID_CAP_MAX_USD,
    "min_volume_ratio": config.MID_CAP_MIN_VOLUME_TO_MCAP_RATIO,
    "min_24h_change": config.MID_CAP_MIN_24H_CHANGE_PERCENT,
}


def passes_basic_filters(coin: dict, profile: dict) -> tuple[bool, list[str]]:
    """
    بررسی می‌کنه کوین از فیلترهای پایه‌ی یک پروفایل مشخص (میکروکپ یا میان‌کپ) رد می‌شه یا نه.
    خروجی: (آیا رد شد, لیست دلایلی که به عنوان سیگنال شناسایی شدن)
    """
    reasons = []

    mcap = coin.get("market_cap_usd")
    volume = coin.get("volume_24h_usd")
    change_24h = coin.get("change_24h_percent")

    if mcap is None or volume is None or mcap <= 0:
        return False, []

    # برای کوین‌های منبع DexScreener، حداقل نقدینگی هم چک می‌شه چون بدون
    # نقدینگی کافی، حتی اگه قیمت رشد کنه عملاً نمی‌شه معامله کرد
    liquidity = coin.get("liquidity_usd")
    if liquidity is not None and liquidity < config.MIN_LIQUIDITY_USD:
        return False, []

    if not (profile["min_mcap"] <= mcap <= profile["max_mcap"]):
        return False, []

    volume_ratio = volume / mcap
    if volume_ratio < profile["min_volume_ratio"]:
        return False, []
    reasons.append(f"نسبت حجم/مارکت‌کپ بالا: {volume_ratio:.2f}")

    if change_24h is None or change_24h < profile["min_24h_change"]:
        return False, []
    reasons.append(f"رشد ۲۴ ساعته: {change_24h:.1f}%")

    return True, reasons


def score_coin(coin: dict, profile: dict) -> float:
    """
    یک امتیاز ساده (0 تا 100) بر اساس شدت سیگنال‌ها می‌ده، نسبت به آستانه‌های
    همون پروفایل (میکروکپ سخت‌گیرتره چون نوسانش طبیعتاً بیشتره).
    """
    mcap = coin.get("market_cap_usd", 0) or 0
    volume = coin.get("volume_24h_usd", 0) or 0
    change_24h = coin.get("change_24h_percent", 0) or 0

    volume_ratio = (volume / mcap) if mcap else 0
    volume_score = min(volume_ratio * 100, 40)
    momentum_score = min(change_24h / 2, 40)
    size_score = max(0, 20 - (mcap / profile["max_mcap"]) * 20)

    total = volume_score + momentum_score + size_score
    return round(min(total, 100), 1)


def screen_coins(coins: list[dict], profile: dict = None) -> list[dict]:
    """
    لیستی از کوین‌های نرمال‌شده رو با یک پروفایل مشخص فیلتر می‌کنه.
    اگه پروفایل داده نشه، پیش‌فرض میکروکپ استفاده می‌شه (سازگاری با کد قبلی).
    """
    profile = profile or MICRO_CAP_PROFILE
    results = []
    for coin in coins:
        ok, reasons = passes_basic_filters(coin, profile)
        if not ok:
            continue
        score = score_coin(coin, profile)
        results.append({**coin, "score": score, "reasons": reasons, "cap_tier": profile["name"]})

    results.sort(key=lambda c: c["score"], reverse=True)
    return results


def screen_coins_multi_tier(coins: list[dict]) -> list[dict]:
    """
    هر دو تیر (میکروکپ و میان‌کپ) رو روی همون لیست کوین‌ها اجرا می‌کنه و
    نتایج رو ترکیب می‌کنه (بدون تکراری، چون هر کوین فقط تو یکی از دو بازه
    مارکت‌کپ می‌گنجه). این تابع اصلی‌ایه که main.py باید صداش کنه.
    """
    micro_results = screen_coins(coins, MICRO_CAP_PROFILE)
    mid_results = screen_coins(coins, MID_CAP_PROFILE)
    combined = micro_results + mid_results
    combined.sort(key=lambda c: c["score"], reverse=True)
    return combined
