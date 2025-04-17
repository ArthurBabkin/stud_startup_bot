from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from app.services.db_service import get_message_stats
from aiogram.utils.exceptions import ChatNotFound
from app.config import config

router = Router()

# ID админа, может быть несколько
ADMIN_IDS = [123456789, 987654321]  # Замените на ID ваших администраторов


# Команда для получения статистики
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("У вас нет прав для использования этой команды.")

    total_messages, unique_users = get_message_stats()
    await message.answer(f"Статистика:\nВсего сообщений: {total_messages}\nУникальных пользователей: {unique_users}")


# Команда для рассылки сообщений всем пользователям
@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("У вас нет прав для использования этой команды.")

    # Сохраняем сообщение для рассылки
    broadcast_message = message.text.split(maxsplit=1)
    if len(broadcast_message) < 2:
        return await message.answer("Пожалуйста, укажите текст сообщения.")

    # Отправляем сообщение всем пользователям
    broadcast_text = broadcast_message[1]
    # Получаем всех пользователей из базы данных
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM users')
    users = cursor.fetchall()
    conn.close()

    for user in users:
        try:
            # Отправляем сообщение каждому пользователю
            await message.bot.send_message(user['username'], broadcast_text)
        except ChatNotFound:
            continue  # Если пользователь заблокировал бота

    await message.answer("Сообщение отправлено всем пользователям.")
