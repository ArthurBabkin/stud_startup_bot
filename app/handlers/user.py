from app.services.openai_service import ask_openai, ask_deepseek
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from pdfplumber import open as pdf_open
from aiogram.fsm.context import FSMContext
from .states import AskStates, CheckStates    # 👈 наше состояние
from app.services import db_service
from app.services.db_service import ASK_LIMIT, PDF_LIMIT, LIMIT_RESET_DAYS
from aiogram.filters import StateFilter
from aiogram.fsm.state import default_state
import os
from datetime import datetime
from app.config import config
from app.services.mistral_service import extract_text_with_mistral_ocr

router = Router()


# ───── /check ─────────────────────────────────────────────
@router.message(Command("check"))
async def start_check(message: Message, state: FSMContext):
    await message.answer(
        "Пришлите PDF‑файл заявки одним сообщением. /cancel — отмена"
    )
    await state.set_state(CheckStates.waiting_for_pdf)

# ───── получаем PDF, если ждём его ───────────────────────
@router.message(CheckStates.waiting_for_pdf,
                lambda m: m.document and m.document.mime_type == "application/pdf")
async def process_pdf(message: Message, state: FSMContext):
    # Отправляем промежуточное сообщение о обработке
    processing_msg = await message.answer("Обрабатываю файл, подождите…")
    
    user_id = message.from_user.id

    # проверка лимита
    _, pdf_used = db_service.get_user_limits(user_id)
    if pdf_used >= PDF_LIMIT:
        # Получаем время до сброса
        hours_until_reset = db_service.get_time_until_reset(user_id)
        reset_text = f"через {hours_until_reset} ч" if hours_until_reset else f"через {LIMIT_RESET_DAYS*24} часов."
        
        # Заменяем сообщение о обработке на сообщение о превышении лимита
        await processing_msg.edit_text(f"Вы уже использовали все {PDF_LIMIT} проверки PDF. "
                             f"Ваш лимит обновится {reset_text}. "
                             f"Или напишите @theother_archeee для получения продвинутого доступа.")
        return

    # Создаем директорию для файлов, если её нет
    os.makedirs("application_files", exist_ok=True)
    
    # Формируем уникальное имя файла из ID пользователя и текущей даты/времени
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"id{user_id}_pdf_{current_time}.pdf"
    file_path = os.path.join("application_files", file_name)
    
    # 1) скачиваем
    file = await message.bot.get_file(message.document.file_id)
    pdf_bytes = await message.bot.download_file(file.file_path)
    with open(file_path, "wb") as f:
        f.write(pdf_bytes.getvalue())

    # 2) конвертируем в текст
    if config.use_mistral_ocr:
        # Используем Mistral OCR с резервным механизмом pdfplumber
        raw_text = await extract_text_with_mistral_ocr(file_path)
    else:
        # Используем pdfplumber напрямую
        raw_text = extract_text_from_pdf(file_path)
    
    clean_text = clean_pdf_text(raw_text)

    # 3) спрашиваем Deepseek
    html_answer = await ask_deepseek(clean_text, message)

    # 4) пост‑обработка (удаляем теги, не поддерж. Telegram)
    html_safe = sanitize_html(html_answer)

    # Удаляем промежуточное сообщение
    await processing_msg.delete()
    
    # Разбиваем длинное сообщение на части и отправляем по частям
    message_chunks = split_long_message(html_safe)
    for chunk in message_chunks:
        await message.answer(chunk, parse_mode="HTML")
    
    db_service.mark_pdf_used(user_id)
    await state.clear()
    
    # Показываем доступные команды после проверки PDF
    ask_count, pdf_used = db_service.get_user_limits(user_id)
    ask_remaining = max(0, ASK_LIMIT - ask_count)
    pdf_remaining = max(0, PDF_LIMIT - pdf_used)
    
    # Получаем время до сброса
    hours_until_reset = db_service.get_time_until_reset(user_id)
    reset_text = f"⏰ Лимиты сбросятся через {hours_until_reset} ч." if hours_until_reset else f"⏰ Лимиты сбрасываются каждые {LIMIT_RESET_DAYS} дня."
    
    commands_text = (
        "📋 <b>Что дальше?</b>\n"
        "/ask — Задать вопрос по результатам проверки\n"
        "/check — Проверить другую заявку\n"
        "/help — Другие команды\n\n"
        
        f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
        f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
        
        f"{reset_text}"
    )
    
    await message.answer(commands_text, parse_mode="HTML")

