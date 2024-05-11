"""
Goal of this file:
given an app that has a simple text-based interface, we want to create a bot-lib telegram bot interface for it
app will have .invoke() method that takes a string and returns a string
"""
from aiogram import Dispatcher

from app import App
from bot_lib import Handler, HandlerDisplayMode, setup_dispatcher, BotConfig
from bot_lib.demo import create_bot, run_bot
from typing import Iterable

class AppInvokeHandler(Handler):
    """
    calmmage bot-lib handler that calls .invoke() on an App instance
    gets input_str from the message text
    sends output_str as a reply
    """

    name = "app_invoke"
    display_mode = HandlerDisplayMode.FULL
    commands = {}

    has_chat_handler = True

    async def chat_handler(self, message, app: App):
        input_str = await self.get_message_text(message)
        output_str = app.invoke(input_str)
        await message.answer(output_str)


# Actually, I will need to implement mechanic to support chat_handler()!

def instantiate_classes_if_necessary(items, to_list=False):
    if to_list:
        if not isinstance(items, list):
            items = [items]
    else:
        item = items
        if isinstance(item, type):
            item = item()
        return item

    result = []
    for item in items:
        if isinstance(item, type):
            item = item()
        result.append(item)
    return result


def take_care_of_everything(
        handlers,
        app,
        run=True
):
    # todo: ALSO check if .env and tokens are missing and create them if necessary
    if not isinstance(handlers, Iterable):
        handlers = (handlers, )
    # handlers = instantiate_classes_if_necessary(handlers, to_list=True)
    app = instantiate_classes_if_necessary(app)

    # create bot config
    config = BotConfig(
        handlers=handlers,
        app=app,
    )
    dp = Dispatcher()
    setup_dispatcher(dp, config)

    bot = create_bot()

    if run:
        run_bot(dp, bot)

    return dp, bot


if __name__ == '__main__':
    take_care_of_everything(AppInvokeHandler, App)
