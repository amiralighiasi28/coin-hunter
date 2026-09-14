"""
لایه‌ی دیتابیس - ذخیره‌ی اسنپ‌شات‌های قیمتی کوین‌ها به صورت سری زمانی.
از SQLite استفاده می‌کنیم چون برای شروع ساده و بدون نیاز به سرور جدا هست.
بعداً اگر حجم داده زیاد شد می‌شه به PostgreSQL/TimescaleDB مهاجرت کرد
بدون این‌که بقیه‌ی سیستم رو تغییر بدیم (فقط این فایل عوض می‌شه).
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

import config


def init_db():
    """جدول‌های اولیه رو می‌سازه اگر وجود نداشته باشن."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coin_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                price_usd REAL,
                market_cap_usd REAL,
                volume_24h_usd REAL,
                change_24h_percent REAL,
                change_7d_percent REAL,
                fetched_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_coin_id_time
            ON coin_snapshots (coin_id, fetched_at)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                reason TEXT NOT NULL,
                score REAL,
                snapshot_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (snapshot_id) REFERENCES coin_snapshots (id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS holder_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id TEXT NOT NULL,
                holder_count INTEGER,
                holder_concentration_percent REAL,
                liquidity_locked_percent REAL,
                fetched_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_holder_coin_time
            ON holder_history (coin_id, fetched_at)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                coin_id TEXT PRIMARY KEY,
                symbol TEXT,
                name TEXT,
                chain_type TEXT,
                goplus_chain_id TEXT,
                contract_address TEXT,
                source TEXT,
                first_seen_at TEXT NOT NULL,
                last_checked_at TEXT NOT NULL,
                times_seen INTEGER DEFAULT 1,
                best_score_seen REAL DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_log (
                coin_id TEXT PRIMARY KEY,
                last_notified_at TEXT NOT NULL
            )
        """)
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def save_snapshot(coin: dict) -> int:
    """یک اسنپ‌شات قیمتی رو ذخیره می‌کنه و id ردیف رو برمی‌گردونه."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO coin_snapshots
            (coin_id, symbol, name, price_usd, market_cap_usd,
             volume_24h_usd, change_24h_percent, change_7d_percent, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            coin["coin_id"], coin["symbol"], coin["name"],
            coin.get("price_usd"), coin.get("market_cap_usd"),
            coin.get("volume_24h_usd"), coin.get("change_24h_percent"),
            coin.get("change_7d_percent"), now,
        ))
        conn.commit()
        return cur.lastrowid


def save_signal(coin_id: str, symbol: str, reason: str, score: float, snapshot_id: int):
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO signals (coin_id, symbol, reason, score, snapshot_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (coin_id, symbol, reason, score, snapshot_id, now))
        conn.commit()


def get_recent_signals(limit: int = 20):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM signals ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_price_history(coin_id: str, limit: int = 50):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM coin_snapshots
            WHERE coin_id = ?
            ORDER BY fetched_at DESC
            LIMIT ?
        """, (coin_id, limit)).fetchall()
        return [dict(r) for r in rows]


def save_holder_snapshot(coin_id: str, holder_count, concentration_percent, liquidity_locked_percent):
    """اسنپ‌شات از وضعیت هولدرها/نقدینگی ذخیره می‌کنه تا بشه روندش رو در طول زمان دید."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO holder_history
            (coin_id, holder_count, holder_concentration_percent, liquidity_locked_percent, fetched_at)
            VALUES (?, ?, ?, ?, ?)
        """, (coin_id, holder_count, concentration_percent, liquidity_locked_percent, now))
        conn.commit()


def get_holder_history(coin_id: str, limit: int = 10):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM holder_history
            WHERE coin_id = ?
            ORDER BY fetched_at DESC
            LIMIT ?
        """, (coin_id, limit)).fetchall()
        return [dict(r) for r in rows]


def upsert_watchlist(coin: dict, score: float):
    """
    فاز ۱-D: یک کاندیدا رو به واچ‌لیست اضافه می‌کنه یا اگه قبلاً بوده، به‌روزش می‌کنه.
    این باعث می‌شه حتی کوینی که این دور critera رو رد کرده، دفعات بعد دوباره
    (مستقیم با آدرس قراردادش، نه وابسته به این‌که تو لیست boosted باشه) چک بشه.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM watchlist WHERE coin_id = ?", (coin["coin_id"],)
        ).fetchone()

        if existing:
            new_best = max(existing["best_score_seen"] or 0, score)
            conn.execute("""
                UPDATE watchlist
                SET last_checked_at = ?, times_seen = times_seen + 1,
                    best_score_seen = ?, status = 'active'
                WHERE coin_id = ?
            """, (now, new_best, coin["coin_id"]))
        else:
            conn.execute("""
                INSERT INTO watchlist
                (coin_id, symbol, name, chain_type, goplus_chain_id, contract_address,
                 source, first_seen_at, last_checked_at, times_seen, best_score_seen, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 'active')
            """, (
                coin["coin_id"], coin.get("symbol"), coin.get("name"),
                coin.get("chain_type"), coin.get("goplus_chain_id"),
                coin.get("contract_address"), coin.get("source"),
                now, now, score,
            ))
        conn.commit()


def get_active_watchlist(max_age_days: int = 30):
    """کاندیداهای فعال واچ‌لیست رو برمی‌گردونه تا مستقیم با آدرس قراردادشون دوباره چک بشن."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM watchlist
            WHERE status = 'active' AND first_seen_at >= ?
        """, (cutoff,)).fetchall()
        return [dict(r) for r in rows]


def expire_old_watchlist_entries(max_age_days: int = 30):
    """کاندیداهایی که مدت زیادیه هیچ اتفاقی براشون نیفتاده رو غیرفعال می‌کنه تا سیستم متمرکز بمونه."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    with get_connection() as conn:
        conn.execute("""
            UPDATE watchlist SET status = 'expired'
            WHERE status = 'active' AND first_seen_at < ?
        """, (cutoff,))
        conn.commit()


def should_notify(coin_id: str, cooldown_hours: float) -> bool:
    """
    فاز ۴ - جلوگیری از اسپم: چک می‌کنه آیا این کوین در بازه‌ی cooldown اخیر
    (مثلاً ۶ ساعت) قبلاً نوتیفیکیشن گرفته یا نه. اگه گرفته، دوباره نمی‌فرستیم
    حتی اگه همچنان واجد شرایط باشه (وگرنه هر ۱۰ دقیقه دوباره پیام می‌ره).
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT last_notified_at FROM notification_log WHERE coin_id = ?",
            (coin_id,),
        ).fetchone()
        if row is None:
            return True
        last_notified = datetime.fromisoformat(row["last_notified_at"])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
        return last_notified < cutoff


def record_notification(coin_id: str):
    """بعد از ارسال موفق پیام، زمانش رو ثبت می‌کنه تا should_notify جلوی تکرار رو بگیره."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO notification_log (coin_id, last_notified_at)
            VALUES (?, ?)
            ON CONFLICT(coin_id) DO UPDATE SET last_notified_at = excluded.last_notified_at
        """, (coin_id, now))
        conn.commit()
        conn.commit()
