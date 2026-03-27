from __future__ import annotations

import json
import math
import os
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, LabeledPrice, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.admin_transfer_pay import AdminTransferLedger
from core.cryptobot_pay import CryptoBotClient, CryptoBotError, CryptoLedger
from core.cryptomus_pay import CryptomusClient, CryptomusError, CryptomusLedger
from core.freekassa import FreeKassaClient, FreeKassaError, PaymentLedger
from core.lava_pay import LavaClient, LavaError, LavaLedger
from core.telegram_stars_pay import TelegramStarsLedger
from messages import master as master_messages
from core.utils import (
    is_golden_key_valid,
    is_password_valid,
    is_proxy_valid,
    is_tg_token_valid,
    is_token_valid,
    is_user_agent_valid,
)
from settings import Settings as sett
from tgbot.master_context import get_manager, get_user_manager
from tgbot.states.all import (
    AccountSettingsStates,
    PaymentStates,
    CreateBotStates,
    CustomizationStates,
    ProxyStates,
    UpdateTokenStates,
)
from tgbot.templates.constructor import (
    get_cancel_kb,
    get_main_menu_kb,
    get_main_menu_text,
    get_skip_kb,
    get_step_text,
    get_success_kb,
    get_success_text,
)


router = Router()
_BTN_STYLE_SUPPORTED = "style" in getattr(InlineKeyboardButton, "model_fields", {})


def _master_msg(name: str, default: str = "") -> str:
    return str(getattr(master_messages, name, default))


def _master_render(name: str, default: str = "", **kwargs) -> str:
    template = _master_msg(name, default)
    try:
        return template.format(**kwargs) if kwargs else template
    except Exception:
        return template


def _kb_button(kb: InlineKeyboardBuilder, *, text: str, callback_data: str | None = None, url: str | None = None, style: str | None = None):
    kwargs = {"text": text}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    if style and _BTN_STYLE_SUPPORTED:
        kwargs["style"] = style
    kb.button(**kwargs)


def _total_steps(chosen: list[str]) -> int:
    total = 1  # final password
    if "playerok" in chosen:
        total += 4
    if "funpay" in chosen:
        total += 4
    return total


def _freekassa_config() -> dict:
    cfg = sett.get("config") or {}
    return ((cfg.get("payments") or {}).get("freekassa") or {})


def _cryptobot_config() -> dict:
    cfg = sett.get("config") or {}
    return ((cfg.get("payments") or {}).get("cryptobot") or {})


def _cryptomus_config() -> dict:
    cfg = sett.get("config") or {}
    return ((cfg.get("payments") or {}).get("cryptomus") or {})


def _lava_config() -> dict:
    cfg = sett.get("config") or {}
    return ((cfg.get("payments") or {}).get("lava") or {})


def _telegram_stars_config() -> dict:
    cfg = sett.get("config") or {}
    return ((cfg.get("payments") or {}).get("telegram_stars") or {})


def _invoice_kb(pay_url: str, payment_id: str):
    kb = InlineKeyboardBuilder()
    _kb_button(kb, text="💳 Оплатить", url=pay_url, style="success")
    _kb_button(kb, text="🔄 Проверить оплату", callback_data=f"topup_fk_check:{payment_id}", style="primary")
    _kb_button(kb, text="➕ Новый счёт", callback_data="topup_menu")
    _kb_button(kb, text="◀️ Главное меню", callback_data="back_to_main", style="danger")
    kb.adjust(1)
    return kb.as_markup()


def _admin_transfer_invoice_kb(order_id: str):
    kb = InlineKeyboardBuilder()
    _kb_button(kb, text="✅ Я оплатил", callback_data=f"topup_admin_paid:{order_id}", style="success")
    _kb_button(kb, text="◀️ Главное меню", callback_data="back_to_main", style="danger")
    kb.adjust(1)
    return kb.as_markup()


def _admin_transfer_review_kb(order_id: str):
    kb = InlineKeyboardBuilder()
    _kb_button(kb, text="✅ Подтвердить", callback_data=f"topup_admin_confirm:{order_id}", style="success")
    _kb_button(kb, text="❌ Отклонить", callback_data=f"topup_admin_reject:{order_id}", style="danger")
    kb.adjust(1)
    return kb.as_markup()


async def _ask_password_step(message: Message, state: FSMContext):
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    total = _total_steps(chosen)
    await state.set_state(CreateBotStates.WAITING_PASSWORD)
    await message.answer(
        get_step_text(
            total,
            total,
            f"🔐 Шаг {total} из {total} — Пароль (общий для всех платформ)",
            "Введите пароль (6-64 символа). Владелец входит без пароля, для остальных он обязателен.",
            "MyBot_2026!",
        ),
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )


