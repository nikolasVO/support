from aiogram.fsm.state import State, StatesGroup


class UserTicketState(StatesGroup):
    waiting_description = State()
