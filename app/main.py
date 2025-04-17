import asyncio
from aiogram import Bot, Dispatcher
from app.config import config
from app.router import register_routers

async def main():
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()

    register_routers(dp)
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
