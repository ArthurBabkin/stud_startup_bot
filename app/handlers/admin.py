from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from app.services.db_service import get_message_stats
from app.config import config

router = Router()

# Command for getting statistics
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id not in config.admin_ids:
        return await message.answer("У вас нет прав для использования этой команды.")

    total_messages, unique_users = get_message_stats()  # Get statistics
    await message.answer(f"Статистика:\nВсего сообщений: {total_messages}\nУникальных пользователей: {unique_users}")
