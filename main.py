import os
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ChatMemberUpdated
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ChatMemberStatus
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.utils.chat_action import ChatActionMiddleware
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

# Определение заданий
TASKS = [
    {"type": "message_count", "count": 10, "desc": "написать 10 сообщений"},
    {"type": "message_count", "count": 20, "desc": "написать 20 сообщений"},
    {"type": "message_count", "count": 30, "desc": "написать 30 сообщений"},
    {"type": "message_count", "count": 40, "desc": "написать 40 сообщений"},
    {"type": "message_count", "count": 50, "desc": "написать 50 сообщений"},
    {"type": "voice", "desc": "отправить голосовое сообщение"},
    {"type": "video_note", "desc": "отправить видеосощщение (кружок)"},
    {"type": "location", "desc": "отправить геолокацию"},
    {"type": "video", "desc": "отправить видео"},
    {"type": "photo", "desc": "отправить фото"},
    {"type": "long_text", "min_len": 50, "desc": "отправить сообщение >50 символов"},
    {"type": "long_text", "min_len": 100, "desc": "отправить сообщение >100 символов"},
    {"type": "sticker", "desc": "отправить стикер"},
    {"type": "gif", "desc": "отправить гифку"},
    {"type": "morning", "desc": "пожелать доброго утра"},
    {"type": "evening", "desc": "пожелать спокойной ночи"},
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
        self.completed_tasks: Dict[int, Dict[str, bool]] = {}
        self.message_counters: Dict[int, Dict[str, int]] = {}
        self.initialize_new_day()
        
    def initialize_new_day(self):
        """Инициализация нового дня и заданий"""
        self.task_indices = random.sample(range(len(TASKS)), 3)
        self.completed_tasks = {}
        self.message_counters = {}
        
        for idx in self.task_indices:
            task = TASKS[idx]
            self.completed_tasks[idx] = {"matthew": False, "yana": False}
            
            if task["type"] == "message_count":
                self.message_counters[idx] = {"matthew": 0, "yana": 0}
    
    def update_status(self, yesterday_success: bool):
        """Обновление статуса огонька на основе выполнения заданий"""
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
        """Проверка выполнения всех заданий за текущий день"""
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
        """Форматирование списка заданий для вывода"""
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

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

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
    return "Матвейка" if user_type == "matthew" else "Янчик"

async def send_reminder():
    """Отправка напоминания о заданиях"""
    if fire_state.status == "frozen" and not fire_state.check_daily_completion():
        cute_matthew = get_cute_name("matthew")
        cute_yana = get_cute_name("yana")
        
        reminder_messages = [
            f"🚨 {cute_matthew} и {cute_yana}! Огонёк сейчас не горит... "
            f"Напоминаю, что нужно выполнить сегодняшние задания, чтобы он снова засиял! 💫",
            
            f"✨ Привет! Огонёк ждёт вашего внимания. "
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
    """Обновление заданий в 00:00 по МСК"""
    global fire_state
    
    # Проверка выполнения вчерашних заданий
    yesterday_success = fire_state.check_daily_completion()
    
    # Обновление состояния
    fire_state.update_status(yesterday_success)
    
    # Инициализация нового дня
    fire_state.current_date = datetime.now(MOSCOW_TZ).date()
    fire_state.initialize_new_day()
    
    # Отправка новых заданий
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

# Обработчики команд и сообщений
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработка команды /start"""
    if is_group_chat(message):
        await message.reply(
            "Привет! Я - Огонёк! "
            "Напишите !огонек чтобы узнать текущий статус."
        )

@dp.message(F.text == "!огонек")
async def fire_command(message: types.Message):
    """Обработка команды !огонек"""
    if is_group_chat(message):
        await message.reply(
            fire_state.get_status_message(),
            parse_mode="HTML"
        )

@dp.message(F.chat.id == GROUP_ID)
async def handle_message(message: types.Message):
    """Обработка всех сообщений в чате"""
    user_type = get_user_type(message.from_user.id)
    if not user_type:
        return
    
    # Обработка всех типов заданий
    for task_idx in fire_state.task_indices:
        task = TASKS[task_idx]
        
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

@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated):
    """Приветствие при добавлении Яны в группу"""
    if event.chat.id == GROUP_ID and event.new_chat_member.user.id == YANA_ID:
        await bot.send_message(
            chat_id=GROUP_ID,
            text=(
                f"Привет, Яна! Я - Огонёк, общайся с Матвеем каждый день, "
                f"чтобы я продолжал гореть.\n\n{fire_state.get_status_message()}"
                f"(пишу тебе через код, бот автоматически отправит это тебе когда"
                f"ты зайдешь в группу, эта группа это замена нашего лс, но только с"
                f"добавлениеи этого бота ахах)"
            ),
            parse_mode="HTML"
        )

async def main():
    """Основная функция запуска"""
    # Настройка планировщика
    scheduler.add_job(
        new_day_tasks,
        CronTrigger(hour=0, minute=0, timezone=MOSCOW_TZ)
    )
    
    # Напоминания 4 раза в день
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
