# -*- coding: utf-8 -*-
"""
bot.py
======
الطبقة المسؤولة عن الاتصال بمنصة Quotex عبر مكتبة pyquotex (مشروع مفتوح
المصدر غير رسمي: https://github.com/cleitonleonel/pyquotex) وتنفيذ الصفقات.

يدعم هذا الإصدار:
- مراقبة عدة أزواج (أصول) في نفس الوقت، يختارها المستخدم من الواجهة.
- إشعارات تليجرام فورية عند كل صفقة وعند أحداث البوت الرئيسية.

تنبيه هام:
- Quotex لا توفر API رسمياً معلناً؛ pyquotex يحاكي تسجيل الدخول عبر
  الويب سوكيت الداخلي للمنصة. هذا قد يخالف شروط الاستخدام الخاصة
  بالمنصة ويعرّض الحساب للحظر أو التجميد. استخدمه على مسؤوليتك.
- التداول (خصوصاً الخيارات الثنائية) ينطوي على مخاطرة عالية بفقدان
  رأس المال. هذا الكود أداة تعليمية/برمجية وليس نصيحة استثمارية.
- ابدأ دائماً بحساب Demo قبل أي تفعيل لحساب حقيقي.
"""

import asyncio
import time
from datetime import datetime

import pandas as pd

from strategy import TripleConfluenceStrategy
from risk_manager import RiskManager
from notifications import TelegramNotifier

try:
    from pyquotex.stable_api import Quotex
except ImportError:
    Quotex = None  # سيتم التحقق من هذا عند التشغيل ورسالة تنبيه للمستخدم


class QuotexBot:
    def __init__(self, email: str, password: str, assets=None,
                 candle_period: int = 60, demo: bool = True,
                 stake_pct: float = 0.02, expiration: int = 60,
                 log_callback=None, telegram_token: str = "",
                 telegram_chat_id: str = "", telegram_enabled: bool = False):
        """
        email/password: بيانات حساب Quotex
        assets: قائمة الأصول المتداولة، مثال ['EURUSD_otc', 'GBPUSD_otc']
        candle_period: الفريم الزمني للشموع بالثواني (60 = دقيقة واحدة)
        demo: True لحساب تجريبي، False لحساب حقيقي
        stake_pct: نسبة الرصيد لكل صفقة
        expiration: مدة صلاحية صفقة الخيار الثنائي بالثواني
        log_callback: دالة تستقبل رسائل نصية لعرضها في واجهة المستخدم
        telegram_*: بيانات إشعارات تليجرام (اختياري)
        """
        if Quotex is None:
            raise ImportError(
                "مكتبة pyquotex غير مثبتة. ثبّتها عبر:\n"
                "pip install -U git+https://github.com/cleitonleonel/pyquotex.git"
            )

        self.email = email
        self.password = password
        self.assets = assets or ["EURUSD_otc"]
        self.candle_period = candle_period
        self.demo = demo
        self.expiration = expiration
        self.running = False

        self.client = Quotex(email=email, password=password)
        self.strategy = TripleConfluenceStrategy()
        self.risk = RiskManager(stake_pct=stake_pct)
        self.log = log_callback or (lambda msg: print(msg))
        self.notifier = TelegramNotifier(
            bot_token=telegram_token, chat_id=telegram_chat_id, enabled=telegram_enabled
        )
        self.history = []  # سجل الصفقات لعرضه في الواجهة
        self.last_signals = {}  # آخر إشارة/مؤشرات لكل أصل (للعرض في الواجهة)

    async def connect(self):
        check, reason = await self.client.connect()
        if not check:
            raise ConnectionError(f"فشل الاتصال بـ Quotex: {reason}")
        self.client.change_account("PRACTICE" if self.demo else "REAL")
        self._log(f"تم الاتصال بنجاح | الحساب: {'Demo' if self.demo else 'Real'}")

    def _log(self, msg: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log(f"[{stamp}] {msg}")

    async def fetch_candles_df(self, asset: str, count: int = 100) -> pd.DataFrame:
        end_from_time = time.time()
        candles = await self.client.get_candles(
            asset, end_from_time, count * self.candle_period, self.candle_period
        )
        df = pd.DataFrame(candles)
        return df

    async def get_balance(self) -> float:
        return await self.client.get_balance()

    async def place_trade(self, asset: str, direction: str, amount: float):
        # direction: 'call' أو 'put'
        status, buy_info = await self.client.buy(
            amount, asset, direction.lower(), self.expiration
        )
        self.history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "asset": asset,
            "direction": direction,
            "amount": amount,
            "status": "sent" if status else "failed",
        })
        return status, buy_info

    async def process_asset(self, asset: str, balance: float):
        """تنفيذ دورة تحليل وتنفيذ لأصل واحد."""
        df = await self.fetch_candles_df(asset)
        if df.empty or "close" not in df.columns:
            self._log(f"⚠️ [{asset}] تعذر جلب بيانات الشموع")
            return

        signal = self.strategy.generate_signal(df)
        snapshot = self.strategy.indicators_snapshot(df)
        self.last_signals[asset] = {**snapshot, "signal": signal}

        self._log(
            f"[{asset}] السعر: {snapshot['price']} | RSI: {snapshot['rsi']} | "
            f"MACD: {snapshot['macd']} / {snapshot['macd_signal']} | "
            f"الإشارة: {signal}"
        )

        if signal in ("CALL", "PUT"):
            size = self.risk.position_size(balance)
            status, info = await self.place_trade(asset, signal, size)
            self.risk.register_trade(asset=asset)
            if status:
                self._log(f"✅ [{asset}] تم إرسال صفقة {signal} بحجم {size}")
            else:
                self._log(f"❌ [{asset}] فشل إرسال الصفقة: {info}")
            self.notifier.notify_trade(
                asset=asset, direction=signal, amount=size,
                status=bool(status), balance=balance,
            )

    async def run_cycle(self):
        """تنفيذ دورة واحدة عبر كل الأصول المختارة."""
        balance = await self.get_balance()
        can_trade, reason = self.risk.can_trade(balance)
        if not can_trade:
            self._log(f"⛔ {reason} (الرصيد: {balance})")
            self.notifier.notify_bot_event(f"{reason} (الرصيد: {balance})")
            self.stop()
            return

        for asset in self.assets:
            try:
                await self.process_asset(asset, balance)
            except Exception as e:
                self._log(f"⚠️ [{asset}] خطأ أثناء المعالجة: {e}")

    async def run_forever(self, poll_seconds: int = 30):
        self.running = True
        await self.connect()
        balance = await self.get_balance()
        self.risk.reset_day(balance)
        assets_str = ", ".join(self.assets)
        self._log(f"🚀 بدء التشغيل | الرصيد الابتدائي: {balance} | الأصول: {assets_str}")
        self.notifier.notify_bot_event(
            f"بدء تشغيل البوت | الرصيد: {balance} | الأصول: {assets_str}"
        )

        while self.running:
            try:
                await self.run_cycle()
            except Exception as e:
                self._log(f"⚠️ خطأ في الدورة: {e}")
            await asyncio.sleep(poll_seconds)

    def stop(self):
        self.running = False
        self._log("⏹️ تم إيقاف البوت")
        self.notifier.notify_bot_event("تم إيقاف البوت")
