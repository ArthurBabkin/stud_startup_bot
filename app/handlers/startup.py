from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from app.services import db_service
from app.services.db_service import ASK_LIMIT, PDF_LIMIT, LIMIT_RESET_DAYS
import os
import logging
from aiogram.fsm.context import FSMContext
from .states import FeedbackStates
from aiogram import F

router = Router()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.message(CommandStart())  # Handler for /start command
async def cmd_start(message: Message):
    user = message.from_user
    logger.info(f"[START] User {user.id} started bot. Username: {user.username}")
    db_service.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    
    # Compose welcome message text
    welcome_text = (
        "<b>Привет! 👋</b>\n"
        "Я — твой ИИ-помощник. Помогу тебе подготовить и улучшить заявку на грант "
        "«Студенческий Стартап» от ФСИ. Я не являюсь официальным инструментом ФСИ, мои советы основаны на личном опыте @theother_archeee.\n\n"
        
        "<b>✅ Я умею проверять заявки:</b>\n"
        "✔️ Проверю заявку на ошибки и несоответствия\n"
        "✔️ Дам рекомендации по улучшению текста\n"
        "✔️ Подскажу, как повысить шансы на одобрение\n\n"
        
        "<b>✅ Я умею отвечать на вопросы по гранту:</b>\n"
        "✔️ Организационные вопросы\n"
        "✔️ Вопросы по заявке\n\n"
        
        "<i>Выбери нужную для тебя опцию ниже:</i>\n"
        f"(бесплатно: {ASK_LIMIT} вопросов и {PDF_LIMIT} проверки PDF каждые {LIMIT_RESET_DAYS} дня)\n\n"
        
        "<b>📋 Список доступных команд:</b>\n"
        "/start — Запуск бота\n"
        "/help — Список команд\n"
        "/ask — Задать вопрос\n"
        "/check — Проверить заявку в PDF\n"
        "/useful — Полезные материалы\n"
        "/privacy — Юридическая информация\n"
    )
    
    logger.debug(f"[START] Welcome text: {welcome_text}")
    try:
        # List of photos to send in one message
        photo_paths = [
            "static/photos/Stud-startup-bot-1.jpg",
            "static/photos/Stud-startup-bot-2.jpg",
            "static/photos/Stud-startup-bot-3.jpg",
            "static/photos/Stud-startup-bot-4.jpg",
            "static/photos/Stud-startup-bot-5.jpg",
            "static/photos/Stud-startup-bot-6.jpg",
            "static/photos/Stud-startup-bot-7.jpg",
            "static/photos/Stud-startup-bot-8.jpg",
            "static/photos/Stud-startup-bot-9.jpg"
            
        ]
        logger.debug(f"[START] Photo paths: {photo_paths}")
        
        # Create a list of media objects for group sending
        media_group = []
        
        # Check if files exist
        for i, photo_path in enumerate(photo_paths):
            if os.path.exists(photo_path):
                # First photo with caption, others without
                caption = welcome_text if i == 0 else None
                media_group.append({
                    "type": "photo",
                    "media": FSInputFile(photo_path),
                    "caption": caption,
                    "parse_mode": "HTML" if caption else None
                })
            else:
                logger.info(f"[START] File not found: {photo_path}")
        
        logger.debug(f"[START] Media group length: {len(media_group)}")
        # Send group of photos in one message
        if media_group:
            await message.answer_media_group(media=media_group)
        else:
            # If no photos, send only text
            await message.answer(welcome_text, parse_mode="HTML")
    
    except Exception as e:
        logger.error(f"[START] Error sending photos: {e}")
        # In case of error, send only text
        await message.answer(welcome_text, parse_mode="HTML")

@router.message(Command("privacy"))
async def privacy_policy_startup(message: Message):
    logger.info(f"[PRIVACY] User {message.from_user.id} requested privacy policy.")
    pdf_paths = [
        "static/privacy/privacy_policy_stud_startup_bot.pdf",
        "static/privacy/user_agreement_stud_startup_bot.pdf"
    ]
    logger.debug(f"[PRIVACY] PDF paths: {pdf_paths}")
    media_group = [
        {
            "type": "document",
            "media": FSInputFile(pdf_paths[0]),
            "caption": "Политика конфиденциальности"
        },
        {
            "type": "document",
            "media": FSInputFile(pdf_paths[1]),
            "caption": "Условия использования"
        }
    ]
    await message.answer_media_group(media=media_group)
    response_text = (
     "<b>📋 Список доступных команд:</b>\n"
        "/start — Запуск бота\n"
        "/help — Список команд\n"
        "/ask — Задать вопрос\n"
        "/check — Проверить заявку в PDF\n"
        "/useful — Полезные материалы\n"
    )
    await message.answer(response_text, parse_mode="HTML")

@router.message(Command("useful"))
async def useful_startup(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"[USEFUL_DATA] User {user_id} requested useful materials.")
    
    text = (
        "<b>Выступление на тему получения гранта Студ. Стартап:</b>\n"
        "📹 Смотреть на YouTube — <a href='https://youtu.be/Q2iyGM5aqME?si=JoqM3bGEW4iPt_7l'>ссылка</a>\n"
        "💬 Смотреть на VK Видео — <a href='https://vkvideo.ru/video-230151407_456239017'>ссылка</a>\n"
        "📑 Презентация с выступления — <a href='https://t.me/theother_channel/63'>ссылка</a>\n\n"
    )
    
    # Get current user limits to show in the command list
    ask_count, pdf_used = db_service.get_user_limits(user_id)
    ask_remaining = max(0, ASK_LIMIT - ask_count)
    pdf_remaining = max(0, PDF_LIMIT - pdf_used)
    hours_until_reset = db_service.get_time_until_reset(user_id)
    reset_text = f"⏰ Лимиты сбросятся через {hours_until_reset} ч." if hours_until_reset else f"⏰ Лимиты сбрасываются каждые {LIMIT_RESET_DAYS} дня."
    
    # Command list with updated limit information
    commands = (
        "<b>📋 Список доступных команд:</b>\n"
        "/start — Запуск бота\n"
        "/help — Список команд\n"
        "/ask — Задать вопрос\n"
        "/check — Проверить заявку в PDF\n"
        "/useful — Полезные материалы\n"
        "/privacy — Юридическая информация\n\n"
        
        f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
        f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
        
        f"{reset_text}"
    )
    
    # Send message with useful materials and commands
    await message.answer(text, parse_mode="HTML")
    await message.answer(commands, parse_mode="HTML")

    logger.info(f"[USEFUL_DATA] Sent useful materials to user {user_id}")
