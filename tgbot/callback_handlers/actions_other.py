from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from pathlib import Path
from collections import deque
import shutil
import os

from playerokapi.enums import ItemDealStatuses
from settings import Settings as sett
from core.modules import get_module_by_uuid, get_modules
from tgbot.master_context import get_manager, get_user_manager

AUTO_BONUS_PREFIX = "auto_bonus"
AUTO_BONUS_PRICE = 490.0

from .. import templates as templ
from .. import callback_datas as calls
from .. import states
from ..helpful import throw_float_message
from .navigation import *
from .pagination import (
    callback_included_restore_items_pagination, 
    callback_excluded_restore_items_pagination,
    callback_included_complete_deals_pagination,
    callback_excluded_complete_deals_pagination,
    callback_included_bump_items_pagination,
    callback_excluded_bump_items_pagination,
    callback_deliv_goods_pagination,
)
from .page import callback_module_page


router = Router()


@router.callback_query(F.data == "destroy")
async def callback_back(callback: CallbackQuery):
    await callback.message.delete()


@router.callback_query(calls.DeleteIncludedRestoreItem.filter())
async def callback_delete_included_restore_item(callback: CallbackQuery, callback_data: calls.DeleteIncludedRestoreItem, state: FSMContext):
    try:
        await state.set_state(None)
        index = callback_data.index
        if index is None:
            raise Exception("❌ Включенный преет не был найен, повторте процесс с саого начала")
        
        auto_restore_items = sett.get("auto_restore_items")
        auto_restore_items["included"].pop(index)
        sett.set("auto_restore_items", auto_restore_items)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        return await callback_included_restore_items_pagination(callback, calls.IncludedRestoreItemsPagination(page=last_page), state)
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_restore_included_float_text(e), 
            reply_markup=templ.back_kb(calls.IncludedRestoreItemsPagination(page=last_page).pack())
        )


@router.callback_query(calls.DeleteExcludedRestoreItem.filter())
async def callback_delete_excluded_restore_item(callback: CallbackQuery, callback_data: calls.DeleteExcludedRestoreItem, state: FSMContext):
    try:
        await state.set_state(None)
        index = callback_data.index
        if index is None:
            raise Exception("❌ сключенный преет не был найен, повторте процесс с саого начала")
        
        auto_restore_items = sett.get("auto_restore_items")
        auto_restore_items["excluded"].pop(index)
        sett.set("auto_restore_items", auto_restore_items)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        return await callback_excluded_restore_items_pagination(callback, calls.ExcludedRestoreItemsPagination(page=last_page), state)
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_restore_included_float_text(e), 
            reply_markup=templ.back_kb(calls.IncludedRestoreItemsPagination(page=last_page).pack())
        )


@router.callback_query(calls.DeleteIncludedCompleteDeal.filter())
async def callback_delete_included_complete_deal(callback: CallbackQuery, callback_data: calls.DeleteIncludedCompleteDeal, state: FSMContext):
    try:
        await state.set_state(None)
        index = callback_data.index
        auto_complete_deals = sett.get("auto_complete_deals")
        auto_complete_deals["included"].pop(index)
        sett.set("auto_complete_deals", auto_complete_deals)
        last_page = (await state.get_data()).get("last_page", 0)
        return await callback_included_complete_deals_pagination(callback, calls.IncludedCompleteDealsPagination(page=last_page), state)
    except Exception as e:
        last_page = (await state.get_data()).get("last_page", 0)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.settings_complete_included_float_text(e),
            reply_markup=templ.back_kb(calls.IncludedCompleteDealsPagination(page=last_page).pack())
        )


@router.callback_query(calls.DeleteExcludedCompleteDeal.filter())
async def callback_delete_excluded_complete_deal(callback: CallbackQuery, callback_data: calls.DeleteExcludedCompleteDeal, state: FSMContext):
    try:
        await state.set_state(None)
        index = callback_data.index
        auto_complete_deals = sett.get("auto_complete_deals")
        auto_complete_deals["excluded"].pop(index)
        sett.set("auto_complete_deals", auto_complete_deals)
        last_page = (await state.get_data()).get("last_page", 0)
        return await callback_excluded_complete_deals_pagination(callback, calls.ExcludedCompleteDealsPagination(page=last_page), state)
    except Exception as e:
        last_page = (await state.get_data()).get("last_page", 0)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.settings_complete_excluded_float_text(e),
            reply_markup=templ.back_kb(calls.ExcludedCompleteDealsPagination(page=last_page).pack())
        )


