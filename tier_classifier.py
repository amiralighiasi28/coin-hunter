"""
سیستم رده‌بندی نهایی - به‌جای یک لیست خام از امتیازها، کوین‌ها رو به
رده‌های واضح تقسیم می‌کنه تا سریع بشه فهمید کدوم واقعاً ارزش توجه داره.

فلسفه‌ی رده‌بندی:
  🟢 S-Tier : بهترین ترکیب - ریسک قرارداد پایین، نقدینگی قفل، روند سالم،
              بدون هشدار نهنگ/wash trading. این‌ها کاندیدای اصلی هستن.
  🟡 A-Tier : سیگنال قویه ولی حداقل یک هشدار (نه بحرانی) داره - نیاز به
              بررسی دستی بیشتر قبل از هر تصمیمی.
  🟠 B-Tier : "بلیط بخت‌آزمایی" - مومنتوم بالا ولی چند تا پرچم هشدار همزمان.
              پتانسیل رشد بالا، ولی احتمال rug/dump هم واقعی و بالاست.
  🔴 رد شد  : پرچم بحرانی داره (هانی‌پات، نقدینگی قفل‌نشده، و ...) - از
              سیستم به‌طور کامل حذف می‌شه، حتی اگه امتیاز مومنتومش عالی باشه.
"""


def classify(coin: dict) -> dict:
    """
    ورودی: dict نهایی کوین شامل risk, trend, whale, wash (اختیاری), final_score.
    خروجی: dict شامل tier (متن), emoji, و توضیح کوتاه.
    """
    risk = coin.get("risk", {})
    trend = coin.get("trend", {})
    whale = coin.get("whale", {})
    wash = coin.get("wash", {}) or {}
    final_score = coin.get("final_score", 0)

    if risk.get("is_disqualified"):
        return {
            "tier": "REJECTED",
            "emoji": "🔴",
            "label": "رد شد",
            "explanation": "حداقل یک پرچم بحرانی در قرارداد پیدا شد",
        }

    warning_count = len(risk.get("warning_flags", []))
    has_single_spike = bool(trend.get("is_single_spike"))
    has_whale_alert = bool(whale.get("whale_alert"))
    has_wash_flag = wash.get("wash_trading_score", 0) >= 40

    red_flags = sum([warning_count > 0, has_single_spike, has_whale_alert, has_wash_flag])

    if final_score >= 65 and red_flags == 0:
        return {
            "tier": "S",
            "emoji": "🟢",
            "label": "بهترین کاندیدا",
            "explanation": "ریسک پایین، روند سالم، بدون هشدار نهنگ/wash trading",
        }

    if final_score >= 45 and red_flags <= 1:
        return {
            "tier": "A",
            "emoji": "🟡",
            "label": "سیگنال قوی - نیاز به بررسی دستی",
            "explanation": f"{red_flags} هشدار غیربحرانی وجود داره، قبل از تصمیم بررسی کن",
        }

    return {
        "tier": "B",
        "emoji": "🟠",
        "label": "بلیط بخت‌آزمایی (ریسک بالا)",
        "explanation": f"{red_flags} هشدار همزمان - پتانسیل بالا ولی احتمال شکست هم بالاست",
    }
