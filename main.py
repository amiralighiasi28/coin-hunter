"""
نقطه‌ی ورود اصلی سیستم شکار کوین.

جریان کامل (هر بار که اجرا می‌شه):
  فاز ۱   : دریافت کوین‌های میکروکپ از CoinGecko
  فاز ۱-B : ردیابی سریع چند-چین (سولانا/BSC/Base/Robinhood) با DexScreener
  فاز ۱-C : رادار فارغ‌التحصیلی Pump.fun (اختیاری، نیاز به Moralis API key)
  فاز ۱-D : رادار ترندهای CoinGecko (علاقه‌ی ناگهانی قبل از انعکاس در قیمت)
  فاز ۱-F : بازبینی واچ‌لیست پایدار (کوین‌هایی که دورهای قبل نزدیک بودن)
  فاز ۲   : فیلتر پایه (دو تیر: میکروکپ + میان‌کپ/موج دوم)
  فاز ۲.۵ : تحلیل ثبات روند از تاریخچه‌ی داخلی
  فاز ۲-C : تشخیص wash trading
  فاز ۲-D : برچسب‌گذاری روایت/ترند
  فاز ۳   : بررسی ریسک قرارداد (GoPlus)
  فاز ۳.۵ : قفل نقدینگی + رصد نهنگ (بخشی از فاز ۳ در risk_scorer)
  رده‌بندی نهایی (S/A/B/REJECTED) + به‌روزرسانی واچ‌لیست
  فاز ۴   : اعلان تلگرام + خروجی JSON برای ربات تعاملی Telegram Serverless

اجرا:  python main.py
"""

import sys
import time
import json
from datetime import datetime, timezone
import database
import config
from coingecko_client import CoinGeckoClient
from dexscreener_client import DexScreenerClient
from pumpfun_client import MoralisPumpFunClient
from narrative_tagger import tag_narrative
from screener import screen_coins_multi_tier
from chain_map import resolve_chain
from risk_client import GoPlusClient
from risk_scorer import evaluate_risk, combine_final_score
from momentum_tracker import analyze_price_trend, analyze_whale_activity
from wash_trading_detector import analyze_trading_pattern
from tier_classifier import classify
from telegram_notifier import TelegramNotifier

# فقط روی این تعداد کوین برتر (بعد از فاز ۲) فاز ۳ رو اجرا می‌کنیم چون هر کوین
# نیاز به یک یا چند درخواست اضافه به CoinGecko/GoPlus داره (محدودیت rate limit)
MAX_COINS_FOR_RISK_CHECK = 20
# فایلی که خلاصه‌ی نتایج توش ذخیره می‌شه تا ربات Telegram Serverless (جاوااسکریپت)
# بتونه از طریق fetch به یک URL عمومی (مثلاً raw.githubusercontent.com) بخونتش
JSON_EXPORT_PATH = "latest_signals.json"


def resolve_coin_chain(client: CoinGeckoClient, coin: dict):
    """
    آدرس قرارداد و چین یک کوین رو پیدا می‌کنه.
    اگه کوین از DexScreener/Pump.fun/واچ‌لیست اومده باشه، این اطلاعات از قبل
    موجوده (نیازی به فراخوانی اضافه نیست). فقط برای کوین‌های خام CoinGecko
    باید جزئیات رو جداگانه گرفت.
    خروجی: (chain_type, goplus_chain_id, address) یا None
    """
    if coin.get("chain_type") and coin.get("contract_address"):
        gp_chain_id = coin.get("goplus_chain_id") or coin["chain_type"]
        return coin["chain_type"], gp_chain_id, coin["contract_address"]

    detail = client.fetch_coin_detail(coin["coin_id"])
    platforms = detail.get("platforms", {})
    return resolve_chain(platforms)