@router.callback_query(calls.DeleteIncludedBumpItem.filter())
async def callback_delete_included_bump_item(callback: CallbackQuery, callback_data: calls.DeleteIncludedBumpItem, state: FSMContext):
    try:
        await state.set_state(None)
        index = callback_data.index
        if index is None:
            raise Exception("❌ Не уалось найт преет, повторте процесс с начала")
        
        auto_bump_items = sett.get("auto_bump_items")
        auto_bump_items["included"].pop(index)
        sett.set("auto_bump_items", auto_bump_items)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        return await callback_included_bump_items_pagination(callback, calls.IncludedBumpItemsPagination(page=last_page), state)
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_bump_included_float_text(e), 
            reply_markup=templ.back_kb(calls.IncludedBumpItemsPagination(page=last_page).pack())
        )


@router.callback_query(calls.DeleteExcludedBumpItem.filter())
async def callback_delete_excluded_bump_item(callback: CallbackQuery, callback_data: calls.DeleteExcludedBumpItem, state: FSMContext):
    try:
        await state.set_state(None)
        index = callback_data.index
        if index is None:
            raise Exception("❌ Не уалось найт преет, повторте процесс с начала")
        
        auto_bump_items = sett.get("auto_bump_items")
        auto_bump_items["excluded"].pop(index)
        sett.set("auto_bump_items", auto_bump_items)

        data = await state.get_data()
        last_page = data.get("last_page", 0)
        return await callback_excluded_bump_items_pagination(callback, calls.ExcludedBumpItemsPagination(page=last_page), state)
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_bump_excluded_float_text(e), 
            reply_markup=templ.back_kb(calls.ExcludedBumpItemsPagination(page=last_page).pack())
        )


@router.callback_query(calls.RememberUsername.filter())
async def callback_remember_username(callback: CallbackQuery, callback_data: calls.RememberUsername, state: FSMContext):
    await state.set_state(None)
    username = callback_data.name
    do = callback_data.do
    await state.update_data(username=username)
    if do == "send_mess":
        await state.set_state(states.ActionsStates.waiting_for_message_content)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.do_action_text(f"💬 Ввете <b>сообщене</b> ля отправк <b>{username}</b> ↓"), 
            reply_markup=templ.destroy_kb(),
            callback=callback,
            send=True
        )


@router.callback_query(calls.RememberDealId.filter())
async def callback_remember_deal_id(callback: CallbackQuery, callback_data: calls.RememberDealId, state: FSMContext):
    await state.set_state(None)
    deal_id = callback_data.de_id
    do = callback_data.do
    await state.update_data(deal_id=deal_id)
    if do == "refund":
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.do_action_text(f'📦✔ Потверте <b>возврат</b> <a href="https://playerok.com/deal/{deal_id}">селк</a> ↓'), 
            reply_markup=templ.confirm_kb(confirm_cb="refund_deal", cancel_cb="destroy"),
            callback=callback,
            send=True
        )
    if do == "complete":
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.do_action_text(f'✔ Потверте <b>выполнене</b> <a href="https://playerok.com/deal/{deal_id}">селк</a> ↓'), 
            reply_markup=templ.confirm_kb(confirm_cb="complete_deal", cancel_cb="destroy"),
            callback=callback,
            send=True
        )


@router.callback_query(calls.SelectBankCard.filter())
async def callback_select_bank_card(callback: CallbackQuery, callback_data: calls.SelectBankCard, state: FSMContext):
    await state.set_state(None)
    card_id = callback_data.id

    config = sett.get("config")
    config["playerok"]["auto_withdrawal"]["credentials_type"] = "card"
    config["playerok"]["auto_withdrawal"]["card_id"] = card_id
    sett.set("config", config)
    
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="withdrawal"), state)


