# app/handlers/states.py  (новый файл)
from aiogram.fsm.state import StatesGroup, State

class AskStates(StatesGroup):
    waiting_for_question = State()

class CheckStates(StatesGroup):
    waiting_for_pdf = State()