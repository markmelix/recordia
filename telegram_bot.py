import asyncio
import logging
import sys

from datetime import timedelta
from dotenv import load_dotenv
from common import *

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

load_dotenv()

TOKEN = getenv("TELEGRAM_TOKEN")
bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

CHATS = {
    425717640,
    # 891074228,
}

# Задержка цикла отправки уведомлений в секундах
NOTIFICATION_DELAY = 1

# Московское стандартное время соответствует UTC+3
TZDELTA = timedelta(hours=3)

create_common_tables()

last_recording_id = None


async def notification_task():
    print("Started notification loop\n------")
    global last_recording_id
    while True:
        cur = con.cursor()

        try:
            id, nickname, fullname, channel = cur.execute(
                "SELECT id, nickname, fullname, channel FROM history ORDER BY id DESC"
            ).fetchone()
        except TypeError:
            continue

        if last_recording_id != id:
            if channel is None:
                text = f"Longcat [{fullname}/{nickname}] решил отдохнуть"
            else:
                text = f'Longcat [{fullname}/{nickname}] сейчас в "{channel}"'

            for chat in CHATS:
                try:
                    await bot.send_message(chat, text)
                except TelegramBadRequest as e:
                    print(
                        f"Error while sending notification message to chat with id {chat}: {e}"
                    )

            last_recording_id = id

        cur.close()

        await asyncio.sleep(NOTIFICATION_DELAY)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(notification_task())
    except KeyboardInterrupt as e:
        print()
    finally:
        con.close()
        logging.disable()
