import os
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ChatMemberUpdated, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ChatMemberStatus
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Настройка логгирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
MATTHEW_ID = int(os.environ['MATTHEW_ID'])
YANA_ID = int(os.environ['YANA_ID'])
GROUP_ID = int(os.environ['GROUP_ID'])
BOT_TOKEN = os.environ['BOT_TOKEN']

# Keep-alive сервер
async def handle(request):
    return web.Response(text="Bot is alive")

async def keep_alive():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("Keep-alive server started")

# ... (остальной код FireState и обработчики остаются без изменений) ...

# Определение заданий
TASKS = [
    {"id": 0, "type": "message_count", "count": 10, "desc": "написать 10 сообщений"},
    {"id": 1, "type": "message_count", "count": 20, "desc": "написать 20 сообщений"},
    {"id": 2, "type": "message_count", "count": 30, "desc": "написать 30 сообщений"},
    {"id": 3, "type": "message_count", "count": 40, "desc": "написать 40 сообщений"},
    {"id": 4, "type": "message_count", "count": 50, "desc": "написать 50 сообщений"},
    {"id": 5, "type": "voice", "desc": "отправить голосовое сообщение"},
    {"id": 6, "type": "video_note", "desc": "отправить видеосощщение (кружок)"},
    {"id": 7, "type": "location", "desc": "отправить геолокацию"},
    {"id": 8, "type": "video", "desc": "отправить видео"},
    {"id": 9, "type": "photo", "desc": "отправить фото"},
    {"id": 10, "type": "long_text", "min_len": 50, "desc": "отправить сообщение >50 символов"},
    {"id": 11, "type": "long_text", "min_len": 100, "desc": "отправить сообщение >100 символов"},
    {"id": 12, "type": "sticker", "desc": "отправить стикер"},
    {"id": 13, "type": "gif", "desc": "отправить гифку"},
    {"id": 14, "type": "morning", "desc": "пожелать доброго утра"},
    {"id": 15, "type": "evening", "desc": "пожелать спокойной ночи"},
]

# Состояние бота
class FireState:
    def __init__(self):
        self.streak = 0
        self.status = "alive"  # alive, frozen, dead
        self.consecutive_misses = 0
        self.series_start_date: Optional[datetime] = None
        self.current_date: datetime = datetime.now(MOSCOW_TZ).date()
        self.task_indices: List[int] = []
        self.tomorrow_tasks: List[int] = []
        self.completed_tasks: Dict[int, Dict[str, bool]] = {}
        self.message_counters: Dict[int, Dict[str, int]] = {}
        self.initialize_new_day()
        
    def initialize_new_day(self):
        """Инициализация нового дня с заданиями"""
        if self.tomorrow_tasks:
            self.task_indices = self.tomorrow_tasks
            self.tomorrow_tasks = []
        else:
            self.task_indices = random.sample(range(len(TASKS)), 3)
        
        self.completed_tasks = {}
        self.message_counters = {}
        
        for idx in self.task_indices:
            task = TASKS[idx]
            self.completed_tasks[idx] = {"matthew": False, "yana": False}
            
            if task["type"] == "message_count":
                self.message_counters[idx] = {"matthew": 0, "yana": 0}
    
    def update_status(self, yesterday_success: bool):
        """Обновление статуса огонька"""
        if yesterday_success:
            self.consecutive_misses = 0
            self.status = "alive"
            self.streak += 1
            if self.streak == 1:
                self.series_start_date = datetime.now(MOSCOW_TZ) - timedelta(days=1)
        else:
            self.consecutive_misses += 1
            if self.consecutive_misses >= 3:
                self.status = "dead"
                self.streak = 0
                self.series_start_date = None
            else:
                self.status = "frozen"
    
    def check_daily_completion(self) -> bool:
        """Проверка выполнения всех заданий"""
        for task_idx in self.task_indices:
            task = TASKS[task_idx]
            
            for user in ["matthew", "yana"]:
                if task["type"] == "message_count":
                    if self.message_counters[task_idx][user] < task["count"]:
                        return False
                elif not self.completed_tasks[task_idx][user]:
                    return False
        return True
    
    def get_status_emoji(self) -> str:
        return {
            "alive": "🔥",
            "frozen": "🧊",
            "dead": "😭"
        }[self.status]
    
    def format_tasks(self) -> str:
        """Форматирование списка заданий"""
        result = []
        for i, task_idx in enumerate(self.task_indices):
            task = TASKS[task_idx]
            statuses = []
            
            for user in ["matthew", "yana"]:
                if task["type"] == "message_count":
                    count = self.message_counters[task_idx][user]
                    required = task["count"]
                    status = f"{count}/{required}"
                    if count >= required:
                        status = f"✅ {status}"
                else:
                    status = "✅" if self.completed_tasks[task_idx][user] else "❌"
                
                statuses.append(status)
            
            result.append(
                f"{i+1}. {task['desc']} - "
                f"Матвей: {statuses[0]}, Яна: {statuses[1]}"
            )
        
        return "\n".join(result)
    
    def get_status_message(self) -> str:
        """Формирование сообщения о статусе"""
        emoji = self.get_status_emoji()
        message = f"<b>{emoji} Статус Огонька:</b>\n\n"
        
        if self.status != "dead":
            message += f"🔥 Серия: {self.streak} дней\n"
            if self.series_start_date:
                start_date = self.series_start_date.strftime("%d.%m.%Y")
                message += f"📅 Дата начала: {start_date}\n"
        
        message += "\n<b>🎯 Задания на сегодня:</b>\n"
        message += self.format_tasks()
        
        return message

