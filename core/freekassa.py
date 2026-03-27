from __future__ import annotations

import hashlib
import hmac
import asyncio
import json
import os
import secrets
import time
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import aiohttp

from core.runtime_paths import resolve_runtime_path
from core.text_normalizer import normalize_data


API_BASE = "https://api.fk.life/v1"
PAYMENTS_PATH = "bot_data/freekassa_payments.json"


class FreeKassaError(RuntimeError):
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


class FreeKassaClient:
    _last_nonce = 0

    def __init__(self, api_key: str, shop_id: int | None = None, timeout: int = 15):
        self.api_key = (api_key or "").strip()
        self.shop_id = int(shop_id or 0)
        self.timeout = timeout
        if not self.api_key:
            raise FreeKassaError("API key FreeKassa не задан.")

    @classmethod
    def _next_nonce(cls) -> int:
        now = int(time.time())
        if now <= cls._last_nonce:
            now = cls._last_nonce + 1
        cls._last_nonce = now
        return now

    def _signature(self, payload: dict[str, Any]) -> str:
        sorted_payload = {k: payload[k] for k in sorted(payload.keys())}
        data = "|".join(str(value) for value in sorted_payload.values())
        return hmac.new(self.api_key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def build_sci_url(
        *,
        shop_id: int,
        secret_word_1: str,
        payment_id: str,
        amount: float,
        currency: str = "RUB",
        method_id: int | None = 42,
        email: str | None = None,
        lang: str = "ru",
        base_url: str = "https://pay.freekassa.net/",
    ) -> str:
        try:
            amount_s = format(Decimal(str(amount)).normalize(), "f")
        except (InvalidOperation, ValueError):
            amount_s = str(amount)
        sign_base = f"{int(shop_id)}:{amount_s}:{secret_word_1}:{currency}:{payment_id}"
        signature = hashlib.md5(sign_base.encode("utf-8")).hexdigest()
        params: dict[str, Any] = {
            "m": int(shop_id),
            "oa": amount_s,
            "o": payment_id,
            "s": signature,
            "currency": currency,
            "lang": lang or "ru",
        }
        if method_id:
            params["i"] = int(method_id)
        if email:
            params["em"] = email
        return f"{base_url.rstrip('/')}/?{urlencode(params)}"

    @staticmethod
    def _extract_error_message(parsed: dict | None, raw: str | None = None) -> str:
        if not isinstance(parsed, dict):
            return (raw or "unknown error").strip() or "unknown error"
        fields = (
            parsed.get("message"),
            parsed.get("error"),
            parsed.get("description"),
            parsed.get("msg"),
        )
        for field in fields:
            if field:
                return str(field)
        errors = parsed.get("errors")
        if isinstance(errors, list) and errors:
            return "; ".join(str(x) for x in errors if x)
        if isinstance(errors, dict) and errors:
            return "; ".join(f"{k}: {v}" for k, v in errors.items())
        if raw:
            return raw.strip()[:1000]
        return "unknown error"

    async def _request(self, endpoint: str, payload: dict[str, Any]) -> dict:
        data = dict(payload)
        data["nonce"] = self._next_nonce()
        if self.shop_id > 0 and "shopId" not in data:
            data["shopId"] = self.shop_id
        data["signature"] = self._signature(data)

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = f"{API_BASE}/{endpoint.lstrip('/')}"
            try:
                # FreeKassa API v1 ожидает JSON-тело.
                async with session.post(url, json=data) as response:
                    raw = await response.text()
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        parsed = {"type": "error", "message": raw}
                    if response.status >= 400:
                        raise FreeKassaError(f"HTTP {response.status}: {self._extract_error_message(parsed, raw)}")
                    if isinstance(parsed, dict) and parsed.get("type") == "error":
                        raise FreeKassaError(f"HTTP {response.status or 400}: {self._extract_error_message(parsed, raw)}")
                    if not isinstance(parsed, dict):
                        raise FreeKassaError("HTTP 400: Некорректный ответ FreeKassa API")
                    return parsed
            except asyncio.TimeoutError as e:
                raise FreeKassaError("HTTP 504: FreeKassa API timeout") from e
            except aiohttp.ClientError as e:
                raise FreeKassaError(f"HTTP 400: {e}") from e

    async def resolve_shop_id(self) -> int:
        if self.shop_id > 0:
            return self.shop_id

        response = await self._request("shops", {})
        shops = response.get("shops") or []
        if not shops:
            raise FreeKassaError("Не удалось получить shopId через API /shops. Укажите payments.freekassa.shop_id вручную.")
        self.shop_id = int(shops[0]["id"])
        return self.shop_id

    async def _resolve_payment_system_id(self, *, currency: str, preferred_id: int | None) -> list[int]:
        ordered_ids: list[int] = []
        if preferred_id:
            # Если метод задан явно в конфиге (например, СБП=42), используем только его.
            return [int(preferred_id)]
        # Автовыбор доступного метода оплаты для валюты (например, RUB).
        response = await self._request("currencies", {})
        currencies = response.get("currencies") or []
        target = (currency or "").upper()
        preferred_order = [42, 13, 12, 4, 8, 6]

        available_ids: list[int] = []
        for row in currencies:
            if not isinstance(row, dict):
                continue
            row_currency = str(row.get("currency") or "").upper()
            if target and row_currency and row_currency != target:
                continue
            status = row.get("status")
            if status is not None and str(status) not in {"1", "true", "True"}:
                continue
            row_id = row.get("id")
            try:
                available_ids.append(int(row_id))
            except Exception:
                continue

        # В авто-режиме исключаем FKWallet, чтобы не уводить на страницу входа fkwallet.io.
        if not preferred_id:
            available_ids = [x for x in available_ids if x not in {1, 36}] or available_ids

        if not available_ids:
            available_ids = [1]
        for method_id in preferred_order:
            if method_id in available_ids:
                ordered_ids.append(method_id)
        for method_id in available_ids:
            if method_id not in ordered_ids:
                ordered_ids.append(method_id)
        return ordered_ids

    async def create_order(
        self,
        *,
        payment_id: str,
        amount: float,
        currency: str = "RUB",
        payment_system_id: int | None = None,
        email: str | None = None,
        ip: str | None = None,
    ) -> dict:
        shop_id = await self.resolve_shop_id()
        method_ids = await self._resolve_payment_system_id(currency=currency, preferred_id=payment_system_id)
        try:
            normalized_amount = format(Decimal(str(amount)).normalize(), "f")
        except (InvalidOperation, ValueError):
            normalized_amount = str(amount)
        safe_local = "".join(ch for ch in (payment_id or "") if ch.isalnum()).lower()[:32] or f"pay{int(time.time())}"
        resolved_email = (email or f"{safe_local}@example.com").strip()
        last_error: FreeKassaError | None = None
        for method_id in method_ids:
            payload: dict[str, Any] = {
                "shopId": shop_id,
                "paymentId": payment_id,
                "amount": normalized_amount,
                "currency": currency,
                "i": int(method_id),
                "email": resolved_email,
            }
            if ip:
                payload["ip"] = ip
            try:
                response = await self._request("orders/create", payload)
                location = str(response.get("location") or "")
                if not location:
                    raise FreeKassaError("FreeKassa не вернула ссылку на оплату.")
                if "fkwallet.io" in location.lower():
                    last_error = FreeKassaError("HTTP 400: Оплата временно не доступна")
                    continue
                return response
            except FreeKassaError as e:
                last_error = e
                msg = str(e).lower()
                if ("оплата временно не доступна" in msg) or ("payments disabled" in msg) or ("temporarily unavailable" in msg):
                    continue
                raise
        if last_error:
            raise last_error
        raise FreeKassaError("Не удалось создать заказ FreeKassa.")

    async def find_order(self, *, payment_id: str) -> dict | None:
        shop_id = await self.resolve_shop_id()
        response = await self._request(
            "orders",
            {
                "shopId": shop_id,
                "paymentId": payment_id,
            },
        )
        orders = response.get("orders") or []
        if not orders:
            return None
        return orders[0]

    @staticmethod
    def is_paid(order: dict | None) -> bool:
        if not order:
            return False
        return int(order.get("status", 0)) == 1


class PaymentLedger:
    @staticmethod
    def all() -> dict[str, dict]:
        return _read_json(PAYMENTS_PATH, {})

    @staticmethod
    def get(payment_id: str) -> dict | None:
        return PaymentLedger.all().get(payment_id)

    @staticmethod
    def create(
        *,
        payment_id: str,
        user_id: int,
        amount: float,
        currency: str,
        pay_url: str,
        fk_order_id: int | None = None,
    ) -> dict:
        payload = PaymentLedger.all()
        now = datetime.now().isoformat(timespec="seconds")
        payload[payment_id] = {
            "payment_id": payment_id,
            "user_id": int(user_id),
            "amount": round(float(amount), 2),
            "currency": currency,
            "pay_url": pay_url,
            "fk_order_id": fk_order_id,
            "status": "new",
            "credited": False,
            "created_at": now,
            "updated_at": now,
            "paid_at": None,
            "raw_order": {},
        }
        _write_json(PAYMENTS_PATH, payload)
        return payload[payment_id]

    @staticmethod
    def mark_paid(payment_id: str, order: dict | None = None) -> dict | None:
        payload = PaymentLedger.all()
        row = payload.get(payment_id)
        if not row:
            return None
        now = datetime.now().isoformat(timespec="seconds")
        row["status"] = "paid"
        row["paid_at"] = row.get("paid_at") or now
        row["updated_at"] = now
        if order:
            row["raw_order"] = order
            if order.get("fk_order_id"):
                row["fk_order_id"] = order.get("fk_order_id")
        payload[payment_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row

    @staticmethod
    def mark_credited(payment_id: str) -> dict | None:
        payload = PaymentLedger.all()
        row = payload.get(payment_id)
        if not row:
            return None
        row["credited"] = True
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        payload[payment_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row

    @staticmethod
    def make_payment_id(user_id: int) -> str:
        return f"tg{int(user_id)}_{int(time.time())}_{secrets.token_hex(4)}"
