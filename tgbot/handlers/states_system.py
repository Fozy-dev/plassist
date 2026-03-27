from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from settings import Settings as sett

from .. import states
from .. import templates as templ
from ..helpful import throw_float_message


router = Router()


@router.message(states.SystemStates.waiting_for_password, F.text)
async def handler_waiting_for_password(message: types.Message, state: FSMContext):
    config = sett.get("config")
    expected = config["telegram"]["bot"]["password"]
    provided = (message.text or "").strip()

    if provided != expected:
        await state.set_state(states.SystemStates.waiting_for_password)
        await throw_float_message(
            state=state,
            message=message,
            text="❌ Неверный пароль. Попробуйте ещё раз.",
            reply_markup=templ.destroy_kb(),
        )
        return

    await state.set_state(None)
    if message.from_user.id not in config["telegram"]["bot"]["signed_users"]:
        config["telegram"]["bot"]["signed_users"].append(message.from_user.id)
        sett.set("config", config)

    await throw_float_message(
        state=state,
        message=message,
        text=templ.menu_text(getattr(message.bot, "token", None)),
        reply_markup=templ.menu_kb(),
    )
