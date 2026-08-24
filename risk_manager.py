# -*- coding: utf-8 -*-
"""إدارة المخاطر: تحديد حجم الصفقة ووقف الخسارة/الربح اليومي.
يدعم تتبع عدد الصفقات الكلي (عبر كل الأزواج) بالإضافة لحدود عامة على الرصيد.
"""


class RiskManager:
    def __init__(self, stake_pct: float = 0.02, daily_loss_limit_pct: float = 0.10,
                 daily_profit_target_pct: float = 0.20, max_trades_per_day: int = 20):
        """
        stake_pct: نسبة الرصيد المستثمرة في كل صفقة (مثال: 0.02 = 2%)
        daily_loss_limit_pct: إيقاف البوت إذا خسر هذه النسبة من رأس المال اليوم
        daily_profit_target_pct: إيقاف البوت إذا حقق هذه النسبة ربح اليوم (اختياري)
        max_trades_per_day: حد أقصى لعدد الصفقات يومياً (عبر كل الأزواج مجتمعة)
        """
        self.stake_pct = stake_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.daily_profit_target_pct = daily_profit_target_pct
        self.max_trades_per_day = max_trades_per_day

        self.start_of_day_balance = None
        self.trades_today = 0
        self.trades_per_asset = {}  # لتتبع عدد الصفقات لكل زوج على حدة (اختياري للعرض)

    def reset_day(self, current_balance: float):
        self.start_of_day_balance = current_balance
        self.trades_today = 0
        self.trades_per_asset = {}

    def position_size(self, balance: float) -> float:
        size = round(balance * self.stake_pct, 2)
        return max(size, 1.0)  # حد أدنى افتراضي 1 وحدة عملة

    def can_trade(self, current_balance: float) -> tuple[bool, str]:
        if self.start_of_day_balance is None:
            self.reset_day(current_balance)

        if self.trades_today >= self.max_trades_per_day:
            return False, "تم الوصول للحد الأقصى لعدد الصفقات اليومية"

        pnl_pct = (current_balance - self.start_of_day_balance) / self.start_of_day_balance

        if pnl_pct <= -self.daily_loss_limit_pct:
            return False, "تم الوصول لحد الخسارة اليومي المسموح - تم إيقاف البوت"

        if pnl_pct >= self.daily_profit_target_pct:
            return False, "تم تحقيق هدف الربح اليومي - تم إيقاف البوت"

        return True, "OK"

    def register_trade(self, asset: str = None):
        self.trades_today += 1
        if asset:
            self.trades_per_asset[asset] = self.trades_per_asset.get(asset, 0) + 1
