import asyncio
import os
import discord

from io import BytesIO
from typing import Collection
from datetime import datetime, timezone
from dotenv import load_dotenv
from common import DTFORMAT, UTCTZ, con, create_common_tables

PROJECT_ROOT = "/".join(__file__.split("/")[:-1])


class LongcatRecorder(discord.Client):
    """Discord bot, отслеживающий и фиксирующий действия лонгкета в голосовых
    чатах указанного сервера."""

    def __init__(
        self,
        *args,
        guild_name: str,
        longcat_names: Collection[str],
        privacy_doorstep: int = 5,
        recorder_sink: discord.sinks.Sink | None = None,
        connect_delay: int = 10,
        disconnect_delay: int = 15,
        disable_connect_delay_just_after_start: bool = True,
        staying_number: int = 1,
        **kwargs,
    ):
        """guild_name       - название сервера, в котором стоит вести слежку
        longcats         - ники аккаунтов лонгкета
        privacy_doorstep - сколько человек как минимум должно быть в голосовом чате, чтобы бот подключался
        recorder_sink    - кодек записи голосовых сообщений, например, `discord.sinks.MP4Sink`, чтобы звук писался в .mp4 формате
        connect_delay    - задержка перед подключением к голосовому чату
        disconnect_delay - задержка перед выходом из голосового чата
        disable_connect_delay_just_after_start:
        - отключить ли искусственную задержку перед подключением в голосовой чат, если бот только что запустился
        """
        super().__init__(*args, **kwargs)

        self.guild_name = guild_name
        self.longcat_names = longcat_names
        self.privacy_doorstep = privacy_doorstep
        self.recorder_sink = (
            recorder_sink if recorder_sink else discord.sinks.WaveSink()
        )
        self.connect_delay = connect_delay
        self.disconnect_delay = disconnect_delay
        self.disable_connect_delay_just_after_start = (
            disable_connect_delay_just_after_start
        )
        self.staying_number = staying_number

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        print(f'Watching {self.longcat_names} within "{self.guild_name}" guild')
        print("------")

        self.guild = discord.utils.get(self.guilds, name=GUILD)
        self.longcats = set(
            filter(lambda member: member.name in LONGCATS, self.guild.members)
        )

        for longcat in self.longcats:
            if longcat.voice is not None and longcat.voice.channel is not None:
                if not self.disable_connect_delay_just_after_start:
                    await asyncio.sleep(self.connect_delay)
                await self.record_or_stop(
                    longcat.voice.channel, self.stamp_voice_state(longcat)
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
            timestamp = datetime.utcnow()
        else:
            timestamp = self.stamp_voice_state(member)

        await asyncio.sleep(self.connect_delay)
        await self.record_or_stop(new_voice_state.channel, timestamp.strftime(DTFORMAT))

    def stamp_voice_state(self, member: discord.Member):
        utc_dt = datetime.now(timezone.utc)
        utc = int(utc_dt.timestamp())

        nickname = member.name

        try:
            fullname = member.global_name
        except AttributeError:
            fullname = member.display_name

        try:
            channel = member.voice.channel.name
        except AttributeError:
            channel = None

        cur = con.cursor()
        cur.execute(
            "INSERT INTO history (utc, nickname, fullname, channel) VALUES (?, ?, ?, ?)",
            (utc, nickname, fullname, channel),
        )
        con.commit()
        cur.close()

        print()
        print(f"Stamped at {utc_dt.astimezone(UTCTZ).strftime(DTFORMAT)}")
        print(f'[{fullname}/{nickname}] in "{channel}"')
        print()

        return utc_dt

    @property
    def vclient(self) -> discord.VoiceClient:
        return self.voice_clients[0] if len(self.voice_clients) != 0 else None

    def privacy_respected(self, vchannel):
        return len(vchannel.members) >= self.privacy_doorstep

    def have_to_go(self, vchannel):
        return (len(vchannel.members) - 1) < self.staying_number

    async def record_or_stop(self, vchannel, save_id):
        if (
            vchannel is not None
            and self.vclient is None
            and self.privacy_respected(vchannel)
        ):
            await vchannel.connect()
            self.record(save_id)
        elif (
            self.vclient is not None
            and self.vclient.recording
            and (vchannel is None or self.have_to_go(vchannel))
        ):
            self.vclient.stop_recording()

    def record(self, save_id):
        """save_id - идентификатор сохранненых записей, например, timestamp"""

        print("Start recording")
        self.vclient.start_recording(
            self.recorder_sink, self.stop_recording_callback, save_id
        )

    async def stop_recording_callback(self, sink: discord.sinks.Sink, save_id):
        print("Stopping recording")

        savedir = f"{PROJECT_ROOT}/records/{save_id}"

        os.makedirs(savedir, exist_ok=True)

        files = []
        for user_id, audio in sink.audio_data.items():
            if (user := self.get_user(user_id)) is None:
                continue
            filename = f"{user.display_name}.{sink.encoding}"
            files.append((audio.file, filename))

        for bytes, name in files:
            bytes: BytesIO
            with open(f"{savedir}/{name}", "wb") as file:
                file.write(bytes.read())

        await asyncio.sleep(self.disconnect_delay)
        await self.vclient.disconnect(force=True)


if __name__ == "__main__":
    create_common_tables()
    load_dotenv()

    TOKEN = os.getenv("DISCORD_TOKEN")

    if TOKEN is None:
        raise ValueError("Discord token was not provided")

    DEBUG = int(os.getenv("DEBUG", 0))

    if DEBUG:
        GUILD, LONGCATS = "Mark's Testing Polygon", {"markmelix2"}
    else:
        GUILD, LONGCATS = "Простое Сообщество", {"agent_of_silence", "а.т.#2766"}

    print("Running in", "debug" if DEBUG else "release", "mode")

    LongcatRecorder(
        guild_name=GUILD,
        longcat_names=LONGCATS,
        privacy_doorstep=int(os.getenv("PRIVACY_DOORSTEP", 0 if DEBUG else 5)),
        disconnect_delay=0 if DEBUG else 15,
        connect_delay=0 if DEBUG else 10,
    ).run(TOKEN)
