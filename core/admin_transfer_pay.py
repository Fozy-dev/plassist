from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime

from core.runtime_paths import resolve_runtime_path
from core.text_normalizer import normalize_data


PAYMENTS_PATH = "bot_data/admin_transfer_payments.json"


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


class AdminTransferLedger:
    @staticmethod
    def all() -> dict[str, dict]:
        return _read_json(PAYMENTS_PATH, {})

    @staticmethod
    def get(order_id: str) -> dict | None:
        return AdminTransferLedger.all().get(order_id)

    @staticmethod
    def make_order_id(user_id: int) -> str:
        return f"adm_{int(user_id)}_{int(time.time())}_{secrets.token_hex(3)}"

    @staticmethod
    def create(*, user_id: int, amount: float, order_id: str | None = None) -> dict:
        payload = AdminTransferLedger.all()
        now = datetime.now().isoformat(timespec="seconds")
        oid = order_id or AdminTransferLedger.make_order_id(user_id)
        payload[oid] = {
            "order_id": oid,
            "user_id": int(user_id),
            "amount": round(float(amount), 2),
            "status": "ожидание оплаты",
            "receipt_file_id": None,
            "reject_reason": None,
            "credited_amount": None,
            "admin_id": None,
            "created_at": now,
            "updated_at": now,
        }
        _write_json(PAYMENTS_PATH, payload)
        return payload[oid]

    @staticmethod
    def attach_receipt(order_id: str, file_id: str) -> dict | None:
        payload = AdminTransferLedger.all()
        row = payload.get(order_id)
        if not row:
            return None
        row["receipt_file_id"] = file_id
        row["status"] = "на проверке"
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        payload[order_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row

    @staticmethod
    def reject(order_id: str, *, reason: str, admin_id: int) -> dict | None:
        payload = AdminTransferLedger.all()
        row = payload.get(order_id)
        if not row:
            return None
        row["status"] = "отклонён"
        row["reject_reason"] = reason
        row["admin_id"] = int(admin_id)
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        payload[order_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row

    @staticmethod
    def confirm(order_id: str, *, credited_amount: float, admin_id: int) -> dict | None:
        payload = AdminTransferLedger.all()
        row = payload.get(order_id)
        if not row:
            return None
        row["status"] = "успешно"
        row["credited_amount"] = round(float(credited_amount), 2)
        row["admin_id"] = int(admin_id)
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        payload[order_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row
