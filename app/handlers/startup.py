from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

router = Router()

@router.message(CommandStart())  # Обработчик для команды /start
async def cmd_start(message: Message):
    # Приветственное сообщение при старте
    await message.answer("Привет! Я бот по гранту Студенческий Стартап. Задай свой вопрос."
                            "Список доступных команд:\n"
                            "/start - Запуск бота\n"
                            "/stats - Статистика\n"
                            "/help - Список команд\n"
                            "/ask - Задать вопрос\n")
