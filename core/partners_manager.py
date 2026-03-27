from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta

from core.runtime_paths import resolve_runtime_path
from core.text_normalizer import normalize_data


PARTNERS_PATH = "bot_data/partners.json"


def _build_referral_link(bot_username: str, slug: str) -> str:
    return f"https://t.me/{bot_username.lstrip('@')}?start={slug}"


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


class PartnersManager:
    def __init__(self):
        _read_json(PARTNERS_PATH, [])

    def all_partners(self) -> list[dict]:
        partners = _read_json(PARTNERS_PATH, [])
        changed = False
        for partner in partners:
            slug = (partner.get("slug") or partner.get("nickname") or "").strip()
            if not slug:
                continue
            partner["slug"] = slug
            if "username" not in partner:
                partner["username"] = ""
                changed = True
            if "tg_id" not in partner:
                partner["tg_id"] = None
                changed = True
            if "payment_events" not in partner:
                partner["payment_events"] = []
                changed = True
            link = partner.get("referral_link", "")
            if "/t.me/" in link:
                link = link.split("https://", 1)[-1]
            if "?start=" not in link:
                bot_username = ""
                if link.startswith("t.me/"):
                    tail = link[5:]
                    bot_username = tail.split("/", 1)[0]
                partner["referral_link"] = _build_referral_link(bot_username or "RaidexAssist_bot", slug)
                changed = True
        if changed:
            self._save(partners)
        return partners

    def _save(self, partners: list[dict]):
        _write_json(PARTNERS_PATH, partners)

    def get_by_id(self, partner_id: str) -> dict | None:
        return next((item for item in self.all_partners() if item.get("id") == partner_id), None)

    def get_by_slug(self, slug: str) -> dict | None:
        slug = (slug or "").strip()
        return next((item for item in self.all_partners() if item.get("slug") == slug), None)

    def create_partner(self, nickname: str, bot_username: str, tg_id: int | None = None, username: str = "") -> dict:
        nickname = (nickname or "").strip()
        if not nickname:
            raise ValueError("Partner nickname is empty")
        existing = self.get_by_slug(nickname)
        if existing:
            raise ValueError("Partner already exists")
        partner = {
            "id": str(uuid.uuid4()),
            "nickname": nickname,
            "username": f"@{username.lstrip('@')}" if username else "",
            "tg_id": tg_id,
            "slug": nickname,
            "referral_link": _build_referral_link(bot_username, nickname),
            "percent": 40,
            "referred_users": [],
            "total_paid_out": 0.0,
            "total_earned": 0.0,
            "total_revenue": 0.0,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        partners = self.all_partners()
        partners.append(partner)
        self._save(partners)
        return partner

    def update_partner(self, partner_id: str, **fields) -> dict | None:
        partners = self.all_partners()
        updated = None
        for partner in partners:
            if partner.get("id") == partner_id:
                partner.update(fields)
                updated = partner
                break
        if updated:
            self._save(partners)
        return updated

    def delete_partner(self, partner_id: str) -> dict | None:
        partners = self.all_partners()
        target = self.get_by_id(partner_id)
        if not target:
            return None
        partners = [item for item in partners if item.get("id") != partner_id]
        self._save(partners)
        return target

    def set_percent(self, partner_id: str, percent: int) -> dict | None:
        return self.update_partner(partner_id, percent=int(percent))

    def add_manual_payout(self, partner_id: str, amount: float) -> dict | None:
        partner = self.get_by_id(partner_id)
        if not partner:
            return None
        paid_out = round(float(partner.get("total_paid_out", 0.0)) + float(amount), 2)
        return self.update_partner(partner_id, total_paid_out=paid_out)

    def bind_user(self, partner_slug: str, user: dict) -> dict | None:
        partner = self.get_by_slug(partner_slug)
        if not partner:
            return None

        referred_users = list(partner.get("referred_users") or [])
        user_id = int(user["tg_id"])
        existing = next((item for item in referred_users if int(item.get("tg_id", 0)) == user_id), None)
        if existing:
            return partner

        referred_users.append(
            {
                "tg_id": user_id,
                "username": user.get("username", ""),
                "first_name": user.get("first_name", ""),
                "joined_at": datetime.now().isoformat(timespec="seconds"),
                "total_paid": 0.0,
                "total_earned": 0.0,
                "payments_count": 0,
            }
        )
        return self.update_partner(partner["id"], referred_users=referred_users)

    def register_payment(self, partner_id: str, user: dict, amount: float) -> tuple[dict, float] | tuple[None, float]:
        partner = self.get_by_id(partner_id)
        if not partner:
            return None, 0.0
        percent = int(partner.get("percent", 40))
        reward = round(float(amount) * percent / 100.0, 2)
        referred_users = list(partner.get("referred_users") or [])
        user_id = int(user["tg_id"])
        row = next((item for item in referred_users if int(item.get("tg_id", 0)) == user_id), None)
        if not row:
            row = {
                "tg_id": user_id,
                "username": user.get("username", ""),
                "first_name": user.get("first_name", ""),
                "joined_at": datetime.now().isoformat(timespec="seconds"),
                "total_paid": 0.0,
                "total_earned": 0.0,
                "payments_count": 0,
            }
            referred_users.append(row)
        row["username"] = user.get("username", row.get("username", ""))
        row["first_name"] = user.get("first_name", row.get("first_name", ""))
        row["total_paid"] = round(float(row.get("total_paid", 0.0)) + float(amount), 2)
        row["total_earned"] = round(float(row.get("total_earned", 0.0)) + reward, 2)
        row["payments_count"] = int(row.get("payments_count", 0)) + 1

        events = list(partner.get("payment_events") or [])
        events.append(
            {
                "tg_id": user_id,
                "amount": round(float(amount), 2),
                "reward": reward,
                "at": datetime.now().isoformat(timespec="seconds"),
            }
        )

        partner = self.update_partner(
            partner["id"],
            referred_users=referred_users,
            payment_events=events,
            total_revenue=round(float(partner.get("total_revenue", 0.0)) + float(amount), 2),
            total_earned=round(float(partner.get("total_earned", 0.0)) + reward, 2),
        )
        return partner, reward

    @staticmethod
    def available_balance(partner: dict) -> float:
        return round(float(partner.get("total_earned", 0.0)) - float(partner.get("total_paid_out", 0.0)), 2)

    @staticmethod
    def stats(partner: dict) -> dict:
        referred_users = list(partner.get("referred_users") or [])
        total_users = len(referred_users)
        paid_users = sum(1 for item in referred_users if float(item.get("total_paid", 0.0)) > 0)
        total_revenue = round(float(partner.get("total_revenue", 0.0)), 2)
        payment_events = list(partner.get("payment_events") or [])

        now = datetime.now()
        border_24h = now - timedelta(hours=24)
        border_7d = now - timedelta(days=7)
        border_30d = now - timedelta(days=30)

        def _safe_dt(value: str | None):
            if not value:
                return None
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return None

        rev_24h = 0.0
        rev_7d = 0.0
        rev_30d = 0.0
        for event in payment_events:
            ts = _safe_dt(event.get("at"))
            if not ts:
                continue
            reward = float(event.get("reward", 0.0))
            if ts >= border_24h:
                rev_24h += reward
            if ts >= border_7d:
                rev_7d += reward
            if ts >= border_30d:
                rev_30d += reward

        conversion = round((paid_users / total_users * 100.0), 2) if total_users else 0.0
        avg_check = round((total_revenue / paid_users), 2) if paid_users else 0.0

        top_ref = None
        if referred_users:
            top_ref = max(referred_users, key=lambda x: float(x.get("total_paid", 0.0)))
            if float(top_ref.get("total_paid", 0.0)) <= 0:
                top_ref = None

        return {
            "total_users": total_users,
            "paid_users": paid_users,
            "total_revenue": total_revenue,
            "total_earned": round(float(partner.get("total_earned", 0.0)), 2),
            "total_paid_out": round(float(partner.get("total_paid_out", 0.0)), 2),
            "available": PartnersManager.available_balance(partner),
            "percent": int(partner.get("percent", 40)),
            "conversion": conversion,
            "avg_check": avg_check,
            "revenue_24h": round(rev_24h, 2),
            "revenue_7d": round(rev_7d, 2),
            "revenue_30d": round(rev_30d, 2),
            "top_ref_tg_id": int(top_ref.get("tg_id", 0)) if top_ref else None,
            "top_ref_name": (top_ref.get("first_name") or top_ref.get("username") or "") if top_ref else "",
            "top_ref_paid": round(float(top_ref.get("total_paid", 0.0)), 2) if top_ref else 0.0,
        }
