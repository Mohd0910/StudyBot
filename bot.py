import os
import sqlite3
import time
from datetime import date

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

    conn.commit()
    conn.close()


def is_paid(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT expires_at FROM paid_users WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()
    conn.close()

    return row is not None and row[0] > time.time()


def add_paid_user(user_id):
    expires_at = time.time() + (30 * 24 * 60 * 60)

    conn = db()
    cur = conn.cursor()
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


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm StudyBot — your AI study assistant!\n\n"
        "Send me any question, text to summarise, or thing to explain.\n"
        "Free plan: 10 messages/day\n"
        "Type /upgrade to get unlimited access."
    )


async def upgrade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await ctx.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="StudyBot Unlimited",
        description="Unlimited AI study help — 30 days",
        payload="monthly_sub",
        currency="XTR",
        prices=[LabeledPrice("Unlimited 30 days", 100)],
        provider_token="",
    )


async def pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    add_paid_user(uid)

    await update.message.reply_text(
        "✅ Payment received! You now have unlimited access for 30 days!"
    )


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_paid(uid):
        count = increase_usage(uid)

        if count > 10:
            await update.message.reply_text(
                "You've used your 10 free messages today!\n"
                "Type /upgrade for unlimited access."
            )
            return

    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful student assistant. Answer clearly and briefly.",
            },
            {"role": "user", "content": update.message.text},
        ],
    )

    await update.message.reply_text(response.choices[0].message.content)


setup_db()

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("upgrade", upgrade))
app.add_handler(PreCheckoutQueryHandler(pre_checkout))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, paid))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()