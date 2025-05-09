from app.services.openai_service import ask_openai, ask_deepseek
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from pdfplumber import open as pdf_open
from aiogram.fsm.context import FSMContext
from .states import AskStates, CheckStates, FeedbackStates
from app.services import db_service
from app.services.db_service import ASK_LIMIT, PDF_LIMIT, LIMIT_RESET_DAYS, update_message_feedback
from aiogram.filters import StateFilter
from aiogram.fsm.state import default_state
import os
from datetime import datetime
from app.config import config
from app.services.ocr import extract_text_with_mistral_ocr
import logging

router = Router()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ----- /check command handler -----
@router.message(Command("check"))
async def start_check(message: Message, state: FSMContext):
    # Instruction text
    check_text = (
        "<b>Как скачать PDF заявку?</b>\n"
        "1. Заходишь на сайт https://online.fasie.ru/m\n"
        "2. Нажимаешь скачать заявку\n"
        "3. Отправляешь боту здесь, одним сообщением\n\n"
        "/cancel — отмена"
    )
    photo_paths = [
        "static/photos/Stud-startup-bot-check-1.jpg",
        "static/photos/Stud-startup-bot-check-2.jpg",
        "static/photos/Stud-startup-bot-check-3.jpg",
        "static/photos/Stud-startup-bot-check-4.jpg"
    ]
    media_group = []
    for i, photo_path in enumerate(photo_paths):
        if os.path.exists(photo_path):
            caption = check_text if i == 0 else None
            media_group.append({
                "type": "photo",
                "media": FSInputFile(photo_path),
                "caption": caption,
                "parse_mode": "HTML" if caption else None
            })
    if media_group:
        await message.answer_media_group(media=media_group)
    else:
        await message.answer(check_text, parse_mode="HTML")
    await message.answer(
        "Пришлите PDF‑файл заявки одним сообщением. /cancel — отмена"
    )
    await state.set_state(CheckStates.waiting_for_pdf)

# ----- receive PDF if waiting for it -----
@router.message(CheckStates.waiting_for_pdf,
                lambda m: m.document and m.document.mime_type == "application/pdf")
