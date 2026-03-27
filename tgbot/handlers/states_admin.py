from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.admin_transfer_pay import AdminTransferLedger
from tgbot.master_context import get_partners_manager, get_user_manager
from tgbot.states.all import AdminStates


router = Router()


def _admin_back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Назад", callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()


def _is_admin(message: Message) -> bool:
    from settings import Settings as sett

    admins = sett.get("config")["telegram"]["master"].get("admins", [])
    return message.from_user.id in admins


def _master_bot_username() -> str:
    from settings import Settings as sett

    username = sett.get("config")["telegram"]["master"].get("username")
    return (username or "RaidexAssist_bot").lstrip("@")


async def _notify_full_admins_topup(
    *,
    bot,
    user_id: int,
    username: str | None,
    amount_rub: float,
    provider: str,
    payment_id: str | None = None,
):
    from settings import Settings as sett

    cfg = sett.get("config") or {}
    admin_ids = (((cfg.get("telegram") or {}).get("master") or {}).get("admins") or [])
    if not admin_ids:
        return

    provider_labels = {
        "admin_transfer": "Ручное подтверждение",
        "admin_topup": "Пополнение админом",
    }
    provider_label = provider_labels.get(provider, provider)
    uname = f"@{username}" if username else "-"

    user_manager = get_user_manager()
    full_admin_ids: list[int] = []
    for raw_admin_id in admin_ids:
        try:
            admin_id = int(raw_admin_id)
        except Exception:
            continue
        admin_user = user_manager.get_user(admin_id) or {}
        if (admin_user.get("admin_level") or "full").lower() == "full":
            full_admin_ids.append(admin_id)

    if not full_admin_ids:
        return

    lines = [
        "💰 Новое пополнение баланса",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Пользователь ID: {int(user_id)}",
        f"Username: {uname}",
        f"Сумма: +{float(amount_rub):.2f} ₽",
        f"Метод: {provider_label}",
    ]
    if payment_id:
        lines.append(f"Платёж: {payment_id}")
    text = "\n".join(lines)

    for admin_id in set(full_admin_ids):
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            pass


def _grant_partner_limited_admin(tg_id: int, username: str | None = None):
    config = sett.get("config")
    master = config.setdefault("telegram", {}).setdefault("master", {})
    admins = list(master.get("admins") or [])
    if tg_id not in admins:
        admins.append(int(tg_id))
        master["admins"] = admins
        sett.set("config", config)

    user_manager = get_user_manager()
    user = user_manager.get_user(int(tg_id))
    if not user:
        user_manager.ensure_user(int(tg_id), (username or "").lstrip("@") or None, "")
    user_manager.update_user(int(tg_id), admin_level="limited")


@router.message(AdminStates.WAITING_TOPUP_AMOUNT, F.text)
async def handle_admin_topup_amount(message: Message, state: FSMContext):
    if not _is_admin(message):
        await state.clear()
        return
    raw = (message.text or "").strip().replace(",", ".")
    try:
        amount = float(raw)
    except ValueError:
        return await message.answer("Введите корректное число, например 250")
    if amount < 0:
        return await message.answer("Сумма должна быть не меньше 0.")

    data = await state.get_data()
    user_id = int(data.get("admin_target_user_id", 0))
    user_manager = get_user_manager()
    current = user_manager.get_user(user_id)
    if not current:
        await state.clear()
        return await message.answer("Пользователь не найден.", reply_markup=_admin_back_kb())

    before = float(current.get("balance", 0.0))
    user = user_manager.set_balance(user_id, amount)
    after = float(user.get("balance", 0.0))
    delta = round(after - before, 2)

    user_manager.log_action("admin", "set_balance", f"{before:.2f} -> {after:.2f} ({user_id})")
    await state.clear()

    await message.answer(
        "✅ Баланс установлен\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Пользователь: {user.get('username') or user_id}\n"
        f"Было: {before:.2f} ₽\n"
        f"Стало: {after:.2f} ₽\n"
        f"Изменение: {delta:+.2f} ₽",
        reply_markup=_admin_back_kb(),
    )
    try:
        await message.bot.send_message(
            user_id,
            "💰 Администратор изменил ваш баланс.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Было: {before:.2f} ₽\n"
            f"Стало: {after:.2f} ₽",
        )
    except Exception:
        pass


