from aiogram.fsm.state import State, StatesGroup


class StaffActionState(StatesGroup):
    waiting_reply_text = State()
    waiting_comment_text = State()
