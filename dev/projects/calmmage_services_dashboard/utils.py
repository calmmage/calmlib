from dotenv import load_dotenv


def send_telegram_message(message, chat_id, bot_token=None):
    """
    Send a message to a Telegram chat
    """
    import os

    if bot_token is None:
        load_dotenv()
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
