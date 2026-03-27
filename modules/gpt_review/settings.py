from settings import Settings as global_settings, SettingsFile


GPT_REVIEW = SettingsFile(
    name="gpt_review",
    path="bot_data/gpt_review.json",
    need_restore=True,
    default={
        "enabled": False,
        "api_base_url": "https://api.groq.com/openai/v1",
        "api_key": "",
        "model": "llama-3.1-8b-instant",
        "timeout_sec": 45,
        "min_stars": 5,
        "only_without_reply": True,
        "prompt": (
            "Ты помощник магазина игровых товаров. Напиши короткий, живой и вежливый ответ на отзыв покупателя на русском языке. "
            "Не упоминай, что ты ИИ. Не используй канцелярит и не пиши слишком длинно. "
            "Учитывай данные заказа и отзыв покупателя.\n\n"
            "Покупатель: {name}\n"
            "Товар: {item}\n"
            "Категория: {categoryfull}\n"
            "Сумма: {cost}\n"
            "Оценка: {rating}/5\n"
            "Текст отзыва: {text}\n\n"
            "Требования: поблагодари за покупку и отзыв, ответ должен быть доброжелательным, естественным и без лишней воды."
        ),
        "messages": {
            "admin_log": "GPT Review: отправлен ответ на отзыв по заказу #{order_id} ({stars}⭐, {author}).",
            "reply_failed": "GPT Review: не удалось ответить на отзыв по заказу #{order_id}. Ошибка: {error}",
        },
        "replied_orders": [],
    },
)
DATA = [GPT_REVIEW]


class Settings:
    @staticmethod
    def get(name: str):
        return global_settings.get(name, DATA)

    @staticmethod
    def set(name: str, new):
        return global_settings.set(name, new, DATA)
