from settings import Settings as global_settings, SettingsFile


AUTO_STEAM = SettingsFile(
    name="auto_steam",
    path="bot_data/auto_steam.json",
    need_restore=True,
    default={
        "enabled": False,
        "api_login": "",
        "api_password": "",
        "auto_refund_on_error": True,
        "order_verification_enabled": True,
        "confirmation_reminder": True,
        "reminder_time_minutes": 2.5,
        "allowed_subcategory_ids": [1086],
        "blacklist_logins": [],
        "messages": {
            "ask_login": "Отправьте логин Steam для пополнения по заказу #{order_id}.",
            "confirm_login": "Проверьте данные:\nЛогин Steam: {steam_login}\nСумма пополнения: {quantity} {currency}\n\nЕсли всё верно, отправьте +",
            "queue_added": "Заявка добавлена в очередь на пополнение Steam. Позиция: {position}.",
            "success": "Средства успешно отправлены в Steam.\nЛогин: {steam_login}\nСумма: {quantity} {currency}\nЗаказ: #{order_id}",
            "invalid_login": "Указанный логин Steam не найден. Отправьте другой логин.",
            "refund": "Средства возвращены из-за ошибки при пополнении Steam.",
            "reply_plus": "Если данные верны, отправьте +. Либо отправьте новый логин Steam.",
            "admin_log": "AutoSteam: заказ #{order_id} успешно выполнен для {steam_login} на {quantity} {currency}.",
            "admin_error": "AutoSteam: ошибка по заказу #{order_id}. Ошибка: {error}",
            "reminder": "Пожалуйста, подтвердите заказ https://funpay.com/orders/{order_id}/"
        },
        "history": []
    },
)
DATA = [AUTO_STEAM]


class Settings:
    @staticmethod
    def get(name: str):
        return global_settings.get(name, DATA)

    @staticmethod
    def set(name: str, new):
        return global_settings.set(name, new, DATA)