# -------- вспомогательные функции --------
ALLOWED_TAGS = {"b", "i", "blockquote"}

def sanitize_html(text: str) -> str:
    """
    Оставляем только <b>, <i>, <blockquote>.
    Переносы строки — обычный \\n.
    """
    # <ul><li> => • пункт \\n
    text = text.replace("<ul>", "").replace("</ul>", "") \
               .replace("</li>", "\n").replace("<li>", "• ")

    # <p> → двойной перевод строки
    text = text.replace("</p>", "\n\n").replace("<p>", "")

    # <br> → перевод строки
    text = text.replace("<br>", "\n").replace("<br/>", "\n")

    import re
    def _keep(m):
        tag = m.group(1).lower()
        return m.group(0) if tag in ALLOWED_TAGS else ""
    cleaned = re.sub(r"</?([a-zA-Z0-9]+)[^>]*>", _keep, text)

    # телеграм игнорирует множественные подряд \n — можно сжать
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

def extract_text_from_pdf(file_path: str) -> str:
    """Функция для извлечения текста из PDF"""
    with pdf_open(file_path) as pdf:
        text = ''
        for page in pdf.pages:
            text += page.extract_text()  # Извлекаем текст с каждой страницы
    return text

def clean_pdf_text(text: str) -> str:
    """Функция для очистки текста от ненужных разделов"""
    sections_to_remove = ["ДАННЫЕ ОБ УЧАСТНИКЕ", "ОПЫТ ВЗАИМОДЕЙСТВИЯ ЗАЯВИТЕЛЯ С ДРУГИМИ ИНСТИТУТАМИ РАЗВИТИЯ"]
    for section in sections_to_remove:
        text = text.replace(section, "")  # Удаляем указанные разделы
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

# Обработчик для команды /help
@router.message(Command("help"))
async def cmd_help(message: Message):
    user_id = message.from_user.id
    
    # Получаем текущие лимиты пользователя
    ask_count, pdf_used = db_service.get_user_limits(user_id)
    
    # Рассчитываем оставшиеся использования
    ask_remaining = max(0, ASK_LIMIT - ask_count)
    pdf_remaining = max(0, PDF_LIMIT - pdf_used)
    
    # Получаем время до сброса
    hours_until_reset = db_service.get_time_until_reset(user_id)
    
    reset_text = f"⏰ Лимиты сбросятся через {hours_until_reset} ч." if hours_until_reset else f"⏰ Лимиты сбрасываются каждые {LIMIT_RESET_DAYS} дня."
    
    help_text = (
        "📌 Список доступных команд:\n"
        "/start - Запуск бота\n"
        "/help - Список команд\n"
        "/ask - Задать вопрос\n"
        "/check - Проверить заявку в пдф формате\n\n"
        
        f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
        f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
        
        f"{reset_text}"
    )
    await message.answer(help_text)


# ───── /ask ────────────────────────────────────────────────
@router.message(Command("ask"))
async def start_ask(message: Message, state: FSMContext):
    await message.answer("Введите свой вопрос одним сообщением. "
                         "Для отмены отправьте /cancel")
    await state.set_state(AskStates.waiting_for_question)

