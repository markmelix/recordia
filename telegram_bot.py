import os
import sys
import asyncio
import logging
import aiogram

from dotenv import load_dotenv
from common import *


class LongcatNotifier:
    def __init__(self, bot, chat_ids, loop_delay=1):
        self.bot = bot
        self.chats = chat_ids
        self.loop_delay = loop_delay

    async def task(self):
        print("Started notification loop\n------")

        last_recording_id = None
        just_started = True

        while True:
            cur = con.cursor()

            try:
                id, nickname, fullname, channel = cur.execute(
                    "SELECT id, nickname, fullname, channel FROM history ORDER BY id DESC"
                ).fetchone()
            except TypeError:
                continue

            if last_recording_id != id or just_started:
                if channel is None:
                    text = f"Longcat [{fullname}/{nickname}] решил отдохнуть"
                else:
                    text = f'Longcat [{fullname}/{nickname}] сейчас в "{channel}"'

                for chat in self.chats:
                    try:
                        await self.bot.send_message(chat, text)
                    except aiogram.exceptions.TelegramBadRequest as e:
                        print(
                            f"Error while sending notification message to chat with id {chat}: {e}"
                        )

                last_recording_id = id

            just_started = False
            cur.close()
            await asyncio.sleep(self.loop_delay)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    create_common_tables()
    load_dotenv()

    TOKEN = os.getenv("TELEGRAM_TOKEN")

    if TOKEN is None:
        raise ValueError("Telegram token was not provided")

    DEBUG = os.getenv("DEBUG", 0)

    ADMINS = {
        425717640,  # Mark
    }
    OTHERS = {
        891074228,  # Anton
    }

    CHATS = ADMINS if DEBUG else ADMINS.union(OTHERS)

    NOTIFICATION_LOOP_DELAY = 1

    try:
        asyncio.run(
            LongcatNotifier(
                bot=aiogram.Bot(TOKEN),
                chat_ids=CHATS,
                loop_delay=NOTIFICATION_LOOP_DELAY,
            ).task()
        )
    except KeyboardInterrupt as e:
        print()
    finally:
        con.close()
        logging.disable()
