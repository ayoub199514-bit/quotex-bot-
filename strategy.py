# -*- coding: utf-8 -*-
"""
استراتيجية التداول: تلاقي ثلاثي (Triple Confluence)
=====================================================
تعتمد على 3 مؤشرات فنية مجتمعة لتقليل الإشارات الخاطئة:
  1. RSI (14)          -> تحديد التشبع الشرائي/البيعي
  2. MACD (12,26,9)     -> تأكيد اتجاه الزخم عبر التقاطع
  3. Bollinger Bands(20)-> تأكيد أن السعر عند حافة القناة السعرية

قاعدة الإشارة:
  CALL (شراء/صعود) عندما:
     - RSI < 30 (تشبع بيعي)
     - تقاطع MACD صاعد (MACD يعبر فوق خط الإشارة)
     - السعر عند/تحت الحد السفلي لبولينجر

  PUT (بيع/هبوط) عندما:
     - RSI > 70 (تشبع شرائي)
     - تقاطع MACD هابط (MACD يعبر تحت خط الإشارة)
     - السعر عند/فوق الحد العلوي لبولينجر

  غير ذلك -> HOLD (لا تداول)

ملاحظة: هذه استراتيجية مبدئية بغرض التوضيح والتعلّم، وليست توصية
استثمارية. عدّلها واختبرها جيداً (Backtesting + Demo) قبل استخدامها
على حساب حقيقي.
"""

import pandas as pd
import numpy as np


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def compute_bollinger(series: pd.Series, period=20, std_mult=2):
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return upper, mid, lower


class TripleConfluenceStrategy:
    """استراتيجية جاهزة للاستخدام مع البوت."""

    def __init__(self, rsi_period=14, rsi_oversold=30, rsi_overbought=70,
                 macd_fast=12, macd_slow=26, macd_signal=9,
                 bb_period=20, bb_std=2):
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.bb_std = bb_std

    def generate_signal(self, df: pd.DataFrame) -> str:
        """
        df يجب أن يحتوي على عمود 'close' على الأقل (مرتب زمنياً تصاعدياً).
        يرجع: 'CALL' أو 'PUT' أو 'HOLD'
        """
        if df is None or len(df) < max(self.bb_period, self.macd_slow) + 5:
            return "HOLD"

        close = df["close"]

        rsi = compute_rsi(close, self.rsi_period)
        macd_line, signal_line = compute_macd(
            close, self.macd_fast, self.macd_slow, self.macd_signal
        )
        upper, mid, lower = compute_bollinger(close, self.bb_period, self.bb_std)

        last_rsi = rsi.iloc[-1]
        last_price = close.iloc[-1]
        last_upper, last_lower = upper.iloc[-1], lower.iloc[-1]

        macd_cross_up = (
            macd_line.iloc[-2] <= signal_line.iloc[-2]
            and macd_line.iloc[-1] > signal_line.iloc[-1]
        )
        macd_cross_down = (
            macd_line.iloc[-2] >= signal_line.iloc[-2]
            and macd_line.iloc[-1] < signal_line.iloc[-1]
        )

        if last_rsi < self.rsi_oversold and macd_cross_up and last_price <= last_lower:
            return "CALL"

        if last_rsi > self.rsi_overbought and macd_cross_down and last_price >= last_upper:
            return "PUT"

        return "HOLD"

    def indicators_snapshot(self, df: pd.DataFrame) -> dict:
        """لإظهار قيم المؤشرات الحالية في واجهة الويب."""
        close = df["close"]
        rsi = compute_rsi(close, self.rsi_period)
        macd_line, signal_line = compute_macd(
            close, self.macd_fast, self.macd_slow, self.macd_signal
        )
        upper, mid, lower = compute_bollinger(close, self.bb_period, self.bb_std)
        return {
            "price": round(close.iloc[-1], 5),
            "rsi": round(rsi.iloc[-1], 2),
            "macd": round(macd_line.iloc[-1], 5),
            "macd_signal": round(signal_line.iloc[-1], 5),
            "bb_upper": round(upper.iloc[-1], 5),
            "bb_mid": round(mid.iloc[-1], 5),
            "bb_lower": round(lower.iloc[-1], 5),
        }
