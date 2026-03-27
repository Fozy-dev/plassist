from aiogram.fsm.state import State, StatesGroup


class SystemStates(StatesGroup):
    waiting_for_password = State()


class ActionsStates(StatesGroup):
    waiting_for_message_content = State()


class SettingsStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_user_agent = State()

    waiting_for_requests_timeout = State()
    waiting_for_listener_requests_delay = State()
    waiting_for_pl_proxy = State()
    waiting_for_tg_proxy = State()

    waiting_for_auto_withdrawal_interval = State()
    waiting_for_sbp_bank_phone_number = State()
    waiting_for_usdt_address = State()

    waiting_for_tg_logging_chat_id = State()
    waiting_for_watermark_value = State()

    waiting_for_logs_max_file_size = State()


class MessagesStates(StatesGroup):
    waiting_for_page = State()
    waiting_for_message_text = State()


class RestoreItemsStates(StatesGroup):
    waiting_for_new_included_restore_item_keyphrases = State()
    waiting_for_new_included_restore_items_keyphrases_file = State()
    waiting_for_new_excluded_restore_item_keyphrases = State()
    waiting_for_new_excluded_restore_items_keyphrases_file = State()


class CompleteDealsStates(StatesGroup):
    waiting_for_new_included_complete_deal_keyphrases = State()
    waiting_for_new_included_complete_deals_keyphrases_file = State()
    waiting_for_new_excluded_complete_deal_keyphrases = State()
    waiting_for_new_excluded_complete_deals_keyphrases_file = State()


class BumpItemsStates(StatesGroup):
    waiting_for_bump_items_interval = State()
    waiting_for_new_included_bump_item_keyphrases = State()
    waiting_for_new_included_bump_items_keyphrases_file = State()
    waiting_for_new_excluded_bump_item_keyphrases = State()
    waiting_for_new_excluded_bump_items_keyphrases_file = State()


class CustomCommandsStates(StatesGroup):
    waiting_for_page = State()
    waiting_for_new_custom_command = State()
    waiting_for_new_custom_command_answer = State()
    waiting_for_custom_command_answer = State()


class AutoDeliveriesStates(StatesGroup):
    waiting_for_page = State()
    waiting_for_new_auto_delivery_keyphrases = State()
    waiting_for_new_auto_delivery_piece = State()
    waiting_for_new_auto_delivery_message = State()
    waiting_for_new_auto_delivery_goods = State()
    waiting_for_auto_delivery_keyphrases = State()
    waiting_for_auto_delivery_piece = State()
    waiting_for_auto_delivery_message = State()
    waiting_for_auto_delivery_goods_add = State()


class CreateBotStates(StatesGroup):
    CONFIRM_START = State()
    CHOOSING_PLATFORM = State()
    WAITING_PL_TG_TOKEN = State()
    WAITING_FP_TG_TOKEN = State()
    WAITING_TG_TOKEN = State()
    WAITING_FP_GOLDEN_KEY = State()
    WAITING_FP_USER_AGENT = State()
    WAITING_FP_PROXY = State()
    WAITING_PL_TOKEN = State()
    WAITING_PL_USER_AGENT = State()
    WAITING_PL_PROXY = State()
    WAITING_USER_AGENT = State()
    WAITING_PROXY = State()
    WAITING_PASSWORD = State()


class UpdateTokenStates(StatesGroup):
    WAITING_TOKEN = State()


class AdminStates(StatesGroup):
    WAITING_TOPUP_AMOUNT = State()
    WAITING_BROADCAST_TEXT = State()
    WAITING_PARTNER_NICK = State()
    WAITING_PARTNER_USERNAME = State()
    WAITING_PARTNER_TG_ID = State()
    WAITING_PARTNER_PERCENT = State()
    WAITING_PARTNER_PAYOUT = State()
    WAITING_TRANSFER_REJECT_REASON = State()
    WAITING_TRANSFER_CONFIRM_AMOUNT = State()


class PaymentStates(StatesGroup):
    WAITING_TOPUP_CUSTOM_AMOUNT = State()
    WAITING_ADMIN_TRANSFER_RECEIPT = State()


class ProxyStates(StatesGroup):
    WAITING_NEW_PROXY = State()


class AccountSettingsStates(StatesGroup):
    WAITING_PL_TOKEN = State()
    WAITING_PL_USER_AGENT = State()
    WAITING_PL_PROXY = State()
    WAITING_FP_TG_TOKEN = State()
    WAITING_FP_GOLDEN_KEY = State()
    WAITING_FP_USER_AGENT = State()
    WAITING_FP_PROXY = State()


class CustomizationStates(StatesGroup):
    WAITING_BOT_DESCRIPTION = State()
    WAITING_BOT_SHORT_DESCRIPTION = State()
    WAITING_LINK_TEXT = State()
    WAITING_LINK_URL = State()
    WAITING_MESSAGE_TEXT = State()
