import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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


def _playerok_stats_text() -> str:
    from plbot.stats import get_stats

    stats = get_stats()
    txt = textwrap.dedent(
        f"""
        <b>📊 Статистика</b>

        Дата запуска бота: <b>{stats.bot_launch_time.strftime('%d.%m.%Y %H:%M:%S') if stats.bot_launch_time else 'Не запущен'}</b>

        <b>Статистика с момента запуска:</b>
        ・ Выполнено: <b>{stats.deals_completed}</b>
        ・ Возвратов: <b>{stats.deals_refunded}</b>
        ・ Заработано: <b>{stats.earned_money}</b>₽
    """
    )
    return txt


def _funpay_stats_text() -> str:
    from fpbot.stats import get_stats

    stats = get_stats()
    txt = textwrap.dedent(
        f"""
        <b>📊 Статистика</b>

        Дата запуска бота: <b>{stats.bot_launch_time.strftime('%d.%m.%Y %H:%M:%S') if stats.bot_launch_time else 'Не запущен'}</b>

        <b>Статистика с момента запуска:</b>
        ・ Выполнено заказов: <b>{stats.orders_completed}</b>
        ・ Возвратов: <b>{stats.orders_refunded}</b>
        ・ Заработано: <b>{stats.earned_money}</b>₽
    """
    )
    return txt


def stats_text(current_bot_token: str | None = None):
    platform = _resolve_platform(current_bot_token)
    if platform == "funpay":
        try:
            return _funpay_stats_text()
        except Exception:
            pass
    if platform == "playerok":
        try:
            return _playerok_stats_text()
        except Exception:
            pass

    try:
        return _playerok_stats_text()
    except Exception:
        pass
    try:
        return _funpay_stats_text()
    except Exception:
        pass
    return "<b>📊 Статистика</b>\n\nДанные статистики пока недоступны."


def stats_kb():
    rows = [[InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="default").pack())]]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
