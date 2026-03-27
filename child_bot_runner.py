from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

from core.modules import connect_modules, load_modules, set_modules
from core.utils import init_main_loop, patch_requests, setup_logger
from plbot.playerokbot import PlayerokBot
from tgbot.telegrambot import TelegramBot


def _load_child_record(uuid_value: str) -> dict:
    path = os.path.join(os.getcwd(), "bot_data", "child_bots.json")
    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        for item in payload:
            if item.get("uuid") == uuid_value:
                return item
    except Exception:
        pass
    return {}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uuid", required=True)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    os.environ["PLAYEROK_BOT_ROOT"] = args.root
    if args.root not in sys.path:
        sys.path.insert(0, args.root)
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    loop = asyncio.get_running_loop()
    init_main_loop(loop)
    patch_requests()
    setup_logger()
    logger = logging.getLogger("universal.child_runner")

    modules = load_modules()
    set_modules(modules)
    await connect_modules(modules)

    cfg = _load_child_record(args.uuid)
    platforms = set([item for item in (cfg.get("platforms") or []) if item in {"playerok", "funpay"}])
    if not platforms:
        platforms = {"playerok"}

    tg_tokens: list[str] = []
    if "playerok" in platforms and cfg.get("pl_tg_token"):
        tg_tokens.append(cfg.get("pl_tg_token", ""))
    if "funpay" in platforms and cfg.get("fp_tg_token"):
        tg_tokens.append(cfg.get("fp_tg_token", ""))
    if not tg_tokens:
        fallback = cfg.get("tg_token", "")
        if fallback:
            tg_tokens = [fallback]
    tg_tokens = [token for token in dict.fromkeys(tg_tokens) if token]

    tg_bot = TelegramBot(tokens=tg_tokens)
    tasks = [asyncio.create_task(tg_bot.run_bot())]

    if "playerok" in platforms and cfg.get("pl_token"):
        try:
            pl_bot = PlayerokBot()
            tasks.append(asyncio.create_task(pl_bot.run_bot()))
        except Exception as exc:
            logger.error("Failed to initialize Playerok bot: %s", exc)

    if "funpay" in platforms and cfg.get("fp_golden_key"):
        try:
            from fpbot.funpaybot import FunPayBot

            fp_bot = FunPayBot()
            tasks.append(asyncio.create_task(fp_bot.run_bot()))
        except Exception as exc:
            logger.error("Failed to initialize FunPay bot: %s", exc)

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
