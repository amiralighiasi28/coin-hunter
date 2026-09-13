"""
تفسیر داده‌ی خام GoPlus و تبدیلش به فلگ‌های قابل‌فهم + یک امتیاز ریسک.
منطق: بعضی فلگ‌ها "بحرانی" هستن (یعنی به احتمال زیاد rug pull/honeypot ست)
و باعث حذف کامل کوین می‌شن. بقیه فقط امتیاز ریسک رو بالا می‌برن ولی حذف نمی‌کنن.

نکته: هیچ فیلتری ۱۰۰٪ تضمین‌کننده نیست. این فقط ریسک آماری رو کم می‌کنه،
نه این‌که rug pull رو غیرممکن کنه.
"""

CRITICAL_EVM_FLAGS = {
    "is_honeypot": "هانی‌پات شناسایی شد (نمی‌تونی بفروشی)",
    "cannot_sell_all": "امکان فروش کامل توکن وجود نداره",
    "hidden_owner": "مالک قرارداد مخفی شده (پرچم قرمز جدی)",
    "is_blacklisted": "قابلیت بلک‌لیست کردن آدرس‌ها وجود داره",
    "selfdestruct": "قرارداد قابلیت self-destruct داره",
}

WARNING_EVM_FLAGS = {
    "is_mintable": "توکن قابل mint نامحدوده (عرضه می‌تونه رقیق بشه)",
    "owner_change_balance": "مالک می‌تونه بالانس کاربران رو تغییر بده",
    "is_proxy": "قرارداد پروکسیه (منطق می‌تونه بعداً عوض بشه)",
    "slippage_modifiable": "مالک می‌تونه tax/slippage رو تغییر بده",
    "trading_cooperation_is_disable": "معامله ممکنه توسط مالک قابل غیرفعال شدن باشه",
}

MAX_SAFE_HOLDER_CONCENTRATION = 50.0  # درصد - بالاتر از این یعنی تمرکز خطرناک در چند کیف‌پول
MAX_SAFE_BUY_SELL_TAX = 15.0  # درصد


def _flag_is_true(raw: dict, key: str) -> bool:
    """GoPlus مقادیر بولین رو به صورت رشته '0'/'1' برمی‌گردونه."""
    val = raw.get(key)
    return str(val) == "1"


def _top_holder_concentration(raw: dict) -> float:
    """درصد مجموع توکن در دست ۱۰ holder برتر (به جز آدرس‌های سوختگی/قرارداد لیکوییدیتی)."""
    holders = raw.get("holders") or []
    total = 0.0
    count = 0
    for h in holders:
        if h.get("is_contract") == 1 or h.get("is_locked") == 1:
            continue
        try:
            total += float(h.get("percent", 0)) * 100
        except (TypeError, ValueError):
            continue
        count += 1
        if count >= 10:
            break
    return round(total, 1)


def _liquidity_lock_percent(raw: dict) -> tuple[float, bool]:
    """
    درصد نقدینگی قفل‌شده یا سوزونده‌شده رو از فیلد lp_holders محاسبه می‌کنه.
    خروجی: (درصد قفل‌شده, آیا اصلاً داده‌ی لیکوییدیتی موجوده)
    این مهم‌ترین سیگنال ضد rug-pull هست: اگه مالک نقدینگی رو قفل نکرده باشه،
    می‌تونه هر لحظه کل استخر رو خالی کنه و قیمت به صفر بره.
    """
    lp_holders = raw.get("lp_holders")
    if not lp_holders:
        return 0.0, False

    locked_percent = 0.0
    for holder in lp_holders:
        is_locked = str(holder.get("is_locked", 0)) == "1"
        # آدرس‌های سوختگی معمولاً تگ is_locked=1 هم می‌گیرن، ولی برای اطمینان
        # آدرس‌های شناخته‌شده‌ی burn رو هم صریح چک می‌کنیم
        address = (holder.get("address") or "").lower()
        is_burn = address.endswith("dead") or address == "0x0000000000000000000000000000000000000000"
        if is_locked or is_burn:
            try:
                locked_percent += float(holder.get("percent", 0)) * 100
            except (TypeError, ValueError):
                continue

    return round(locked_percent, 1), True


