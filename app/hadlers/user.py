from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from app.services.openai_service import ask_openai

router = Router()

@router.message()
async def handle_message(message: Message):
    user_input = message.text
    reply = await ask_openai(user_input)
    await message.answer(reply)
