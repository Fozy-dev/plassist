from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, Message

from settings import Settings as sett
from tgbot.helpful import do_auth, throw_float_message

from ..helpers import prompt_text
from ..services import service
from ..states import AutoSmmStates
from ..storage import (
    add_domain,
    add_mapping,
    get_allowed_domains,
    get_api_key,
    get_api_url,
    get_mappings,
    is_auto_refund_enabled,
    is_confirm_link_enabled,
    is_enabled,
    is_owned,
    remove_domain,
    remove_mapping,
    set_api_key,
    set_api_url,
    set_auto_refund,
    set_confirm_link,
    set_enabled,
    set_message,
)
from ..templates import domains_kb, domains_text, edit_message_prompt, history_kb, history_text, mappings_kb, mappings_text, menu_kb, menu_text, messages_kb, messages_text


router = Router()


async def _is_authorized(message: Message) -> bool:
    config = sett.get("config") or {}
    signed = config.get("telegram", {}).get("bot", {}).get("signed_users", [])
    return bool(message.from_user and message.from_user.id in signed)


async def _show_menu(message: Message, state: FSMContext):
    await state.set_state(None)
    balance = service.get_balance()
    balance_text = f"{balance:.2f}" if balance is not None else "ошибка"
    await throw_float_message(state, message, menu_text(balance_text), menu_kb())


@router.message(Command("autosmm"))
async def command_autosmm(message: Message, state: FSMContext):
    if not await _is_authorized(message):
        return await do_auth(message, state)
    if not is_owned():
        return await message.answer("Модуль AutoSMM не подключён к этому боту.")
    await _show_menu(message, state)


@router.callback_query(F.data == "asm_back")
async def callback_asm_back(callback, state: FSMContext):
    await _show_menu(callback.message, state)


@router.callback_query(F.data == "asm_toggle_enabled")
async def callback_asm_toggle_enabled(callback, state: FSMContext):
    set_enabled(not is_enabled())
    await _show_menu(callback.message, state)


@router.callback_query(F.data == "asm_toggle_auto_refund")
async def callback_asm_toggle_auto_refund(callback, state: FSMContext):
    set_auto_refund(not is_auto_refund_enabled())
    await _show_menu(callback.message, state)


@router.callback_query(F.data == "asm_toggle_confirm_link")
async def callback_asm_toggle_confirm_link(callback, state: FSMContext):
    set_confirm_link(not is_confirm_link_enabled())
    await _show_menu(callback.message, state)


@router.callback_query(F.data == "asm_edit_api_url")
async def callback_asm_edit_api_url(callback, state: FSMContext):
    await state.update_data(asm_field="api_url")
    await state.set_state(AutoSmmStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text(f"Отправьте API URL.\nТекущий: <code>{get_api_url() or 'не задан'}</code>"), callback=callback, send=True)


@router.callback_query(F.data == "asm_edit_api_key")
async def callback_asm_edit_api_key(callback, state: FSMContext):
    await state.update_data(asm_field="api_key")
    await state.set_state(AutoSmmStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text(f"Отправьте API KEY.\nТекущий: <code>{'задан' if get_api_key() else 'не задан'}</code>"), callback=callback, send=True)


@router.callback_query(F.data == "asm_domains_menu")
async def callback_asm_domains_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, domains_text(), domains_kb(), callback)


@router.callback_query(F.data == "asm_domain_add")
async def callback_asm_domain_add(callback, state: FSMContext):
    await state.update_data(asm_field="domain_add")
    await state.set_state(AutoSmmStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text("Отправьте домен для добавления, например <code>instagram.com</code>."), callback=callback, send=True)


@router.callback_query(F.data == "asm_domain_remove")
async def callback_asm_domain_remove(callback, state: FSMContext):
    current = ", ".join(get_allowed_domains()) or "пусто"
    await state.update_data(asm_field="domain_remove")
    await state.set_state(AutoSmmStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text(f"Отправьте домен для удаления.\nСейчас: <code>{current}</code>"), callback=callback, send=True)


@router.callback_query(F.data == "asm_mappings_menu")
async def callback_asm_mappings_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, mappings_text(), mappings_kb(), callback)