MIN_SAFE_LIQUIDITY_LOCKED_PERCENT = 50.0


def evaluate_evm_risk(raw: dict) -> dict:
    critical = []
    warnings = []

    for key, msg in CRITICAL_EVM_FLAGS.items():
        if _flag_is_true(raw, key):
            critical.append(msg)

    for key, msg in WARNING_EVM_FLAGS.items():
        if _flag_is_true(raw, key):
            warnings.append(msg)

    if not _flag_is_true(raw, "is_open_source"):
        warnings.append("سورس قرارداد باز نیست (نمی‌شه کد رو بررسی کرد)")

    concentration = _top_holder_concentration(raw)
    if concentration > MAX_SAFE_HOLDER_CONCENTRATION:
        warnings.append(f"تمرکز بالا در ۱۰ کیف‌پول برتر: {concentration}%")

    liquidity_locked, has_liquidity_data = _liquidity_lock_percent(raw)
    if has_liquidity_data and liquidity_locked < MIN_SAFE_LIQUIDITY_LOCKED_PERCENT:
        critical.append(
            f"نقدینگی قفل/سوزونده‌شده فقط {liquidity_locked}% - ریسک بالای rug pull"
        )
    elif not has_liquidity_data:
        warnings.append("داده‌ی قفل نقدینگی موجود نیست - نمی‌شه از این نظر مطمئن شد")

    try:
        holder_count = int(raw.get("holder_count", 0))
    except (TypeError, ValueError):
        holder_count = 0

    try:
        buy_tax = float(raw.get("buy_tax", 0)) * 100
        sell_tax = float(raw.get("sell_tax", 0)) * 100
    except (TypeError, ValueError):
        buy_tax = sell_tax = 0.0

    if buy_tax > MAX_SAFE_BUY_SELL_TAX or sell_tax > MAX_SAFE_BUY_SELL_TAX:
        warnings.append(f"تکس بالا: خرید {buy_tax:.0f}% / فروش {sell_tax:.0f}%")

    risk_score = min(100, len(critical) * 40 + len(warnings) * 10)

    return {
        "critical_flags": critical,
        "warning_flags": warnings,
        "holder_concentration_percent": concentration,
        "liquidity_locked_percent": liquidity_locked if has_liquidity_data else None,
        "holder_count": holder_count,
        "buy_tax_percent": round(buy_tax, 1),
        "sell_tax_percent": round(sell_tax, 1),
        "risk_score": risk_score,  # 0 = بدون پرچم قابل مشاهده, 100 = خیلی خطرناک
        "is_disqualified": len(critical) > 0,
    }


def evaluate_solana_risk(raw: dict) -> dict:
    critical = []
    warnings = []

    if str(raw.get("mintable", {}).get("status")) == "1":
        warnings.append("توکن قابل mint نامحدوده")
    if str(raw.get("freezable", {}).get("status")) == "1":
        critical.append("امکان فریز کردن اکانت‌ها وجود داره")
    if str(raw.get("closable", {}).get("status")) == "1":
        warnings.append("امکان بستن اکانت توکن وجود داره")

    concentration = _top_holder_concentration(raw)
    if concentration > MAX_SAFE_HOLDER_CONCENTRATION:
        warnings.append(f"تمرکز بالا در ۱۰ کیف‌پول برتر: {concentration}%")

    liquidity_locked, has_liquidity_data = _liquidity_lock_percent(raw)
    if has_liquidity_data and liquidity_locked < MIN_SAFE_LIQUIDITY_LOCKED_PERCENT:
        critical.append(
            f"نقدینگی قفل/سوزونده‌شده فقط {liquidity_locked}% - ریسک بالای rug pull"
        )
    elif not has_liquidity_data:
        warnings.append("داده‌ی قفل نقدینگی موجود نیست - نمی‌شه از این نظر مطمئن شد")

    try:
        holder_count = int(raw.get("holder_count", 0))
    except (TypeError, ValueError):
        holder_count = 0

    risk_score = min(100, len(critical) * 40 + len(warnings) * 10)

    return {
        "critical_flags": critical,
        "warning_flags": warnings,
        "holder_concentration_percent": concentration,
        "liquidity_locked_percent": liquidity_locked if has_liquidity_data else None,
        "holder_count": holder_count,
        "buy_tax_percent": 0.0,
        "sell_tax_percent": 0.0,
        "risk_score": risk_score,
        "is_disqualified": len(critical) > 0,
    }


