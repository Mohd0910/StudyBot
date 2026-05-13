import os
from telegram import Update, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
    ContextTypes,
)
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

usage = {}
paid_users = set()


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
    paid_users.add(uid)

    await update.message.reply_text(
        "✅ Payment received! You now have unlimited access."
    )


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid not in paid_users:
        usage[uid] = usage.get(uid, 0) + 1

        if usage[uid] > 10:
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


app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("upgrade", upgrade))
app.add_handler(PreCheckoutQueryHandler(pre_checkout))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, paid))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app.run_polling()