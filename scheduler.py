import os
import asyncio
import schedule
import time
import random
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
import telegram

try:
    import tweepy
except ImportError:
    tweepy = None

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

YOUR_CHANNEL = os.getenv("YOUR_CHANNEL", "@StudyBotUpdates")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@Studysnapaibot")
GROUP_CHAT_IDS = os.getenv("GROUP_CHAT_IDS", "")

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

MODEL = "llama-3.1-8b-instant"

groq_client = Groq(api_key=GROQ_API_KEY)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def ai(prompt, max_tokens=350):
    response = groq_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def generate_arabic_post():
    topics = [
        "كيف تذاكر قبل الاختبار بيوم",
        "طريقة تلخيص درس طويل بسرعة",
        "كيف تحفظ المعلومات لفترة أطول",
        "أفضل طريقة تراجع قبل النوم",
        "كيف تستخدم الذكاء الاصطناعي في الدراسة",
        "طريقة البومودورو للطلاب",
        "كيف ترتب وقتك بين المواد",
        "كيف تراجع بدون توتر",
        "كيف تذاكر الرياضيات بذكاء",
        "كيف توقف التسويف",
    ]

    topic = random.choice(topics)

    return ai(f"""
اكتب منشور تيليجرام عربي مفيد عن: {topic}

الشروط:
- مناسب لطلاب السعودية
- 80 إلى 140 كلمة
- مفيد فعلاً
- بدون مبالغة
- لا تذكر السعر
- اذكر {BOT_USERNAME} بشكل طبيعي في النهاية
- 2 إلى 3 إيموجي
""")


def generate_video_script():
    return ai(f"""
اكتب فكرة فيديو قصيرة للترويج لـ StudyBot.

الشروط:
- 15 ثانية
- مناسبة لطلاب السعودية
- قابلة للتصوير بالجوال
- لا وعود مبالغ فيها
- استخدم هذا الشكل:

🎬 فكرة فيديو اليوم
Hook:
Scene:
Text on screen:
Voiceover:
CTA:

اختم بـ {BOT_USERNAME}
""", max_tokens=450)


def generate_tweet():
    return ai(f"""
Write a tweet for students about studying smarter.

Rules:
- under 240 chars
- mention {BOT_USERNAME}
- 2 hashtags max
- no hype scam language
""", max_tokens=120)


async def post_to_chat(text, target):
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)

        if str(target).startswith("-100"):
            chat_id = target
        else:
            chat = await bot.get_chat(target)
            chat_id = chat.id

        await bot.send_message(chat_id=chat_id, text=text)
        print(f"[{now()}] Posted to {target}")

    except Exception as e:
        print(f"[{now()}] Telegram error for {target}: {e}")


async def broadcast(text):
    await post_to_chat(text, YOUR_CHANNEL)

    groups = [g.strip() for g in GROUP_CHAT_IDS.split(",") if g.strip()]
    for group in groups:
        await post_to_chat(text, group)


def post_to_twitter(text):
    if tweepy is None:
        return

    if not all([
        TWITTER_API_KEY,
        TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN,
        TWITTER_ACCESS_SECRET,
    ]):
        return

    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )
        client.create_tweet(text=text[:280])
        print(f"[{now()}] Twitter posted")

    except Exception as e:
        print(f"[{now()}] Twitter error: {e}")


def promo_post():
    text = (
        "📚 عندك واجب؟ اختبار؟ شرح صعب؟\n\n"
        "StudyBot يساعدك في:\n"
        "✅ شرح الدروس\n"
        "✅ تلخيص النصوص\n"
        "✅ ترجمة عربي ↔ English\n"
        "✅ إجابات سريعة وواضحة\n\n"
        f"جرّبه هنا 👇\n{BOT_USERNAME}"
    )
    asyncio.run(broadcast(text))


def reminder_post():
    reminders = [
        f"📚 وقت المذاكرة! إذا علقت في أي سؤال — {BOT_USERNAME}",
        f"💡 اختصر وقت البحث، اسأل {BOT_USERNAME}",
        f"🧠 المذاكرة الذكية أهم من المذاكرة الطويلة — {BOT_USERNAME}",
    ]
    asyncio.run(broadcast(random.choice(reminders)))


def ai_study_post():
    asyncio.run(broadcast(generate_arabic_post()))


def ai_video_post():
    asyncio.run(broadcast(generate_video_script()))


def twitter_post():
    post_to_twitter(generate_tweet())


def main():
    print(f"[{now()}] Scheduler started")
    print(f"Channel: {YOUR_CHANNEL}")
    print(f"Bot: {BOT_USERNAME}")

    asyncio.run(broadcast(
        f"✅ Scheduler started!\nDaily AI marketing active.\n{BOT_USERNAME}"
    ))

    schedule.every().day.at("09:00").do(ai_study_post)
    schedule.every().day.at("12:00").do(reminder_post)
    schedule.every().day.at("15:00").do(ai_video_post)
    schedule.every().day.at("17:00").do(twitter_post)
    schedule.every().day.at("18:00").do(promo_post)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()