def evaluate_risk(raw: dict, chain_type: str) -> dict:
    """نقطه‌ی ورود یکسان - بسته به نوع چین، تابع مناسب رو صدا می‌زنه."""
    if not raw:
        # داده‌ای برنگشت (قرارداد ناشناخته یا API قطع بود) -> ریسک نامشخص، محتاطانه رفتار کن
        return {
            "critical_flags": [],
            "warning_flags": ["داده‌ی امنیتی در دسترس نبود - با احتیاط بیشتری برخورد کن"],
            "holder_concentration_percent": None,
            "liquidity_locked_percent": None,
            "holder_count": None,
            "buy_tax_percent": None,
            "sell_tax_percent": None,
            "risk_score": 50,
            "is_disqualified": False,
        }
    if chain_type == "solana":
        return evaluate_solana_risk(raw)
    return evaluate_evm_risk(raw)


def combine_scores(momentum_score: float, risk_score: float) -> float:
    """
    امتیاز نهایی = امتیاز حرکت قیمتی، جریمه‌شده با امتیاز ریسک.
    هرچی ریسک بالاتر بره، امتیاز نهایی سریع‌تر افت می‌کنه.
    (این تابع برای سازگاری با کدهای قبلی نگه داشته شده؛ برای امتیاز نهایی کامل
    از combine_final_score که فاز ۲.۵ رو هم لحاظ می‌کنه استفاده کن.)
    """
    risk_penalty_factor = 1 - (risk_score / 100) * 0.8  # حداکثر ۸۰٪ کاهش
    return round(momentum_score * risk_penalty_factor, 1)


def combine_final_score(momentum_score: float, risk_score: float,
                         trend_info: dict, whale_info: dict,
                         wash_info: dict = None) -> float:
    """
    امتیاز نهایی کامل با احتساب فاز ۲.۵ (ثبات روند)، رصد نهنگ‌ها، و فاز ۲-C
    (تشخیص wash trading).
    ترتیب اعمال جریمه‌ها:
      ۱. جریمه‌ی ریسک قرارداد (تا ۸۰٪ کاهش)
      ۲. ضریب ثبات روند (اگه روند فقط یک اسپایک تنها باشه، شدیداً جریمه می‌شه)
      ۳. جریمه‌ی ثابت اگه نهنگ‌ها اخیراً در حال جمع‌آوری مشکوک بودن
      ۴. جریمه‌ی نسبی اگه الگوی معاملاتی مشکوک به wash trading باشه
    """
    score = combine_scores(momentum_score, risk_score)

    consistency = trend_info.get("consistency_score", 50)
    trend_factor = 0.7 + 0.3 * (consistency / 100)  # بین 0.7 و 1.0
    if trend_info.get("is_single_spike"):
        trend_factor *= 0.5  # جریمه‌ی سنگین برای اسپایک مشکوک
    score *= trend_factor

    if whale_info.get("whale_alert"):
        score -= 15

    if wash_info:
        wash_score = wash_info.get("wash_trading_score", 0)
        wash_factor = 1 - (wash_score / 100) * 0.6  # حداکثر ۶۰٪ کاهش
        score *= wash_factor

    return round(max(score, 0), 1)
