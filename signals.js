// lib/signals.js
//
// این ماژول خلاصه‌ی سیگنال‌های تولیدشده توسط سیستم پایتون (که روی GitHub
// Actions اجرا می‌شه) رو از یک URL عمومی می‌خونه. پل ارتباطی بین دو سیستم
// (پایتون + این ربات جاوااسکریپتی) همین فایل JSON عمومی است - نه دیتابیس
// مشترک، نه سرور مشترک. کاملاً رایگان و بدون زیرساخت اضافه.
//
// ⚠️ قبل از استفاده، SIGNALS_URL رو با آدرس raw.githubusercontent.com ریپوی
// خودت جایگزین کن، مثلاً:
// https://raw.githubusercontent.com/USERNAME/REPO/main/latest_signals.json

import { fetch } from 'sdk';

const SIGNALS_URL = 'https://raw.githubusercontent.com/USERNAME/REPO/main/latest_signals.json';

const TIER_EMOJI = { S: '🟢', A: '🟡', B: '🟠' };

export async function fetchLatestSignals() {
  const res = await fetch(SIGNALS_URL, { method: 'GET' });
  if (!res.ok) {
    throw new Error(`نتونستم خلاصه‌ی سیگنال‌ها رو بگیرم (وضعیت ${res.status})`);
  }
  return res.json();
}

export function formatSignalsList(data, limit = 10) {
  if (!data || !data.signals || data.signals.length === 0) {
    return 'در حال حاضر هیچ سیگنال فعالی ثبت نشده.';
  }

  const lines = [
    `📊 آخرین اسکن: ${formatRelativeTime(data.generated_at)}`,
    `تعداد کل سیگنال‌های فعال: ${data.count}`,
    '',
  ];

  const top = data.signals.slice(0, limit);
  for (const s of top) {
    const emoji = TIER_EMOJI[s.tier] || '⚪';
    lines.push(`${emoji} [${s.tier}] ${s.symbol} — امتیاز ${s.final_score}`);
    lines.push(`   مارکت‌کپ: $${formatNumber(s.market_cap_usd)} | رشد ۲۴س: ${s.change_24h_percent?.toFixed(1)}%`);
    lines.push(`   منبع: ${s.source}`);
    lines.push('');
  }

  lines.push('⚠️ این توصیه‌ی خرید نیست، فقط خروجی فیلترهای آماری سیستم است.');
  return lines.join('\n');
}

function formatNumber(n) {
  if (n == null) return '?';
  return Math.round(n).toLocaleString('en-US');
}

function formatRelativeTime(isoString) {
  if (!isoString) return 'نامشخص';
  const then = new Date(isoString).getTime();
  const now = Date.now();
  const minutes = Math.round((now - then) / 60000);
  if (minutes < 1) return 'همین الان';
  if (minutes < 60) return `${minutes} دقیقه پیش`;
  const hours = Math.round(minutes / 60);
  return `${hours} ساعت پیش`;
}
