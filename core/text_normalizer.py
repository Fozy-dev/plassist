from __future__ import annotations

from typing import Any


MOJIBAKE_MARKERS = (
    "рџ",
    "вЂ",
    "в„",
    "вќ",
    "вљ",
    "гѓ",
    "Р",
    "С",
    "Ð",
    "Ñ",
    "Â",
    "Ã",
    "�",
)

BAD_SEQUENCES = (
    "Рџ",
    "РЎ",
    "Рќ",
    "С‚",
    "СЏ",
    "СЂ",
    "рџ",
    "вЂ",
)

STATIC_FIXES = {
    "РІ'Р…": "₽",
    "Р Р†'Р вЂ¦": "₽",
    "в‚Ѕ": "₽",
}


def fix_mojibake(value: str) -> str:
    if not isinstance(value, str) or not value:
        return value

    text = value
    for bad, good in STATIC_FIXES.items():
        text = text.replace(bad, good)

    def suspicious(s: str) -> bool:
        if not s:
            return False
        markers = sum(s.count(marker) for marker in MOJIBAKE_MARKERS)
        bad_seq = sum(s.count(seq) for seq in BAD_SEQUENCES)
        return markers >= 2 or bad_seq >= 1

    if not suspicious(text):
        return text

    def score(s: str) -> int:
        cyrillic = sum(1 for ch in s if "\u0400" <= ch <= "\u04FF")
        ascii_letters = sum(1 for ch in s if "a" <= ch.lower() <= "z")
        digits = sum(1 for ch in s if ch.isdigit())
        marker_count = sum(s.count(marker) for marker in MOJIBAKE_MARKERS)
        bad_seq = sum(s.count(seq) for seq in BAD_SEQUENCES)
        replacement = s.count("�")
        box = sum(1 for ch in s if "\u2500" <= ch <= "\u257F")
        return cyrillic * 4 + ascii_letters + digits - marker_count * 5 - bad_seq * 12 - replacement * 20 - box * 10

    def decode_variant(s: str, source_encoding: str) -> str | None:
        try:
            return s.encode(source_encoding, errors="strict").decode("utf-8", errors="strict")
        except UnicodeError:
            return None

    best = text
    best_score = score(text)
    queue = [text]
    seen = {text}

    for _ in range(3):
        new_queue = []
        for current in queue:
            for enc in ("latin1", "cp1251", "cp866"):
                candidate = decode_variant(current, enc)
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)
                new_queue.append(candidate)
                candidate_score = score(candidate)
                if candidate_score > best_score:
                    best = candidate
                    best_score = candidate_score
        if not new_queue:
            break
        queue = new_queue

    return best


def normalize_data(value):
    if isinstance(value, str):
        return fix_mojibake(value)
    if isinstance(value, list):
        return [normalize_data(item) for item in value]
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            fixed_key = fix_mojibake(key) if isinstance(key, str) else key
            normalized[fixed_key] = normalize_data(item)
        return normalized
    return value


def normalize_reply_markup(reply_markup: Any):
    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    except Exception:
        return reply_markup

    if not isinstance(reply_markup, InlineKeyboardMarkup):
        return reply_markup

    allowed_fields = (
        "url",
        "callback_data",
        "web_app",
        "login_url",
        "switch_inline_query",
        "switch_inline_query_current_chat",
        "switch_inline_query_chosen_chat",
        "copy_text",
        "callback_game",
        "pay",
    )
    normalized_rows = []
    for row in reply_markup.inline_keyboard:
        normalized_row = []
        for button in row:
            text = fix_mojibake(getattr(button, "text", "") or "")
            payload: dict[str, Any] = {"text": text}
            for field in allowed_fields:
                value = getattr(button, field, None)
                if value is not None:
                    payload[field] = value
            normalized_row.append(InlineKeyboardButton(**payload))
        normalized_rows.append(normalized_row)
    return InlineKeyboardMarkup(inline_keyboard=normalized_rows)


_PATCHED = False


def _normalize_payload(kwargs: dict):
    if "text" in kwargs and isinstance(kwargs.get("text"), str):
        kwargs["text"] = fix_mojibake(kwargs["text"])
    if "caption" in kwargs and isinstance(kwargs.get("caption"), str):
        kwargs["caption"] = fix_mojibake(kwargs["caption"])
    if "reply_markup" in kwargs:
        kwargs["reply_markup"] = normalize_reply_markup(kwargs["reply_markup"])
    return kwargs


def install_aiogram_text_patches():
    global _PATCHED
    if _PATCHED:
        return

    from aiogram.client.bot import Bot
    from aiogram.types import CallbackQuery, Message

    def patch_method(owner, name: str):
        original = getattr(owner, name, None)
        if not original or getattr(original, "__text_normalized__", False):
            return

        async def wrapped(self, *args, **kwargs):
            if args:
                args = list(args)
                if len(args) >= 1 and isinstance(args[0], str):
                    args[0] = fix_mojibake(args[0])
                args = tuple(args)
            kwargs = _normalize_payload(kwargs)
            return await original(self, *args, **kwargs)

        wrapped.__text_normalized__ = True
        setattr(owner, name, wrapped)

    bot_methods = [
        "send_message",
        "edit_message_text",
        "send_photo",
        "send_document",
        "send_video",
        "send_animation",
        "send_audio",
        "send_voice",
        "edit_message_caption",
    ]
    message_methods = [
        "answer",
        "reply",
        "edit_text",
        "answer_photo",
        "answer_document",
        "answer_video",
        "answer_animation",
        "answer_audio",
        "answer_voice",
    ]
    callback_methods = ["answer"]

    for method in bot_methods:
        patch_method(Bot, method)
    for method in message_methods:
        patch_method(Message, method)
    for method in callback_methods:
        patch_method(CallbackQuery, method)

    _PATCHED = True
