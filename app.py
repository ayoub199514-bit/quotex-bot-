# -*- coding: utf-8 -*-
"""
app.py — واجهة ويب (Streamlit) للتحكم في بوت Quotex متعدد الأصول
تشغيل: streamlit run app.py
"""

import asyncio
import threading

import streamlit as st

from bot import QuotexBot

st.set_page_config(page_title="Quotex Trading Bot", page_icon="📈", layout="centered")

if "logs" not in st.session_state:
    st.session_state.logs = []
if "bot" not in st.session_state:
    st.session_state.bot = None
if "thread" not in st.session_state:
    st.session_state.thread = None

AVAILABLE_ASSETS = [
    "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc",
    "USDCAD_otc", "USDCHF_otc", "NZDUSD_otc", "EURGBP_otc",
    "EURJPY_otc", "GBPJPY_otc",
]


def log_callback(msg: str):
    st.session_state.logs.append(msg)
    st.session_state.logs = st.session_state.logs[-300:]  # آخر 300 سطر فقط


def start_bot_thread(bot: QuotexBot, poll_seconds: int):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot.run_forever(poll_seconds=poll_seconds))
    except Exception as e:
        log_callback(f"❌ توقف البوت بسبب خطأ: {e}")


st.title("📈 بوت تداول Quotex")
st.warning(
    "⚠️ تنبيه: Quotex ليست لديها API رسمي، والاتصال يتم عبر مكتبة غير "
    "رسمية (pyquotex). هذا قد يخالف شروط استخدام المنصة، والتداول "
    "ينطوي على مخاطرة حقيقية بفقدان المال. ابدأ دائماً بحساب Demo، "
    "وهذا الكود لأغراض تعليمية وليس نصيحة استثمارية."
)

with st.sidebar:
    st.header("⚙️ إعدادات الحساب")
    email = st.text_input("البريد الإلكتروني (Quotex)")
    password = st.text_input("كلمة المرور", type="password")
    account_type = st.radio("نوع الحساب", ["تجريبي (Demo)", "حقيقي (Real)"])

    st.divider()
    st.header("💱 الأصول المتداولة")
    selected_assets = st.multiselect(
        "اختر الأزواج (يمكن اختيار أكثر من واحد)",
        options=AVAILABLE_ASSETS,
        default=["EURUSD_otc"],
    )
    custom_asset = st.text_input(
        "أضف زوج غير موجود بالقائمة (اختياري)", placeholder="مثال: EURTRY_otc"
    )

    st.divider()
    st.header("📊 إعدادات التداول")
    expiration = st.number_input("مدة الصفقة (ثانية)", min_value=30, value=60, step=30)
    stake_pct = st.slider("نسبة رأس المال لكل صفقة (%)", 1, 10, 2) / 100
    poll_seconds = st.number_input("فترة الفحص (ثانية)", min_value=10, value=30, step=5)

    st.divider()
    st.header("📩 إشعارات تليجرام (اختياري)")
    telegram_enabled = st.checkbox("تفعيل إشعارات تليجرام")
    telegram_token = st.text_input("Bot Token", type="password", disabled=not telegram_enabled)
    telegram_chat_id = st.text_input("Chat ID", disabled=not telegram_enabled)
    st.caption(
        "احصل على Token عبر @BotFather وعلى Chat ID عبر @userinfobot في تليجرام."
    )

    st.divider()
    col1, col2 = st.columns(2)
    start_clicked = col1.button("▶️ تشغيل", use_container_width=True)
    stop_clicked = col2.button("⏹️ إيقاف", use_container_width=True)

# دمج الأصول المختارة مع أي أصل مخصص
final_assets = list(selected_assets)
if custom_asset.strip():
    final_assets.append(custom_asset.strip())

if start_clicked:
    if not email or not password:
        st.error("الرجاء إدخال البريد الإلكتروني وكلمة المرور")
    elif not final_assets:
        st.error("الرجاء اختيار أصل واحد على الأقل")
    elif telegram_enabled and (not telegram_token or not telegram_chat_id):
        st.error("فعّلت إشعارات تليجرام لكن لم تُدخل Token أو Chat ID")
    elif st.session_state.thread and st.session_state.thread.is_alive():
        st.info("البوت يعمل بالفعل")
    else:
        demo = account_type.startswith("تجريبي")
        bot = QuotexBot(
            email=email, password=password, assets=final_assets,
            demo=demo, stake_pct=stake_pct, expiration=int(expiration),
            log_callback=log_callback,
            telegram_token=telegram_token, telegram_chat_id=telegram_chat_id,
            telegram_enabled=telegram_enabled,
        )
        st.session_state.bot = bot
        t = threading.Thread(
            target=start_bot_thread, args=(bot, int(poll_seconds)), daemon=True
        )
        st.session_state.thread = t
        t.start()
        st.success(f"تم بدء تشغيل البوت على {len(final_assets)} أصل/أصول")

if stop_clicked:
    if st.session_state.bot:
        st.session_state.bot.stop()
        st.success("تم إرسال أمر الإيقاف")
    else:
        st.info("لا يوجد بوت يعمل حالياً")

st.subheader("📋 السجل المباشر")
log_box = st.empty()
log_box.code("\n".join(st.session_state.logs[-50:]) or "لا توجد رسائل بعد...")

if st.session_state.bot and st.session_state.bot.last_signals:
    st.subheader("📡 آخر حالة لكل أصل")
    rows = []
    for asset, data in st.session_state.bot.last_signals.items():
        rows.append({
            "الأصل": asset,
            "السعر": data.get("price"),
            "RSI": data.get("rsi"),
            "الإشارة": data.get("signal"),
        })
    st.dataframe(rows, use_container_width=True)

if st.session_state.bot and st.session_state.bot.history:
    st.subheader("🧾 سجل الصفقات")
    st.dataframe(st.session_state.bot.history, use_container_width=True)

st.caption(
    "لتحديث السجل أثناء تشغيل البوت اضغط زر إعادة التحميل في المتصفح، "
    "أو أضف st_autorefresh لاحقاً لتحديث تلقائي."
)
