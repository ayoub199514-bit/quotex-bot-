# -*- coding: utf-8 -*-
"""
notifications.py — إرسال إشعارات فورية عبر تليجرام عند تنفيذ الصفقات.

طريقة الحصول على البيانات المطلوبة:
1. Bot Token: تكلم مع @BotFather على تليجرام → /newbot → اتبع التعليمات
   → يعطيك توكن شكله: 123456789:ABCdefGhIJKlmNoPQRstuVWXyz
2. Chat ID: تكلم مع @userinfobot على تليجرام → يعطيك رقم الـ ID الخاص بك
   (أو أضف البوت لمجموعة واستخدم ID المجموعة)
"""

import requests


class TelegramNotifier:
    def __init__(self, bot_token: str = "", chat_id: str = "", enabled: bool = False):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled and bool(bot_token) and bool(chat_id)
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send(self, message: str) -> bool:
        """يرسل رسالة نصية. يرجع True/False حسب النجاح، ولا يوقف البوت عند الفشل."""
        if not self.enabled:
            return False
        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                data={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            # لا نوقف البوت أبداً بسبب فشل إشعار
            return False

    def notify_trade(self, asset: str, direction: str, amount: float,
                      status: bool, balance: float = None):
        emoji = "🟢" if direction.upper() == "CALL" else "🔴"
        status_text = "✅ تم التنفيذ" if status else "❌ فشل التنفيذ"
        msg = (
            f"{emoji} <b>صفقة جديدة</b>\n"
            f"الأصل: <b>{asset}</b>\n"
            f"الاتجاه: <b>{direction}</b>\n"
            f"المبلغ: <b>{amount}</b>\n"
            f"الحالة: {status_text}"
        )
        if balance is not None:
            msg += f"\nالرصيد الحالي: <b>{balance}</b>"
        self.send(msg)

    def notify_bot_event(self, message: str):
        """للأحداث العامة: بدء تشغيل، إيقاف، وصول لحد الخسارة/الربح، إلخ."""
        self.send(f"ℹ️ {message}")
