import asyncio
import logging
import random
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
import uvicorn
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
MATTHEW = int(os.getenv("MATTHEW"))
YANA = int(os.getenv("YANA"))
BACKGROUND = os.getenv("BACKGROUND")

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# Для веба
app = FastAPI()
app.mount("/fonts", StaticFiles(directory="docs/fonts"), name="fonts")
env = Environment(loader=FileSystemLoader("docs"))

# Структура состояния огонька
state = {
    "name": "Огонёк",
    "started_at": None,
    "streak": 0,
    "missed_days": {MATTHEW: 0, YANA: 0},
    "status": "🔥",
    "tasks": [],
    "progress": {},  # task_id -> list of user_ids
}

AVAILABLE_TASKS = [
    {"type": "sticker", "desc": "Отправить стикер"},
    {"type": "video", "desc": "Отправить видео"},
    {"type": "messages", "count": c, "desc": f"Отправить {c} сообщений"} for c in [10, 20, 30, 40, 50, 60]
] + [
    {"type": "morning", "desc": "Пожелать доброго утра"},
    {"type": "night", "desc": "Пожелать спокойной ночи"},
]

KEYWORDS = {
    "morning": ["доброе утро", "доброго утра", "доброе утречко", "доброго утречка"],
    "night": ["спокойной ночи", "сладких снов", "спокойной ночки"]
}

# ================== BOT LOGIC ===================

def get_user_nickname(user_id):
    return "Матвейка" if user_id == MATTHEW else "Яночка"

def get_current_time():
    return datetime.utcnow() + timedelta(hours=3)  # MSK

def generate_tasks():
    chosen = random.sample(AVAILABLE_TASKS, 3)
    state["tasks"] = chosen
    state["progress"] = {i: [] for i in range(3)}

def reset_day():
    dt = get_current_time()
    if state["started_at"] is None:
        state["started_at"] = dt.date()

    # Проверка выполнения
    everyone_done = True
    for uid in [MATTHEW, YANA]:
        for i in range(3):
            if uid not in state["progress"].get(i, []):
                state["missed_days"][uid] += 1
                everyone_done = False
                break
        else:
            state["missed_days"][uid] = 0

    if all(uid in state["progress"][i] for i in range(3) for uid in [MATTHEW, YANA]):
        state["streak"] += 1
    elif not everyone_done:
        state["status"] = "🔥" if state["status"] != "😭" else "😭"  # Не обнуляем, просто заморозка

    for uid in [MATTHEW, YANA]:
        if state["missed_days"][uid] >= 3:
            asyncio.create_task(bot.send_message(GROUP_ID, f"🥺 Огонёк потух, потому что {get_user_nickname(uid)} три дня подряд не выполнял задания. Серия обнуляется."))
            state["streak"] = 0
            state["started_at"] = None
            state["status"] = "😭"
            break
        elif any(uid not in state["progress"][i] for i in range(3)):
            asyncio.create_task(bot.send_message(GROUP_ID, f"⏳ {get_user_nickname(uid)} не выполнил все задания, огонёк сегодня стал серым."))
            state["status"] = "🧊"

    generate_tasks()
    asyncio.create_task(post_tasks())

async def post_tasks():
    lines = [f"📋 Задания на сегодня ({get_current_time().date()}):"]
    for i, task in enumerate(state["tasks"]):
        lines.append(f"{i+1}. {task['desc']}")
    msg = "\n".join(lines)
    await bot.send_message(GROUP_ID, msg)

async def check_task_completion(user_id, message: Message):
    for i, task in enumerate(state["tasks"]):
        if user_id in state["progress"].get(i, []):
            continue

        if task["type"] == "sticker" and message.sticker:
            pass
        elif task["type"] == "video" and message.video:
            pass
        elif task["type"] == "messages":
            key = f"messages_{user_id}_{i}"
            count = message.chat.get_or_add_int(key, 0) + 1
            message.chat.set_int(key, count)
            if count < task["count"]:
                continue
        elif task["type"] in KEYWORDS:
            if not any(word in message.text.lower() for word in KEYWORDS[task["type"]]):
                continue
        else:
            continue

        state["progress"][i].append(user_id)
        done = sum(user_id in v for v in state["progress"].values())
        await message.answer(f"✅ {get_user_nickname(user_id)} выполнил задание {i+1}! ({done}/3)")

@dp.message(F.chat.id == GROUP_ID)
async def group_handler(message: Message):
    user_id = message.from_user.id
    if user_id not in [MATTHEW, YANA]:
        return
    if message.text:
        text = message.text.strip().lower()
        if text.startswith(".имя"):
            await message.answer("✏️ Введите новое имя огонька:")
            # Сделай FSM если надо
        elif text.startswith(".огонек"):
            await message.answer(f"{state['name']} {state['status']}\nСерия: {state['streak']}\nС {state['started_at']}")
        elif text.startswith(".задания"):
            lines = [f"📋 Текущие задания:"]
            for i, task in enumerate(state["tasks"]):
                p = len(state["progress"].get(i, []))
                lines.append(f"{i+1}. {task['desc']} ({p}/2)")
            await message.answer("\n".join(lines))
        elif text.startswith(".статистика"):
            stats = [f"📊 Статистика:"]
            for uid in [MATTHEW, YANA]:
                stats.append(f"{get_user_nickname(uid)}: {3 - sum(uid in v for v in state['progress'].values())}/3 осталось")
            await message.answer("\n".join(stats))
        else:
            await check_task_completion(user_id, message)
    else:
        await check_task_completion(user_id, message)

@dp.message()
async def other_handler(message: Message):
    pass  # игнор

async def scheduler():
    while True:
        now = get_current_time()
        if now.hour == 0 and now.minute == 0:
            reset_day()
        await asyncio.sleep(60)

# ============= FASTAPI ROUTES ===============

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    template = env.get_template("index.html")
    rendered = template.render(
        name=state["name"],
        status=state["status"],
        streak=state["streak"],
        started_at=state["started_at"],
        background=BACKGROUND,
        tasks=[
            {
                "desc": task["desc"],
                "done": len(state["progress"].get(i, [])),
            }
            for i, task in enumerate(state["tasks"])
        ]
    )
    return HTMLResponse(rendered)

@app.get("/api/state")
async def get_state():
    return JSONResponse({
        "name": state["name"],
        "status": state["status"],
        "streak": state["streak"],
        "started_at": str(state["started_at"]),
        "tasks": [
            {
                "desc": task["desc"],
                "done": len(state["progress"].get(i, [])),
            }
            for i, task in enumerate(state["tasks"])
        ]
    })

# ============= RUN ==========================

async def main():
    logging.basicConfig(level=logging.INFO)
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    uvicorn.run(app, host="0.0.0.0", port=10000)