# Глобальное состояние
fire_state = FireState()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
user_state = {}  # Для хранения состояния админ-меню

# Вспомогательные функции
def get_user_type(user_id: int) -> Optional[str]:
    if user_id == MATTHEW_ID:
        return "matthew"
    elif user_id == YANA_ID:
        return "yana"
    return None

def is_group_chat(message: types.Message) -> bool:
    return message.chat.id == GROUP_ID

def get_cute_name(user_type: str) -> str:
    return "Матвейчик" if user_type == "matthew" else "Янчик"

async def send_task_completion_notice(task_idx: int):
    """Уведомление о выполнении задания"""
    task = TASKS[task_idx]
    statuses = []
    
    for user in ["matthew", "yana"]:
        if task["type"] == "message_count":
            count = fire_state.message_counters[task_idx][user]
            required = task["count"]
            status = f"{count}/{required}"
            if count >= required:
                status = f"✅ {status}"
        else:
            status = "✅" if fire_state.completed_tasks[task_idx][user] else "❌"
        
        statuses.append(status)
    
    message = (
        f"🎯 Задание выполнено!\n"
        f"<b>{task['desc']}</b>\n"
        f"Матвей: {statuses[0]}, Яна: {statuses[1]}"
    )
    
    await bot.send_message(
        chat_id=GROUP_ID,
        text=message,
        parse_mode="HTML"
    )

async def send_reminder():
    """Отправка напоминания"""
    if fire_state.status == "frozen" and not fire_state.check_daily_completion():
        cute_matthew = get_cute_name("matthew")
        cute_yana = get_cute_name("yana")
        
        reminder_messages = [
            f"🚨 {cute_matthew} и {cute_yana}! Огонёк сейчас не горит... "
            f"Напоминаю, что нужно выполнить сегодняшние задания, чтобы он снова засиял! 💫",
            
            f"✨ Здрасьте-забор покрасьте! Огонёк ждёт вашего внимания. "
            f"Не забыли про задания на сегодня?",
            
            f"{cute_matthew} и {cute_yana}, ваш огонёк скучает! "
            f"Подарите ему немного тепла, выполнив задания 🔥",
            
            f"⏰ Тик-так, время идёт! Огонёк напоминает: "
            f"сегодняшние задания ждут вашего выполнения!",
        ]
        
        await bot.send_message(
            chat_id=GROUP_ID,
            text=random.choice(reminder_messages)
        )

async def new_day_tasks():
    """Обновление заданий в 00:00"""
    global fire_state
    
    yesterday_success = fire_state.check_daily_completion()
    fire_state.update_status(yesterday_success)
    fire_state.current_date = datetime.now(MOSCOW_TZ).date()
    fire_state.initialize_new_day()
    
    status_emoji = fire_state.get_status_emoji()
    message = (
        f"{status_emoji} <b>Новый день! Новые задания!</b> {status_emoji}\n\n"
        f"{fire_state.get_status_message()}"
    )
    
    if fire_state.status == "frozen":
        cute_matthew = get_cute_name("matthew")
        cute_yana = get_cute_name("yana")
        message += (
            "\n\n💔 Огонёк потускнел... "
            f"{cute_matthew} и {cute_yana}, сегодня нужно обязательно "
            "выполнить все задания, чтобы он снова загорелся!"
        )
    
    await bot.send_message(
        chat_id=GROUP_ID,
        text=message,
        parse_mode="HTML"
    )

