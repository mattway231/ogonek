import asyncio
import os
from datetime import datetime, timedelta
import random

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

import firebase_admin
from firebase_admin import credentials, db

from dotenv import load_dotenv

load_dotenv()

# ENV variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
MATTHEW = int(os.getenv("MATTHEW"))
YANA = int(os.getenv("YANA"))
BACKGROUND = os.getenv("BACKGROUND")

firebase_admin.initialize_app(
    credentials.Certificate({
        "type": "service_account",
        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
        "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\\n"),
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
        "client_id": os.getenv("FIREBASE_CLIENT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
    }),
    {'databaseURL': os.getenv("FIREBASE_DB_URL")}
)

db_ref = db.reference("/")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

app = FastAPI()
app.mount("/fonts", StaticFiles(directory="docs/fonts"), name="fonts")

env = Environment(loader=FileSystemLoader("docs"))

# ----- ЗАДАНИЯ -----
ALL_TASKS = [
    "Отправить стикер",
    "Отправить видео",
    "Отправить голосовое сообщение",
    "Отправить 20 сообщений",
    "Отправить 30 сообщений",
    "Отправить 40 сообщений",
    "Отправить 50 сообщений",
    "Отправить 60 сообщений",
    "Отправить фото",
    "Отправить местоположение",
    "Пожелать доброго утра",
    "Пожелать спокойной ночи"
]

MORNING_PHRASES = ["доброе утро", "доброго утра", "доброе утречко", "доброго утречка"]
NIGHT_PHRASES = ["спокойной ночи", "сладких снов", "спокойной ночки"]

# Запуск задач в 00:00
async def scheduler():
    while True:
        now = datetime.now()
        target = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        wait_time = (target - now).total_seconds()
        await asyncio.sleep(wait_time)
        await generate_daily_tasks()

async def generate_daily_tasks():
    today = datetime.now().strftime("%Y-%m-%d")
    tasks = random.sample(ALL_TASKS, 3)
    db_ref.child("daily").set({
        "date": today,
        "tasks": tasks,
        "progress": {
            "0": [],
            "1": []
        }
    })
    db_ref.child("meta").update({
        "message_pinned": False
    })

    msg = "<b>🔥 Задания на сегодня:</b>\\n"
    for task in tasks:
        msg += f"▪️ {task}\\n"

    await bot.send_message(GROUP_ID, msg)

# Обработка команд
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Бот активен! Используй .огонек, .имя, .задания и т.д.")

@dp.message(F.chat.id == GROUP_ID)
async def handle_text(message: Message):
    text = message.text.lower()
    user_id = message.from_user.id
    nickname = "Матвейка" if user_id == MATTHEW else "Яночка" if user_id == YANA else "?"

    if text.startswith(".огонек"):
        meta = db_ref.child("meta").get()
        await message.reply(f"{meta.get('name', 'Огонёк')} — {meta.get('streak', 0)}🔥")

    elif text.startswith(".имя"):
        new_name = message.text[5:].strip()
        if new_name:
            db_ref.child("meta/name").set(new_name)
            await message.reply(f"Теперь огонёк называется <b>{new_name}</b>")
        else:
            await message.reply("Напиши новое имя после .имя")

    elif text.startswith(".задания"):
        daily = db_ref.child("daily").get()
        msg = f"🔥 Задания на {daily['date']}\\n"
        for task in daily["tasks"]:
            msg += f"▪️ {task}\\n"
        await message.reply(msg)

    else:
        await check_for_task_completion(message, nickname, user_id)

async def check_for_task_completion(message: Message, nickname: str, user_id: int):
    daily = db_ref.child("daily").get()
    if not daily:
        return

    idx = "0" if user_id == MATTHEW else "1" if user_id == YANA else None
    if idx is None:
        return

    done = daily["progress"].get(idx, [])
    updated = False

    for task in daily["tasks"]:
        if task in done:
            continue
        if task == "Отправить стикер" and message.sticker:
            done.append(task)
        elif task == "Отправить видео" and message.video:
            done.append(task)
        elif task == "Отправить голосовое сообщение" and message.voice:
            done.append(task)
        elif task == "Отправить фото" and message.photo:
            done.append(task)
        elif task == "Отправить местоположение" and message.location:
            done.append(task)
        elif task.startswith("Отправить") and "сообщений" in task:
            count = db_ref.child("counts").child(idx).get() or 0
            db_ref.child("counts").child(idx).set(count + 1)
            required = int(task.split()[1])
            if count + 1 >= required:
                done.append(task)
        elif task == "Пожелать доброго утра" and any(p in message.text.lower() for p in MORNING_PHRASES):
            done.append(task)
        elif task == "Пожелать спокойной ночи" and any(p in message.text.lower() for p in NIGHT_PHRASES):
            done.append(task)

    if len(done) > len(daily["progress"][idx]):
        db_ref.child("daily/progress").child(idx).set(done)
        n = len(done)
        await bot.send_message(GROUP_ID, f"✅ {nickname} выполнил задание ({n}/3)")

# ----- FastAPI -----
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    daily = db_ref.child("daily").get() or {}
    meta = db_ref.child("meta").get() or {}
    tasks = daily.get("tasks", [])
    progress = daily.get("progress", {"0": [], "1": []})
    streak = meta.get("streak", 0)
    name = meta.get("name", "Огонёк")
    start_date = meta.get("start_date", datetime.now().strftime("%Y-%m-%d"))

    rendered = env.get_template("index.html").render(
        background=BACKGROUND,
        name=name,
        streak=streak,
        date=start_date,
        tasks=tasks,
        p0=len(progress.get("0", [])),
        p1=len(progress.get("1", [])),
    )
    return HTMLResponse(rendered)

# ----- Запуск -----
async def main():
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
