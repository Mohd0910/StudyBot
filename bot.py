import os
import sqlite3
import time
from datetime import date, datetime

from dotenv import load_dotenv
from groq import Groq
from telegram import Update, LabeledPrice
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

BOT_USERNAME = os.getenv("BOT_USERNAME", "@Studysnapaibot")
UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", "@StudyBotUpdates")

MODEL = "llama-3.1-8b-instant"
FREE_LIMIT = 10
STARS_PRICE = 100
DB_FILE = "studybot.db"

client = Groq(api_key=GROQ_API_KEY)


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


def add_paid_user(user_id, days=30):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT expires_at FROM paid_users WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()

    base = max(row[0], time.time()) if row else time.time()
    expires_at = base + (days * 86400)

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
    if str(referrer_id) == str(referred_id):
        return False

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


def get_paid_expiry(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT expires_at FROM paid_users WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def is_arabic(text):
    return any("\u0600" <= ch <= "\u06FF" for ch in text)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if ctx.args:
        arg = ctx.args[0]
        if arg.startswith("ref"):
            try:
                referrer_id = int(arg[3:])
                is_new = record_referral(referrer_id, uid)

                if is_new:
                    refs = count_referrals(referrer_id)

                    reward_days = 0
                    if refs == 3:
                        reward_days = 7
                    elif refs == 10:
                        reward_days = 30
                    elif refs > 10 and refs % 10 == 0:
                        reward_days = 30

                    if reward_days:
                        add_paid_user(referrer_id, days=reward_days)
                        try:
                            await ctx.bot.send_message(
                                chat_id=referrer_id,
                                text=(
                                    f"🎁 إحالة جديدة!\n\n"
                                    f"وصلت إلى {refs} إحالات.\n"
                                    f"تمت إضافة {reward_days} يوم Pro لحسابك ✅"
                                ),
                            )
                        except Exception:
                            pass

            except ValueError:
                pass

    await update.message.reply_text(
        f"👋 أهلاً {user.first_name}! أنا StudyBot 🤖\n\n"
        "أرسل لي أي سؤال، نص تريد تلخيصه، أو شيء تريد شرحه.\n"
        "أقدر أجاوبك بالعربي أو الإنجليزي حسب لغتك.\n\n"
        f"📦 المجاني: {FREE_LIMIT} رسائل يومياً\n"
        f"⭐ Pro: غير محدود لمدة 30 يوم مقابل {STARS_PRICE} Stars\n\n"
        f"📢 نصائح وتحديثات: {UPDATE_CHANNEL}\n"
        f"🔗 شارك البوت: /refer\n"
        f"🚀 جرّب الآن — اكتب سؤالك مباشرة."
    )


async def upgrade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await ctx.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="StudyBot Pro ⭐",
        description="Unlimited AI study help for 30 days",
        payload="studybot_pro_30_days",
        currency="XTR",
        prices=[LabeledPrice("StudyBot Pro — 30 days", STARS_PRICE)],
        provider_token="",
    )


async def pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    add_paid_user(uid, days=30)

    await update.message.reply_text(
        "✅ Payment received!\n\n"
        "You now have StudyBot Pro for 30 days 🎉\n"
        "Use /status to check your plan."
    )


async def refer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    refs = count_referrals(uid)
    link = f"https://t.me/{BOT_USERNAME.lstrip('@')}?start=ref{uid}"

    await update.message.reply_text(
        "🔗 رابط الإحالة الخاص بك:\n\n"
        f"{link}\n\n"
        f"👥 إحالاتك الحالية: {refs}\n\n"
        "🎁 المكافآت:\n"
        "3 أصدقاء = 7 أيام Pro\n"
        "10 أصدقاء = 30 يوم Pro\n\n"
        "انسخه وارسله لأصدقائك أو مجموعات الدراسة 🚀"
    )


async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    refs = count_referrals(uid)

    if is_paid(uid):
        expiry = get_paid_expiry(uid)
        expiry_text = datetime.fromtimestamp(expiry).strftime("%Y-%m-%d") if expiry else "unknown"

        await update.message.reply_text(
            "✅ Plan: Pro\n"
            f"📅 Expires: {expiry_text}\n"
            f"👥 Referrals: {refs}\n\n"
            "You have unlimited messages."
        )
    else:
        used = get_usage(uid)
        remaining = max(0, FREE_LIMIT - used)

        await update.message.reply_text(
            "📦 Plan: Free\n"
            f"💬 Remaining today: {remaining}/{FREE_LIMIT}\n"
            f"👥 Referrals: {refs}\n\n"
            "Use /upgrade for Pro or /refer to earn free Pro days."
        )


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text or ""

    if not is_paid(uid):
        count = increase_usage(uid)

        if count > FREE_LIMIT:
            await update.message.reply_text(
                "⚠️ You used all your free messages today.\n\n"
                "Use /upgrade for unlimited access ⭐\n"
                "or /refer to earn free Pro days."
            )
            return

    system_prompt = (
        "You are StudyBot, a helpful AI study assistant for students. "
        "Reply in the same language the user mainly uses. "
        "If the user writes Arabic, reply in Arabic. "
        "If the user writes English, reply in English. "
        "If the user mixes Arabic and English, reply naturally in a similar mixed style. "
        "Keep answers clear, useful, and not too long. "
        "For school questions, explain step by step when helpful. "
        "Do not claim guaranteed grades or results."
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.4,
            max_tokens=700,
        )

        await update.message.reply_text(response.choices[0].message.content)

    except Exception as e:
        print(f"Groq error: {e}")

        if is_arabic(text):
            await update.message.reply_text("⚠️ صار خطأ بسيط. حاول مرة ثانية بعد لحظة.")
        else:
            await update.message.reply_text("⚠️ Something went wrong. Try again in a moment.")


def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Missing TELEGRAM_TOKEN")
    if not GROQ_API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY")

    setup_db()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upgrade", upgrade))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, paid))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("✅ StudyBot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()