@router.callback_query(calls.SelectSbpBank.filter())
async def callback_select_sbp_bank(callback: CallbackQuery, callback_data: calls.SelectSbpBank, state: FSMContext):
    await state.set_state(None)
    bank_id = callback_data.id

    await state.update_data(sbp_bank_id=bank_id)
    await state.set_state(states.SettingsStates.waiting_for_sbp_bank_phone_number)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_withdrawal_sbp_float_text(f"📲 Ввете <b>ноер телефона</b>, на который нужно бует совершать выво:"), 
        reply_markup=templ.back_kb(calls.SettingsNavigation(to="withdrawal").pack())
    )
        

@router.callback_query(F.data == "refund_deal")
async def callback_refund_deal(callback: CallbackQuery, state: FSMContext):
    from plbot.playerokbot import get_playerok_bot
    await state.set_state(None)
    plbot = get_playerok_bot()
    data = await state.get_data()
    deal_id = data.get("deal_id")
    plbot.playerok_account.update_deal(deal_id, ItemDealStatuses.ROLLED_BACK)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.do_action_text(f"✅ По селке <b>https://playerok.com/deal/{deal_id}</b> был офорлен возврат"), 
        reply_markup=templ.destroy_kb()
    )
        

@router.callback_query(F.data == "complete_deal")
async def callback_complete_deal(callback: CallbackQuery, state: FSMContext):
    from plbot.playerokbot import get_playerok_bot
    await state.set_state(None)
    plbot = get_playerok_bot()
    data = await state.get_data()
    deal_id = data.get("deal_id")
    plbot.playerok_account.update_deal(deal_id, ItemDealStatuses.SENT)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.do_action_text(f"✅ Селка <b>https://playerok.com/deal/{deal_id}</b> была поечена ва, как выполненная"), 
        reply_markup=templ.destroy_kb()
    )


@router.callback_query(F.data == "bump_items")
async def callback_bump_items(callback: CallbackQuery, state: FSMContext):
    try:
        from plbot.playerokbot import get_playerok_bot
        await state.set_state(None)
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.events_float_text(f"⬆ т <b>поняте преетов</b>, ожайте (с. консоль)..."), 
            reply_markup=templ.back_kb(calls.MenuNavigation(to="events").pack())
        )

        get_playerok_bot().bump_items()
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.events_float_text(f"⬆✅ <b>Прееты</b> был успешно поняты"), 
            reply_markup=templ.back_kb(calls.MenuNavigation(to="events").pack())
        )
    except Exception as e:
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.events_float_text(e), 
            reply_markup=templ.back_kb(calls.MenuNavigation(to="events").pack())
        )


@router.callback_query(F.data == "request_withdrawal")
async def callback_request_withdrawal(callback: CallbackQuery, state: FSMContext):
    try:
        from plbot.playerokbot import get_playerok_bot
        await state.set_state(None)
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.events_float_text(f" Созаю <b>транзакцю на выво среств</b>, ожайте (с. консоль)..."), 
            reply_markup=templ.back_kb(calls.MenuNavigation(to="events").pack())
        )

        success = get_playerok_bot().request_withdrawal()
        
        if success:
            await throw_float_message(
                state=state, 
                message=callback.message, 
                text=templ.events_float_text(f"✅ <b>Транзакця на выво среств</b> была успешно созана"), 
                reply_markup=templ.back_kb(calls.MenuNavigation(to="events").pack())
            )
        else:
            await throw_float_message(
                state=state, 
                message=callback.message, 
                text=templ.events_float_text(f"❌ Не уалось созать <b>транзакцю на выво среств</b> (с. консоль на налче ошбок)"), 
                reply_markup=templ.back_kb(calls.MenuNavigation(to="events").pack())
            )
    except Exception as e:
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.events_float_text(e), 
            reply_markup=templ.back_kb(calls.MenuNavigation(to="events").pack())
        )


@router.callback_query(F.data == "clean_fp_proxy")
@router.callback_query(F.data == "clean_pl_proxy")
async def callback_clean_fp_proxy(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["playerok"]["api"]["proxy"] = ""
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="conn"), state)


@router.callback_query(F.data == "clean_tg_proxy")
async def callback_clean_tg_proxy(callback: CallbackQuery, state: FSMContext):
    config = sett.get("config")
    config["telegram"]["api"]["proxy"] = ""
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="conn"), state)


