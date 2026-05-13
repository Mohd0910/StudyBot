import os
import sqlite3
import time
from datetime import date, datetime

from dotenv import load_dotenv
from groq import Groq
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

YOUR_CHANNEL = os.getenv("YOUR_CHANNEL", "@StudySnapUpdates")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@StudyBot")

FREE_LIMIT = 10
STARS_PRICE = 100

client = Groq(api_key=GROQ_API_KEY)

DB_FILE = "studybot.db"


def db():
    return sqlite3.connect(DB_FILE)


def setup_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            user_id TEXT PRIMARY KEY,
            day TEXT,
            count INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS paid_users (
            user_id TEXT PRIMARY KEY,
            expires_at REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id TEXT,
            referred_id TEXT PRIMARY KEY,
            created_at REAL
        )
    """)

    conn.commit()
    conn.close()


def is_paid(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT expires_at FROM paid_users WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()
    conn.close()
    return row is not None and row[0] > time.time()


def add_paid_user(user_id, extra_days=0):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT expires_at FROM paid_users WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()

    base = max(row[0], time.time()) if row else time.time()
    expires_at = base + ((30 + extra_days) * 86400)

    cur.execute(
        "INSERT OR REPLACE INTO paid_users (user_id, expires_at) VALUES (?, ?)",
        (str(user_id), expires_at),
    )

    conn.commit()
    conn.close()


def get_usage(user_id):
    today = str(date.today())

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT day, count FROM usage WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()

    if row is None or row[0] != today:
        cur.execute(
            "INSERT OR REPLACE INTO usage (user_id, day, count) VALUES (?, ?, ?)",
            (str(user_id), today, 0),
        )
        conn.commit()
        conn.close()
        return 0

    conn.close()
    return row[1]


def increase_usage(user_id):
    today = str(date.today())
    current = get_usage(user_id)
    new_count = current + 1

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR REPLACE INTO usage (user_id, day, count) VALUES (?, ?, ?)",
        (str(user_id), today, new_count),
    )

    conn.commit()
    conn.close()

    return new_count


def record_referral(referrer_id, referred_id):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT referred_id FROM referrals WHERE referred_id = ?", (str(referred_id),))
    if cur.fetchone():
        conn.close()
        return False

    cur.execute(
        "INSERT INTO referrals (referrer_id, referred_id, created_at) VALUES (?, ?, ?)",
        (str(referrer_id), str(referred_id), time.time()),
    )

    conn.commit()
    conn.close()
    return True


def count_referrals(referrer_id):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (str(referrer_id),))
    count = cur.fetchone()[0]

    conn.close()
    return count


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if ctx.args:
        arg = ctx.args[0]

        if arg.startswith("ref"):
            try:
                referrer_id = int(arg[3:])

                if referrer_id != uid:
                    is_new = record_referral(referrer_id, uid)

                    if is_new:
                        refs = count_referrals(referrer_id)

                        if refs % 3 == 0:
                            add_paid_user(referrer_id, extra_days=1)

                            try:
                                await ctx.bot.send_message(
                                    chat_id=referrer_id,
                                    text=(
                                        f"🎁 شكراً! حصلت على {refs} إحالة.\n"
                                        "تمت إضافة يوم مجاني إضافي لاشتراكك! ✅"
                                    ),
                                )
                            except Exception:
                                pass

            except ValueError:
                pass

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ ترقية للـ Pro", callback_data="upgrade")],
        [InlineKeyboardButton("🔗 شارك وأكسب", callback_data="refer")],
    ])

    await update.message.reply_text(
        f"👋 أهلاً {user.first_name}! أنا StudyBot 🤖\n\n"
        "أرسل لي أي سؤال، نص تريد تلخيصه، أو شيء تريد شرحه — وأجاوبك فوراً.\n\n"
        f"📦 الخطة المجانية: {FREE_LIMIT} رسائل/يوم\n"
        f"⭐ Pro: رسائل غير محدودة مقابل {STARS_PRICE} Star/شهر\n\n"
        "شارك البوت مع صديق وساعده في دراسته! 🙌\n"
        f"👉 {BOT_USERNAME}",
        reply_markup=keyboard,
    )


async def upgrade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await ctx.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="StudyBot Pro ⭐",
        description="رسائل غير محدودة لمدة 30 يوم — بدون إعلانات",
        payload="monthly_sub",
        currency="XTR",
        prices=[LabeledPrice("Pro — 30 يوم", STARS_PRICE)],
        provider_token="",
    )


async def refer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    refs = count_referrals(uid)
    link = f"https://t.me/{BOT_USERNAME.lstrip('@')}?start=ref{uid}"

    await update.message.reply_text(
        "🔗 رابط الإحالة الخاص بك:\n"
        f"{link}\n\n"
        f"👥 إجمالي إحالاتك: {refs}\n"
        "🎁 كل 3 أصدقاء = يوم مجاني مضاف لاشتراكك!\n\n"
        "شارك الرابط في مجموعات الدراسة وعلى تيك توك 🚀"
    )


async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    refs = count_referrals(uid)

    if is_paid(uid):
        conn = db()
        cur = conn.cursor()

        cur.execute("SELECT expires_at FROM paid_users WHERE user_id = ?", (str(uid),))
        row = cur.fetchone()

        conn.close()

        expires = datetime.fromtimestamp(row[0]).strftime("%Y-%m-%d")

        await update.message.reply_text(
            f"✅ أنت على خطة Pro!\n"
            f"📅 تنتهي بتاريخ: {expires}\n"
            f"👥 إحالاتك: {refs}"
        )
    else:
        used = get_usage(uid)
        remaining = max(0, FREE_LIMIT - used)

        await update.message.reply_text(
            f"📦 خطتك: مجانية\n"
            f"💬 رسائل متبقية اليوم: {remaining}/{FREE_LIMIT}\n"
            f"👥 إحالاتك: {refs}\n\n"
            "اكتب /upgrade للترقية ⭐"
        )


async def pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    add_paid_user(uid)

    await update.message.reply_text(
        "✅ تم الدفع بنجاح!\n"
        "أنت الآن على خطة Pro — رسائل غير محدودة لمدة 30 يوم 🎉\n\n"
        "شارك البوت مع أصدقائك واكسب أيام مجانية:\n"
        "/refer"
    )


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if not is_paid(uid):
        count = increase_usage(uid)

        if count > FREE_LIMIT:
            await update.message.reply_text(
                f"⚠️ استنفدت {FREE_LIMIT} رسائل المجانية لهذا اليوم!\n\n"
                "⭐ اكتب /upgrade للحصول على وصول غير محدود.\n"
                "🔗 أو شارك /refer واكسب أيام مجانية!"
            )
            return

    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are StudyBot, a helpful AI study assistant for students. "
                        "Always reply in the same language the user mainly uses. "
                        "If the user writes Arabic, reply in Arabic. "
                        "If the user writes English, reply in English. "
                        "If the user mixes Arabic and English, reply in the same mixed style. "
                        "Keep answers clear, useful, and not too long. "
                        "For school questions, explain step by step when needed."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text("⚠️ حدث خطأ، حاول مرة أخرى بعد لحظة.")
        print(f"Groq error: {e}")


async def daily_promo(ctx: ContextTypes.DEFAULT_TYPE):
    try:
        await ctx.bot.send_message(
            chat_id=YOUR_CHANNEL,
            text=(
                "📚 هل تذاكر الليلة؟\n\n"
                "StudyBot يساعدك:\n"
                "✅ إجابات فورية على أسئلتك\n"
                "✅ تلخيص النصوص الطويلة\n"
                "✅ شرح المفاهيم الصعبة\n"
                "✅ ترجمة عربي ↔ إنجليزي\n\n"
                f"جرّبه مجاناً 👇\n"
                f"👉 {BOT_USERNAME}"
            ),
        )
    except Exception as e:
        print(f"Daily promo error: {e}")


setup_db()

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.job_queue.run_daily(
    daily_promo,
    time=datetime.strptime("18:00", "%H:%M").time(),
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("upgrade", upgrade))
app.add_handler(CommandHandler("refer", refer))
app.add_handler(CommandHandler("status", status))
app.add_handler(PreCheckoutQueryHandler(pre_checkout))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, paid))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("✅ StudyBot is running...")
app.run_polling()