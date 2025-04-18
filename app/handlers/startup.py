from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from app.services import db_service

router = Router()

@router.message(CommandStart())  # Обработчик для команды /start
async def cmd_start(message: Message):
    user = message.from_user
    db_service.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    # Приветственное сообщение при старте
    await message.answer("<b>Привет! 👋</b>\n"
            "Я — твой ИИ-помощник. Помогу тебе подготовить и улучшить заявку на грант "
            "«Студенческий Стартап» от ФСИ.\n\n"
        
            "<b>✅ Я умею проверять заявки:</b>\n"
            "✔️ Проверю заявку на ошибки и несоответствия\n"
            "✔️ Дам рекомендации по улучшению текста\n"
            "✔️ Подскажу, как повысить шансы на одобрение\n\n"
        
            "<b>✅ Я умею отвечать на вопросы по гранту:</b>\n"
            "✔️ Организационные вопросы\n"
            "✔️ Вопросы по заявке\n\n"
        
            "<i>Выбери нужную для тебя опцию ниже:</i>\n"
            "(бесплатно: 5 вопросов и 1 проверка PDF)\n\n"
        
            "<b>📋 Список доступных команд:</b>\n"
            "/start — Запуск бота\n"
            "/help — Список команд\n"
            "/ask — Задать вопрос\n"
            "/check — Проверить заявку в PDF\n",
            parse_mode="HTML"
        )


