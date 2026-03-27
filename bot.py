import asyncio
import atexit
import json
import os
import subprocess
import traceback

from colorama import Fore, init as init_colorama

from __init__ import ACCENT_COLOR, VERSION
from core.child_manager import ChildBotManager
from core.user_manager import UserManager
from core.utils import (
    init_main_loop,
    install_requirements,
    is_tg_token_valid,
    patch_requests,
    set_title,
    setup_logger,
)
from settings import Settings as sett

LOCK_PATH = os.path.join("bot_data", "master_bot.lock")


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_master_lock() -> bool:
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    current_pid = os.getpid()
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        payload = {}

    existing_pid = int(payload.get("pid") or 0)
    if existing_pid and existing_pid != current_pid and _pid_is_alive(existing_pid):
        print(f"{Fore.LIGHTYELLOW_EX}Мастер-бот уже запущен в другом процессе (PID {existing_pid}). Второй экземпляр не будет стартовать.")
        return False

    with open(LOCK_PATH, "w", encoding="utf-8") as file:
        json.dump({"pid": current_pid}, file, ensure_ascii=False, indent=2)

    def _cleanup():
        try:
            with open(LOCK_PATH, "r", encoding="utf-8") as file:
                current = json.load(file)
            if int(current.get("pid") or 0) == current_pid:
                os.remove(LOCK_PATH)
        except Exception:
            pass

    atexit.register(_cleanup)
    return True


def run_mojibake_guard() -> bool:
    try:
        result = subprocess.run(
            ["python", "scripts/check_mojibake.py", "--root", ".", "--max-lines", "120"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        print(f"{Fore.LIGHTRED_EX}Не удалось запустить проверку mojibake: {exc}")
        return False

    if result.returncode == 0:
        return True

    print(f"{Fore.LIGHTRED_EX}{result.stdout.strip() or result.stderr.strip()}")
    print(f"{Fore.LIGHTYELLOW_EX}Обнаружены подозрительные строки. Бот продолжит запуск, но рекомендуется исправить их.")
    return True


def check_and_configure_master_token():
    config = sett.get("config")
    while not config["telegram"]["master"]["token"]:
        print(
            "\nВведите токен управляющего Telegram-бота.\n"
            "Создайте его у @BotFather командой /newbot.\n"
            "Пример: 7257913369:AAG2KjLL3-zvvfSQFSVhaTb4w7tR2iXsJXM"
        )
        token = input("→ ").strip()
        if is_tg_token_valid(token):
            config["telegram"]["master"]["token"] = token
            sett.set("config", config)
            print("\nТокен мастер-бота сохранён.")
            break
        print("\nНекорректный токен. Проверьте формат и попробуйте снова.")


async def main():
    from tgbot.master_bot import MasterBot

    patch_requests()
    loop = asyncio.get_running_loop()
    init_main_loop(loop)

    manager = ChildBotManager()
    user_manager = UserManager()
    started = await manager.autostart()
    print(f"{Fore.GREEN}Загружено дочерних ботов: {started}")

    while True:
        master = MasterBot(manager, user_manager)
        print(f"{Fore.GREEN}Мастер-бот запущен. Ожидаю команды в Telegram.")
        try:
            await master.run()
        except Exception as e:
            print(f"{Fore.LIGHTRED_EX}Ошибка polling: {e}")
            await asyncio.sleep(5)
        finally:
            try:
                await master.bot.session.close()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        if not acquire_master_lock():
            raise SystemExit(0)
        install_requirements("requirements.txt")
        setup_logger()
        init_colorama()
        set_title(f"Playerok Universal v{VERSION} constructor")
        print(
            f"\n\n"
            f"\n   {ACCENT_COLOR}Playerok Universal {Fore.WHITE}v{Fore.LIGHTWHITE_EX}{VERSION}"
            f"\n"
            f"\n   {Fore.YELLOW}Наши ссылки:"
            f"\n   {Fore.WHITE}· TG бот: {Fore.LIGHTWHITE_EX}https://t.me/alexey_production_bot"
            f"\n   {Fore.WHITE}· TG канал: {Fore.LIGHTWHITE_EX}https://t.me/alexeyproduction"
            f"\n   {Fore.WHITE}· GitHub: {Fore.LIGHTWHITE_EX}https://github.com/alleexxeeyy/playerok-universal"
            f"\n\n"
        )
        run_mojibake_guard()
        check_and_configure_master_token()
        asyncio.run(main())
    except Exception:
        traceback.print_exc()
