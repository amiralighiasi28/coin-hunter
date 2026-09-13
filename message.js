// handlers/message.js
//
// دستورات پشتیبانی‌شده:
//   /start   - معرفی ربات
//   /status  - نمایش خلاصه‌ی آخرین اسکن (رده S/A/B)
//   /top     - نمایش فقط کوین‌های رده‌ی S (بهترین کاندیداها)
//
// این handler هیچ داده‌ای خودش تولید نمی‌کنه - فقط خروجی JSON سیستم پایتون
// (که روی GitHub Actions هر چند دقیقه اجرا می‌شه) رو می‌خونه و فرمت می‌کنه.

import { api } from 'sdk';
import { fetchLatestSignals, formatSignalsList } from 'lib/signals';

export default async function (message) {
  const chatId = message.chat.id;
  const text = (message.text || '').trim();

  if (text === '/start') {
    await api.sendMessage({
      chat_id: chatId,
      text:
        '👋 به ربات شکار کوین خوش اومدی.\n\n' +
        'دستورات:\n' +
        '/status — خلاصه‌ی کامل آخرین اسکن\n' +
        '/top — فقط کوین‌های رده‌ی S (بهترین کاندیداها)\n\n' +
        '⚠️ این ربات فقط خروجی یک سیستم فیلتر آماریه، نه توصیه‌ی مالی.',
    });
    return;
  }

  if (text === '/status' || text === '/top') {
    try {
      const data = await fetchLatestSignals();
      if (text === '/top') {
        data.signals = (data.signals || []).filter((s) => s.tier === 'S');
      }
      const reply = formatSignalsList(data, text === '/top' ? 20 : 10);
      await api.sendMessage({ chat_id: chatId, text: reply });
    } catch (err) {
      console.error(err);
      await api.sendMessage({
        chat_id: chatId,
        text: '❌ نتونستم آخرین داده رو بگیرم. چند دقیقه‌ی دیگه دوباره امتحان کن.',
      });
    }
    return;
  }

  // هر پیام دیگه‌ای -> راهنمای مختصر
  await api.sendMessage({
    chat_id: chatId,
    text: 'دستور نامشخصه. از /status یا /top استفاده کن.',
  });
}
