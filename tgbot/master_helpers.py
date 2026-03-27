from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest
from core.text_normalizer import fix_mojibake, normalize_reply_markup


async def render_message(target: Message | CallbackQuery, text: str, reply_markup):
    text = fix_mojibake(text)
    reply_markup = normalize_reply_markup(reply_markup)
    if isinstance(target, CallbackQuery):
        message = target.message
        try:
            await target.answer()
        except TelegramBadRequest as exc:
            # Telegram may reject late callback acknowledgements if the query
            # is already expired. The UI update itself can still succeed.
            if "query is too old" not in str(exc).lower() and "query id is invalid" not in str(exc).lower():
                raise
        try:
            return await message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return message
            raise
    return await target.answer(text, reply_markup=reply_markup, parse_mode="HTML")
