# main.py
import logging
import random
import datetime
import json
from telegram import Update, MessageEntity
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)

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

MORNING_PHRASES = ["доброго утра", "доброе утро", "добречка", "доброго утречка", "доброго утречка"]
NIGHT_PHRASES = ["спокойной ночи", "спок", "спокойной ночки", "сладких снов"]

STATE_FILE = "state.json"

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf‑8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf‑8") as f:
        json.dump(state, f, ensure_ascii=False)

def start_fire(chat_id, state):
    state[str(chat_id)] = {
        "started": datetime.date.today().isoformat(),
        "day": 0,
        "status": "🔥",
        "missed": 0,
        "tasks": []
    }

def next_day(chat_id, state):
    info = state[str(chat_id)]
    info["day"] += 1
    info["tasks"] = random.sample(TASKS, 3)
    info["today_done"] = {"me": False, "them": False}

def check_failure(chat_id, state):
    info = state[str(chat_id)]
    if info["missed"] >= 3:
        info["status"] = "😭"

async def send_new_tasks(context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    today = datetime.date.today().isoformat()
    for chat_id, info in state.items():
        if info["status"] == "😭": continue
        if info.get("last_date") != today:
            # advance day
            if info["day"] > 0 and (not info["today_done"]["me"] or not info["today_done"]["them"]):
                info["missed"] += 1
                if info["status"] == "🔥":
                    info["status"] = "🧊"
            check_failure(chat_id, state)
            next_day(chat_id, state)
            info["last_date"] = today
            # send tasks to both
            text = (
                f"привет! я - Огонек Матвея, общайся с матвеем каждый день, чтобы я продолжал гореть.\n\n"
                f"задания на сегодня: {info['tasks'][0]}, {info['tasks'][1]}, {info['tasks'][2]}\n\n"
                "если кто‑то из вас двоих не сделает задание, то огонек станет серым, "
                "серия не продвинется, на третий день огонек потухнет."
            )
            await context.bot.send_message(int(chat_id), text)
    save_state(state)

def check_phrase_done(text):
    low = text.lower()
    if any(p in low for p in MORNING_PHRASES):
        return "morning"
    if any(p in low for p in NIGHT_PHRASES):
        return "night"
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat_id = msg.chat.id
    me = str(context.bot.id)
    state = load_state()
    info = state.get(str(chat_id))
    if info is None:
        # first interaction
        start_fire(chat_id, state)
        info = state[str(chat_id)]
        # send greeting + tasks (will be populated at midnight job)
        text = (
            "привет! я - Огонек Матвея, общайся с матвеем каждый день, чтобы я продолжал гореть.\n\n"
            "задания на сегодня: (будут выданы в полночь)\n\n"
            "если кто‑то из вас двоих не сделает задание, то огонек станет серым, "
            "серия не продвинется, на третий день огонек потухнет."
        )
        await msg.reply_text(text)
    else:
        # track tasks
        done = False
        # if message by me or them?
        actor = "me" if msg.from_user.is_bot == False and msg.from_user.id == context.application.bot.id else "them"
        # fetch today's tasks
        for task in info.get("tasks", []):
            if task.startswith("написать "):
                num = int(task.split()[1])
                if context.chat_data.get("count_"+task, 0) + len(msg.text or "") >= num:
                    done = True
                    context.chat_data["count_"+task] = num
                else:
                    context.chat_data["count_"+task] = context.chat_data.get("count_"+task, 0) + len(msg.text or "")
            elif task == "отправить голосовое сообщение" and msg.voice:
                done = True
            elif task == "отправить видеосообщение (кружок)" and msg.video_note:
                done = True
            elif task == "отправить геолокацию" and msg.location:
                done = True
            elif task == "отправить видео" and msg.video:
                done = True
            elif task == "отправить фото" and msg.photo:
                done = True
            elif task == "отправить сообщение >50 символов" and msg.text and len(msg.text) > 50:
                done = True
            elif task == "отправить сообщение >100 символов" and msg.text and len(msg.text) > 100:
                done = True
            elif task == "отправить стикер" and msg.sticker:
                done = True
            elif task == "отправить гифку" and msg.animation:
                done = True
            elif task == "пожелать доброго утра" and check_phrase_done(msg.text) == "morning":
                done = True
            elif task == "пожелать спокойной ночи" and check_phrase_done(msg.text) == "night":
                done = True
            if done:
                info["today_done"][actor] = True
        state[str(chat_id)] = info
    save_state(state)

    # handle "!огонек"
    if msg.text and msg.text.strip() == "!огонек":
        info = state[str(chat_id)]
        if info["status"] != "🔥":
            text = f"статус: {info['status']}\n"
            if info["status"] == "😭":
                await msg.reply_text(text)
                return
        started = info["started"]
        tasks = info.get("tasks", [])
        done_me = info["today_done"].get("me", False)
        done_them = info["today_done"].get("them", False)
        text = (
            f"🔥 серия огонька\n"
            f"статус: {info['status']}\n"
            f"дата начала: {started}\n"
            f"задания на сегодня: {', '.join(tasks)}\n"
            f"выполнено: {1 if done_me else 0}/2 (вы), {1 if done_them else 0}/2 (собеседник)\n"
        )
        await msg.reply_text(text)

async def main():
    app = ApplicationBuilder().token("YOUR_TELEGRAM_TOKEN").build()
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("start", handle_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!огонек$"), handle_message))
    job_queue = app.job_queue
    # schedule at midnight MSK -> Berlin is UTC+2 or UTC+3 depending DST
    job_queue.run_daily(send_new_tasks, time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone(datetime.timedelta(hours=3))))
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
