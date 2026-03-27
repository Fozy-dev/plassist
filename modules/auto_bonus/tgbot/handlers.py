from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, Message

from settings import Settings as sett
from tgbot.helpful import do_auth, throw_float_message

from ..helpers import format_message
from ..states import AutoBonusStates
from ..storage import (
    delete_bonus,
    get_bonus,
    get_bonuses,
    get_config,
    get_messages,
    is_enabled,
    is_owned,
    save_config,
    set_enabled,
    set_message,
    upsert_bonus,
)
from ..templates import (
    bonus_page_kb,
    bonus_page_text,
    bonuses_kb,
    bonuses_text,
    message_page_kb,
    message_page_text,
    messages_kb,
    messages_text,
    menu_kb,
    menu_text,
    prompt_text,
)


router = Router()


async def _is_authorized(message: Message) -> bool:
    config = sett.get("config") or {}
    signed = config.get("telegram", {}).get("bot", {}).get("signed_users", [])
    return message.from_user and message.from_user.id in signed


async def _show_menu(message: Message, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, message, menu_text(), menu_kb())


@router.message(Command("bonus"))
async def command_bonus(message: Message, state: FSMContext):
    if not await _is_authorized(message):
        return await do_auth(message, state)
    if not is_owned():
        return await message.answer("Модуль AutoBonus не подключен к этому боту.")
    await _show_menu(message, state)


@router.callback_query(F.data == "ab_back")
async def callback_ab_back(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, menu_text(), menu_kb(), callback)


@router.callback_query(F.data == "ab_toggle_enabled")
async def callback_ab_toggle_enabled(callback, state: FSMContext):
    await state.set_state(None)
    new_state = not is_enabled()
    set_enabled(new_state)
    await throw_float_message(state, callback.message, menu_text(), menu_kb(), callback)


@router.callback_query(F.data == "ab_messages_menu")
async def callback_ab_messages_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, messages_text(), messages_kb(), callback)


@router.callback_query(F.data == "ab_bonuses_menu")
async def callback_ab_bonuses_menu(callback, state: FSMContext):
    await state.set_state(None)
    await state.update_data(ab_page=0)
    await throw_float_message(state, callback.message, bonuses_text(0), bonuses_kb(0), callback)


@router.callback_query(F.data.startswith("ab_bonuses_page:"))
async def callback_ab_bonuses_page(callback, state: FSMContext):
    await state.set_state(None)
    page = int(callback.data.split(":", 1)[1])
    await state.update_data(ab_page=page)
    await throw_float_message(state, callback.message, bonuses_text(page), bonuses_kb(page), callback)


@router.callback_query(F.data.startswith("ab_message:"))
async def callback_ab_message(callback, state: FSMContext):
    await state.set_state(None)
    message_key = callback.data.split(":", 1)[1]
    await state.update_data(ab_message_key=message_key)
    await state.set_state(AutoBonusStates.waiting_for_message_text)
    await throw_float_message(state, callback.message, message_page_text(message_key), message_page_kb(message_key), callback)


@router.callback_query(F.data == "ab_add_bonus")
async def callback_ab_add_bonus(callback, state: FSMContext):
    await state.set_state(AutoBonusStates.waiting_for_target)
    await state.update_data(ab_mode="create")
    await throw_float_message(
        state,
        callback.message,
        prompt_text("Отправьте название товара или его ID, к которому нужно привязать бонус."),
        callback=callback,
        send=True,
    )


@router.callback_query(F.data.startswith("ab_bonus:"))
async def callback_ab_bonus(callback, state: FSMContext):
    await state.set_state(None)
    bonus_id = callback.data.split(":", 1)[1]
    bonus = get_bonus(bonus_id)
    if not bonus:
        await throw_float_message(state, callback.message, prompt_text("Бонус не найден."), bonuses_kb((await state.get_data()).get("ab_page", 0)), callback)
        return
    await state.update_data(ab_bonus_id=bonus_id, ab_page=(await state.get_data()).get("ab_page", 0))
    await throw_float_message(state, callback.message, bonus_page_text(bonus), bonus_page_kb(bonus_id), callback)


@router.callback_query(F.data.startswith("ab_edit_target:"))
async def callback_ab_edit_target(callback, state: FSMContext):
    await state.set_state(AutoBonusStates.waiting_for_target)
    bonus_id = callback.data.split(":", 1)[1]
    await state.update_data(ab_mode="edit_target", ab_bonus_id=bonus_id)
    bonus = get_bonus(bonus_id)
    await throw_float_message(
        state,
        callback.message,
        prompt_text(
            "Отправьте новое название товара или его ID."
            if bonus
            else "Бонус не найден."
        ),
        bonus_page_kb(bonus_id),
        callback,
        send=True,
    )


