from app.services.openai_service import ask_openai, ask_deepseek
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from pdfplumber import open as pdf_open
from aiogram.fsm.context import FSMContext
from .states import AskStates, CheckStates    # 👈 наше состояние
from app.services import db_service
from aiogram.filters import StateFilter
from aiogram.fsm.state import default_state
import os
from datetime import datetime

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
    await message.answer("Обрабатываю файл, подождите…")
    user_id = message.from_user.id

    # проверка лимита
    _, pdf_used = db_service.get_user_limits(user_id)
    if pdf_used:
        await message.answer("Вы уже использовали проверку PDF. "
                             "Вы получите новую через 72 часа. "
                             "Или напишите @theother_archeee для получения продвинутого доступа.")
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
    raw_text = extract_text_from_pdf(file_path)
    clean_text = clean_pdf_text(raw_text)

    # 3) спрашиваем Deepseek
    html_answer = await ask_deepseek(clean_text, message)

    # 4) пост‑обработка (удаляем теги, не поддерж. Telegram)
    html_safe = sanitize_html(html_answer)

    await message.answer(html_safe, parse_mode="HTML")
    db_service.mark_pdf_used(user_id)
    await state.clear()

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

# def format_html(response: str) -> str:
#     """Форматируем ответ в HTML-разметку и убираем неподдерживаемые теги"""
#     # Заменяем ** на <b> и другие поддерживаемые теги
#     response = response.replace("**", "<b>").replace("</b>", "</b>")
#     response = response.replace("- ", "<ul><li>").replace("\n", "</li></ul>")
#     response = response.replace("<p>", "").replace("</p>", "")  # Убираем <p> теги
#     return response
#
# def validate_html(html_content: str) -> str:
#     try:
#         tree = html.fromstring(html_content)
#         return html.tostring(tree, pretty_print=True).decode()
#     except (etree.XMLSyntaxError, etree.DocumentInvalid):
#         return "There was an error with the HTML formatting."
#
# def clean_html(response: str) -> str:
#     """Удаляет неподдерживаемые теги и возвращает валидный HTML"""
#     tree = html.fromstring(response)  # Парсим строку HTML
#     # Удаляем все неподдерживаемые теги, например, <p>, <div>
#     for elem in tree.xpath("//p | //div"):  # Удаляем все теги <p> и <div>
#         elem.getparent().remove(elem)
#
#     # Преобразуем обратно в строку
#     cleaned_html = html.tostring(tree, method='html').decode()
#     return cleaned_html


# Обработчик для команды /help
@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "Список доступных команд:\n"
        "/start - Запуск бота\n"
        "/help - Список команд\n"
        "/ask - Задать вопрос\n"
        "/check - Проверить заявку в пдф формате\n"
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
        await message.answer("Действие отменено.\n"
                             "Список доступных команд:\n"
                                "/start - Запуск бота\n"
                                "/help - Список команд\n"
                                "/ask - Задать вопрос\n"
                                "/cancel - Отмена\n"
                                "/check - Проверить заявку в пдф формате\n")
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
    if ask_count >= 5:
        await message.answer("Вы уже использовали все 5 вопросов. "
                             "Ваш лимит обновится через 72 часа. "
                             "Или напишите @theother_archeee для получения продвинутого доступа.")
        return

    await message.answer("Думаю…")
    answer = await ask_openai(text, user_id)
    await message.answer(answer)

    db_service.increment_ask(user_id)
    await state.clear()

# Хендлер на любые другие текстовые сообщения
@router.message(StateFilter(default_state), F.text)
async def fallback_help(message: Message):
    help_text = (
        "📌 Список доступных команд:\n"
        "/start — Запуск бота\n"
        "/help — Справка\n"
        "/ask — Задать вопрос\n"
        "/check — Проверить заявку (PDF)\n"
        "/cancel — Отмена текущего действия\n\n"
        "✉️ Просто выбери нужную команду — я помогу!"
    )
    await message.answer(help_text)

@router.message(CheckStates.waiting_for_pdf)
async def handle_invalid_file(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте именно PDF‑файл заявки.")