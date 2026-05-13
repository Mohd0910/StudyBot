import os
import json
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

USAGE_FILE = "usage.json"
PAID_FILE = "paid_users.json"


def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default


def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f)


usage = load_json(USAGE_FILE, {})
paid_users = load_json(PAID_FILE, {})


def is_paid(uid):
    uid = str(uid)
    return uid in paid_users and paid_users[uid] > time.time()


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
    uid = str(update.effective_user.id)

    # 30 days premium
    paid_users[uid] = time.time() + (30 * 24 * 60 * 60)
    save_json(PAID_FILE, paid_users)

    await update.message.reply_text(
        "✅ Payment received! You now have unlimited access for 30 days!"
    )


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    today = str(date.today())

    if uid not in usage or usage[uid].get("date") != today:
        usage[uid] = {"date": today, "count": 0}

    if not is_paid(uid):
        usage[uid]["count"] += 1
        save_json(USAGE_FILE, usage)

        if usage[uid]["count"] > 10:
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


app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("upgrade", upgrade))
app.add_handler(PreCheckoutQueryHandler(pre_checkout))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, paid))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()