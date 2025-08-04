# main.py
import logging
import random
import datetime
import json
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

BOT_TOKEN = "8215048455:AAHo0yQazQdG93cvlDuhjn67VT-OUt7I9VM"  # замените на токен бота

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TASKS = [
    "написать 10 сообщений", "написать 20 сообщений", "написать 30 сообщений",
    "написать 40 сообщений", "написать 50 сообщений", "отправить голосовое сообщение",
    "отправить видеосообщение (кружок)", "отправить геолокацию",
    "отправить видео", "отправить фото", "отправить сообщение >50 символов",
    "отправить сообщение >100 символов", "отправить стикер", "отправить гифку",
    "пожелать доброго утра", "пожелать спокойной ночи"
]

MORNING_PHRASES = ["доброго утра", "доброе утро", "доброе утречко", "доброго утречка"]
NIGHT_PHRASES = ["спокойной ночи", "спок", "спокойной ночки", "сладких снов"]

STATE_FILE = "state.json"

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def start_fire(chat_id, state):
    state[str(chat_id)] = {
        "started": datetime.date.today().isoformat(),
        "day": 0,
        "status": "🔥",
        "missed": 0,
        "tasks": [],
        "last_date": None,
        "today_done": {"me": False, "them": False},
        "message_count": {"me": 0, "them": 0}
    }

def next_day(chat_id, state):
    info = state[str(chat_id)]
    info["day"] += 1
    info["tasks"] = random.sample(TASKS, 3)
    info["today_done"] = {"me": False, "them": False}
    info["message_count"] = {"me": 0, "them": 0}

def check_failure(chat_id, state):
    info = state[str(chat_id)]
    if info["missed"] >= 3:
        info["status"] = "😭"

async def send_new_tasks(context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    today = datetime.date.today().isoformat()
    for chat_id, info in state.items():
        if info["status"] == "😭":
            continue
        if info.get("last_date") != today:
            if info["day"] > 0 and (not info["today_done"]["me"] or not info["today_done"]["them"]):
                info["missed"] += 1
                if info["status"] == "🔥":
                    info["status"] = "🧊"
            check_failure(chat_id, state)
            next_day(chat_id, state)
            info["last_date"] = today
            tasks = info["tasks"]
            text = (
                f"привет! я - Огонек Матвея, общайся с матвеем каждый день, чтобы я продолжал гореть.\n\n"
                f"задания на сегодня: {', '.join(tasks)}\n\n"
                "если кто-то из вас двоих не сделает задание, то огонек станет серым, "
                "если 3 дня подряд пропускать задания, огонек потухнет."
            )
            await context.bot.send_message(int(chat_id), text)
    save_state(state)

def task_completed(task, msg, info, who):
    if task.startswith("написать"):
        needed = int(task.split()[1])
        return info["message_count"][who] >= needed
    if task == "отправить голосовое сообщение" and msg.voice:
        return True
    if task == "отправить видеосообщение (кружок)" and msg.video_note:
        return True
    if task == "отправить геолокацию" and msg.location:
        return True
    if task == "отправить видео" and msg.video:
        return True
    if task == "отправить фото" and msg.photo:
        return True
    if task == "отправить сообщение >50 символов" and msg.text and len(msg.text) > 50:
        return True
    if task == "отправить сообщение >100 символов" and msg.text and len(msg.text) > 100:
        return True
    if task == "отправить стикер" and msg.sticker:
        return True
    if task == "отправить гифку" and msg.animation:
        return True
    if task == "пожелать доброго утра" and msg.text and any(p in msg.text.lower() for p in MORNING_PHRASES):
        return True
    if task == "пожелать спокойной ночи" and msg.text and any(p in msg.text.lower() for p in NIGHT_PHRASES):
        return True
    return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    chat_id = str(msg.chat_id)
    sender_id = msg.from_user.id
    state = load_state()
    info = state.get(chat_id)

    if not info:
        start_fire(chat_id, state)
        info = state[chat_id]
        await msg.reply_text(
            "привет! я - Огонек Матвея, общайся с матвеем каждый день, чтобы я продолжал гореть.\n\n"
            "задания на сегодня: (будут выданы в полночь)\n\n"
            "если кто-то из вас двоих не сделает задание, то огонек станет серым, "
            "если 3 дня подряд пропускать задания, огонек потухнет."
        )
        save_state(state)
        return

    # !огонек
    if msg.text and msg.text.strip() == "!огонек":
        if info["status"] == "😭":
            await msg.reply_text("Огонёк потух 😭")
            return
        tasks = info.get("tasks", [])
        done_me = info["today_done"]["me"]
        done_them = info["today_done"]["them"]
        await msg.reply_text(
            f"🔥 серия огонька\n"
            f"статус: {info['status']}\n"
            f"дата начала: {info['started']}\n"
            f"задания на сегодня: {', '.join(tasks)}\n"
            f"выполнено: {1 if done_me else 0}/2 (вы), {1 if done_them else 0}/2 (собеседник)"
        )
        return

    who = "me" if sender_id == context.bot.id else "them"
    info["message_count"][who] += 1

    for task in info.get("tasks", []):
        if task_completed(task, msg, info, who):
            info["today_done"][who] = True

    state[chat_id] = info
    save_state(state)

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL, handle_message))

    # исправляем ошибку: инициализация job_queue явно
    job_queue = app.job_queue
    job_queue.run_daily(
        send_new_tasks,
        time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
    )

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