async def process_pdf(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        logger.info(f"[PDF] User {user_id} started PDF check.")
        processing_msg = await message.answer("Обрабатываю файл, подождите…")
        _, pdf_used = db_service.get_user_limits(user_id)
        if pdf_used >= PDF_LIMIT:
            logger.info(f"[PDF] User {user_id} exceeded PDF limit.")
            hours_until_reset = db_service.get_time_until_reset(user_id)
            reset_text = f"через {hours_until_reset} ч" if hours_until_reset else f"через {LIMIT_RESET_DAYS*24} часов."
            await processing_msg.edit_text(f"Вы уже использовали все {PDF_LIMIT} проверки PDF. "
                                 f"Ваш лимит обновится {reset_text}. "
                                 f"Или напишите @theother_archeee для получения продвинутого доступа.\n\n"
                                 f"Также вы можете посмотреть полезные материалы /useful")
            return
        os.makedirs("application_files", exist_ok=True)
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"id{user_id}_pdf_{current_time}.pdf"
        file_path = os.path.join("application_files", file_name)
        file = await message.bot.get_file(message.document.file_id)
        pdf_bytes = await message.bot.download_file(file.file_path)
        with open(file_path, "wb") as f:
            f.write(pdf_bytes.getvalue())
        logger.info(f"[PDF] Saving file to {file_path}")
        if config.use_mistral_ocr:
            logger.info(f"[PDF] Using Mistral OCR for user {user_id}")
            raw_text = await extract_text_with_mistral_ocr(file_path)
        else:
            logger.info(f"[PDF] Using pdfplumber for user {user_id}")
            raw_text = extract_text_from_pdf(file_path)
        logger.debug(f"[PDF] Extracted raw text: {raw_text}")
        clean_text = clean_pdf_text(raw_text)
        logger.debug(f"[PDF] Cleaned text: {clean_text}")
        try:
            html_answer = await ask_deepseek(clean_text, message)
        except Exception as e:
            logger.error(f"[PDF] Error from ask_deepseek: {e}")
            await processing_msg.delete()
            await send_error_and_commands(message, user_id, context='check')
            await state.clear()
            return
        logger.debug(f"[PDF] Deepseek answer: {html_answer}")
        html_safe = sanitize_html(html_answer)
        logger.debug(f"[PDF] Sanitized HTML: {html_safe}")
        await processing_msg.delete()
        message_chunks = split_long_message(html_safe)
        for chunk in message_chunks:
            await message.answer(chunk, parse_mode="HTML")
        db_service.mark_pdf_used(user_id)
        await state.clear()
        ask_count, pdf_used = db_service.get_user_limits(user_id)
        ask_remaining = max(0, ASK_LIMIT - ask_count)
        pdf_remaining = max(0, PDF_LIMIT - pdf_used)
        hours_until_reset = db_service.get_time_until_reset(user_id)
        reset_text = f"⏰ Лимиты сбросятся через {hours_until_reset} ч." if hours_until_reset else f"⏰ Лимиты сбрасываются каждые {LIMIT_RESET_DAYS} дня."
        commands_text = (
            "📋 <b>Что дальше?</b>\n"
            "/ask — Задать вопрос\n"
            "/check — Проверить другую заявку\n"
            "/help — Другие команды\n\n"
            f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
            f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
            f"{reset_text}"
        )
        await message.answer(commands_text, parse_mode="HTML")
        logger.info(f"[PDF] User {user_id} finished PDF check.")
        markup = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Да")], [KeyboardButton(text="Нет")]],
            resize_keyboard=True
        )
        await message.answer("Хотите оценить ответ?", reply_markup=markup)
        pdf_id = db_service.save_pdf(user_id, pdf_bytes.getvalue(), html_safe)
        await state.set_state(FeedbackStates.waiting_for_feedback_decision)
        await state.update_data(feedback_context='check', feedback_answer=html_safe, pdf_id=pdf_id)
    except Exception as e:
        logger.error(f"[PDF] Unexpected error: {e}")
        await send_error_and_commands(message, user_id, context='check')
        await state.clear()

# -------- helper functions --------
ALLOWED_TAGS = {"b", "i", "blockquote"}

def sanitize_html(text: str) -> str:
    """
    Only keep <b>, <i>, <blockquote>.
    Line breaks are regular \\n.
    """
    # <ul><li> => • item \\n
    text = text.replace("<ul>", "").replace("</ul>", "") \
               .replace("</li>", "\n").replace("<li>", "• ")

    # <p> → double line break
    text = text.replace("</p>", "\n\n").replace("<p>", "")

    # <br> → line break
    text = text.replace("<br>", "\n").replace("<br/>", "\n")

    import re
    def _keep(m):
        tag = m.group(1).lower()
        return m.group(0) if tag in ALLOWED_TAGS else ""
    cleaned = re.sub(r"</?([a-zA-Z0-9]+)[^>]*>", _keep, text)

    # Telegram ignores multiple consecutive \n — can compress
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

def extract_text_from_pdf(file_path: str) -> str:
    """Function to extract text from PDF"""
    with pdf_open(file_path) as pdf:
        text = ''
        for page in pdf.pages:
            text += page.extract_text()  # Extract text from each page
    return text

def clean_pdf_text(text: str) -> str:
    """Function to clean text from unnecessary sections"""
    sections_to_remove = ["ДАННЫЕ ОБ УЧАСТНИКЕ", "ОПЫТ ВЗАИМОДЕЙСТВИЯ ЗАЯВИТЕЛЯ С ДРУГИМИ ИНСТИТУТАМИ РАЗВИТИЯ"]
    for section in sections_to_remove:
        text = text.replace(section, "")  # Remove specified sections
    return text