@router.callback_query(F.data == "asm_mapping_add")
async def callback_asm_mapping_add(callback, state: FSMContext):
    await state.update_data(asm_field="mapping_add")
    await state.set_state(AutoSmmStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text("Отправьте маппинг в формате:\n<code>Название | фраза из лота | service_id | quantity</code>"), callback=callback, send=True)


@router.callback_query(F.data == "asm_mapping_remove")
async def callback_asm_mapping_remove(callback, state: FSMContext):
    lines = [f"{idx}. {item.get('name')}" for idx, item in enumerate(get_mappings(), start=1)]
    await state.update_data(asm_field="mapping_remove")
    await state.set_state(AutoSmmStates.waiting_for_text)
    await throw_float_message(state, callback.message, prompt_text("Отправьте номер маппинга для удаления.\n" + ("\n".join(lines) if lines else "Список пуст.")), callback=callback, send=True)


@router.callback_query(F.data == "asm_messages_menu")
async def callback_asm_messages_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, messages_text(), messages_kb(), callback)


@router.callback_query(F.data == "asm_history_menu")
async def callback_asm_history_menu(callback, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(state, callback.message, history_text(), history_kb(), callback)


@router.callback_query(F.data.startswith("asm_message:"))
async def callback_asm_message(callback, state: FSMContext):
    message_key = callback.data.split(":", 1)[1]
    await state.update_data(asm_message_key=message_key)
    await state.set_state(AutoSmmStates.waiting_for_message_text)
    await throw_float_message(state, callback.message, edit_message_prompt(message_key), callback=callback, send=True)


@router.message(AutoSmmStates.waiting_for_text, F.text)
async def message_asm_text(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("asm_field")
    text = (message.text or "").strip()
    if not text:
        return await message.answer("Текст не должен быть пустым.")
    if field == "api_url":
        set_api_url(text)
        await state.clear()
        return await _show_menu(message, state)
    if field == "api_key":
        set_api_key(text)
        await state.clear()
        return await _show_menu(message, state)
    if field == "domain_add":
        add_domain(text)
        await state.clear()
        return await message.answer(domains_text(), reply_markup=domains_kb(), parse_mode="HTML")
    if field == "domain_remove":
        remove_domain(text)
        await state.clear()
        return await message.answer(domains_text(), reply_markup=domains_kb(), parse_mode="HTML")
    if field == "mapping_add":
        parts = [part.strip() for part in text.split("|")]
        if len(parts) != 4:
            return await message.answer("Нужен формат: Название | фраза | service_id | quantity")
        try:
            add_mapping(parts[0], parts[1], int(parts[2]), int(parts[3]))
        except ValueError:
            return await message.answer("service_id и quantity должны быть числами.")
        await state.clear()
        return await message.answer(mappings_text(), reply_markup=mappings_kb(), parse_mode="HTML")
    if field == "mapping_remove":
        try:
            remove_mapping(int(text) - 1)
        except ValueError:
            return await message.answer("Отправьте номер маппинга.")
        await state.clear()
        return await message.answer(mappings_text(), reply_markup=mappings_kb(), parse_mode="HTML")
    await state.clear()
    await message.answer("Поле не найдено.")


@router.message(AutoSmmStates.waiting_for_message_text, F.text)
async def message_asm_message_text(message: Message, state: FSMContext):
    data = await state.get_data()
    message_key = data.get("asm_message_key")
    text = (message.text or "").strip()
    if not message_key:
        await state.clear()
        return await message.answer("Ключ сообщения не найден.")
    if not text:
        return await message.answer("Текст не должен быть пустым.")
    set_message(message_key, text)
    await state.clear()
    await message.answer(messages_text(), reply_markup=messages_kb(), parse_mode="HTML")


async def on_telegram_bot_init(telegram_bot):
    for bot in getattr(telegram_bot, "bots", []):
        try:
            await bot.set_my_commands([
                BotCommand(command="/start", description="Главное меню"),
                BotCommand(command="/autosmm", description="Настройки AutoSMM"),
            ])
        except Exception:
            pass


BOT_EVENT_HANDLERS = {"ON_TELEGRAM_BOT_INIT": [on_telegram_bot_init]}