@router.callback_query(F.data.startswith("ab_edit_bonus:"))
async def callback_ab_edit_bonus(callback, state: FSMContext):
    await state.set_state(AutoBonusStates.waiting_for_bonus_text)
    bonus_id = callback.data.split(":", 1)[1]
    await state.update_data(ab_mode="edit_bonus", ab_bonus_id=bonus_id)
    bonus = get_bonus(bonus_id)
    await throw_float_message(
        state,
        callback.message,
        prompt_text(
            "Отправьте новый текст бонуса."
            if bonus
            else "Бонус не найден."
        ),
        bonus_page_kb(bonus_id),
        callback,
        send=True,
    )


@router.callback_query(F.data.startswith("ab_delete_bonus:"))
async def callback_ab_delete_bonus(callback, state: FSMContext):
    await state.set_state(None)
    bonus_id = callback.data.split(":", 1)[1]
    delete_bonus(bonus_id)
    page = (await state.get_data()).get("ab_page", 0)
    await throw_float_message(state, callback.message, bonuses_text(page), bonuses_kb(page), callback)


@router.callback_query(F.data == "ab_void")
async def callback_ab_void(callback):
    await callback.answer()


@router.message(AutoBonusStates.waiting_for_target, F.text)
async def message_ab_target(message: Message, state: FSMContext):
    data = await state.get_data()
    mode = data.get("ab_mode")
    target = (message.text or "").strip()
    if not target:
        return await message.answer("Текст не должен быть пустым.")

    if mode == "edit_target":
        bonus_id = data.get("ab_bonus_id")
        bonus = get_bonus(bonus_id) if bonus_id else None
        if not bonus:
            await state.clear()
            return await message.answer("Бонус не найден.")
        upsert_bonus(target, bonus.get("bonus", ""), bonus_id=bonus_id)
        await state.clear()
        return await message.answer(bonus_page_text(get_bonus(bonus_id)), reply_markup=bonus_page_kb(bonus_id), parse_mode="HTML")

    await state.update_data(ab_target=target)
    await state.set_state(AutoBonusStates.waiting_for_bonus_text)
    await message.answer(
        prompt_text("Теперь отправьте текст бонуса, который получит покупатель."),
        parse_mode="HTML",
    )


@router.message(AutoBonusStates.waiting_for_bonus_text, F.text)
async def message_ab_bonus_text(message: Message, state: FSMContext):
    data = await state.get_data()
    mode = data.get("ab_mode")
    text = (message.text or "").strip()
    if not text:
        return await message.answer("Текст не должен быть пустым.")

    if mode == "edit_bonus":
        bonus_id = data.get("ab_bonus_id")
        bonus = get_bonus(bonus_id) if bonus_id else None
        if not bonus:
            await state.clear()
            return await message.answer("Бонус не найден.")
        upsert_bonus(bonus.get("target", ""), text, bonus_id=bonus_id)
        await state.clear()
        updated = get_bonus(bonus_id)
        return await message.answer(
            bonus_page_text(updated),
            reply_markup=bonus_page_kb(bonus_id),
            parse_mode="HTML",
        )

    target = data.get("ab_target")
    if not target:
        await state.clear()
        return await message.answer("Цель бонуса не найдена.")
    bonus = upsert_bonus(target, text)
    await state.clear()
    await message.answer(
        bonus_page_text(bonus),
        reply_markup=bonus_page_kb(bonus["id"]),
        parse_mode="HTML",
    )


@router.message(AutoBonusStates.waiting_for_message_text, F.text)
async def message_ab_message_text(message: Message, state: FSMContext):
    data = await state.get_data()
    message_key = data.get("ab_message_key")
    text = (message.text or "").strip()
    if not message_key:
        await state.clear()
        return await message.answer("Ключ сообщения не найден.")
    if not text:
        return await message.answer("Текст не должен быть пустым.")
    set_message(message_key, text)
    await state.clear()
    await message.answer(
        message_page_text(message_key),
        reply_markup=message_page_kb(message_key),
        parse_mode="HTML",
    )


async def on_telegram_bot_init(telegram_bot):
    for bot in getattr(telegram_bot, "bots", []):
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="/start", description="Главное меню"),
                    BotCommand(command="/bonus", description="Настройки AutoBonus"),
                ]
            )
        except Exception:
            pass


BOT_EVENT_HANDLERS = {
    "ON_TELEGRAM_BOT_INIT": [on_telegram_bot_init],
}
