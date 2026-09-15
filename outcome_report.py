"""
گزارش رصد نتیجه - این اسکریپت رو روز دهم (یا هر وقت خواستی وضعیت رو ببینی)
جداگانه اجرا کن تا خلاصه‌ی کاملی از عملکرد واقعی سیستم بگیری:
چند تا سیگنال داده شده، چندتاشون به ۱۰۰۰%+ رسیدن، و لیست کامل برای بررسی.

اجرا:  python outcome_report.py
"""

import database
import config


def print_report():
    database.init_db()
    stats = database.get_tracking_stats()

    print("=" * 60)
    print("گزارش رصد نتیجه‌ی سیگنال‌ها")
    print("=" * 60)
    print(f"کل سیگنال‌های ثبت‌شده: {stats['total_signals']}")
    print(f"رسیده به هدف ({config.OUTCOME_HIT_MULTIPLIER}x / +{(config.OUTCOME_HIT_MULTIPLIER-1)*100:.0f}%): {stats['hit_count']}")
    print(f"نرخ موفقیت: {stats['hit_rate_percent']}%")
    print(f"هنوز در حال رصد: {stats['still_tracking_count']}")
    print(f"منقضی‌شده بدون رسیدن به هدف: {stats['expired_without_hit_count']}")
    print()

    if stats["hits"]:
        print("--- سیگنال‌هایی که به هدف رسیدن (مرتب بر اساس بیشترین رشد) ---")
        for h in stats["hits"]:
            multiplier = h["peak_multiplier"] or 0
            growth = (multiplier - 1) * 100
            print(f"  #{h['symbol']:10s} رشد اوج: {growth:8.0f}% | "
                  f"سیگنال: {h['signal_at'][:10]} | رده‌ی سیگنال: {h['signal_tier']} | "
                  f"امتیاز سیگنال: {h['signal_final_score']}")
        print()

    print("--- همه‌ی سیگنال‌ها (برای بررسی کامل) ---")
    all_sorted = sorted(stats["all"], key=lambda r: r["peak_multiplier"] or 0, reverse=True)
    for r in all_sorted:
        multiplier = r["peak_multiplier"] or 1.0
        growth = (multiplier - 1) * 100
        hit_mark = "🎯" if r["hit_target"] else "  "
        status = r["status"]
        print(f"  {hit_mark} #{r['symbol']:10s} اوج: {growth:8.0f}% | وضعیت: {status:10s} | "
              f"رده‌ی سیگنال: {r['signal_tier']} | تاریخ: {r['signal_at'][:10]}")

    print()
    print("نکته: 'اوج' یعنی بیشترین رشدی که این کوین از لحظه‌ی سیگنال تا الان داشته،")
    print("نه لزوماً قیمت همین الانش (ممکنه بعد از اوج ریخته باشه).")


if __name__ == "__main__":
    print_report()
