from settings import Settings as global_settings, SettingsFile


AUTO_SMM = SettingsFile(
    name="auto_smm",
    path="bot_data/auto_smm.json",
    need_restore=True,
    default={
        "enabled": False,
        "api_url": "https://optsmm.ru/api/v2",
        "api_key": "",
        "auto_refund_on_error": True,
        "confirm_link": True,
        "allowed_domains": [
            "instagram.com",
            "www.instagram.com",
            "tiktok.com",
            "www.tiktok.com",
            "vk.com",
            "www.vk.com",
            "youtube.com",
            "www.youtube.com",
            "t.me",
            "telegram.me"
        ],
        "mappings": [],
        "messages": {
            "after_payment": "Спасибо за оплату заказа #{order_id}.\n\nОтправьте ссылку на страницу или пост для запуска услуги.",
            "confirm_link": "Проверьте ссылку:\n{link}\n\nЕсли всё верно, отправьте +\nИли отправьте новую ссылку.",
            "queue_added": "Заявка добавлена в очередь. Позиция: {position}.",
            "after_confirmation": "Заказ успешно оформлен.\n\nID в сервисе: {service_order_id}\nСсылка: {link}",
            "invalid_link": "Ссылка не подходит. Отправьте корректную ссылку с разрешённого домена.",
            "mapping_not_found": "Для этого лота пока не настроено соответствие AutoSMM. Ожидайте продавца.",
            "reply_plus": "Если ссылка верная, отправьте +. Либо пришлите новую ссылку.",
            "refund": "Средства возвращены из-за ошибки при оформлении AutoSMM.",
            "admin_log": "AutoSMM: заказ #{order_id} оформлен. Service order: {service_order_id}. Ссылка: {link}",
            "admin_error": "AutoSMM: ошибка по заказу #{order_id}. Ошибка: {error}"
        },
        "history": []
    },
)
DATA = [AUTO_SMM]


class Settings:
    @staticmethod
    def get(name: str):
        return global_settings.get(name, DATA)

    @staticmethod
    def set(name: str, new):
        return global_settings.set(name, new, DATA)
