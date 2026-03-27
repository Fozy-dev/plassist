from settings import Settings as global_settings, SettingsFile


AUTO_BONUS = SettingsFile(
    name="auto_bonus",
    path="bot_data/auto_bonus.json",
    need_restore=True,
    default={
        "enabled": False,
        "messages": {
            "new_deal": "Спасибо за покупку! Пожалуйста оставьте отзыв и после этого вы автоматически получите ваш подарок 🎁",
            "bonus_sent": "🎁 Ваш бонус:\n{bonus}",
            "bonus_not_found": "❌ Бонус для этого товара не найден.",
        },
        "bonuses": [],
        "sent_deals": [],
    },
)

DATA = [AUTO_BONUS]


class Settings:
    @staticmethod
    def get(name: str):
        return global_settings.get(name, DATA)

    @staticmethod
    def set(name: str, new):
        return global_settings.set(name, new, DATA)
