# -*- coding: utf-8 -*-
"""
app.py — واجهة ويب بسيطة (Streamlit) للتحكم في بوت Quotex
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


def log_callback(msg: str):
    st.session_state.logs.append(msg)
    st.session_state.logs = st.session_state.logs[-200:]  # آخر 200 سطر فقط


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
    st.header("⚙️ الإعدادات")
    email = st.text_input("البريد الإلكتروني (Quotex)")
    password = st.text_input("كلمة المرور", type="password")
    account_type = st.radio("نوع الحساب", ["تجريبي (Demo)", "حقيقي (Real)"])
    asset = st.text_input("الأصل المتداول", value="EURUSD_otc")
    expiration = st.number_input("مدة الصفقة (ثانية)", min_value=30, value=60, step=30)
    stake_pct = st.slider("نسبة رأس المال لكل صفقة (%)", 1, 10, 2) / 100
    poll_seconds = st.number_input("فترة الفحص (ثانية)", min_value=10, value=30, step=5)

    st.divider()
    col1, col2 = st.columns(2)
    start_clicked = col1.button("▶️ تشغيل", use_container_width=True)
    stop_clicked = col2.button("⏹️ إيقاف", use_container_width=True)

if start_clicked:
    if not email or not password:
        st.error("الرجاء إدخال البريد الإلكتروني وكلمة المرور")
    elif st.session_state.thread and st.session_state.thread.is_alive():
        st.info("البوت يعمل بالفعل")
    else:
        demo = account_type.startswith("تجريبي")
        bot = QuotexBot(
            email=email, password=password, asset=asset,
            demo=demo, stake_pct=stake_pct, expiration=int(expiration),
            log_callback=log_callback,
        )
        st.session_state.bot = bot
        t = threading.Thread(
            target=start_bot_thread, args=(bot, int(poll_seconds)), daemon=True
        )
        st.session_state.thread = t
        t.start()
        st.success("تم بدء تشغيل البوت")

if stop_clicked:
    if st.session_state.bot:
        st.session_state.bot.stop()
        st.success("تم إرسال أمر الإيقاف")
    else:
        st.info("لا يوجد بوت يعمل حالياً")

st.subheader("📋 السجل المباشر")
log_box = st.empty()
log_box.code("\n".join(st.session_state.logs[-40:]) or "لا توجد رسائل بعد...")

if st.session_state.bot and st.session_state.bot.history:
    st.subheader("🧾 سجل الصفقات")
    st.dataframe(st.session_state.bot.history, use_container_width=True)

st.caption(
    "لتحديث السجل أثناء تشغيل البوت اضغط زر إعادة التحميل في المتصفح، "
    "أو أضف st_autorefresh لاحقاً لتحديث تلقائي."
)
