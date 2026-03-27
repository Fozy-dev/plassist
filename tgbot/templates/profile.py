import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from settings import Settings as sett

from .. import callback_datas as calls


def _resolve_platform(current_bot_token: str | None = None) -> str:
    cfg = sett.get("config")
    runtime = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    pl_token = runtime.get("pl_tg_token") or ""
    fp_token = runtime.get("fp_tg_token") or ""

    token = current_bot_token or ""
    if token and fp_token and token == fp_token:
        return "funpay"
    if token and pl_token and token == pl_token:
        return "playerok"

    has_pl = bool(cfg.get("playerok", {}).get("api", {}).get("token"))
    has_fp = bool(cfg.get("funpay", {}).get("api", {}).get("golden_key"))
    if has_fp and not has_pl:
        return "funpay"
    if has_pl and not has_fp:
        return "playerok"
    return "mixed"


def _playerok_profile_text() -> str:
    from plbot.playerokbot import get_playerok_bot

    bot = get_playerok_bot()
    if not bot or not getattr(bot, "playerok_account", None):
        raise RuntimeError("Playerok runtime is not available")

    acc = bot.playerok_account.get()
    profile = acc.profile
    txt = textwrap.dedent(
        f"""
        <b>👤 Мой профиль</b>

        <b>🆔 ID:</b> <code>{profile.id}</code>
        <b>👤 Никнейм:</b> {profile.username}
        <b>📪 Email:</b> {profile.email}
        <b>💬 Отзывы:</b> {profile.reviews_count} (<b>Рейтинг:</b> {profile.rating} ⭐)

        <b>💰 Баланс:</b> {profile.balance.value if profile.balance else 0}₽
        <b>・ 👁 Доступно:</b> {profile.balance.available if profile.balance else 0}₽
        <b>・ ⌛ В процессе:</b> {profile.balance.pending_income if profile.balance else 0}₽
        <b>・ ❄️ Заморожено:</b> {profile.balance.frozen if profile.balance else 0}₽

        <b>📅 Дата регистрации:</b> {datetime.fromisoformat(profile.created_at.replace('Z', '+00:00')).strftime('%d.%m.%Y %H:%M:%S')}
    """
    )
    return txt


def _funpay_profile_text() -> str:
    from fpbot.funpaybot import get_funpay_bot

    bot = get_funpay_bot()
    if not bot or not getattr(bot, "account", None):
        raise RuntimeError("FunPay runtime is not available")

    acc = bot.account
    cur_name = acc.currency.name if getattr(acc, "currency", None) else "RUB"
    txt = textwrap.dedent(
        f"""
        <b>👤 Мой профиль</b>

        <b>🆔 ID:</b> <code>{getattr(acc, 'id', '-')}</code>
        <b>👤 Никнейм:</b> {getattr(acc, 'username', '-')}

        <b>💰 Баланс:</b> {getattr(acc, 'total_balance', 0)} {cur_name}
        <b>🛒 Активные продажи:</b> {getattr(acc, 'active_sales', 0)}
    """
    )
    return txt


def profile_text(current_bot_token: str | None = None):
    platform = _resolve_platform(current_bot_token)
    if platform == "funpay":
        try:
            return _funpay_profile_text()
        except Exception:
            pass
    if platform == "playerok":
        try:
            return _playerok_profile_text()
        except Exception:
            pass

    try:
        return _playerok_profile_text()
    except Exception:
        pass
    try:
        return _funpay_profile_text()
    except Exception:
        pass
    return "<b>👤 Профиль</b>\n\nДанные профиля пока недоступны."


def profile_kb():
    rows = [
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="default").pack())],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