@router.callback_query(F.data == "clean_tg_logging_chat_id")
async def callback_clean_tg_logging_chat_id(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    config = sett.get("config")
    config["playerok"]["tg_logging"]["chat_id"] = ""
    sett.set("config", config)
    return await callback_settings_navigation(callback, calls.SettingsNavigation(to="logger"), state)


@router.callback_query(F.data == "send_new_included_restore_items_keyphrases_file")
async def callback_send_new_included_restore_items_keyphrases_file(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.RestoreItemsStates.waiting_for_new_included_restore_items_keyphrases_file)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_restore_included_float_text(f"📄 Отправьте <b>.txt</b> файл с <b>ключевы фраза</b>, по оной запс в строке (ля кажого товара указываются через запятую, напрер, \"samp аккаунт, со все анны\")"), 
        reply_markup=templ.back_kb(calls.IncludedRestoreItemsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "send_new_excluded_restore_items_keyphrases_file")
async def callback_send_new_excluded_restore_items_keyphrases_file(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.RestoreItemsStates.waiting_for_new_excluded_restore_items_keyphrases_file)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_restore_excluded_float_text(f"📄 Отправьте <b>.txt</b> файл с <b>ключевы фраза</b>, по оной запс в строке (ля кажого товара указываются через запятую, напрер, \"samp аккаунт, со все анны\")"), 
        reply_markup=templ.back_kb(calls.ExcludedRestoreItemsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "send_new_included_complete_deals_keyphrases_file")
async def callback_send_new_included_complete_deals_keyphrases_file(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.CompleteDealsStates.waiting_for_new_included_complete_deals_keyphrases_file)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.settings_new_complete_included_float_text("📄 Отправьте .txt файл с ключевы фраза ля включеня в авто-потвержене."),
        reply_markup=templ.back_kb(calls.IncludedCompleteDealsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "send_new_excluded_complete_deals_keyphrases_file")
async def callback_send_new_excluded_complete_deals_keyphrases_file(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.CompleteDealsStates.waiting_for_new_excluded_complete_deals_keyphrases_file)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=templ.settings_new_complete_excluded_float_text("📄 Отправьте .txt файл с ключевы фраза ля сключеня з авто-потверженя."),
        reply_markup=templ.back_kb(calls.ExcludedCompleteDealsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "send_new_included_bump_items_keyphrases_file")
async def callback_send_new_included_bump_items_keyphrases_file(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.BumpItemsStates.waiting_for_new_included_bump_items_keyphrases_file)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_bump_included_float_text(f"📄 Отправьте <b>.txt</b> файл с <b>ключевы фраза</b>, по оной запс в строке (ля кажого товара указываются через запятую, напрер, \"samp аккаунт, со все анны\")"), 
        reply_markup=templ.back_kb(calls.IncludedBumpItemsPagination(page=last_page).pack())
    )


@router.callback_query(F.data == "send_new_excluded_bump_items_keyphrases_file")
async def callback_send_new_excluded_bump_items_keyphrases_file(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await state.set_state(states.BumpItemsStates.waiting_for_new_excluded_bump_items_keyphrases_file)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.settings_new_bump_excluded_float_text(f"📄 Отправьте <b>.txt</b> файл с <b>ключевы фраза</b>, по оной запс в строке (ля кажого товара указываются через запятую, напрер, \"samp аккаунт, со все анны\")"), 
        reply_markup=templ.back_kb(calls.ExcludedBumpItemsPagination(page=last_page).pack())
    )


