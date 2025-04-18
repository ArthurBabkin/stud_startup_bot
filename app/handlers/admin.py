from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from app.services.db_service import get_message_stats

router = Router()

ADMIN_IDS = [123456789, 987654321]  # Список ID администраторов

# Команда для получения статистики
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("У вас нет прав для использования этой команды.")

    total_messages, unique_users = get_message_stats()  # Получаем статистику
    await message.answer(f"Статистика:\nВсего сообщений: {total_messages}\nУникальных пользователей: {unique_users}")
