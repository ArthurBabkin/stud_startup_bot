from aiogram import Dispatcher
from app.handlers import user, startup, admin  # Импортируем обработчики
import logging

# Добавляем логгер
logger = logging.getLogger(__name__)

def register_routers(dp: Dispatcher):
    logger.info("Регистрация роутера startup.router")
    dp.include_router(startup.router)
    
    logger.info("Регистрация роутера admin.router")
    dp.include_router(admin.router)  # Добавляем админские команды

    # Регистрация всех маршрутов для бота
    logger.info("Регистрация роутера user.router")
    dp.include_router(user.router)

    # Выводим количество обработчиков
    logger.info(f"Всего зарегистрировано обработчиков: {len(startup.router.message.handlers) + len(user.router.message.handlers) + len(admin.router.message.handlers)}")
