from __future__ import annotations

from core.child_manager import ChildBotManager
from core.partners_manager import PartnersManager
from core.user_manager import UserManager


manager: ChildBotManager | None = None
user_manager: UserManager | None = None
partners_manager: PartnersManager | None = None


def set_manager(value: ChildBotManager):
    global manager
    manager = value


def set_user_manager(value: UserManager):
    global user_manager
    user_manager = value


def set_partners_manager(value: PartnersManager):
    global partners_manager
    partners_manager = value


def get_manager() -> ChildBotManager:
    if manager is None:
        raise RuntimeError("ChildBotManager is not initialized")
    return manager


def get_user_manager() -> UserManager:
    if user_manager is None:
        raise RuntimeError("UserManager is not initialized")
    return user_manager


def get_partners_manager() -> PartnersManager:
    if partners_manager is None:
        raise RuntimeError("PartnersManager is not initialized")
    return partners_manager
