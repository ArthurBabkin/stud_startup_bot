from aiogram import Router, Dispatcher
from app.handlers import user, startup, admin

def register_routers(dp: Dispatcher):
    dp.include_router(startup.router)
    dp.include_router(user.router)
    dp.include_router(admin.router)  # Подключаем админские команды
