import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from app.config import config
from app.router import register_routers
from app.services.db_service import init_db


async def main():
    init_db()                                  # ← создаём таблицы

    bot = Bot(token=config.bot_token)
    dp  = Dispatcher(storage=MemoryStorage())  # FSM для /ask

    register_routers(dp)

    print("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())