import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
usage = {}

async def start(update: Update, ctx):
    await update.message.reply_text(
        "👋 Hi! I'm StudyBot — your AI study assistant!\n\n"
        "Send me any question, text to summarise, or thing to explain.\n"
        "Free plan: 10 messages/day\n"
        "Type /upgrade to get unlimited access."
    )

async def handle(update: Update, ctx):
    uid = update.effective_user.id
    usage[uid] = usage.get(uid, 0) + 1
    if usage[uid] > 10:
        await update.message.reply_text(
            "You've used your 10 free messages today! "
            "Type /upgrade for unlimited access."
        )
        return
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role":"system","content":"You are a helpful student assistant. Answer clearly and briefly."},
            {"role":"user","content":update.message.text}
        ]
    )
    await update.message.reply_text(response.choices[0].message.content)

async def upgrade(update: Update, ctx):
    await update.message.reply_text(
        "⭐ Upgrade to unlimited for 100 Telegram Stars/month!\n"
        "(Payment setup coming soon — stay tuned!)"
    )

app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("upgrade", upgrade))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.run_polling()