# Админ-панель
def get_admin_keyboard():
    """Клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Выбрать задания на сегодня", callback_data="select_today_tasks")
    builder.button(text="📅 Выбрать задания на завтра", callback_data="select_tomorrow_tasks")
    builder.button(text="🔥 Установить серию", callback_data="set_streak")
    builder.button(text="📨 Отправить сообщение", callback_data="send_message")
    builder.button(text="🔄 Обновить статус", callback_data="refresh_status")
    builder.adjust(1)
    return builder.as_markup()

def get_task_selection_keyboard(target: str):
    """Клавиатура для выбора заданий"""
    builder = InlineKeyboardBuilder()
    
    # Группируем задания по категориям
    categories = {
        "Сообщения": [0, 1, 2, 3, 4, 10, 11],
        "Медиа": [5, 6, 7, 8, 9, 12, 13],
        "Пожелания": [14, 15]
    }
    
    for category, task_ids in categories.items():
        builder.button(
            text=f"📌 {category}",
            callback_data=f"category_{target}_{'_'.join(map(str, task_ids))}"
        )
    
    builder.button(text="🎲 Случайные 3 задания", callback_data=f"random_{target}")
    builder.button(text="⬅️ Назад", callback_data="back_to_admin")
    builder.adjust(1)
    return builder.as_markup()

def get_tasks_from_category(category_tasks: str):
    """Получение клавиатуры с заданиями из категории"""
    task_ids = list(map(int, category_tasks.split('_')))
    builder = InlineKeyboardBuilder()
    
    for task_id in task_ids:
        task = TASKS[task_id]
        builder.button(
            text=task["desc"],
            callback_data=f"task_{task_id}"
        )
    
    builder.button(text="⬅️ Назад", callback_data="back_to_task_selection")
    builder.adjust(1)
    return builder.as_markup()

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    """Обработка команды /admin"""
    if message.from_user.id == MATTHEW_ID and message.chat.type == "private":
        user_state[message.from_user.id] = {"mode": "admin"}
        await message.answer(
            "🔧 <b>Админ-панель</b>\n\n"
            "Выберите действие:",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML"
        )

@dp.callback_query(F.data.startswith("category_"))
async def select_category(callback: CallbackQuery):
    """Выбор категории заданий"""
    if callback.from_user.id != MATTHEW_ID:
        await callback.answer("Доступ запрещен")
        return
    
    _, target, category_tasks = callback.data.split('_', 2)
    user_state[callback.from_user.id] = {
        "mode": "select_tasks",
        "target": target,
        "selected_tasks": []
    }
    
    await callback.message.edit_text(
        "Выберите задания из категории:",
        reply_markup=get_tasks_from_category(category_tasks)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("task_"))
async def select_task(callback: CallbackQuery):
    """Выбор конкретного задания"""
    if callback.from_user.id != MATTHEW_ID:
        await callback.answer("Доступ запрещен")
        return
    
    task_id = int(callback.data.split('_')[1])
    user_state[callback.from_user.id]["selected_tasks"].append(task_id)
    
    if len(user_state[callback.from_user.id]["selected_tasks"]) >= 3:
        target = user_state[callback.from_user.id]["target"]
        
        if target == "today":
            fire_state.task_indices = user_state[callback.from_user.id]["selected_tasks"][:3]
            fire_state.initialize_new_day()
            await callback.message.edit_text(
                "✅ Задания на сегодня обновлены!\n\n" + fire_state.get_status_message(),
                parse_mode="HTML"
            )
        else:
            fire_state.tomorrow_tasks = user_state[callback.from_user.id]["selected_tasks"][:3]
            tasks_list = "\n".join([f"• {TASKS[idx]['desc']}" for idx in fire_state.tomorrow_tasks])
            await callback.message.edit_text(
                f"✅ Задания на завтра установлены:\n{tasks_list}",
                parse_mode="HTML"
            )
        
        user_state[callback.from_user.id] = {"mode": "admin"}
    else:
        await callback.answer(f"Выбрано задание: {TASKS[task_id]['desc']}")

@dp.callback_query(F.data.startswith("random_"))
async def select_random_tasks(callback: CallbackQuery):
    """Выбор случайных заданий"""
    if callback.from_user.id != MATTHEW_ID:
        await callback.answer("Доступ запрещен")
        return
    
    target = callback.data.split('_')[1]
    
    if target == "today":
        fire_state.task_indices = random.sample(range(len(TASKS)), 3)
        fire_state.initialize_new_day()
        await callback.message.edit_text(
            "🎲 Случайные задания на сегодня:\n\n" + fire_state.get_status_message(),
            parse_mode="HTML"
        )
    else:
        fire_state.tomorrow_tasks = random.sample(range(len(TASKS)), 3)
        tasks_list = "\n".join([f"• {TASKS[idx]['desc']}" for idx in fire_state.tomorrow_tasks])
        await callback.message.edit_text(
            f"🎲 Случайные задания на завтра:\n{tasks_list}",
            parse_mode="HTML"
        )
    
    await callback.answer()

@dp.callback_query(F.data == "select_today_tasks")
async def select_today_tasks(callback: CallbackQuery):
    """Выбор заданий на сегодня"""
    if callback.from_user.id != MATTHEW_ID:
        await callback.answer("Доступ запрещен")
        return
    
    user_state[callback.from_user.id] = {
        "mode": "select_tasks",
        "target": "today",
        "selected_tasks": []
    }
    
    await callback.message.edit_text(
        "📝 Выберите 3 задания на сегодня:",
        reply_markup=get_task_selection_keyboard("today")
    )
    await callback.answer()

@dp.callback_query(F.data == "select_tomorrow_tasks")
async def select_tomorrow_tasks(callback: CallbackQuery):
    """Выбор заданий на завтра"""
    if callback.from_user.id != MATTHEW_ID:
        await callback.answer("Доступ запрещен")
        return
    
    user_state[callback.from_user.id] = {
        "mode": "select_tasks",
        "target": "tomorrow",
        "selected_tasks": []
    }
    
    await callback.message.edit_text(
        "📅 Выберите 3 задания на завтра:",
        reply_markup=get_task_selection_keyboard("tomorrow")
    )
    await callback.answer()

@dp.callback_query(F.data == "set_streak")
async def set_streak(callback: CallbackQuery):
    """Установка серии"""
    if callback.from_user.id != MATTHEW_ID:
        await callback.answer("Доступ запрещен")
        return
    
    user_state[callback.from_user.id] = {"mode": "set_streak"}
    await callback.message.answer(
        "Введите новую длину серии (число дней):"
    )
    await callback.answer()

@dp.callback_query(F.data == "send_message")
async def prepare_send_message(callback: CallbackQuery):
    """Подготовка к отправке сообщения"""
    if callback.from_user.id != MATTHEW_ID:
        await callback.answer("Доступ запрещен")
        return
    
    user_state[callback.from_user.id] = {"mode": "send_message"}
    await callback.message.answer(
        "Введите сообщение, которое я отправлю в группу:"
    )
    await callback.answer()

@dp.callback_query(F.data == "refresh_status")
async def refresh_status(callback: CallbackQuery):
    """Обновление статуса"""
    if callback.from_user.id != MATTHEW_ID:
        await callback.answer("Доступ запрещен")
        return
    
    await callback.message.edit_text(
        fire_state.get_status_message(),
        parse_mode="HTML"
    )
    await callback.answer("Статус обновлен")

@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery):
    """Возврат в админ-панель"""
    if callback.from_user.id != MATTHEW_ID:
        await callback.answer("Доступ запрещен")
        return
    
    user_state[callback.from_user.id] = {"mode": "admin"}
    await callback.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_task_selection")
async def back_to_task_selection(callback: CallbackQuery):
    """Возврат к выбору заданий"""
    if callback.from_user.id != MATTHEW_ID:
        await callback.answer("Доступ запрещен")
        return
    
    target = user_state[callback.from_user.id]["target"]
    await callback.message.edit_text(
        f"Выберите задания на {'сегодня' if target == 'today' else 'завтра'}:",
        reply_markup=get_task_selection_keyboard(target)
    )
    await callback.answer()

@dp.message(F.chat.type == "private", F.from_user.id == MATTHEW_ID)
async def handle_admin_commands(message: Message):
    """Обработка команд админа"""
    user_id = message.from_user.id
    
    if user_id not in user_state:
        return
    
    if user_state[user_id].get("mode") == "set_streak":
        try:
            new_streak = int(message.text)
            fire_state.streak = new_streak
            fire_state.series_start_date = datetime.now(MOSCOW_TZ) - timedelta(days=new_streak)
            fire_state.status = "alive"
            fire_state.consecutive_misses = 0
            
            await message.answer(
                f"✅ Серия установлена: {new_streak} дней\n\n"
                f"{fire_state.get_status_message()}",
                parse_mode="HTML"
            )
            user_state[user_id] = {"mode": "admin"}
        except ValueError:
            await message.answer("❌ Пожалуйста, введите число")
    
    elif user_state[user_id].get("mode") == "send_message":
        await bot.send_message(
            chat_id=GROUP_ID,
            text=message.text
        )
        await message.answer("✅ Сообщение отправлено в группу")
        user_state[user_id] = {"mode": "admin"}

# Основные обработчики
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработка команды /start"""
    if is_group_chat(message):
        await message.reply(
            "Привет! Я - Огонёк! "
            "Напишите !огонек чтобы узнать текущий статус."
        )
    elif message.from_user.id == MATTHEW_ID:
        await admin_panel(message)

