from settings import Settings as global_settings, SettingsFile


SELLER_GPT = SettingsFile(
    name="seller_gpt",
    path="bot_data/seller_gpt.json",
    need_restore=True,
    default={
        "enabled": False,
        "api_base_url": "https://api.groq.com/openai/v1",
        "api_key": "",
        "model": "llama-3.1-8b-instant",
        "timeout_sec": 45,
        "history_limit": 8,
        "ignore_links": True,
        "use_lot_context": True,
        "prompt": (
            "Ты продавец на FunPay и отвечаешь покупателям в личном чате. "
            "Отвечай только по делу, коротко и естественно, на русском языке. "
            "Не упоминай, что ты ИИ. Не обещай того, чего не знаешь. "
            "Если покупатель задаёт уточняющий вопрос по товару, помоги выбрать подходящий вариант. "
            "Если информации не хватает, задай один короткий уточняющий вопрос. "
            "Не рекламируй другие площадки и не уходи в лишнюю болтовню."
        ),
        "messages": {
            "admin_log": "Seller GPT: отправлен автоответ пользователю {author} в чате {chat_id}.",
            "reply_failed": "Seller GPT: не удалось ответить пользователю {author} в чате {chat_id}. Ошибка: {error}",
        },
        "handled_message_ids": [],
    },
)
DATA = [SELLER_GPT]


class Settings:
    @staticmethod
    def get(name: str):
        return global_settings.get(name, DATA)

    @staticmethod
    def set(name: str, new):
        return global_settings.set(name, new, DATA)