def split_long_message(text, max_length=4000):
    """Split a long message into chunks that fit within Telegram's limits."""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by paragraphs (double newlines)
    paragraphs = text.split("\n\n")
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed the limit
        if len(current_chunk) + len(paragraph) + 2 > max_length:
            # If the current chunk is not empty, add it to chunks
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            
            # If the paragraph itself is longer than max_length, split it further
            if len(paragraph) > max_length:
                # Split by newlines
                lines = paragraph.split("\n")
                for line in lines:
                    if len(current_chunk) + len(line) + 1 > max_length:
                        if current_chunk:
                            chunks.append(current_chunk)
                            current_chunk = ""
                        
                        # If even a single line is too long, split it by characters
                        if len(line) > max_length:
                            for i in range(0, len(line), max_length):
                                chunks.append(line[i:i+max_length])
                        else:
                            current_chunk = line
                    else:
                        if current_chunk:
                            current_chunk += "\n" + line
                        else:
                            current_chunk = line
            else:
                current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

# Handler for /help command
@router.message(Command("help"))
async def cmd_help(message: Message):
    user_id = message.from_user.id
    
    # Get current user limits
    ask_count, pdf_used = db_service.get_user_limits(user_id)
    
    # Calculate remaining uses
    ask_remaining = max(0, ASK_LIMIT - ask_count)
    pdf_remaining = max(0, PDF_LIMIT - pdf_used)
    
    # Get time until reset
    hours_until_reset = db_service.get_time_until_reset(user_id)
    
    reset_text = f"⏰ Лимиты сбросятся через {hours_until_reset} ч." if hours_until_reset else f"⏰ Лимиты сбрасываются каждые {LIMIT_RESET_DAYS} дня."
    
    help_text = (
        "📌 Список доступных команд:\n"
        "/start - Запуск бота\n"
        "/help - Список команд\n"
        "/ask - Задать вопрос\n"
        "/check - Проверить заявку в пдф формате\n"
        "/useful - Полезные материалы\n"
        "/privacy - Юридическая информация\n\n"
        
        f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
        f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
        
        f"{reset_text}\n\n"
    )
    await message.answer(help_text)


# ----- /ask command handler -----
@router.message(Command("ask"))
async def start_ask(message: Message, state: FSMContext):
    await message.answer("Введите свой вопрос одним сообщением. "
                         "Для отмены отправьте /cancel")
    await state.set_state(AskStates.waiting_for_question)

# ----- cancel handler -----
@router.message(Command("cancel"))
async def cancel_anytime(message: Message, state: FSMContext):
    if await state.get_state():
        await state.clear()
        
        user_id = message.from_user.id
        
        # Get current user limits
        ask_count, pdf_used = db_service.get_user_limits(user_id)
        
        # Calculate remaining uses
        ask_remaining = max(0, ASK_LIMIT - ask_count)
        pdf_remaining = max(0, PDF_LIMIT - pdf_used)
        
        # Get time until reset
        hours_until_reset = db_service.get_time_until_reset(user_id)
        
        reset_text = f"⏰ Лимиты сбросятся через {hours_until_reset} ч." if hours_until_reset else f"⏰ Лимиты сбрасываются каждые {LIMIT_RESET_DAYS} дня."
        
        await message.answer(
            "Действие отменено.\n\n"
            "📌 Список доступных команд:\n"
            "/start - Запуск бота\n"
            "/help - Список команд\n"
            "/ask - Задать вопрос\n"
            "/check - Проверить заявку в пдф формате\n"
            "/useful - Полезные материалы\n"
            "/privacy - Юридическая информация\n\n"
            
            f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
            f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
            
            f"{reset_text}"
        )
    else:
        await message.answer("Нечего отменять.")

