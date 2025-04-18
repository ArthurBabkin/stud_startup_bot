from aiogram import Dispatcher
from app.handlers import user, startup, admin  # Импортируем обработчики

def register_routers(dp: Dispatcher):
    # Регистрация всех маршрутов для бота
    dp.include_router(startup.router)
    dp.include_router(user.router)
    dp.include_router(admin.router)  # Добавляем админские команды
