from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime

from core.runtime_paths import resolve_runtime_path
from core.text_normalizer import normalize_data


PAYMENTS_PATH = "bot_data/telegram_stars_payments.json"


def _read_json(path: str, default):
    path = resolve_runtime_path(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        normalized = normalize_data(payload)
        if normalized != payload:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(normalized, file, ensure_ascii=False, indent=4)
        return normalized
    except Exception:
        normalized_default = normalize_data(default)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(normalized_default, file, ensure_ascii=False, indent=4)
        return normalized_default


def _write_json(path: str, payload):
    path = resolve_runtime_path(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    normalized_payload = normalize_data(payload)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(normalized_payload, file, ensure_ascii=False, indent=4)


class TelegramStarsLedger:
    @staticmethod
    def all() -> dict[str, dict]:
        return _read_json(PAYMENTS_PATH, {})

    @staticmethod
    def get(payment_id: str) -> dict | None:
        return TelegramStarsLedger.all().get(payment_id)

    @staticmethod
    def make_payment_id(user_id: int) -> str:
        return f"st{int(user_id)}_{int(time.time())}_{secrets.token_hex(4)}"

    @staticmethod
    def create(
        *,
        payment_id: str,
        user_id: int,
        amount_rub: float,
        stars_amount: int,
        rate: float,
        requested_amount_rub: float | None = None,
    ) -> dict:
        payload = TelegramStarsLedger.all()
        now = datetime.now().isoformat(timespec="seconds")
        payload[payment_id] = {
            "payment_id": str(payment_id),
            "user_id": int(user_id),
            "amount": round(float(amount_rub), 2),
            "requested_amount": round(float(requested_amount_rub or amount_rub), 2),
            "stars_amount": int(stars_amount),
            "rate": round(float(rate), 4),
            "status": "new",
            "credited": False,
            "created_at": now,
            "updated_at": now,
            "paid_at": None,
            "raw_payment": {},
        }
        _write_json(PAYMENTS_PATH, payload)
        return payload[payment_id]

    @staticmethod
    def mark_paid(payment_id: str, raw_payment: dict | None = None) -> dict | None:
        payload = TelegramStarsLedger.all()
        row = payload.get(payment_id)
        if not row:
            return None
        now = datetime.now().isoformat(timespec="seconds")
        row["status"] = "paid"
        row["paid_at"] = row.get("paid_at") or now
        row["updated_at"] = now
        if raw_payment:
            row["raw_payment"] = raw_payment
        payload[payment_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row

    @staticmethod
    def mark_credited(payment_id: str) -> dict | None:
        payload = TelegramStarsLedger.all()
        row = payload.get(payment_id)
        if not row:
            return None
        row["credited"] = True
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        payload[payment_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row
