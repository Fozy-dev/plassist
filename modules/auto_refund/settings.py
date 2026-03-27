from settings import Settings as global_settings, SettingsFile


AUTO_REFUND = SettingsFile(
    name="auto_refund",
    path="bot_data/auto_refund.json",
    need_restore=True,
    default={
        "enabled": False,
        "ratings": {"1": True, "2": True, "3": False, "4": False, "5": False},
        "max_price": 1.0,
        "notify_buyer": True,
        "messages": {
            "refund_sent": "Средства по заказу #{order_id} были возвращены автоматически. Причина: отзыв на {stars}⭐.",
            "admin_log": "AutoRefund: заказ #{order_id}, сумма {price:.2f}, отзыв {stars}⭐ от {author}. Возврат выполнен.",
            "refund_failed": "AutoRefund: не удалось вернуть средства по заказу #{order_id}. Ошибка: {error}",
        },
        "refunded_orders": [],
    },
)

DATA = [AUTO_REFUND]


class Settings:
    @staticmethod
    def get(name: str):
        return global_settings.get(name, DATA)

    @staticmethod
    def set(name: str, new):
        return global_settings.set(name, new, DATA)