def run_once():
    print("=" * 60)
    client = CoinGeckoClient()
    dex_client = DexScreenerClient()
    normalized = []

    # --- فاز ۱: میکروکپ CoinGecko ---
    print("فاز ۱: دریافت کوین‌های میکروکپ از CoinGecko ...")
    try:
        raw_coins = client.fetch_new_listings(pages=6)
        normalized.extend(client.normalize_coin(c) for c in raw_coins)
        print(f"تعداد {len(raw_coins)} کوین دریافت شد.")
    except Exception as e:
        print(f"خطا در دریافت داده از CoinGecko: {e}", file=sys.stderr)

    # --- فاز ۱-B: چند-چین با DexScreener ---
    print()
    print("فاز ۱-B: ردیابی سریع چند-چین (سولانا/BSC/Base/Robinhood) با DexScreener ...")
    try:
        multichain_candidates = dex_client.fetch_multichain_candidates()
        print(f"تعداد {len(multichain_candidates)} pool تازه با نقدینگی کافی پیدا شد.")
        normalized.extend(multichain_candidates)
    except Exception as e:
        print(f"خطا در دریافت داده از DexScreener: {e}", file=sys.stderr)

    # --- فاز ۱-C: رادار فارغ‌التحصیلی Pump.fun ---
    print()
    print("فاز ۱-C: رادار فارغ‌التحصیلی Pump.fun (Moralis) ...")
    pumpfun_client = MoralisPumpFunClient()
    if pumpfun_client.enabled:
        try:
            grad_candidates = pumpfun_client.get_recent_graduation_candidates()
            print(f"تعداد {len(grad_candidates)} توکن در بازه‌ی امن بعد از فارغ‌التحصیلی پیدا شد.")
            addresses = [c["address"] for c in grad_candidates]
            age_map = {c["address"]: c["age_hours"] for c in grad_candidates}
            pairs = dex_client.get_pairs_for_tokens(addresses)
            added = 0
            for pair in pairs:
                if pair.get("chainId") != "solana":
                    continue
                token_addr = (pair.get("baseToken") or {}).get("address")
                norm = dex_client.normalize_pair(pair, age_map.get(token_addr))
                norm["source"] = "pumpfun_graduate"
                normalized.append(norm)
                added += 1
            print(f"تعداد {added} تا با داده‌ی معاملاتی کامل به لیست اضافه شد.")
        except Exception as e:
            print(f"خطا در دریافت داده از Moralis/Pump.fun: {e}", file=sys.stderr)
    else:
        print("MORALIS_API_KEY ست نشده - این فاز رد می‌شه (اختیاریه، راهنما در config.py).")

    # --- فاز ۱-D: رادار ترندهای CoinGecko ---
    if config.ENABLE_TRENDING_RADAR:
        print()
        print("فاز ۱-D: رادار ترندهای CoinGecko (علاقه‌ی ناگهانی) ...")
        try:
            trending_items = client.fetch_trending()
            trending_ids = [item.get("id") for item in trending_items if item.get("id")]
            trending_markets = client.fetch_markets_by_ids(trending_ids)
            for raw in trending_markets:
                norm = client.normalize_coin(raw)
                norm["source"] = "trending"
                normalized.append(norm)
            print(f"تعداد {len(trending_markets)} کوین ترند با داده‌ی کامل اضافه شد.")
        except Exception as e:
            print(f"خطا در دریافت رادار ترند: {e}", file=sys.stderr)

    # --- فاز ۱-F: بازبینی واچ‌لیست پایدار ---
    print()
    print("فاز ۱-F: بازبینی واچ‌لیست پایدار ...")
    try:
        database.expire_old_watchlist_entries(config.WATCHLIST_MAX_AGE_DAYS)
        watchlist_entries = database.get_active_watchlist(config.WATCHLIST_MAX_AGE_DAYS)
        print(f"تعداد {len(watchlist_entries)} کاندیدای واچ‌لیست برای بازبینی پیدا شد.")

        watch_with_contract = [w for w in watchlist_entries if w.get("contract_address")]
        watch_coingecko_only = [w for w in watchlist_entries if not w.get("contract_address")]

        if watch_with_contract:
            addresses = [w["contract_address"] for w in watch_with_contract]
            pairs = dex_client.get_pairs_for_tokens(addresses)
            for pair in pairs:
                norm = dex_client.normalize_pair(pair, None)
                norm["source"] = f"watchlist_{norm.get('source', 'unknown')}"
                normalized.append(norm)

        if watch_coingecko_only:
            ids = [w["coin_id"] for w in watch_coingecko_only]
            markets = client.fetch_markets_by_ids(ids)
            for raw in markets:
                norm = client.normalize_coin(raw)
                norm["source"] = "watchlist_coingecko"
                normalized.append(norm)
    except Exception as e:
        print(f"خطا در بازبینی واچ‌لیست: {e}", file=sys.stderr)

    if not normalized:
        print("هیچ داده‌ای از هیچ منبعی دریافت نشد - اجرا متوقف می‌شه.")
        return

    print()
    print(f"جمع کل کاندیداهای این دور از همه‌ی منابع: {len(normalized)}")
    print("ذخیره در دیتابیس ...")
    snapshot_ids = {}
    for coin in normalized:
        try:
            snap_id = database.save_snapshot(coin)
            snapshot_ids[coin["coin_id"]] = snap_id
        except Exception as e:
            print(f"خطا در ذخیره‌ی {coin.get('coin_id')}: {e}", file=sys.stderr)

    # --- فاز ۲: فیلتر پایه (میکروکپ + میان‌کپ) ---
    print()
    print("فاز ۲: اجرای فیلتر پایه (میکروکپ + میان‌کپ/موج دوم) ...")
    signals = screen_coins_multi_tier(normalized)

    if not signals:
        print("هیچ کوینی از فیلترها رد نشد.")
        return

    print(f"{len(signals)} کوین از فیلتر اولیه رد شدن.")
    print()
    print("فاز ۳: بررسی ریسک قرارداد (GoPlus Security) روی کوین‌های برتر ...")

    goplus = GoPlusClient()
    final_results = []

    for coin in signals[:MAX_COINS_FOR_RISK_CHECK]:
        risk_info = {
            "critical_flags": [], "warning_flags": [],
            "risk_score": 50, "is_disqualified": False,
            "holder_concentration_percent": None,
            "liquidity_locked_percent": None, "holder_count": None,
        }
        try:
            resolved = resolve_coin_chain(client, coin)
            if resolved:
                chain_type, chain_id, address = resolved
                raw_risk = goplus.check_token(chain_type, chain_id, address)
                risk_info = evaluate_risk(raw_risk, chain_type)
            else:
                risk_info["warning_flags"].append(
                    "چین/آدرس قرارداد پیدا نشد (ممکنه کوین native یا لیست‌نشده باشه)"
                )
        except Exception as e:
            risk_info["warning_flags"].append(f"خطا در بررسی ریسک: {e}")
        time.sleep(1)  # احترام به rate limit هر دو API

        trend_info = analyze_price_trend(coin["coin_id"])
        whale_info = analyze_whale_activity(
            coin["coin_id"], risk_info.get("holder_concentration_percent")
        )
        wash_info = analyze_trading_pattern(coin)
        narrative_info = tag_narrative(coin)

        try:
            database.save_holder_snapshot(
                coin["coin_id"],
                risk_info.get("holder_count"),
                risk_info.get("holder_concentration_percent"),
                risk_info.get("liquidity_locked_percent"),
            )
        except Exception as e:
            print(f"خطا در ذخیره‌ی اسنپ‌شات هولدر: {e}", file=sys.stderr)

        final_score = combine_final_score(
            coin["score"], risk_info["risk_score"], trend_info, whale_info, wash_info
        )
        if narrative_info["has_narrative_boost"]:
            final_score = min(100, final_score + config.NARRATIVE_SCORE_BONUS)

        result_coin = {
            **coin, "risk": risk_info, "trend": trend_info,
            "whale": whale_info, "wash": wash_info, "narrative": narrative_info,
            "final_score": final_score,
        }
        result_coin["tier"] = classify(result_coin)
        final_results.append(result_coin)

        # فاز ۱-F: کاندیداهای امیدوارکننده (S/A/B، نه رد‌شده) وارد واچ‌لیست می‌شن
        # تا حتی اگه دور بعد دیگه تو boosted/trending نباشن، دوباره چک بشن
        if result_coin["tier"]["tier"] != "REJECTED":
            try:
                database.upsert_watchlist(result_coin, final_score)
            except Exception as e:
                print(f"خطا در به‌روزرسانی واچ‌لیست: {e}", file=sys.stderr)

    final_results.sort(key=lambda c: c["final_score"], reverse=True)

    print()
    print("=" * 60)
    print("نتیجه‌ی نهایی (رده‌بندی‌شده، از همه‌ی منابع ترکیب‌شده):\n")

    for coin in final_results:
        risk = coin["risk"]
        trend = coin["trend"]
        whale = coin["whale"]
        wash = coin["wash"]
        tier = coin["tier"]
        snap_id = snapshot_ids.get(coin["coin_id"])
        reason_text = " | ".join(coin["reasons"])

        print(f"  {tier['emoji']} [{tier['tier']}] [{coin['final_score']:5.1f}] {coin['symbol']:10s} - {tier['label']}")
        source_tag = coin.get("source", "coingecko")
        cap_tier = coin.get("cap_tier", "?")
        age_note = f" | سن: {coin['age_hours']}س" if coin.get("age_hours") is not None else ""
        print(f"      منبع: {source_tag} | تیر مارکت‌کپ: {cap_tier}{age_note}")
        print(f"      مارکت‌کپ: ${coin['market_cap_usd']:,.0f} | رشد ۲۴س: {coin['change_24h_percent']:.1f}%")
        print(f"      سیگنال حرکت: {reason_text}")
        print(f"      روند: {trend['note']}")
        print(f"      نهنگ‌ها: {whale['note']}")
        print(f"      معاملات: {wash['note']}")
        if coin["narrative"]["has_narrative_boost"]:
            print(f"      روایت: {coin['narrative']['note']}")
        if risk.get("liquidity_locked_percent") is not None:
            print(f"      نقدینگی قفل‌شده: {risk['liquidity_locked_percent']}%")
        if risk["critical_flags"]:
            print(f"      پرچم بحرانی: {' ، '.join(risk['critical_flags'])}")
        if risk["warning_flags"]:
            print(f"      هشدار: {' ، '.join(risk['warning_flags'])}")
        print(f"      توضیح رده: {tier['explanation']}")
        print()

        if snap_id and tier["tier"] != "REJECTED":
            full_reason = (
                f"{reason_text} || ریسک: {risk['risk_score']} || "
                f"روند: {trend['consistency_score']} || رده: {tier['tier']}"
            )
            database.save_signal(
                coin["coin_id"], coin["symbol"], full_reason, coin["final_score"], snap_id
            )

    print("⚠️  یادآوری: حتی کوین‌های رده‌ی S هم تضمینی نیستن.")
    print("این فقط ریسک آماری رو کم می‌کنه، نه صفر. با سرمایه‌ی مازاد و حجم کم وارد شو.")

    print()
    print("فاز ۴: ارسال اعلان تلگرام برای سیگنال‌های واجد شرایط ...")
    notifier = TelegramNotifier()
    qualifying = [c for c in final_results if c["tier"]["tier"] != "REJECTED"]
    notifier.notify_signals(qualifying)
    if notifier.enabled:
        sent_count = len([c for c in qualifying if c["final_score"] >= config.NOTIFY_MIN_SCORE])
        print(f"تعداد {sent_count} پیام تلگرام ارسال شد (آستانه‌ی امتیاز: {config.NOTIFY_MIN_SCORE}).")

    export_json_summary(final_results)