@router.message(PaymentStates.WAITING_TOPUP_CUSTOM_AMOUNT, F.text)
async def handle_topup_custom_amount(message: Message, state: FSMContext):
    raw = (message.text or "").strip().replace(",", ".")
    try:
        amount = float(raw)
    except ValueError:
        return await message.answer("Введите сумму числом. Пример: 250")
    if amount < 80:
        return await message.answer("Минимальная сумма пополнения: 80 ₽")

    data = await state.get_data()
    provider = (data.get("payment_provider") or "freekassa").strip().lower()
    payment_id = PaymentLedger.make_payment_id(message.from_user.id)

    if provider == "telegram_stars":
        stars_cfg = _telegram_stars_config()
        if stars_cfg and not stars_cfg.get("enabled", True):
            await state.clear()
            return await message.answer("⭐ Оплата Telegram Stars сейчас выключена администратором.")
        rate = float(stars_cfg.get("stars_per_rub") or stars_cfg.get("rub_per_star") or 1.9)
        if rate <= 0:
            rate = 1.9
        stars_amount = max(1, int(math.ceil(amount * rate)))
        credited_rub = round(float(amount), 2)
        payment_id = TelegramStarsLedger.make_payment_id(message.from_user.id)
        payload = f"stars_topup:{payment_id}"
        TelegramStarsLedger.create(
            payment_id=payment_id,
            user_id=message.from_user.id,
            amount_rub=credited_rub,
            requested_amount_rub=amount,
            stars_amount=stars_amount,
            rate=rate,
        )
        try:
            await message.bot.send_invoice(
                chat_id=message.from_user.id,
                title="Пополнение баланса",
                description=(
                    f"К зачислению: {credited_rub:.2f} ₽\n"
                    f"К оплате: {stars_amount} ⭐\n"
                    f"Курс: 1 ₽ = {rate:.2f} ⭐"
                ),
                payload=payload,
                currency="XTR",
                prices=[LabeledPrice(label=_master_render("TOPUP_STARS_INVOICE_LABEL", "Пополнение баланса ({stars_amount} ⭐)", stars_amount=stars_amount), amount=stars_amount)],
            )
        except Exception as e:
            await state.clear()
            return await message.answer(
                "❌ Не удалось создать счёт Telegram Stars\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{e}",
            )
        await state.clear()
        get_user_manager().log_action(message.from_user.username or str(message.from_user.id), "topup_invoice_stars", payment_id)
        return await message.answer(
            "🧾 Счёт создан (Telegram Stars)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"К оплате: {stars_amount} ⭐\n"
            f"Будет зачислено: +{credited_rub:.2f} ₽\n"
            f"Номер платежа: <code>{payment_id}</code>\n\n"
            "Оплатите счёт во всплывающем окне Telegram.",
            parse_mode="HTML",
        )

    if provider == "admin_transfer":
        order = AdminTransferLedger.create(user_id=message.from_user.id, amount=amount)
        order_id = str(order["order_id"])
        await state.clear()
        get_user_manager().log_action(message.from_user.username or str(message.from_user.id), "topup_invoice_admin_transfer", order_id)
        return await message.answer(
            "Отправьте сумму на:\n"
            "+79964091244 (Альфа-Банк)\n\n"
            f"В комментариях укажите номер заказа: <code>{order_id}</code>\n\n"
            "После оплаты:\n"
            "- нажмите на \"Я оплатил\"\n"
            "- следуйте инструкции в чате",
            reply_markup=_admin_transfer_invoice_kb(order_id),
            parse_mode="HTML",
        )

    if provider == "lava":
        lv_cfg = _lava_config()
        if not lv_cfg.get("enabled"):
            await state.clear()
            return await message.answer("LAVA сейчас выключена администратором.")
        signature = (lv_cfg.get("api_token") or "").strip()
        shop_id = str(lv_cfg.get("shop_id") or "").strip()
        if not signature:
            await state.clear()
            return await message.answer("Не задан токен/подпись LAVA. Обратитесь к администратору.")
        if not shop_id:
            await state.clear()
            return await message.answer("Не задан shop_id LAVA. Обратитесь к администратору.")

        client = LavaClient(signature=signature, timeout=int(lv_cfg.get("timeout") or 20))
        payment_id = LavaLedger.make_payment_id(message.from_user.id)
        order_id = f"tg_{message.from_user.id}_{payment_id[-8:]}"
        try:
            response = await client.create_invoice(
                amount_rub=amount,
                order_id=order_id,
                shop_id=shop_id,
                comment=f"Пополнение баланса {message.from_user.id}",
            )
        except LavaError as e:
            await state.clear()
            return await message.answer(
                "❌ Не удалось создать счёт LAVA\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{e}",
            )
        invoice = (response or {}).get("data") or {}
        pay_url = str(invoice.get("url") or "")
        if not pay_url:
            await state.clear()
            return await message.answer("❌ LAVA не вернула ссылку на оплату.")
        invoice_id = invoice.get("id")
        LavaLedger.create(
            payment_id=payment_id,
            user_id=message.from_user.id,
            amount=amount,
            shop_id=shop_id,
            order_id=order_id,
            invoice_id=str(invoice_id) if invoice_id else None,
            pay_url=pay_url,
        )
        await state.clear()
        get_user_manager().log_action(message.from_user.username or str(message.from_user.id), "topup_invoice_lava", payment_id)
        kb = InlineKeyboardBuilder()
        _kb_button(kb, text="💳 Оплатить", url=pay_url, style="success")
        _kb_button(kb, text="🔄 Проверить оплату", callback_data=f"topup_lv_check:{payment_id}", style="primary")
        _kb_button(kb, text="➕ Новый счёт", callback_data="topup_menu")
        _kb_button(kb, text="◀️ Главное меню", callback_data="back_to_main", style="danger")
        kb.adjust(1)
        return await message.answer(
            "🧾 Счёт создан (LAVA)\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Сумма: {amount:.2f} ₽\n"
            f"Номер платежа: <code>{payment_id}</code>\n\n"
            "1) Нажмите «Оплатить»\n"
            "2) После оплаты нажмите «Проверить оплату»",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

    if provider == "cryptobot":
        cb_cfg = _cryptobot_config()
        if not cb_cfg.get("enabled"):
            await state.clear()
            return await message.answer("CryptoBot сейчас выключен администратором.")
        token = (cb_cfg.get("api_token") or "").strip()
        if not token:
            await state.clear()
            return await message.answer("Не задан API-токен CryptoBot. Обратитесь к администратору.")

        client = CryptoBotClient(api_token=token, timeout=int(cb_cfg.get("timeout") or 20))
        try:
            invoice = await client.create_invoice(
                amount_rub=amount,
                description=f"Пополнение баланса {message.from_user.id}",
            )
        except CryptoBotError as e:
            await state.clear()
            return await message.answer(
                "❌ Не удалось создать счёт CryptoBot\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{e}",
            )

        pay_url = invoice.get("bot_invoice_url") or invoice.get("pay_url")
        invoice_id = int(invoice.get("invoice_id"))
        CryptoLedger.create(
            payment_id=payment_id,
            user_id=message.from_user.id,
            amount=amount,
            invoice_id=invoice_id,
            pay_url=pay_url,
        )
        await state.clear()
        get_user_manager().log_action(message.from_user.username or str(message.from_user.id), "topup_invoice_cb", payment_id)
        kb = InlineKeyboardBuilder()
        _kb_button(kb, text="💳 Оплатить", url=pay_url, style="success")
        _kb_button(kb, text="🔄 Проверить оплату", callback_data=f"topup_cb_check:{payment_id}", style="primary")
        _kb_button(kb, text="➕ Новый счёт", callback_data="topup_menu")
        _kb_button(kb, text="◀️ Главное меню", callback_data="back_to_main", style="danger")
        kb.adjust(1)
        return await message.answer(
            "🧾 Счёт создан (CryptoBot)\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Сумма: {amount:.2f} ₽\n"
            f"Номер платежа: <code>{payment_id}</code>\n\n"
            "1) Нажмите «Оплатить»\n"
            "2) После оплаты нажмите «Проверить оплату»",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

    if provider == "cryptomus":
        cm_cfg = _cryptomus_config()
        if not cm_cfg.get("enabled"):
            await state.clear()
            return await message.answer("Cryptomus сейчас выключен администратором.")
        merchant_id = (cm_cfg.get("merchant_id") or "").strip()
        api_key = (cm_cfg.get("api_key") or "").strip()
        if not merchant_id:
            await state.clear()
            return await message.answer(
                "Не задан merchant_id Cryptomus.\n"
                "Заполните payments.cryptomus.merchant_id в bot_settings/config.json"
            )
        if not api_key:
            await state.clear()
            return await message.answer("Не задан API key Cryptomus. Обратитесь к администратору.")
        client = CryptomusClient(
            merchant_id=merchant_id,
            api_key=api_key,
            timeout=int(cm_cfg.get("timeout") or 20),
        )
        order_id = f"tg_{message.from_user.id}_{payment_id[-8:]}"
        try:
            invoice = await client.create_invoice(amount_rub=amount, order_id=order_id)
        except CryptomusError as e:
            await state.clear()
            return await message.answer(
                "❌ Не удалось создать счёт Cryptomus\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{e}",
            )
        pay_url = invoice.get("url") or ""
        CryptomusLedger.create(
            payment_id=payment_id,
            user_id=message.from_user.id,
            amount=amount,
            order_id=order_id,
            invoice_uuid=invoice.get("uuid"),
            pay_url=pay_url,
        )
        await state.clear()
        get_user_manager().log_action(message.from_user.username or str(message.from_user.id), "topup_invoice_cm", payment_id)
        kb = InlineKeyboardBuilder()
        _kb_button(kb, text="💳 Оплатить", url=pay_url, style="success")
        _kb_button(kb, text="🔄 Проверить оплату", callback_data=f"topup_cm_check:{payment_id}", style="primary")
        _kb_button(kb, text="➕ Новый счёт", callback_data="topup_menu")
        _kb_button(kb, text="◀️ Главное меню", callback_data="back_to_main", style="danger")
        kb.adjust(1)
        return await message.answer(
            "🧾 Счёт создан (Cryptomus)\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Сумма: {amount:.2f} ₽\n"
            f"Номер платежа: <code>{payment_id}</code>\n\n"
            "1) Нажмите «Оплатить»\n"
            "2) После оплаты нажмите «Проверить оплату»",
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )

    fk_cfg = _freekassa_config()
    if not fk_cfg.get("enabled"):
        await state.clear()
        return await message.answer("FreeKassa сейчас выключена администратором.")
    api_key = (fk_cfg.get("api_key") or "").strip()
    if not api_key:
        await state.clear()
        return await message.answer("Не задан API-ключ FreeKassa. Обратитесь к администратору.")

    client = FreeKassaClient(
        api_key=api_key,
        shop_id=int(fk_cfg.get("shop_id") or 0),
        timeout=int(fk_cfg.get("timeout") or 20),
    )
    try:
        checkout_mode = str(fk_cfg.get("checkout_mode") or "auto").strip().lower()
        secret_word_1 = str(fk_cfg.get("secret_word_1") or "").strip()
        if checkout_mode == "sci" and not secret_word_1:
            raise FreeKassaError("Для SCI-оплаты нужно заполнить payments.freekassa.secret_word_1")
        use_sci = checkout_mode == "sci" or (checkout_mode == "auto" and bool(secret_word_1))
        if use_sci:
            email_local = f"tg{int(message.from_user.id)}_{int(datetime.now().timestamp())}"
            email_safe = "".join(ch for ch in email_local if ch.isalnum()).lower()[:32] or "user"
            pay_url = FreeKassaClient.build_sci_url(
                shop_id=int(fk_cfg.get("shop_id") or 0),
                secret_word_1=secret_word_1,
                payment_id=payment_id,
                amount=amount,
                currency=(fk_cfg.get("currency") or "RUB"),
                method_id=(
                    int(fk_cfg.get("payment_system_id"))
                    if str(fk_cfg.get("payment_system_id") or "").strip()
                    and int(fk_cfg.get("payment_system_id") or 0) > 0
                    else None
                ),
                email=f"{email_safe}@example.com",
                lang="ru",
                base_url=str(fk_cfg.get("sci_url") or "https://pay.freekassa.net/"),
            )
            order = {"location": pay_url, "orderId": None}
        else:
            order = await client.create_order(
                payment_id=payment_id,
                amount=amount,
                currency=(fk_cfg.get("currency") or "RUB"),
                payment_system_id=42,
            )
    except FreeKassaError as e:
        extra_hint = ""
        if "Merchant API KEY not exist" in str(e):
            extra_hint = (
                "\n\nПодсказка: укажите API-ключ из раздела API в кабинете FreeKassa "
                "(не секретное слово SCI и не shop_id)."
            )
        await state.clear()
        return await message.answer(
            "❌ Не удалось создать счёт FreeKassa\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{e}\n\n"
            f"Текущий shop_id: <code>{int(fk_cfg.get('shop_id') or 0)}</code>"
            f"{extra_hint}",
            parse_mode="HTML",
        )

    pay_url = order.get("location")
    PaymentLedger.create(
        payment_id=payment_id,
        user_id=message.from_user.id,
        amount=amount,
        currency=(fk_cfg.get("currency") or "RUB"),
        pay_url=pay_url,
        fk_order_id=order.get("orderId"),
    )
    get_user_manager().log_action(message.from_user.username or str(message.from_user.id), "topup_invoice_fk", payment_id)
    await state.clear()
    await message.answer(
        "🧾 Счёт создан (FreeKassa)\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Сумма: {amount:.2f} ₽\n"
        f"Номер платежа: <code>{payment_id}</code>\n\n"
        "1) Нажмите «Оплатить»\n"
        "2) После оплаты нажмите «Проверить оплату»",
        reply_markup=_invoice_kb(pay_url, payment_id),
        parse_mode="HTML",
    )


@router.message(PaymentStates.WAITING_ADMIN_TRANSFER_RECEIPT, F.document)
async def handle_admin_transfer_receipt_document(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = str(data.get("admin_transfer_order_id") or "")
    if not order_id:
        await state.clear()
        return await message.answer("Заказ не найден. Начните пополнение заново.")

    order = AdminTransferLedger.get(order_id)
    if not order or int(order.get("user_id", 0)) != int(message.from_user.id):
        await state.clear()
        return await message.answer("Заказ не найден. Начните пополнение заново.")

    doc = message.document
    mime = (doc.mime_type or "").lower()
    file_name = (doc.file_name or "").lower()
    if mime != "application/pdf" and not file_name.endswith(".pdf"):
        return await message.answer("Нужен PDF чек. Отправьте документ в формате PDF.")

    updated = AdminTransferLedger.attach_receipt(order_id, doc.file_id)
    if not updated:
        await state.clear()
        return await message.answer("Не удалось сохранить чек. Попробуйте ещё раз.")

    await state.clear()
    await message.answer("Ваш перевод отправлен на проверку, ожидайте подтверждения")

    config = sett.get("config")
    admins = list(((config.get("telegram") or {}).get("master") or {}).get("admins") or [])
    username = f"@{message.from_user.username}" if message.from_user.username else "-"
    caption = (
        "Новая оплата!\n"
        f"ID заказа: {order_id}\n"
        f"Сумма: {float(updated.get('amount', 0)):.2f}\n"
        f"Пользователь: {username} (ID: {message.from_user.id})"
    )
    for admin_id in admins:
        try:
            await message.bot.send_document(
                int(admin_id),
                document=doc.file_id,
                caption=caption,
                reply_markup=_admin_transfer_review_kb(order_id),
            )
        except Exception:
            continue


@router.message(PaymentStates.WAITING_ADMIN_TRANSFER_RECEIPT)
async def handle_admin_transfer_receipt_not_document(message: Message):
    await message.answer("Отправьте PDF чек об оплате")


async def _ask_funpay_tg_step(message: Message, state: FSMContext):
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    total = _total_steps(chosen)
    step = 1
    if "playerok" in chosen:
        step += 4
    await state.set_state(CreateBotStates.WAITING_FP_TG_TOKEN)
    await message.answer(
        get_step_text(
            step,
            total,
            _master_render("CREATE_STEP_FP_TG_TITLE", "🟠 Шаг {step} из {total} — Telegram-токен для FunPay-бота", step=step, total=total),
            _master_msg("CREATE_STEP_FP_TG_DESC", "Отправьте токен Telegram-бота для управления FunPay-аккаунтом. Это должен быть отдельный бот от Playerok."),
            "7257913369:AAG2KjLL3-zvvfSQFSVhaTb4w7tR2iXsJXM",
        ),
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )


async def _finalize_create(message: Message, state: FSMContext):
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    manager = get_manager()
    config = manager.create(
        owner_id=message.from_user.id,
        pl_tg_token=data.get("pl_tg_token", ""),
        fp_tg_token=data.get("fp_tg_token", ""),
        pl_token=data.get("pl_token", ""),
        ua=data.get("pl_user_agent", ""),
        proxy=data.get("pl_proxy", ""),
        password=data["password"],
        platforms=chosen,
        fp_golden_key=data.get("fp_golden_key", ""),
        fp_user_agent=data.get("fp_user_agent", ""),
        fp_proxy=data.get("fp_proxy", ""),
        modules_owned=list((get_user_manager().get_user(message.from_user.id) or {}).get("modules_owned") or []),
    )
    await manager.start(config["uuid"])
    get_user_manager().log_action(message.from_user.username or str(message.from_user.id), "create_bot", config["uuid"])
    await state.clear()
    await message.answer(get_success_text(config), reply_markup=get_success_kb(), parse_mode="HTML")


@router.message(CreateBotStates.WAITING_PL_TG_TOKEN, F.text)
async def handle_pl_tg_token(message: Message, state: FSMContext):
    token = (message.text or "").strip()
    if not is_tg_token_valid(token):
        return await message.answer(
            "❌ Некорректный токен Telegram-бота.",
            reply_markup=get_cancel_kb(),
        )
    await state.update_data(pl_tg_token=token)
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    total = _total_steps(chosen)
    await state.set_state(CreateBotStates.WAITING_PL_TOKEN)
    await message.answer(
        get_step_text(
            2,
            total,
            _master_render("CREATE_STEP_PL_TOKEN_TITLE", "🔑 Шаг {step} из {total} — Токен Playerok-аккаунта", step=2, total=total),
            _master_msg("CREATE_STEP_PL_TOKEN_DESC", "Отправьте токен Playerok-аккаунта (JWT)."),
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        ),
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )


@router.message(CreateBotStates.WAITING_PL_TOKEN, F.text)
async def handle_pl_token(message: Message, state: FSMContext):
    token = (message.text or "").strip()
    if not is_token_valid(token):
        return await message.answer("❌ Некорректный токен Playerok.", reply_markup=get_cancel_kb())
    await state.update_data(pl_token=token)
    data = await state.get_data()
    total = _total_steps(list(data.get("chosen_platforms") or []))
    await state.set_state(CreateBotStates.WAITING_PL_USER_AGENT)
    await message.answer(
        get_step_text(
            3,
            total,
            _master_render("CREATE_STEP_PL_UA_TITLE", "🖥 Шаг {step} из {total} — User Agent Playerok", step=3, total=total),
            _master_msg("CREATE_STEP_PL_UA_DESC", "Отправьте User Agent или нажмите «▶️ Пропустить»."),
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        ),
        reply_markup=get_skip_kb("pl_user_agent"),
        parse_mode="HTML",
    )


@router.message(CreateBotStates.WAITING_PL_USER_AGENT, F.text)
@router.message(CreateBotStates.WAITING_USER_AGENT, F.text)
async def handle_pl_user_agent(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not is_user_agent_valid(value):
        return await message.answer("❌ Некорректный User Agent.", reply_markup=get_skip_kb("pl_user_agent"))
    await state.update_data(user_agent=value, pl_user_agent=value)
    data = await state.get_data()
    total = _total_steps(list(data.get("chosen_platforms") or []))
    await state.set_state(CreateBotStates.WAITING_PL_PROXY)
    await message.answer(
        get_step_text(
            4,
            total,
            _master_render("CREATE_STEP_PL_PROXY_TITLE", "🌐 Шаг {step} из {total} — Прокси Playerok", step=4, total=total),
            _master_msg("CREATE_STEP_PL_PROXY_DESC", "Отправьте HTTP IPv4 прокси или нажмите «▶️ Пропустить»."),
            "DRjcQTm3Yc:m8GnUN8Q9L@46.161.30.187:8000",
        ),
        reply_markup=get_skip_kb("pl_proxy"),
        parse_mode="HTML",
    )


@router.message(CreateBotStates.WAITING_PL_PROXY, F.text)
@router.message(CreateBotStates.WAITING_PROXY, F.text)
async def handle_pl_proxy(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not is_proxy_valid(value):
        return await message.answer("❌ Некорректный формат прокси.", reply_markup=get_skip_kb("pl_proxy"))
    await state.update_data(proxy=value, pl_proxy=value)
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    if "funpay" in chosen:
        return await _ask_funpay_tg_step(message, state)
    await _ask_password_step(message, state)


@router.message(CreateBotStates.WAITING_FP_TG_TOKEN, F.text)
async def handle_fp_tg_token(message: Message, state: FSMContext):
    token = (message.text or "").strip()
    if not is_tg_token_valid(token):
        return await message.answer("❌ Некорректный токен Telegram-бота для FunPay.", reply_markup=get_cancel_kb())
    await state.update_data(fp_tg_token=token)
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    total = _total_steps(chosen)
    step = 2 if "playerok" not in chosen else 6
    await state.set_state(CreateBotStates.WAITING_FP_GOLDEN_KEY)
    await message.answer(
        get_step_text(
            step,
            total,
            _master_render("CREATE_STEP_FP_KEY_TITLE", "🟠 Шаг {step} из {total} — Golden Key FunPay", step=step, total=total),
            _master_msg("CREATE_STEP_FP_KEY_DESC", "Отправьте Golden Key FunPay (32 символа, a-z0-9)."),
            "blkrlwv7epmhx21xxxxxxxxxxxxxxxxx",
        ),
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )


@router.message(CreateBotStates.WAITING_FP_GOLDEN_KEY, F.text)
async def handle_fp_golden_key(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not is_golden_key_valid(value):
        return await message.answer("❌ Некорректный Golden Key FunPay.", reply_markup=get_cancel_kb())
    await state.update_data(fp_golden_key=value)
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    total = _total_steps(chosen)
    step = 3 if "playerok" not in chosen else 7
    await state.set_state(CreateBotStates.WAITING_FP_USER_AGENT)
    await message.answer(
        get_step_text(
            step,
            total,
            _master_render("CREATE_STEP_FP_UA_TITLE", "🖥 Шаг {step} из {total} — User Agent FunPay", step=step, total=total),
            _master_msg("CREATE_STEP_FP_UA_DESC", "Отправьте User Agent для FunPay или нажмите «▶️ Пропустить»."),
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        ),
        reply_markup=get_skip_kb("fp_user_agent"),
        parse_mode="HTML",
    )


@router.message(CreateBotStates.WAITING_FP_USER_AGENT, F.text)
async def handle_fp_user_agent(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not is_user_agent_valid(value):
        return await message.answer("❌ Некорректный User Agent.", reply_markup=get_skip_kb("fp_user_agent"))
    await state.update_data(fp_user_agent=value)
    data = await state.get_data()
    chosen = list(data.get("chosen_platforms") or [])
    total = _total_steps(chosen)
    step = 4 if "playerok" not in chosen else 8
    await state.set_state(CreateBotStates.WAITING_FP_PROXY)
    await message.answer(
        get_step_text(
            step,
            total,
            _master_render("CREATE_STEP_FP_PROXY_TITLE", "🌐 Шаг {step} из {total} — Прокси FunPay", step=step, total=total),
            _master_msg("CREATE_STEP_FP_PROXY_DESC", "Отправьте HTTP IPv4 прокси для FunPay или нажмите «▶️ Пропустить»."),
            "DRjcQTm3Yc:m8GnUN8Q9L@46.161.30.187:8000",
        ),
        reply_markup=get_skip_kb("fp_proxy"),
        parse_mode="HTML",
    )


@router.message(CreateBotStates.WAITING_FP_PROXY, F.text)
async def handle_fp_proxy(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not is_proxy_valid(value):
        return await message.answer("❌ Некорректный формат прокси.", reply_markup=get_skip_kb("fp_proxy"))
    await state.update_data(fp_proxy=value)
    await _ask_password_step(message, state)


@router.message(CreateBotStates.WAITING_PASSWORD, F.text)
async def handle_password(message: Message, state: FSMContext):
    password = (message.text or "").strip()
    if not is_password_valid(password):
        return await message.answer(
            "❌ Пароль не подходит. Используйте 6-64 символа и не берите слишком простой пароль.",
            reply_markup=get_cancel_kb(),
        )
    await state.update_data(password=password)
    await _finalize_create(message, state)


@router.message(UpdateTokenStates.WAITING_TOKEN, F.text)
async def handle_update_pl_token(message: Message, state: FSMContext):
    token = (message.text or "").strip()
    if not is_token_valid(token):
        return await message.answer("❌ Некорректный токен Playerok.", reply_markup=get_cancel_kb())
    data = await state.get_data()
    manager = get_manager()
    manager.update(data["uuid"], pl_token=token)
    await manager.restart(data["uuid"])
    await state.clear()
    user_manager = get_user_manager()
    profile = user_manager.get_user(message.from_user.id)
    bots = manager.get_all(message.from_user.id)
    await message.answer(
        get_main_menu_text(message.from_user, bots, float(profile["balance"]), profile),
        reply_markup=get_main_menu_kb(profile),
        parse_mode="HTML",
    )


@router.message(ProxyStates.WAITING_NEW_PROXY, F.text)
async def handle_add_proxy(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not is_proxy_valid(value):
        return await message.answer("❌ Некорректный формат прокси. Пример: user:pass@1.2.3.4:8080")
    data = await state.get_data()
    uuid_value = data.get("proxy_bot_uuid")
    manager = get_manager()
    bot = manager.get(uuid_value)
    if not bot or bot["owner_tg_id"] != message.from_user.id:
        await state.clear()
        return await message.answer("Бот не найден.")
    ok = manager.add_proxy(uuid_value, value)
    await state.clear()
    if not ok:
        return await message.answer("Не удалось добавить прокси.")
    await message.answer("✅ Прокси добавлен. Откройте карточку бота, чтобы проверить список.")


@router.message(AccountSettingsStates.WAITING_PL_TOKEN, F.text)
async def handle_account_pl_token(message: Message, state: FSMContext):
    token = (message.text or "").strip()
    if not is_token_valid(token):
        return await message.answer("❌ Некорректный токен Playerok.", reply_markup=get_cancel_kb())
    data = await state.get_data()
    manager = get_manager()
    manager.update(data["uuid"], pl_token=token, pl_is_active=True)
    await manager.restart(data["uuid"])
    await state.clear()
    await message.answer("✅ Токен Playerok обновлён.")


@router.message(AccountSettingsStates.WAITING_PL_USER_AGENT, F.text)
async def handle_account_pl_user_agent(message: Message, state: FSMContext):
    ua = (message.text or "").strip()
    if not is_user_agent_valid(ua):
        return await message.answer("❌ Некорректный User Agent.", reply_markup=get_cancel_kb())
    data = await state.get_data()
    manager = get_manager()
    manager.update(data["uuid"], pl_user_agent=ua)
    await manager.restart(data["uuid"])
    await state.clear()
    await message.answer("✅ User Agent Playerok обновлён.")


@router.message(AccountSettingsStates.WAITING_PL_PROXY, F.text)
async def handle_account_pl_proxy(message: Message, state: FSMContext):
    proxy = (message.text or "").strip()
    if not is_proxy_valid(proxy):
        return await message.answer("❌ Некорректный формат прокси.", reply_markup=get_cancel_kb())
    data = await state.get_data()
    manager = get_manager()
    manager.update(data["uuid"], pl_proxy=proxy, proxy=proxy)
    await manager.restart(data["uuid"])
    await state.clear()
    await message.answer("✅ Прокси Playerok обновлён.")


@router.message(AccountSettingsStates.WAITING_FP_TG_TOKEN, F.text)
async def handle_account_fp_tg_token(message: Message, state: FSMContext):
    token = (message.text or "").strip()
    if not is_tg_token_valid(token):
        return await message.answer("❌ Некорректный Telegram-токен для FunPay.", reply_markup=get_cancel_kb())
    await state.update_data(fp_tg_token=token)
    await state.set_state(AccountSettingsStates.WAITING_FP_GOLDEN_KEY)
    await message.answer(
        "🟠 Подключение FunPay — Шаг 2 из 4\n\n"
        "Отправьте Golden Key FunPay-аккаунта.",
        reply_markup=get_cancel_kb(),
    )


@router.message(AccountSettingsStates.WAITING_FP_GOLDEN_KEY, F.text)
async def handle_account_fp_golden_key(message: Message, state: FSMContext):
    golden_key = (message.text or "").strip()
    if not is_golden_key_valid(golden_key):
        return await message.answer("❌ Некорректный Golden Key FunPay.", reply_markup=get_cancel_kb())
    data = await state.get_data()
    flow = data.get("fp_flow", "attach")
    if flow == "update_key":
        manager = get_manager()
        manager.update(data["uuid"], fp_golden_key=golden_key, fp_is_active=True)
        await manager.restart(data["uuid"])
        await state.clear()
        return await message.answer("✅ Golden Key FunPay обновлён.")
    await state.update_data(fp_golden_key=golden_key)
    await state.set_state(AccountSettingsStates.WAITING_FP_USER_AGENT)
    await message.answer("🖥 Подключение FunPay — Шаг 3 из 4\n\nВведите User Agent или '-' для пропуска.")


@router.message(AccountSettingsStates.WAITING_FP_USER_AGENT, F.text)
async def handle_account_fp_user_agent(message: Message, state: FSMContext):
    ua = (message.text or "").strip()
    if ua == "-":
        ua = ""
    elif not is_user_agent_valid(ua):
        return await message.answer("❌ Некорректный User Agent.", reply_markup=get_cancel_kb())
    await state.update_data(fp_user_agent=ua)
    await state.set_state(AccountSettingsStates.WAITING_FP_PROXY)
    await message.answer("🌐 Подключение FunPay — Шаг 4 из 4\n\nВведите прокси или '-' для пропуска.")


@router.message(AccountSettingsStates.WAITING_FP_PROXY, F.text)
async def handle_account_fp_proxy(message: Message, state: FSMContext):
    proxy = (message.text or "").strip()
    if proxy == "-":
        proxy = ""
    elif not is_proxy_valid(proxy):
        return await message.answer("❌ Некорректный формат прокси.", reply_markup=get_cancel_kb())
    data = await state.get_data()
    manager = get_manager()
    manager.attach_funpay(
        data["uuid"],
        data["fp_golden_key"],
        fp_tg_token=data.get("fp_tg_token", ""),
        ua=data.get("fp_user_agent", ""),
        proxy=proxy,
    )
    await manager.restart(data["uuid"])
    await state.clear()
    await message.answer("✅ FunPay подключён и перезапущен.")


@router.message(CustomizationStates.WAITING_BOT_DESCRIPTION, F.text)
async def handle_custom_bot_description(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    data = await state.get_data()
    manager = get_manager()
    manager.update(data["uuid"], bot_description=text)
    await manager.restart(data["uuid"])
    await state.clear()
    await message.answer("✅ Описание бота обновлено.")


@router.message(CustomizationStates.WAITING_BOT_SHORT_DESCRIPTION, F.text)
async def handle_custom_bot_short_description(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    data = await state.get_data()
    manager = get_manager()
    manager.update(data["uuid"], bot_short_description=text)
    await manager.restart(data["uuid"])
    await state.clear()
    await message.answer("✅ Короткое описание обновлено.")


@router.message(CustomizationStates.WAITING_LINK_TEXT, F.text)
async def handle_custom_link_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 1:
        return await message.answer("❌ Текст кнопки не может быть пустым.")
    await state.update_data(link_text=text)
    await state.set_state(CustomizationStates.WAITING_LINK_URL)
    await message.answer("🔗 Отправьте URL кнопки.")


@router.message(CustomizationStates.WAITING_LINK_URL, F.text)
async def handle_custom_link_url(message: Message, state: FSMContext):
    url = (message.text or "").strip()
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("tg://")):
        return await message.answer("❌ Некорректный URL. Пример: https://t.me/your_channel")
    data = await state.get_data()
    manager = get_manager()
    bot = manager.get(data["uuid"]) or {}
    buttons = list(bot.get("link_buttons") or [])
    buttons.append({"text": data["link_text"], "url": url})
    manager.update(data["uuid"], link_buttons=buttons)
    await manager.restart(data["uuid"])
    await state.clear()
    await message.answer("✅ Кнопка добавлена.")


@router.message(CustomizationStates.WAITING_MESSAGE_TEXT, F.text)
async def handle_custom_message_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    data = await state.get_data()
    uuid_value = data["uuid"]
    key = data["message_key"]
    path = os.path.join("bot_data", "bots", uuid_value, "messages.json")
    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        payload = {}
    payload.setdefault(key, {"enabled": True, "text": []})
    payload[key]["enabled"] = True
    payload[key]["text"] = text.splitlines() or [text]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=4)
    await state.clear()
    await message.answer(f"✅ Сообщение `{key}` обновлено.", parse_mode="Markdown")