# ----- receive user question -----
@router.message(AskStates.waiting_for_question, F.text)
async def process_question(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()
    try:
        logger.info(f"[ASK] User {user_id} asked a question.")
        logger.debug(f"[ASK] Question text: {text}")
        answer_message_id = db_service.save_message(user_id, text, None)
        ask_count, _ = db_service.get_user_limits(user_id)
        if ask_count >= ASK_LIMIT:
            logger.info(f"[ASK] User {user_id} exceeded ask limit.")
            hours_until_reset = db_service.get_time_until_reset(user_id)
            reset_text = f"через {hours_until_reset} ч" if hours_until_reset else f"через {LIMIT_RESET_DAYS*24} часов."
            await message.answer(f"Вы уже использовали все {ASK_LIMIT} вопросов. "
                                 f"Ваш лимит обновится {reset_text}. "
                                 f"Или напишите @theother_archeee для получения продвинутого доступа.\n\n"
                                 f"Также вы можете посмотреть полезные материалы /useful")
            return
        thinking_msg = await message.answer("Думаю...")
        try:
            answer = await ask_openai(text, user_id)
        except Exception as e:
            logger.error(f"[ASK] Error from ask_openai: {e}")
            await send_error_and_commands(message, user_id, context='ask')
            await state.clear()
            return
        logger.debug(f"[ASK] OpenAI answer: {answer}")
        await thinking_msg.edit_text(answer)
        with db_service.get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE messages SET message_answer = %s WHERE message_id = %s", (answer, answer_message_id))
            conn.commit()
        db_service.increment_ask(user_id)
        await state.clear()
        ask_count, pdf_used = db_service.get_user_limits(user_id)
        ask_remaining = max(0, ASK_LIMIT - ask_count)
        pdf_remaining = max(0, PDF_LIMIT - pdf_used)
        hours_until_reset = db_service.get_time_until_reset(user_id)
        reset_text = f"⏰ Лимиты сбросятся через {hours_until_reset} ч." if hours_until_reset else f"⏰ Лимиты сбрасываются каждые {LIMIT_RESET_DAYS} дня."
        commands_text = (
            "📋 <b>Что дальше?</b>\n"
            "/ask — Задать еще вопрос\n"
            "/check — Проверить заявку (PDF)\n"
            "/help — Другие команды\n\n"
            f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
            f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
            f"{reset_text}"
        )
        await message.answer(commands_text, parse_mode="HTML")
        logger.info(f"[ASK] User {user_id} finished question.")
        markup = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Да")], [KeyboardButton(text="Нет")]],
            resize_keyboard=True
        )
        await message.answer("Хотите оценить ответ?", reply_markup=markup)
        await state.set_state(FeedbackStates.waiting_for_feedback_decision)
        await state.update_data(feedback_context='ask', feedback_answer=answer, answer_message_id=answer_message_id)
    except Exception as e:
        logger.error(f"[ASK] Unexpected error: {e}")
        await send_error_and_commands(message, user_id, context='ask')
        await state.clear()

