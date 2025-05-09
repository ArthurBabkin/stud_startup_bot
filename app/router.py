from aiogram import Dispatcher
from app.handlers import user, startup, admin  # Import handlers
import logging

# Add logger
logger = logging.getLogger(__name__)

def register_routers(dp: Dispatcher):
    logger.info("Регистрация роутера startup.router")
    dp.include_router(startup.router)
    
    logger.info("Регистрация роутера admin.router")
    dp.include_router(admin.router)  # Add admin commands

    # Register all routes for the bot
    logger.info("Регистрация роутера user.router")
    dp.include_router(user.router)

    # Output the number of handlers
    logger.info(f"Всего зарегистрировано обработчиков: {len(startup.router.message.handlers) + len(user.router.message.handlers) + len(admin.router.message.handlers)}")