@dp.message(F.text == "!огонек")
async def fire_command(message: Message):
    """Обработка команды !огонек"""
    if is_group_chat(message):
        await message.reply(
            fire_state.get_status_message(),
            parse_mode="HTML"
        )

@dp.message(F.chat.id == GROUP_ID)
async def handle_message(message: Message):
    """Обработка всех сообщений в чате"""
    user_type = get_user_type(message.from_user.id)
    if not user_type:
        return
    
    # Проверяем все задания
    for task_idx in fire_state.task_indices:
        task = TASKS[task_idx]
        was_completed = fire_state.completed_tasks[task_idx][user_type]
        
        # Подсчет сообщений
        if task["type"] == "message_count":
            fire_state.message_counters[task_idx][user_type] += 1
        
        # Голосовые сообщения
        elif task["type"] == "voice" and message.voice:
            fire_state.completed_tasks[task_idx][user_type] = True
        
        # Видеосообщения (кружки)
        elif task["type"] == "video_note" and message.video_note:
            fire_state.completed_tasks[task_idx][user_type] = True
        
        # Геолокация
        elif task["type"] == "location" and message.location:
            fire_state.completed_tasks[task_idx][user_type] = True
        
        # Видео
        elif task["type"] == "video" and message.video:
            fire_state.completed_tasks[task_idx][user_type] = True
        
        # Фото
        elif task["type"] == "photo" and message.photo:
            fire_state.completed_tasks[task_idx][user_type] = True
        
        # Длинные сообщения
        elif task["type"] == "long_text" and message.text:
            if len(message.text) >= task["min_len"]:
                fire_state.completed_tasks[task_idx][user_type] = True
        
        # Стикеры
        elif task["type"] == "sticker" and message.sticker:
            fire_state.completed_tasks[task_idx][user_type] = True
        
        # GIF
        elif task["type"] == "gif" and message.animation:
            fire_state.completed_tasks[task_idx][user_type] = True
        
        # Приветствия утром
        elif task["type"] == "morning" and message.text:
            text = message.text.lower()
            phrases = ["доброго утра", "доброе утро", "доброе утречко", "доброго утречка"]
            if any(phrase in text for phrase in phrases):
                fire_state.completed_tasks[task_idx][user_type] = True
        
        # Пожелания спокойной ночи
        elif task["type"] == "evening" and message.text:
            text = message.text.lower()
            phrases = ["спокойной ночи", "спок", "спокойной ночки", "сладких снов"]
            if any(phrase in text for phrase in phrases):
                fire_state.completed_tasks[task_idx][user_type] = True
        
        # Уведомление о выполнении задания
        if not was_completed and fire_state.completed_tasks[task_idx][user_type]:
            await send_task_completion_notice(task_idx)

@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated):
    """Приветствие при добавлении Яны в группу"""
    if event.chat.id == GROUP_ID and event.new_chat_member.user.id == YANA_ID:
        await bot.send_message(
            chat_id=GROUP_ID,
            text=(
                f"Привет, Яна! Я - Огонёк, общайся с Матвеем каждый день, "
                f"чтобы я продолжал гореть.\n\n{fire_state.get_status_message()}"
            ),
            parse_mode="HTML"
        )


async def main():
    # Запускаем keep-alive сервер
    asyncio.create_task(keep_alive())
    
    # Настройка планировщика
    scheduler.add_job(
        new_day_tasks,
        CronTrigger(hour=0, minute=0, timezone=MOSCOW_TZ)
    )
    
    for hour in [10, 14, 18, 22]:
        scheduler.add_job(
            send_reminder,
            CronTrigger(hour=hour, minute=0, timezone=MOSCOW_TZ)
        )
    
    scheduler.start()
    
    # Запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
