from aiogram.fsm.state import StatesGroup, State

class AskStates(StatesGroup):
    waiting_for_question = State()

class CheckStates(StatesGroup):
    waiting_for_pdf = State()

class FeedbackStates(StatesGroup):
    waiting_for_feedback_decision = State()
    waiting_for_feedback_text = State()