@router.message(AdminStates.WAITING_BROADCAST_TEXT, F.text)
async def handle_admin_broadcast_text(message: Message, state: FSMContext):
    if not _is_admin(message):
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        return await message.answer("Текст не должен быть пустым.")
    data = await state.get_data()
    audience = data.get("broadcast_audience", "all")

    user_manager = get_user_manager()
    users = list(user_manager.all_users().values())
    if audience == "active7":
        border = datetime.now() - timedelta(days=7)
        users = [u for u in users if u.get("last_active") and datetime.fromisoformat(u["last_active"]) >= border]
    elif audience == "tariff":
        users = [u for u in users if user_manager.has_active_tariff(int(u["tg_id"]))]
    elif audience == "no_tariff":
        users = [u for u in users if not user_manager.has_active_tariff(int(u["tg_id"]))]

    sent = 0
    failed = 0
    for user in users:
        try:
            await message.bot.send_message(int(user["tg_id"]), text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    user_manager.log_action("admin", "broadcast", f"{audience}:{sent}/{len(users)}")
    await state.clear()
    await message.answer(
        "✅ Рассылка завершена!\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Отправлено успешно: {sent}\n"
        f"Ошибок: {failed}\n"
        f"Всего получателей: {len(users)}",
        reply_markup=_admin_back_kb(),
    )


@router.message(AdminStates.WAITING_PARTNER_NICK, F.text)
async def handle_partner_nick(message: Message, state: FSMContext):
    if not _is_admin(message):
        await state.clear()
        return
    nickname = (message.text or "").strip().lstrip("@")
    if not nickname or any(ch.isspace() for ch in nickname):
        return await message.answer("Введите ник без @ и без пробелов.")
    if get_partners_manager().get_by_slug(nickname):
        return await message.answer("Партнёр с таким ником уже существует.")

    await state.set_state(AdminStates.WAITING_PARTNER_USERNAME)
    await state.update_data(partner_nickname=nickname)
    await message.answer(
        "📨 Username для связи\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Ник партнёра: {nickname}\n\n"
        "Отправьте Telegram username партнёра (можно с @).",
        reply_markup=_admin_back_kb(),
    )


@router.message(AdminStates.WAITING_PARTNER_USERNAME, F.text)
async def handle_partner_username(message: Message, state: FSMContext):
    if not _is_admin(message):
        await state.clear()
        return
    raw_username = (message.text or "").strip()
    username = raw_username.lstrip("@")
    if not username or any(ch.isspace() for ch in username):
        return await message.answer("Введите корректный username, например @partner_name")

    data = await state.get_data()
    nickname = (data.get("partner_nickname") or "").strip()
    try:
        partner = get_partners_manager().create_partner(
            nickname=nickname,
            bot_username=_master_bot_username(),
            tg_id=None,
            username=username,
        )
    except ValueError:
        return await message.answer("Партнёр с таким ником уже существует.")

    await state.clear()
    await message.answer(
        "✅ Партнёр создан\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Ник: {partner['nickname']}\n"
        f"Username: {partner.get('username') or '-'}\n"
        f"Telegram ID: {partner.get('tg_id') or '-'}\n"
        f"Ссылка: {partner['referral_link']}",
        reply_markup=_admin_back_kb(),
    )


@router.message(AdminStates.WAITING_PARTNER_TG_ID, F.text)
async def handle_partner_tg_id(message: Message, state: FSMContext):
    if not _is_admin(message):
        await state.clear()
        return
    raw = (message.text or "").strip()
    if raw.lower() in {"очистить", "clear", "-", "none"}:
        new_id = None
    else:
        if not raw.lstrip("-").isdigit():
            return await message.answer("Введите числовой Telegram ID или 'очистить'.")
        new_id = int(raw)

    partner_id = (await state.get_data()).get("partner_id")
    partner = get_partners_manager().update_partner(partner_id, tg_id=new_id)
    if not partner:
        await state.clear()
        return await message.answer("Партнёр не найден.", reply_markup=_admin_back_kb())

    if new_id is not None:
        _grant_partner_limited_admin(new_id, partner.get("username"))

    await state.clear()
    await message.answer(
        "✅ Telegram ID обновлён\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Партнёр: {partner['nickname']}\n"
        f"Telegram ID: {partner.get('tg_id') or '-'}\n"
        f"Доступ к /admin: {'ограниченный' if new_id is not None else 'не выдан'}",
        reply_markup=_admin_back_kb(),
    )


@router.message(AdminStates.WAITING_PARTNER_PERCENT, F.text)
async def handle_partner_percent(message: Message, state: FSMContext):
    if not _is_admin(message):
        await state.clear()
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        return await message.answer("Введите целое число от 1 до 99.")
    percent = int(raw)
    if percent < 1 or percent > 99:
        return await message.answer("Процент должен быть от 1 до 99.")
    partner_id = (await state.get_data()).get("partner_id")
    partner = get_partners_manager().set_percent(partner_id, percent)
    if not partner:
        await state.clear()
        return await message.answer("Партнёр не найден.", reply_markup=_admin_back_kb())
    await state.clear()
    await message.answer(
        f"✅ Процент партнёра обновлён: {percent}%",
        reply_markup=_admin_back_kb(),
    )


@router.message(AdminStates.WAITING_PARTNER_PAYOUT, F.text)
async def handle_partner_payout(message: Message, state: FSMContext):
    if not _is_admin(message):
        await state.clear()
        return
    raw = (message.text or "").strip().replace(",", ".")
    try:
        amount = float(raw)
    except ValueError:
        return await message.answer("Введите корректную сумму, например 500")
    if amount <= 0:
        return await message.answer("Сумма должна быть больше 0.")
    partner_id = (await state.get_data()).get("partner_id")
    partners_manager = get_partners_manager()
    partner = partners_manager.get_by_id(partner_id)
    if not partner:
        await state.clear()
        return await message.answer("Партнёр не найден.", reply_markup=_admin_back_kb())
    available = partners_manager.available_balance(partner)
    if amount > available:
        return await message.answer(f"Недоступно для выплаты. Сейчас доступно: {available:.2f} ₽")
    partner = partners_manager.add_manual_payout(partner_id, amount)
    await state.clear()
    await message.answer(
        "✅ Выплата сохранена\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Партнёр: {partner['nickname']}\n"
        f"Сумма: {amount:.2f} ₽\n"
        f"Выплачено всего: {float(partner.get('total_paid_out', 0)):.2f} ₽",
        reply_markup=_admin_back_kb(),
    )


@router.message(AdminStates.WAITING_TRANSFER_REJECT_REASON, F.text)
async def handle_admin_transfer_reject_reason(message: Message, state: FSMContext):
    if not _is_admin(message):
        await state.clear()
        return
    reason = (message.text or "").strip()
    if not reason:
        return await message.answer("Введите причину отклонения.")

    data = await state.get_data()
    order_id = str(data.get("admin_transfer_order_id") or "")
    order = AdminTransferLedger.get(order_id)
    if not order:
        await state.clear()
        return await message.answer("Заказ не найден.", reply_markup=_admin_back_kb())
    if str(order.get("status")) in {"успешно", "отклонён"}:
        await state.clear()
        return await message.answer("Заказ уже обработан.", reply_markup=_admin_back_kb())

    updated = AdminTransferLedger.reject(order_id, reason=reason, admin_id=message.from_user.id)
    await state.clear()
    if not updated:
        return await message.answer("Не удалось отклонить заказ.", reply_markup=_admin_back_kb())

    get_user_manager().log_action("admin", "topup_admin_reject", f"{order_id}: {reason}")
    await message.answer(
        f"❌ Заказ {order_id} отклонён.",
        reply_markup=_admin_back_kb(),
    )
    try:
        await message.bot.send_message(
            int(updated["user_id"]),
            "Оплата отклонена ❌\n"
            f"Причина: {reason}",
        )
    except Exception:
        pass


@router.message(AdminStates.WAITING_TRANSFER_CONFIRM_AMOUNT, F.text)
async def handle_admin_transfer_confirm_amount(message: Message, state: FSMContext):
    if not _is_admin(message):
        await state.clear()
        return
    raw = (message.text or "").strip().replace(",", ".")
    try:
        amount = float(raw)
    except ValueError:
        return await message.answer("Введите сумму числом, например 250")
    if amount <= 0:
        return await message.answer("Сумма должна быть больше 0.")

    data = await state.get_data()
    order_id = str(data.get("admin_transfer_order_id") or "")
    order = AdminTransferLedger.get(order_id)
    if not order:
        await state.clear()
        return await message.answer("Заказ не найден.", reply_markup=_admin_back_kb())
    if str(order.get("status")) in {"успешно", "отклонён"}:
        await state.clear()
        return await message.answer("Заказ уже обработан.", reply_markup=_admin_back_kb())

    user_id = int(order.get("user_id", 0))
    user = get_user_manager().get_user(user_id)
    if not user:
        await state.clear()
        return await message.answer("Пользователь не найден.", reply_markup=_admin_back_kb())

    user = get_user_manager().add_balance(user_id, amount)
    updated = AdminTransferLedger.confirm(order_id, credited_amount=amount, admin_id=message.from_user.id)
    await state.clear()
    if not updated:
        return await message.answer("Не удалось подтвердить заказ.", reply_markup=_admin_back_kb())

    get_user_manager().log_action("admin", "topup_admin_confirm", f"{order_id}: +{amount:.2f}")
    await _notify_full_admins_topup(
        bot=message.bot,
        user_id=user_id,
        username=user.get("username"),
        amount_rub=amount,
        provider="admin_transfer",
        payment_id=order_id,
    )
    await message.answer(
        "✅ Пополнение подтверждено\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"ID заказа: {order_id}\n"
        f"Начислено: {amount:.2f} ₽\n"
        f"Пользователь: {user.get('username') or user_id}",
        reply_markup=_admin_back_kb(),
    )
    try:
        await message.bot.send_message(
            user_id,
            "Пополнение успешно ✅\n"
            f"Зачислено: {amount:.2f} руб.",
        )
    except Exception:
        pass