# --- feedback processing after /ask ---
@router.message(FeedbackStates.waiting_for_feedback_decision, F.text)
async def feedback_decision(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    data = await state.get_data()
    if text == "нет":
        await message.answer("Спасибо за использование!", reply_markup=ReplyKeyboardRemove())
        ask_count, pdf_used = db_service.get_user_limits(message.from_user.id)
        await send_what_next(message, ask_count, pdf_used, data.get('feedback_context', 'ask'))
        await state.clear()
    elif text == "да":
        await message.answer("Пожалуйста, напишите ваш отзыв одним сообщением:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(FeedbackStates.waiting_for_feedback_text)
    else:
        await message.answer("Пожалуйста, выберите 'Да' или 'Нет' на клавиатуре.")

# --- text feedback processing ---
@router.message(FeedbackStates.waiting_for_feedback_text, F.text)
async def feedback_text(message: Message, state: FSMContext):
    feedback = message.text.strip()
    data = await state.get_data()
    user_id = message.from_user.id
    context = data.get('feedback_context', 'ask')
    if context == 'ask' and 'answer_message_id' in data:
        db_service.update_message_feedback(data['answer_message_id'], True, feedback)
    elif context == 'check' and 'pdf_id' in data:
        db_service.update_pdf_feedback(data['pdf_id'], True, feedback)
    await message.answer("Спасибо за ваш отзыв!", reply_markup=ReplyKeyboardRemove())
    ask_count, pdf_used = db_service.get_user_limits(user_id)
    await send_what_next(message, ask_count, pdf_used, context)
    await state.clear()


# Handler for any other text messages
@router.message(StateFilter(default_state), F.text)
async def fallback_help(message: Message):
    user_id = message.from_user.id
    logger.info(f"[FALLBACK] User {user_id} sent unknown text in default state.")
    
    # Get current user limits
    ask_count, pdf_used = db_service.get_user_limits(user_id)
    
    # Calculate remaining uses
    ask_remaining = max(0, ASK_LIMIT - ask_count)
    pdf_remaining = max(0, PDF_LIMIT - pdf_used)
    
    # Get time until reset
    hours_until_reset = db_service.get_time_until_reset(user_id)
    
    reset_text = f"⏰ Лимиты сбросятся через {hours_until_reset} ч." if hours_until_reset else f"⏰ Лимиты сбрасываются каждые {LIMIT_RESET_DAYS} дня."
    
    help_text = (
        "📌 Список доступных команд:\n"
        "/start — Запуск бота\n"
        "/help — Список команд\n"
        "/ask — Задать вопрос\n"
        "/check — Проверить заявку (PDF)\n"
        "/useful — Полезные материалы\n"
        "/privacy — Юридическая информация\n\n"
        
        f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
        f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
        
        f"{reset_text}\n\n"
        
        "✉️ Просто выбери нужную команду — я помогу! Если нужной команды нет, напишите @theother_archeee."
    )
    await message.answer(help_text)

@router.message(CheckStates.waiting_for_pdf)
async def handle_invalid_file(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте именно PDF‑файл заявки. /cancel - отмена")

@router.message(Command("privacy"))
async def privacy_policy(message: Message):
    pdf_paths = [
        "static/privacy/privacy_policy_stud_startup_bot.pdf",
        "static/privacy/user_agreement_stud_startup_bot.pdf"
    ]
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

# --- helper function to show "what's next" ---
def send_what_next(message, ask_count, pdf_used, state_type):
    ask_remaining = max(0, ASK_LIMIT - ask_count)
    pdf_remaining = max(0, PDF_LIMIT - pdf_used)
    hours_until_reset = db_service.get_time_until_reset(message.from_user.id)
    reset_text = f"⏰ Лимиты сбросятся через {hours_until_reset} ч." if hours_until_reset else f"⏰ Лимиты сбрасываются каждые {LIMIT_RESET_DAYS} дня."
    if state_type == 'ask':
        commands_text = (
            "📋 <b>Что дальше?</b>\n"
            "/ask — Задать еще вопрос\n"
            "/check — Проверить заявку (PDF)\n"
            "/useful — Полезные материалы\n"
            "/help — Другие команды\n\n"
            f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
            f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
            f"{reset_text}"
        )
    else:
        commands_text = (
            "📋 <b>Что дальше?</b>\n"
            "/ask — Задать вопрос по результатам проверки\n"
            "/check — Проверить другую заявку\n"
            "/useful — Полезные материалы\n"
            "/help — Другие команды\n\n"
            f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
            f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
            f"{reset_text}"
        )
    return message.answer(commands_text, parse_mode="HTML")

@router.message(AskStates.waiting_for_question)
async def handle_non_text_question(message: Message):
    await message.answer("⚠️ Вопрос должен быть текстом. Для отмены отправьте /cancel")

async def send_error_and_commands(message, user_id, context='ask'):
    ask_count, pdf_used = db_service.get_user_limits(user_id)
    await message.answer(
        "⚠️ Произошла ошибка. Попробуйте еще раз или воспользуйтесь одной из команд ниже.",
        parse_mode="HTML"
    )
    await send_what_next(message, ask_count, pdf_used, context)

@router.message(Command("useful"))
async def useful(message: Message):
    user_id = message.from_user.id
    logger.info(f"[USEFUL_DATA] User {user_id} requested useful materials.")
    
    # Add debug message
    print(f"DEBUG: /useful command received from user {user_id}")
    logger.info(f"[USEFUL_DATA] Starting useful handler processing for user {user_id}")
    
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