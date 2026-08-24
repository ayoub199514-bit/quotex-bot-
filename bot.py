# -*- coding: utf-8 -*-
"""
bot.py
======
الطبقة المسؤولة عن الاتصال بمنصة Quotex عبر مكتبة pyquotex (مشروع مفتوح
المصدر غير رسمي: https://github.com/cleitonleonel/pyquotex) وتنفيذ الصفقات.

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

try:
    from pyquotex.stable_api import Quotex
except ImportError:
    Quotex = None  # سيتم التحقق من هذا عند التشغيل ورسالة تنبيه للمستخدم


class QuotexBot:
    def __init__(self, email: str, password: str, asset: str = "EURUSD",
                 candle_period: int = 60, demo: bool = True,
                 stake_pct: float = 0.02, expiration: int = 60,
                 log_callback=None):
        """
        email/password: بيانات حساب Quotex
        asset: الأصل المتداول، مثال 'EURUSD' أو 'EURUSD_otc'
        candle_period: الفريم الزمني للشموع بالثواني (60 = دقيقة واحدة)
        demo: True لحساب تجريبي، False لحساب حقيقي
        stake_pct: نسبة الرصيد لكل صفقة
        expiration: مدة صلاحية صفقة الخيار الثنائي بالثواني
        log_callback: دالة تستقبل رسائل نصية لعرضها في واجهة المستخدم
        """
        if Quotex is None:
            raise ImportError(
                "مكتبة pyquotex غير مثبتة. ثبّتها عبر:\n"
                "pip install -U git+https://github.com/cleitonleonel/pyquotex.git"
            )

        self.email = email
        self.password = password
        self.asset = asset
        self.candle_period = candle_period
        self.demo = demo
        self.expiration = expiration
        self.running = False

        self.client = Quotex(email=email, password=password)
        self.strategy = TripleConfluenceStrategy()
        self.risk = RiskManager(stake_pct=stake_pct)
        self.log = log_callback or (lambda msg: print(msg))
        self.history = []  # سجل الصفقات لعرضه في الواجهة

    async def connect(self):
        check, reason = await self.client.connect()
        if not check:
            raise ConnectionError(f"فشل الاتصال بـ Quotex: {reason}")
        self.client.change_account("PRACTICE" if self.demo else "REAL")
        self._log(f"تم الاتصال بنجاح | الحساب: {'Demo' if self.demo else 'Real'}")

    def _log(self, msg: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log(f"[{stamp}] {msg}")

    async def fetch_candles_df(self, count: int = 100) -> pd.DataFrame:
        end_from_time = time.time()
        candles = await self.client.get_candles(
            self.asset, end_from_time, count * self.candle_period, self.candle_period
        )
        df = pd.DataFrame(candles)
        df.rename(columns={"close": "close", "open": "open",
                            "high": "high", "low": "low"}, inplace=True)
        return df

    async def get_balance(self) -> float:
        return await self.client.get_balance()

    async def place_trade(self, direction: str, amount: float):
        # direction: 'call' أو 'put'
        status, buy_info = await self.client.buy(
            amount, self.asset, direction.lower(), self.expiration
        )
        self.history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "asset": self.asset,
            "direction": direction,
            "amount": amount,
            "status": "sent" if status else "failed",
        })
        return status, buy_info

    async def run_cycle(self):
        """تنفيذ دورة واحدة: جلب بيانات -> تحليل -> قرار -> (تنفيذ إن وجدت إشارة)."""
        balance = await self.get_balance()
        can_trade, reason = self.risk.can_trade(balance)
        if not can_trade:
            self._log(f"⛔ {reason} (الرصيد: {balance})")
            return

        df = await self.fetch_candles_df()
        if df.empty or "close" not in df.columns:
            self._log("⚠️ تعذر جلب بيانات الشموع")
            return

        signal = self.strategy.generate_signal(df)
        snapshot = self.strategy.indicators_snapshot(df)
        self._log(
            f"السعر: {snapshot['price']} | RSI: {snapshot['rsi']} | "
            f"MACD: {snapshot['macd']} / {snapshot['macd_signal']} | "
            f"الإشارة: {signal}"
        )

        if signal in ("CALL", "PUT"):
            size = self.risk.position_size(balance)
            status, info = await self.place_trade(signal, size)
            self.risk.register_trade()
            if status:
                self._log(f"✅ تم إرسال صفقة {signal} بحجم {size}")
            else:
                self._log(f"❌ فشل إرسال الصفقة: {info}")

    async def run_forever(self, poll_seconds: int = 30):
        self.running = True
        await self.connect()
        balance = await self.get_balance()
        self.risk.reset_day(balance)
        self._log(f"🚀 بدء التشغيل | الرصيد الابتدائي: {balance}")

        while self.running:
            try:
                await self.run_cycle()
            except Exception as e:
                self._log(f"⚠️ خطأ في الدورة: {e}")
            await asyncio.sleep(poll_seconds)

    def stop(self):
        self.running = False
        self._log("⏹️ تم إيقاف البوت")
