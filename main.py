import os
import asyncio
import random
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
MATTHEW = int(os.getenv("MATTHEW"))
YANA = int(os.getenv("YANA"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

fire_data = {
    "name": "Огонёк",
    "series": 0,
    "start_date": None,
    "status": "🔥",
    "tasks": [],
    "done": {MATTHEW: set(), YANA: set()},
    "frozen_days": 0,
}

task_templates = [
    "Отправить стикер", "Отправить видео", "Отправить 10 сообщений",
    "Отправить 20 сообщений", "Отправить 30 сообщений", "Отправить 40 сообщений",
    "Отправить 50 сообщений", "Отправить 60 сообщений",
    "Пожелать доброго утра", "Пожелать спокойной ночи",
    "Отправить голосовое сообщение", "Отправить фото", "Отправить местоположение",
    "Написать длинное сообщение (100+ символов)"
]

def is_morning(text): return any(w in text.lower() for w in ["доброе утро", "доброго утра", "доброе утречко", "доброго утречка"])
def is_night(text): return any(w in text.lower() for w in ["спокойной ночи", "сладких снов", "спокойной ночки"])

def pick_tasks(): return random.sample(task_templates, 3)

async def send_tasks():
    fire_data["tasks"] = pick_tasks()
    fire_data["done"] = {MATTHEW: set(), YANA: set()}
    fire_data["status"] = "🔥"
    now = datetime.now().strftime("%d.%m.%Y")
    text = f"<b>{fire_data['status']} {fire_data['name']}</b>\n"
    if fire_data["series"]: text += f"Серия: {fire_data['series']}🔥 с {fire_data['start_date']}\n"
    else: text += "Серия: 0🔥 (ожидается начало)\n"
    text += f"📅 Задания на {now}:\n\n"
    for t in fire_data["tasks"]: text += f"⬜ {t}\n"
    msg = await bot.send_message(chat_id=GROUP_ID, text=text)
    try: await bot.unpin_all_chat_messages(chat_id=GROUP_ID)
    except: pass
    await msg.pin()

async def check_series():
    done_all = all(len(fire_data["done"][uid]) == 3 for uid in (MATTHEW, YANA))
    if done_all:
        if fire_data["series"] == 0:
            fire_data["start_date"] = datetime.now().strftime("%d.%m.%Y")
        fire_data["series"] += 1
        fire_data["frozen_days"] = 0
    else:
        fire_data["frozen_days"] += 1
        fire_data["status"] = "🧊"
        missing = []
        for uid in (MATTHEW, YANA):
            if len(fire_data["done"][uid]) < 3:
                missing.append("Матвейка" if uid == MATTHEW else "Яночка")
        await bot.send_message(GROUP_ID, f"⚠️ {' и '.join(missing)}, вы не выполнили все задания.")
        if fire_data["frozen_days"] >= 3:
            fire_data.update({"series": 0, "start_date": None, "status": "😭"})
            await bot.send_message(GROUP_ID, "💔 Огонёк потух. Серия обнулилась.")

async def midnight_loop():
    while True:
        now = datetime.now()
        next_run = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        await asyncio.sleep((next_run - now).total_seconds())
        await check_series()
        await send_tasks()

@dp.message_handler(commands=["start"])
async def start_cmd(m: types.Message):
    if m.chat.id == GROUP_ID:
        await m.reply("👋 Бот запущен")

@dp.message_handler(lambda m: m.text and m.text.startswith("."))
async def commands(m: types.Message):
    if m.chat.id != GROUP_ID: return
    cmd = m.text.lower()
    if cmd == ".огонек":
        await m.reply(f"{fire_data['status']} Серия: {fire_data['series']}🔥")
    elif cmd == ".имя":
        await m.reply("Напиши новое имя огонька")
    elif cmd == ".задания":
        lines = []
        for i, t in enumerate(fire_data["tasks"]):
            count = sum(1 for uid in (MATTHEW, YANA) if i in fire_data["done"][uid])
            lines.append(f"{'☑️' if count==2 else '⬜'} {t} — {count}/2")
        await m.reply("\n".join(lines))
    elif cmd == ".статистика":
        matt = len(fire_data["done"][MATTHEW])
        yana = len(fire_data["done"][YANA])
        await m.reply(f"{fire_data['status']} {fire_data['name']}\nМатвейка: {matt}/3\nЯночка: {yana}/3")

@dp.message_handler()
async def track(m: types.Message):
    if m.chat.id != GROUP_ID or m.from_user.id not in (MATTHEW, YANA): return
    uid = m.from_user.id
    tasks = fire_data["tasks"]
    done = fire_data["done"][uid]
    def complete(i):
        if i not in done:
            done.add(i)
            who = "Матвейка" if uid == MATTHEW else "Яночка"
            asyncio.create_task(bot.send_message(GROUP_ID, f"✅ {who} выполнил: {tasks[i]} ({len(done)}/3)"))
    for i, t in enumerate(tasks):
        if t == "Отправить стикер" and m.sticker: complete(i)
        elif t == "Отправить видео" and m.video: complete(i)
        elif t.startswith("Отправить голосовое") and m.voice: complete(i)
        elif t.startswith("Отправить фото") and m.photo: complete(i)
        elif t.startswith("Отправить местоположение") and m.location: complete(i)
        elif t.startswith("Пожелать доброго утра") and m.text and is_morning(m.text): complete(i)
        elif t.startswith("Пожелать спокойной ночи") and m.text and is_night(m.text): complete(i)
        elif t.startswith("Написать длинное") and m.text and len(m.text) > 100: complete(i)
        elif "сообщений" in t:
            if not hasattr(dp, "msg_count"): dp.msg_count = {}
            dp.msg_count.setdefault((uid, i), 0)
            dp.msg_count[(uid, i)] += 1
            if dp.msg_count[(uid, i)] >= int(t.split()[1]): complete(i)

# Web
routes = web.RouteTableDef()

@routes.get("/")
async def index(request): return web.FileResponse("docs/index.html")

@routes.get("/background")
async def background(request): return web.HTTPFound(location=os.getenv("BACKGROUND"))

@routes.get("/fonts/{name}")
async def fonts(request): return web.FileResponse(f"docs/fonts/{request.match_info['name']}")

@routes.get("/api/state")
async def api(request):
    tasks = []
    for i, name in enumerate(fire_data["tasks"]):
        count = sum(1 for uid in (MATTHEW, YANA) if i in fire_data["done"][uid])
        tasks.append({"name": name, "count": count})
    return web.json_response({
        "name": fire_data["name"],
        "series": fire_data["series"],
        "start_date": fire_data["start_date"],
        "status": fire_data["status"],
        "tasks": tasks
    })

def start_web(): app = web.Application(); app.add_routes(routes); return app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(midnight_loop())
    web_app = start_web()
    loop.create_task(web._run_app(web_app, port=8080))
    executor.start_polling(dp, skip_updates=True)
