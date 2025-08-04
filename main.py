# main.py
import logging
import random
import datetime
import json
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

BOT_TOKEN = "8215048455:AAHo0yQazQdG93cvlDuhjn67VT-OUt7I9VM"  # 🔁 Укажи свой настоящий токен бота

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
        "completed_tasks": {"me": [], "them": []},
        "message_count": {"me": 0, "them": 0}
    }

def next_day(chat_id, state):
    info = state[str(chat_id)]
    info["day"] += 1
    info["tasks"] = random.sample(TASKS, 3)
    info["completed_tasks"] = {"me": [], "them": []}
    info["message_count"] = {"me": 0, "them": 0}

def check_failure(chat_id, state):
    info = state[str(chat_id)]
    me_done = len(info["completed_tasks"]["me"]) >= 1
    them_done = len(info["completed_tasks"]["them"]) >= 1

    if not me_done or not them_done:
        info["missed"] += 1
        if info["status"] == "🔥":
            info["status"] = "🧊"

    if info["missed"] >= 3:
        info["status"] = "😭"

# ⏰ Ежедневные задачи
async def send_new_tasks(context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    today = datetime.date.today().isoformat()

    for chat_id, info in state.items():
        if info["status"] == "😭":
            continue

        if info.get("last_date") != today:
            check_failure(chat_id, state)
            next_day(chat_id, state)
            info["last_date"] = today

            tasks = info["tasks"]
            text = (
                f"🔥 привет! я - Огонёк. общайся с собеседником каждый день, чтобы я продолжал гореть.\n\n"
                f"задания на сегодня:\n• " + "\n• ".join(tasks) + "\n\n"
                "если хотя бы один из вас не выполнит задание, огонёк станет серым.\n"
                "3 дня подряд без выполнения — огонёк потухнет."
            )
            await context.bot.send_message(chat_id=int(chat_id), text=text)

    save_state(state)

# ✅ Проверка выполнения задачи
def is_task_done(task: str, msg: Update.message, who: str, info) -> bool:
    if task.startswith("написать"):
        match = re.search(r"написать (\d+) сообщений", task)
        if match:
            required = int(match.group(1))
            return info["message_count"][who] >= required
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

# 📩 Обработка всех сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.chat or not msg.from_user:
        return

    chat_id = str(msg.chat_id)
    sender_id = msg.from_user.id
    state = load_state()
    info = state.get(chat_id)

    if not info:
        start_fire(chat_id, state)
        info = state[chat_id]
        await msg.reply_text(
            "привет! я - Огонёк. задания будут выданы в полночь по МСК.\n"
            "выполняйте их каждый день вдвоём, чтобы Огонёк продолжал гореть!"
        )
        save_state(state)
        return

    # Команда "!огонек"
    if msg.text and msg.text.strip() == "!огонек":
        tasks = info.get("tasks", [])
        done_me = len(info["completed_tasks"]["me"]) >= 1
        done_them = len(info["completed_tasks"]["them"]) >= 1
        await msg.reply_text(
            f"🔥 серия огонька\n"
            f"статус: {info['status']}\n"
            f"дата начала: {info['started']}\n"
            f"день: {info['day']}\n"
            f"задания на сегодня:\n• " + "\n• ".join(tasks) + "\n\n"
            f"выполнено: {'✅' if done_me else '❌'} вы, {'✅' if done_them else '❌'} собеседник"
        )
        return

    who = "me" if sender_id == context.bot.id else "them"
    info["message_count"][who] += 1

    new_done = False
    for task in info.get("tasks", []):
        if task in info["completed_tasks"][who]:
            continue
        if is_task_done(task, msg, who, info):
            info["completed_tasks"][who].append(task)
            new_done = True

    if new_done:
        await msg.reply_text(f"✅ Задание выполнено! Огонёк разгорается 🔥")

    save_state(state)

# 🚀 Запуск
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL, handle_message))

    app.job_queue.run_daily(
        send_new_tasks,
        time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
    )

    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
