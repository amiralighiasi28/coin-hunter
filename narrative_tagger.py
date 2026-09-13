"""
فاز ۲-D - برچسب‌گذاری روایت/ترند (Narrative Tagging).

مشاهده‌ای که این فاز رو به وجود آورد: کوین‌هایی که اسمشون رو از برندها یا
ترندهای وایرال روز می‌گیرن (مثل ROBINHOOD، یا میم‌های وایرال تیک‌تاک مثل
"Tralalero Tralala" و "GLORP") به‌خاطر شناخته‌شدن سریع، توجه و FOMO بیشتری
جذب می‌کنن و مستعد پامپ سریع‌تری هستن نسبت به یه اسم کاملاً ناشناس.

این ماژول اسم/نماد کوین رو با لیست کلیدواژه‌ی قابل‌تنظیم در config.py مقایسه می‌کنه.

⚠️ نکته‌ی مهم: این سیگنال ضعیفیه و فقط باید یه امتیاز کوچیک اضافه (بونوس) بده،
نه یه فیلتر سخت‌گیرانه - چون هر کسی می‌تونه اسم یه برند رو رو کوینش بذاره
بدون این‌که واقعاً پتانسیل رشد داشته باشه. این لیست رو باید مرتب خودت
به‌روز نگه داری (هر وقت یه ترند جدید مثل ROBINHOOD دیدی، کلیدواژه‌ش رو اضافه کن).
"""

import config


def tag_narrative(coin: dict) -> dict:
    """
    اسم و نماد کوین رو با TRENDING_KEYWORDS مقایسه می‌کنه.
    خروجی: dict شامل کلیدواژه‌های منطبق و یک توضیح کوتاه.
    """
    name = (coin.get("name") or "").lower()
    symbol = (coin.get("symbol") or "").lower()

    matched = [
        kw for kw in config.TRENDING_KEYWORDS
        if kw.lower() in name or kw.lower() in symbol
    ]

    return {
        "matched_keywords": matched,
        "has_narrative_boost": len(matched) > 0,
        "note": (
            f"🔥 اسم منطبق با ترند فعلی: {', '.join(matched)}"
            if matched else
            "بدون تطابق با لیست ترندهای فعلی (config.TRENDING_KEYWORDS)"
        ),
    }