@router.callback_query(calls.SetNewDelivPiece.filter())
async def callback_set_new_deliv_piece(callback: CallbackQuery, callback_data: calls.SetNewDelivPiece, state: FSMContext):
    await state.update_data(new_auto_delivery_piece=callback_data.val)
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    if callback_data.val:
        await state.set_state(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_goods)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.settings_new_deliv_goods_float_text("📦 Отправьте товары спско л .txt файло."),
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )
    else:
        await state.set_state(states.AutoDeliveriesStates.waiting_for_new_auto_delivery_message)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.settings_new_deliv_float_text("💬 Ввете сообщене авто-выач."),
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "add_new_custom_command")
async def callback_add_new_custom_command(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        custom_commands = sett.get("custom_commands")
        new_custom_command = data.get("new_custom_command")
        new_custom_command_answer = data.get("new_custom_command_answer")
        if not new_custom_command:
            raise Exception("❌ Новая коана не была найена, повторте процесс с саого начала")
        if not new_custom_command_answer:
            raise Exception("❌ Ответ на новую коану не был найен, повторте процесс с саого начала")

        custom_commands[new_custom_command] = new_custom_command_answer.splitlines()
        sett.set("custom_commands", custom_commands)
        last_page = data.get("last_page", 0)
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_new_comm_float_text(f"✅ <b>Коана</b> <code>{new_custom_command}</code> была обавлена"), 
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_new_comm_float_text(e), 
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "confirm_deleting_custom_command")
async def callback_confirm_deleting_custom_command(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        custom_command = data.get("custom_command")
        if not custom_command:
            raise Exception("❌ Коана не была найена, повторте процесс с саого начала")
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_comm_page_float_text(f" Потверте <b>уалене коаны</b> <code>{custom_command}</code>"), 
            reply_markup=templ.confirm_kb(confirm_cb="delete_custom_command", cancel_cb=calls.CustomCommandPage(command=custom_command).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_comm_page_float_text(e), 
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "delete_custom_command")
async def callback_delete_custom_command(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        custom_commands = sett.get("custom_commands")
        custom_command = data.get("custom_command")
        if not custom_command:
            raise Exception("❌ Коана не была найена, повторте процесс с саого начала")
        
        del custom_commands[custom_command]
        sett.set("custom_commands", custom_commands)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_comm_page_float_text(f"✅ <b>Коана</b> <code>{custom_command}</code> была уалена"), 
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_comm_page_float_text(e), 
            reply_markup=templ.back_kb(calls.CustomCommandsPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "add_new_auto_delivery")
async def callback_add_new_auto_delivery(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        auto_deliveries = sett.get("auto_deliveries")
        new_auto_delivery_keyphrases = data.get("new_auto_delivery_keyphrases")
        new_auto_delivery_piece = data.get("new_auto_delivery_piece")
        new_auto_delivery_message = data.get("new_auto_delivery_message")
        new_auto_delivery_goods = data.get("new_auto_delivery_goods", [])
        if not new_auto_delivery_keyphrases:
            raise Exception("❌ Ключевые фразы авто-выач не был найены, повторте процесс с саого начала")
        if new_auto_delivery_piece is None:
            raise Exception("❌ Тп авто-выач не был выбран")
        if new_auto_delivery_piece and not new_auto_delivery_goods:
            raise Exception("❌ Товары ля поштучной авто-выач не зааны")
        if not new_auto_delivery_piece and not new_auto_delivery_message:
            raise Exception("❌ Сообщене авто-выач не было найено, повторте процесс с саого начала")

        auto_deliveries.append(
            {
                "keyphrases": new_auto_delivery_keyphrases,
                "piece": bool(new_auto_delivery_piece),
                "message": [] if new_auto_delivery_piece else new_auto_delivery_message.splitlines(),
                "goods": list(new_auto_delivery_goods) if new_auto_delivery_piece else [],
            }
        )
        sett.set("auto_deliveries", auto_deliveries)
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_new_deliv_float_text(f"✅ <b>Авто-выача</b> была обавлена"), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_new_deliv_float_text(e), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )



@router.callback_query(F.data == "confirm_deleting_auto_delivery")
async def callback_confirm_deleting_auto_delivery(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        auto_delivery_index = data.get("auto_delivery_index")
        if auto_delivery_index is None:
            raise Exception("❌ Авто-выача не была найена, повторте процесс с саого начала")
        

        auto_deliveries = sett.get("auto_deliveries")
        auto_delivery_keyphrases = "</code>, <code>".join(auto_deliveries[auto_delivery_index]["keyphrases"]) or "❌ Не заано"
       
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(f" Потверте <b>уалене авто-выач</b> ля ключевых фраз <code>{auto_delivery_keyphrases}</code>"), 
            reply_markup=templ.confirm_kb(confirm_cb="delete_auto_delivery", cancel_cb=calls.AutoDeliveryPage(index=auto_delivery_index).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(e), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "delete_auto_delivery")
async def callback_delete_auto_delivery(callback: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        auto_delivery_index = data.get("auto_delivery_index")
        if auto_delivery_index is None:
            raise Exception("❌ Авто-выача не была найена, повторте процесс с саого начала")
        
        auto_deliveries = sett.get("auto_deliveries")
        del auto_deliveries[auto_delivery_index]
        sett.set("auto_deliveries", auto_deliveries)
        last_page = data.get("last_page", 0)
        
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(f"✅ <b>Авто-выача</b> была уалена"), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.settings_deliv_page_float_text(e), 
            reply_markup=templ.back_kb(calls.AutoDeliveriesPagination(page=last_page).pack())
        )


@router.callback_query(calls.DeleteDelivGood.filter())
async def callback_delete_deliv_good(callback: CallbackQuery, callback_data: calls.DeleteDelivGood, state: FSMContext):
    try:
        await state.set_state(None)
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        delivery_index = data.get("auto_delivery_index", 0)
        good_index = callback_data.index

        auto_deliveries = sett.get("auto_deliveries")
        auto_deliveries[delivery_index]["goods"].pop(good_index)
        sett.set("auto_deliveries", auto_deliveries)
        return await callback_deliv_goods_pagination(callback, calls.DelivGoodsPagination(page=last_page), state)
    except Exception as e:
        last_page = (await state.get_data()).get("last_page", 0)
        await throw_float_message(
            state=state,
            message=callback.message,
            text=templ.settings_deliv_goods_float_text(e),
            reply_markup=templ.back_kb(calls.DelivGoodsPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "reload_module")
async def callback_reload_module(callback: CallbackQuery, state: FSMContext):
    from core.modules import reload_module
    try:
        await state.set_state(None)
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        module_uuid = data.get("module_uuid")
        if not module_uuid:
            auto_bonus_module = next((m for m in get_modules() if m.meta.prefix == AUTO_BONUS_PREFIX), None)
            module_uuid = auto_bonus_module.uuid if auto_bonus_module else None
        if not module_uuid:
            raise Exception("❌ UUID оуля не был найен, повторте процесс с саого начала")
        
        await reload_module(module_uuid)
        return await callback_module_page(callback, calls.ModulePage(uuid=module_uuid), state)
    except Exception as e:
        data = await state.get_data()
        last_page = data.get("last_page", 0)
        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.module_page_float_text(e), 
            reply_markup=templ.back_kb(calls.ModulesPagination(page=last_page).pack())
        )


@router.callback_query(F.data == "buy_module")
@router.callback_query(F.data.startswith("buy_module:"))
async def callback_buy_module(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    config = sett.get("config") or {}
    master_username = (config.get("telegram", {}).get("master", {}).get("username") or "RaidexAssist_bot").lstrip("@")
    master_url = f"https://t.me/{master_username}?start=modules_shop"

    kb = InlineKeyboardBuilder()
    kb.button(text="Open Master Bot", url=master_url)
    kb.button(text="Back", callback_data=calls.ModulesPagination(page=last_page).pack())
    kb.adjust(1)
    await throw_float_message(
        state=state,
        message=callback.message,
        text=(
            "     .\n\n"
            "     -.\n"
            "   -    ."
        ),
        reply_markup=kb.as_markup(),
    )
@router.callback_query(F.data == "select_logs_file_lines")
async def callback_select_logs_file_lines(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await throw_float_message(
        state=state, 
        message=callback.message, 
        text=templ.logs_float_text(f"Выберте объ файла:"), 
        reply_markup=templ.logs_file_lines_kb()
    )


@router.callback_query(calls.SendLogsFile.filter())
async def callback_send_logs_file(callback: CallbackQuery, callback_data: calls.SendLogsFile, state: FSMContext):
    await state.set_state(None)
    lines = callback_data.lines
    
    try:
        src_dir = Path(__file__).resolve().parents[2]
        logs_file = os.path.join(src_dir, "logs", "latest.log")
        txt_file = os.path.join(src_dir, "logs", "Лог работы.txt")
        
        if lines > 0:
            with open(logs_file, 'r', encoding='utf-8') as f:
                last_lines = deque(f, lines)
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.writelines(last_lines)
        else:
            shutil.copy(logs_file, txt_file)
        
        await callback.message.answer_document(
            document=FSInputFile(txt_file),
            reply_markup=templ.destroy_kb()
        )
        try: await callback.bot.answer_callback_query(callback.id, cache_time=0)
        except: pass

        await throw_float_message(
            state=state, 
            message=callback.message, 
            text=templ.logs_text(), 
            reply_markup=templ.logs_kb()
        )
    finally:
        try: os.remove(txt_file)
        except: pass


