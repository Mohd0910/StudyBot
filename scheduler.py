"""
scheduler.py — StudyBot daily auto-marketing
Runs as a SECOND Railway service beside bot.py.

Posts:
- Telegram channel daily reminders
- AI Arabic study posts
- AI TikTok/Reels video script ideas
- Optional Twitter/X posts if keys are added
"""

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
YOUR_CHANNEL = os.getenv("YOUR_CHANNEL", "@StudySnapUpdates")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@StudyBot")

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

groq_client = Groq(api_key=GROQ_API_KEY)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def ai(prompt, max_tokens=350):
    response = groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
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
    ]
    topic = random.choice(topics)

    return ai(f"""
اكتب منشور تيليجرام عربي عن: {topic}

الشروط:
- 80 إلى 120 كلمة
- مناسب لطلاب السعودية
- بداية جذابة
- لا تذكر السعر
- اذكر StudyBot بشكل طبيعي في النهاية
- اختم بـ {BOT_USERNAME}
- استخدم 2-3 إيموجي فقط
اكتب المنشور مباشرة.
""")


def generate_video_script():
    return ai(f"""
اكتب فكرة فيديو تيك توك/ريلز قصيرة للترويج لـ StudyBot.

الشروط:
- مدة 15 ثانية
- مناسب لطلاب السعودية
- اجعله قابل للتصوير بالجوال
- لا تدّعي نتائج مبالغ فيها
- استخدم هذا الشكل فقط:

🎬 فكرة فيديو اليوم

Hook:
Scene:
Text on screen:
Voiceover:
CTA:

اختم بذكر {BOT_USERNAME}
""", max_tokens=450)


def generate_tweet():
    return ai(f"""
Write a Twitter/X post for students about studying smarter with AI.

Rules:
- Max 240 characters
- Mention {BOT_USERNAME}
- 2 hashtags only
- No hype scam language
- Direct tweet only
""", max_tokens=120)


async def post_to_telegram(text):
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=YOUR_CHANNEL, text=text)
        print(f"[{now()}] Telegram posted OK")
    except Exception as e:
        print(f"[{now()}] Telegram error: {e}")


def post_to_twitter(text):
    if tweepy is None:
        print(f"[{now()}] Twitter skipped — tweepy not installed")
        return

    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        print(f"[{now()}] Twitter skipped — missing credentials")
        return

    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )
        client.create_tweet(text=text[:280])
        print(f"[{now()}] Twitter posted OK")
    except Exception as e:
        print(f"[{now()}] Twitter error: {e}")


def job_midday_reminder():
    reminders = [
        f"📚 وقت المذاكرة!\n\nإذا عندك سؤال أو نص تبي تلخصه — {BOT_USERNAME} جاهز يساعدك فوراً ✅",
        f"🤖 تعبت من البحث؟\n\nاكتب سؤالك في {BOT_USERNAME} وخذ إجابة واضحة بسرعة.",
        f"💡 نصيحة اليوم: لخص الدرس قبل الحفظ.\n\n{BOT_USERNAME} يساعدك تلخص وتفهم أسرع ✅",
    ]
    asyncio.run(post_to_telegram(random.choice(reminders)))


def job_daily_arabic():
    print(f"[{now()}] Running Arabic post...")
    asyncio.run(post_to_telegram(generate_arabic_post()))


def job_video_script():
    print(f"[{now()}] Running video script...")
    asyncio.run(post_to_telegram(generate_video_script()))


def job_twitter():
    print(f"[{now()}] Running Twitter post...")
    post_to_twitter(generate_tweet())


def main():
    print(f"[{now()}] Scheduler started ✅")
    print(f"Channel: {YOUR_CHANNEL}")
    print(f"Bot: {BOT_USERNAME}")

    schedule.every().day.at("12:00").do(job_midday_reminder)
    schedule.every().day.at("15:00").do(job_video_script)
    schedule.every().day.at("18:00").do(job_daily_arabic)
    schedule.every().day.at("17:00").do(job_twitter)

    # Startup test
    asyncio.run(post_to_telegram(
        f"✅ Scheduler started!\n\nDaily AI posts are now active.\n{BOT_USERNAME}"
    ))

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()