# ───── отмена ─────────────────────────────────────────────
@router.message(Command("cancel"))
async def cancel_anytime(message: Message, state: FSMContext):
    if await state.get_state():
        await state.clear()
        
        user_id = message.from_user.id
        
        # Получаем текущие лимиты пользователя
        ask_count, pdf_used = db_service.get_user_limits(user_id)
        
        # Рассчитываем оставшиеся использования
        ask_remaining = max(0, ASK_LIMIT - ask_count)
        pdf_remaining = max(0, PDF_LIMIT - pdf_used)
        
        # Получаем время до сброса
        hours_until_reset = db_service.get_time_until_reset(user_id)
        
        reset_text = f"⏰ Лимиты сбросятся через {hours_until_reset} ч." if hours_until_reset else f"⏰ Лимиты сбрасываются каждые {LIMIT_RESET_DAYS} дня."
        
        await message.answer(
            "Действие отменено.\n\n"
            "📌 Список доступных команд:\n"
            "/start - Запуск бота\n"
            "/help - Список команд\n"
            "/ask - Задать вопрос\n"
            "/cancel - Отмена\n"
            "/check - Проверить заявку в пдф формате\n\n"
            
            f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
            f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
            
            f"{reset_text}"
        )
    else:
        await message.answer("Нечего отменять.")

# ───── получаем вопрос пользователя ───────────────────────
@router.message(AskStates.waiting_for_question, F.text)
async def process_question(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()

    # логируем
    db_service.save_message(user_id, text)

    # проверка лимита
    ask_count, _ = db_service.get_user_limits(user_id)
    if ask_count >= ASK_LIMIT:
        # Получаем время до сброса
        hours_until_reset = db_service.get_time_until_reset(user_id)
        reset_text = f"через {hours_until_reset} ч" if hours_until_reset else f"через {LIMIT_RESET_DAYS*24} часов."
        
        await message.answer(f"Вы уже использовали все {ASK_LIMIT} вопросов. "
                             f"Ваш лимит обновится {reset_text}. "
                             f"Или напишите @theother_archeee для получения продвинутого доступа.")
        return

    # Отправляем промежуточное сообщение "Думаю..."
    thinking_msg = await message.answer("Думаю...")
    
    # Получаем ответ от OpenAI
    answer = await ask_openai(text, user_id)
    
    # Редактируем сообщение "Думаю..." на ответ от модели
    await thinking_msg.edit_text(answer)

    # Получаем обновленные лимиты после использования
    db_service.increment_ask(user_id)
    await state.clear()
    
    # Показываем доступные команды после ответа
    ask_count, pdf_used = db_service.get_user_limits(user_id)
    ask_remaining = max(0, ASK_LIMIT - ask_count)
    pdf_remaining = max(0, PDF_LIMIT - pdf_used)
    
    # Получаем время до сброса
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

# Хендлер на любые другие текстовые сообщения
@router.message(StateFilter(default_state), F.text)
async def fallback_help(message: Message):
    user_id = message.from_user.id
    
    # Получаем текущие лимиты пользователя
    ask_count, pdf_used = db_service.get_user_limits(user_id)
    
    # Рассчитываем оставшиеся использования
    ask_remaining = max(0, ASK_LIMIT - ask_count)
    pdf_remaining = max(0, PDF_LIMIT - pdf_used)
    
    # Получаем время до сброса
    hours_until_reset = db_service.get_time_until_reset(user_id)
    
    reset_text = f"⏰ Лимиты сбросятся через {hours_until_reset} ч." if hours_until_reset else f"⏰ Лимиты сбрасываются каждые {LIMIT_RESET_DAYS} дня."
    
    help_text = (
        "📌 Список доступных команд:\n"
        "/start — Запуск бота\n"
        "/help — Справка\n"
        "/ask — Задать вопрос\n"
        "/check — Проверить заявку (PDF)\n"
        "/cancel — Отмена текущего действия\n\n"
        
        f"💬 У вас осталось {ask_remaining} из {ASK_LIMIT} вопросов\n"
        f"📄 У вас осталось {pdf_remaining} из {PDF_LIMIT} проверок PDF\n\n"
        
        f"{reset_text}\n\n"
        
        "✉️ Просто выбери нужную команду — я помогу!"
    )
    await message.answer(help_text)

@router.message(CheckStates.waiting_for_pdf)
async def handle_invalid_file(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте именно PDF‑файл заявки.")