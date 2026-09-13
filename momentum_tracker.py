"""
فاز ۲.۵ - Trend Consistency: با استفاده از اسنپ‌شات‌های تاریخی که خود سیستم
در اجراهای قبلی ذخیره کرده، بررسی می‌کنه که آیا رشد قیمت یک روند واقعیه
یا فقط یک اسپایک لحظه‌ای (که می‌تونه نشونه‌ی wash trading یا شروع dump باشه).

همچنین رصد نهنگ‌ها (Whale Monitoring): تغییر تمرکز هولدرها در طول زمان رو
دنبال می‌کنه - اگه یهو تمرکز چند کیف‌پول بزرگ زیاد بشه، ممکنه قبل از یک dump باشه.

نکته: این ماژول فقط از اجرای دوم به بعد داده‌ی معنادار می‌ده، چون به تاریخچه نیاز داره.
در اولین اجرا هر کوین امتیاز خنثی (نه مثبت نه منفی) می‌گیره.
"""

import database

MIN_SNAPSHOTS_FOR_TREND = 2
# اگه تمرکز هولدرها بیش از این مقدار در بین دو اسنپ‌شات متوالی بالا بره، هشدار می‌ده
WHALE_ACCUMULATION_ALERT_PERCENT = 10.0


def analyze_price_trend(coin_id: str) -> dict:
    """
    روند قیمت رو از تاریخچه‌ی ذخیره‌شده در دیتابیس بررسی می‌کنه.
    خروجی شامل یک امتیاز consistency (0-100) و توضیح هست.
    """
    history = database.get_price_history(coin_id, limit=10)

    if len(history) < MIN_SNAPSHOTS_FOR_TREND:
        return {
            "consistency_score": 50,  # خنثی - داده‌ی کافی نیست
            "note": "داده‌ی تاریخی کافی نیست (این کوین اولین یا دومین بار دیده می‌شه)",
            "is_single_spike": False,
        }

    # history از جدید به قدیم مرتبه؛ برعکسش می‌کنیم که زمانی بشه
    history = list(reversed(history))
    prices = [h["price_usd"] for h in history if h["price_usd"] is not None]

    if len(prices) < MIN_SNAPSHOTS_FOR_TREND:
        return {
            "consistency_score": 50,
            "note": "داده‌ی قیمتی کافی نیست",
            "is_single_spike": False,
        }

    # چند تا از بازه‌ها مثبت بودن؟
    positive_moves = 0
    total_moves = 0
    for i in range(1, len(prices)):
        if prices[i - 1] == 0:
            continue
        change = (prices[i] - prices[i - 1]) / prices[i - 1]
        total_moves += 1
        if change > 0:
            positive_moves += 1

    if total_moves == 0:
        return {"consistency_score": 50, "note": "داده‌ی کافی برای مقایسه نیست", "is_single_spike": False}

    consistency_ratio = positive_moves / total_moves

    # تشخیص "اسپایک تنها": اگه آخرین جهش خیلی بزرگ‌تر از بقیه‌ی جهش‌ها باشه
    # و روند قبلش تقریباً صاف بوده، احتمال pump مصنوعی / wash trading بیشتره
    is_single_spike = False
    if len(prices) >= 3 and prices[-2] != 0:
        last_move = abs((prices[-1] - prices[-2]) / prices[-2])
        earlier_moves = []
        for i in range(1, len(prices) - 1):
            if prices[i - 1] != 0:
                earlier_moves.append(abs((prices[i] - prices[i - 1]) / prices[i - 1]))
        avg_earlier = sum(earlier_moves) / len(earlier_moves) if earlier_moves else 0
        if avg_earlier > 0 and last_move > avg_earlier * 5:
            is_single_spike = True

    consistency_score = round(consistency_ratio * 100)
    note = f"{positive_moves}/{total_moves} بازه‌ی اخیر مثبت بودن"
    if is_single_spike:
        note += " - ⚠️ آخرین جهش غیرعادی بزرگ‌تر از روند قبلیه (احتمال اسپایک مصنوعی)"

    return {
        "consistency_score": consistency_score,
        "note": note,
        "is_single_spike": is_single_spike,
    }


def analyze_whale_activity(coin_id: str, current_concentration) -> dict:
    """
    تغییر تمرکز هولدرها رو نسبت به آخرین اسنپ‌شات ذخیره‌شده مقایسه می‌کنه.
    """
    history = database.get_holder_history(coin_id, limit=1)

    if not history or current_concentration is None:
        return {"whale_alert": False, "note": "داده‌ی تاریخی هولدر موجود نیست"}

    previous = history[0].get("holder_concentration_percent")
    if previous is None:
        return {"whale_alert": False, "note": "اسنپ‌شات قبلی تمرکز هولدر نداشت"}

    delta = current_concentration - previous
    if delta >= WHALE_ACCUMULATION_ALERT_PERCENT:
        return {
            "whale_alert": True,
            "note": f"تمرکز هولدرهای برتر {delta:.1f} درصد افزایش یافته - احتمال جمع‌آوری نهنگ قبل از dump",
        }

    return {"whale_alert": False, "note": f"تغییر تمرکز: {delta:+.1f}% (عادی)"}
