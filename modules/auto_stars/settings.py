from settings import Settings as global_settings, SettingsFile


AUTO_STARS = SettingsFile(
    name="auto_stars",
    path="bot_data/auto_stars.json",
    need_restore=True,
    default={
        "enabled": False,
        "allowed_quantities": [10, 15, 25, 50, 75, 100, 150, 200, 250, 350, 500, 1000, 2500],
        "auto_refund": False,
        "show_sender": "0",
        "fragment_api": {
            "hash": "",
            "cookie": "",
            "url": "https://fragment.com/api",
            "subcategory_id": 2418,
        },
        "ton": {
            "api_key": "",
            "is_testnet": False,
            "mnemonic": [],
            "destination_address": "",
        },
        "notifications": {
            "telegram_user_id": 0,
        },
        "messages": {
            "new_order": (
                "Спасибо за заказ на {quantity} Stars.\n\n"
                "Отправьте ваш @username в Telegram, на который нужно зачислить Stars."
            ),
            "invalid_username": "Неверный формат username. Отправьте username в формате @username.",
            "confirm_username": (
                "Ваш username: {username}\n"
                "Имя в Telegram: {preview_name}\n"
                "Fragment ID: {recipient_id}\n\n"
                "Если всё верно, ответьте: Да\n"
                "Если хотите изменить username, ответьте: Нет\n"
                "Для отмены и возврата используйте: !бек"
            ),
            "queue_added": "Заявка поставлена в очередь на выдачу Stars. Позиция в очереди: {position}.",
            "ask_username_again": "Хорошо, отправьте @username ещё раз.",
            "reply_yes_no": "Пожалуйста, ответьте только: Да или Нет.",
            "cancelled": "Заказ отменён, средства возвращены.",
            "completed": (
                "Заказ выполнен.\n"
                "Stars: {quantity}\n"
                "Ref ID: Ref#{ref_id}\n"
                "Транзакция: {ton_viewer_url}"
            ),
            "payment_failed": "Не удалось выполнить выдачу Stars. Причина: {error}",
            "not_configured": "Модуль AutoStars настроен не полностью. Обратитесь к продавцу.",
            "insufficient_balance": "На кошельке продавца недостаточно средств для выполнения заказа.",
        },
        "pending_orders": {},
        "stats": {},
    },
)

DATA = [AUTO_STARS]


class Settings:
    @staticmethod
    def get(name: str):
        return global_settings.get(name, DATA)

    @staticmethod
    def set(name: str, new):
        return global_settings.set(name, new, DATA)