def export_json_summary(final_results: list):
    """
    یه خلاصه‌ی سبک از نتایج رو به فرمت JSON می‌نویسه. این فایل قراره تو ریپوی
    گیت‌هاب کامیت بشه (بخشی از GitHub Actions workflow) تا از طریق
    raw.githubusercontent.com عمومی در دسترس باشه. ربات تعاملی Telegram
    Serverless (جاوااسکریپت) با fetch همین آدرس رو می‌خونه و به دستورات
    /status و /watchlist کاربر جواب می‌ده - بدون نیاز به سرور یا دیتابیس مشترک.
    """
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(final_results),
        "signals": [
            {
                "symbol": c["symbol"],
                "name": c.get("name"),
                "tier": c["tier"]["tier"],
                "tier_label": c["tier"]["label"],
                "final_score": c["final_score"],
                "market_cap_usd": c.get("market_cap_usd"),
                "change_24h_percent": c.get("change_24h_percent"),
                "source": c.get("source", "coingecko"),
                "chain_type": c.get("chain_type"),
                "contract_address": c.get("contract_address"),
                "coingecko_url": f"https://www.coingecko.com/en/coins/{c['coin_id']}"
                    if not c.get("contract_address") else None,
            }
            for c in final_results if c["tier"]["tier"] != "REJECTED"
        ],
    }
    try:
        with open(JSON_EXPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"خلاصه‌ی JSON در {JSON_EXPORT_PATH} ذخیره شد ({len(summary['signals'])} سیگنال).")
    except Exception as e:
        print(f"خطا در نوشتن خروجی JSON: {e}", file=sys.stderr)


if __name__ == "__main__":
    database.init_db()
    run_once()
