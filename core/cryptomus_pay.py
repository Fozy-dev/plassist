from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime
from typing import Any

import aiohttp

from core.runtime_paths import resolve_runtime_path
from core.text_normalizer import normalize_data


API_BASE = "https://api.cryptomus.com/v1"
PAYMENTS_PATH = "bot_data/cryptomus_payments.json"


class CryptomusError(RuntimeError):
    pass


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


class CryptomusClient:
    def __init__(self, merchant_id: str, api_key: str, timeout: int = 20):
        self.merchant_id = (merchant_id or "").strip()
        self.api_key = (api_key or "").strip()
        self.timeout = timeout
        if not self.merchant_id:
            raise CryptomusError("Не задан merchant_id Cryptomus.")
        if not self.api_key:
            raise CryptomusError("Не задан API key Cryptomus.")

    def _sign(self, body_raw: str) -> str:
        # Docs: md5(base64_encode(body) + API_KEY)
        body_b64 = base64.b64encode(body_raw.encode("utf-8")).decode("utf-8")
        return hashlib.md5((body_b64 + self.api_key).encode("utf-8")).hexdigest()

    async def _request(self, endpoint: str, payload: dict[str, Any]) -> dict:
        body_raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        headers = {
            "merchant": self.merchant_id,
            "sign": self._sign(body_raw),
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{API_BASE}/{endpoint.lstrip('/')}", data=body_raw.encode("utf-8"), headers=headers) as response:
                raw = await response.text()
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    raise CryptomusError(f"Некорректный ответ Cryptomus: {raw[:300]}")
                if response.status >= 400:
                    errors = parsed.get("errors") if isinstance(parsed, dict) else None
                    raise CryptomusError(str(errors or parsed or f"HTTP {response.status}"))
                if isinstance(parsed, dict) and int(parsed.get("state", 1)) != 0:
                    raise CryptomusError(str(parsed.get("errors") or parsed))
                if not isinstance(parsed, dict):
                    raise CryptomusError("Пустой ответ Cryptomus")
                return parsed.get("result") or {}

    async def create_invoice(self, *, amount_rub: float, order_id: str) -> dict:
        payload = {
            "amount": f"{amount_rub:.2f}",
            "currency": "RUB",
            "order_id": order_id,
        }
        return await self._request("payment", payload)

    async def payment_info(self, *, order_id: str) -> dict | None:
        result = await self._request("payment/info", {"order_id": order_id})
        return result or None

    @staticmethod
    def is_paid(payment: dict | None) -> bool:
        if not payment:
            return False
        status = str(payment.get("payment_status") or payment.get("status") or "").lower()
        return status in {"paid", "paid_over"}


class CryptomusLedger:
    @staticmethod
    def all() -> dict[str, dict]:
        return _read_json(PAYMENTS_PATH, {})

    @staticmethod
    def get(payment_id: str) -> dict | None:
        return CryptomusLedger.all().get(payment_id)

    @staticmethod
    def create(
        *,
        payment_id: str,
        user_id: int,
        amount: float,
        order_id: str,
        invoice_uuid: str | None,
        pay_url: str,
    ) -> dict:
        payload = CryptomusLedger.all()
        now = datetime.now().isoformat(timespec="seconds")
        payload[payment_id] = {
            "payment_id": payment_id,
            "user_id": int(user_id),
            "amount": round(float(amount), 2),
            "order_id": order_id,
            "invoice_uuid": invoice_uuid,
            "pay_url": pay_url,
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
    def mark_paid(payment_id: str, payment: dict | None = None) -> dict | None:
        payload = CryptomusLedger.all()
        row = payload.get(payment_id)
        if not row:
            return None
        now = datetime.now().isoformat(timespec="seconds")
        row["status"] = "paid"
        row["paid_at"] = row.get("paid_at") or now
        row["updated_at"] = now
        if payment:
            row["raw_payment"] = payment
            if payment.get("uuid"):
                row["invoice_uuid"] = payment.get("uuid")
        payload[payment_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row

    @staticmethod
    def mark_credited(payment_id: str) -> dict | None:
        payload = CryptomusLedger.all()
        row = payload.get(payment_id)
        if not row:
            return None
        row["credited"] = True
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        payload[payment_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row
