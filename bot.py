import os
import logging
import asyncio
import discord
import aiogram

from io import BytesIO
from typing import Collection
from datetime import datetime
from dotenv import load_dotenv

DTFORMAT = "%a %d %b %H_%M_%S"

PROJECT_ROOT = os.path.dirname(__file__)


class BaseNotifier:
    async def notify(self, timestamp: datetime, name: str, channel: str | None):
        print()
        print(f"Stamped at {timestamp.strftime(DTFORMAT)}")
        print(f'{name} in "{channel}"')
        print()


class TelegramNotifier(aiogram.Bot):
    def __init__(self, chats, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chats = chats

    async def notify(self, _: datetime, name: str, channel: str | None):
        if channel is None:
            text = f"Longcat {name} решил отдохнуть"
        else:
            text = f'Longcat {name} сейчас в "{channel}"'

        for chat in self.chats:
            try:
                await self.send_message(chat, text)
            except aiogram.exceptions.TelegramBadRequest as e:
                print(
                    f"Error while sending notification message to chat with id {chat}: {e}"
                )


class SilenceAudioSource(discord.AudioSource):
    def read(self) -> bytes:
        # play 40ms of silence
        return b"0" * 3840


class LongcatRecorder(discord.Client):
    """Discord bot, отслеживающий и фиксирующий и записывающий действия лонгкета
    в голосовых чатах указанного сервера."""

    def __init__(
        self,
        *args,
        guild_name: str,
        longcat_names: Collection[str],
        notifiers: tuple,
        record: bool = True,
        recorder_sink=None,
        privacy_doorstep: int = 5,
        connect_delay: int = 10,
        disconnect_delay: int = 15,
        disable_connect_delay_just_after_start: bool = True,
        staying_number: int = 1,
        **kwargs,
    ):
        """guild_name       - название сервера, в котором стоит вести слежку
        longcat_names    - ники аккаунтов лонгкета
        notifiers        - нотификаторы
        record           - стоит ли записывать, что говорят люди в голосовом чате
        recorder_sink    - **не** инициализированный кодек записи голосовых сообщений, например, `discord.sinks.MP4Sink`, чтобы звук писался в .mp4 формате
        privacy_doorstep - сколько человек как минимум должно быть в голосовом чате, чтобы бот подключался
        connect_delay    - задержка перед подключением к голосовому чату
        disconnect_delay - задержка перед выходом из голосового чата
        disable_connect_delay_just_after_start:
        - отключить ли искусственную задержку перед подключением в голосовой чат, если бот только что запустился
        staying_number   - сколько человек должно быть в голосовом чате, чтобы бот оставался в чате
        """
        super().__init__(*args, **kwargs)

        self.guild_name = guild_name
        self.longcat_names = longcat_names
        self.do_record = record
        self.privacy_doorstep = privacy_doorstep
        self.recorder_sink = recorder_sink if recorder_sink else discord.sinks.WaveSink
        self.connect_delay = connect_delay
        self.disconnect_delay = disconnect_delay
        self.disable_connect_delay_just_after_start = (
            disable_connect_delay_just_after_start
        )
        self.staying_number = staying_number
        self.notifiers = notifiers
        self.last_timestamp = None

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        print(f'Watching {self.longcat_names} within "{self.guild_name}" guild')
        print("------")

        self.guild = discord.utils.get(self.guilds, name=GUILD)
        self.initial_nickname = self.guild.me.nick
        self.longcats = set(
            filter(lambda member: member.name in LONGCATS, self.guild.members)
        )

        for longcat in self.longcats:
            if longcat.voice is not None and longcat.voice.channel is not None:
                if not self.disable_connect_delay_just_after_start:
                    await asyncio.sleep(self.connect_delay)
                await self.record_or_stop(
                    longcat.voice.channel,
                    (await self.stamp_voice_state(longcat)).strftime(DTFORMAT),
                )
                break

    async def on_voice_state_update(
        self,
        member: discord.Member,
        old_voice_state: discord.VoiceState,
        new_voice_state: discord.VoiceState,
    ):
        if not self.is_ready() or member not in self.longcats:
            return

        if old_voice_state.channel == new_voice_state.channel:
            timestamp = datetime.now()
        else:
            timestamp = await self.stamp_voice_state(member)

        await asyncio.sleep(self.connect_delay)
        await self.record_or_stop(new_voice_state.channel, timestamp.strftime(DTFORMAT))

    async def stamp_voice_state(self, member: discord.Member):
        self.last_timestamp = datetime.now()
        nickname = member.name

        try:
            fullname = member.global_name
        except AttributeError:
            fullname = member.display_name

        try:
            channel = member.voice.channel.name
        except AttributeError:
            channel = None

        name = f"[{fullname}/{nickname}]"

        for notifier in self.notifiers:
            await notifier.notify(self.last_timestamp, name, channel)

        return self.last_timestamp

    @property
    def vclient(self) -> discord.VoiceClient:
        return self.voice_clients[0] if len(self.voice_clients) != 0 else None

    def privacy_respected(self, vchannel):
        return len(vchannel.members) >= self.privacy_doorstep

    def have_to_go(self, vchannel):
        return (len(vchannel.members) - 1) < self.staying_number

    async def change_nickname(self, old, new):
        await self.guild.me.edit(nick=new)
        print(f'Changed current nick "{old}" to "{new}"')

    async def record_or_stop(self, vchannel, save_id):
        if (
            self.do_record
            and vchannel is not None
            and self.vclient is None
            and self.privacy_respected(vchannel)
        ):
            if self.initial_nickname:
                await self.change_nickname(
                    self.guild.me.nick,
                    "Deputy " + self.initial_nickname.lstrip("Deputy "),
                )

            try:
                await vchannel.connect()
            except discord.errors.ClientException as e:
                print(f"Error while connecting to a voice channel: {e}")

            await self.start_recording(save_id)
        elif (
            self.vclient is not None
            and self.vclient.recording
            and (vchannel is None or self.have_to_go(vchannel))
        ):
            await self.stop_recording()
            await self.reset_nickname()

    async def start_recording(self, save_id):
        """save_id - идентификатор сохранненых записей, например, timestamp"""

        print("Start recording")

        self.vclient.play(
            SilenceAudioSource()
        )  # see https://github.com/Pycord-Development/pycord/issues/1432#issuecomment-1214196651

        if self.vclient and not self.vclient.recording:
            self.vclient.start_recording(
                self.recorder_sink(),
                self.stop_recording_callback,
                save_id,
                sync_start=True,
            )

    async def reset_nickname(self):
        if self.initial_nickname:
            await self.change_nickname(
                self.guild.me.nick, self.initial_nickname.lstrip("Deputy ")
            )

    async def stop_recording(self):
        if self.vclient and self.vclient.recording:
            self.vclient.stop_recording()

    async def stop_recording_callback(self, sink: discord.sinks.Sink, save_id):
        print(f"Stopping recording")
        if self.last_timestamp:
            taken = datetime.now() - self.last_timestamp
            print(f"Taken {taken}")

        if self.vclient is not None:
            self.vclient.stop()

        savedir = os.path.join(PROJECT_ROOT, "records", save_id)

        os.makedirs(savedir, exist_ok=True)

        files = []
        for user_id, audio in sink.audio_data.items():
            if (user := self.get_user(user_id)) is None:
                continue
            filename = f"{user.display_name}.{sink.encoding}"
            files.append((audio.file, filename))

        for bytes, name in files:
            bytes: BytesIO
            path = os.path.join(savedir, name)
            with open(path, "wb") as file:
                file.write(bytes.read())
                print(f'Saved "{path}"')

        print(f"Waiting {self.disconnect_delay}s before disconecting voice channel")
        await asyncio.sleep(self.disconnect_delay)

        if self.vclient is not None:
            await self.vclient.disconnect(force=True)
            print("Disconnected from voice channel")

        print("Stopped recording")

    async def close(self):
        if self.vclient and self.vclient.recording:
            await self.stop_recording()
            await self.reset_nickname()

        await super().close()


if __name__ == "__main__":
    logging.disable(logging.INFO)
    load_dotenv()

    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

    if DISCORD_TOKEN is None:
        raise ValueError("Discord token was not provided")

    if TELEGRAM_TOKEN is None:
        raise ValueError("Discord token was not provided")

    DEBUG = int(os.getenv("DEBUG", 0))

    if DEBUG:
        GUILD, LONGCATS = "Mark's Testing Polygon", {"markmelix2"}
    else:
        GUILD, LONGCATS = "Простое Сообщество", {"agent_of_silence", "а.т.#2766"}

    ADMINS = {
        425717640,  # Mark
    }
    OTHERS = {
        891074228,  # Anton
    }

    CHATS = ADMINS if DEBUG else ADMINS.union(OTHERS)

    print("Running in", "debug" if DEBUG else "release", "mode")

    LongcatRecorder(
        guild_name=GUILD,
        longcat_names=LONGCATS,
        notifiers=(BaseNotifier(),)
        if DEBUG
        else (BaseNotifier(), TelegramNotifier(chats=CHATS, token=TELEGRAM_TOKEN)),
        recorder_sink=discord.sinks.OGGSink,
        privacy_doorstep=int(os.getenv("PRIVACY_DOORSTEP", 0 if DEBUG else 3)),
        disconnect_delay=0 if DEBUG else 15,
        connect_delay=0 if DEBUG else 10,
    ).run(DISCORD_TOKEN)
