#!/usr/bin/env python3

import os
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
            text = f"{name} desided to take a rest"
        else:
            text = f'{name} is inside "{channel}"'

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


class RecordiaBot(discord.Client):
    """Discord bot logging and recording discord user actions inside voice
    channels within specified discord guild."""

    def __init__(
        self,
        *args,
        guild_name: str,
        user_names: Collection[str],
        notifiers: Collection,
        record: bool = True,
        recorder_sink=None,
        privacy_doorstep: int = 5,
        connect_delay: int = 10,
        disconnect_delay: int = 15,
        disable_connect_delay_just_after_start: bool = True,
        staying_number: int = 1,
        **kwargs,
    ):
        """guild_name       - guild name to log
        user_names       - names of users to be logged
        notifiers        - classes with `notify` method to be called when some vc-related action happened
        record           - should bot record what people say in a voice channel
        recorder_sink    - **un**initialized voice recording codec, e. g. `discord.sinks.MP4Sink` to write sound in mp4 format
        privacy_doorstep - minimum number of people inside a voice channel for bot to connect
        connect_delay    - delay before voice channel connection
        disconnect_delay - delay before voice channel disconnection
        disable_connect_delay_just_after_start:
        - should the fake connect delay be turned off if the bot had just started
        staying_number   - how many people should be in a voice channel for bot to stay there
        """
        super().__init__(*args, **kwargs)

        self.guild_name = guild_name
        self.user_names = user_names
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
        print(f'Watching {self.user_names} within "{self.guild_name}" guild')
        print("------")

        self.guild = discord.utils.get(self.guilds, name=self.guild_name)
        self.initial_nickname = self.guild.me.nick
        self.watch_users = set(
            filter(lambda member: member.name in self.user_names, self.guild.members)
        )

        for user in self.watch_users:
            if user.voice is not None and user.voice.channel is not None:
                if not self.disable_connect_delay_just_after_start:
                    await asyncio.sleep(self.connect_delay)
                await self.record_or_stop(
                    user.voice.channel,
                    (await self.stamp_voice_state(user)).strftime(DTFORMAT),
                )
                break

    async def on_voice_state_update(
        self,
        member: discord.Member,
        old_voice_state: discord.VoiceState,
        new_voice_state: discord.VoiceState,
    ):
        if not self.is_ready() or member not in self.watch_users:
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
        """save_id - identifier of the saved recording, e. g. timestamp."""

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
    import logging

    SINKS = {
        "m4a": discord.sinks.M4ASink,
        "mka": discord.sinks.MKASink,
        "mkv": discord.sinks.MKVSink,
        "mp3": discord.sinks.MP3Sink,
        "mp4": discord.sinks.MP4Sink,
        "ogg": discord.sinks.OGGSink,
        "pcm": discord.sinks.PCMSink,
        "wave": discord.sinks.WaveSink,
    }

    def parse_args():
        import argparse

        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        parser.add_argument(
            "-D",
            "--discord-token",
            metavar="TOKEN",
            help="Token used to authorize the discord bot or DISCORD_TOKEN env",
        )
        parser.add_argument(
            "-T",
            "--telegram-token",
            metavar="TOKEN",
            help="Token used to authorize the telegram bot or TELEGRAM_TOKEN env",
        )
        parser.add_argument(
            "-C",
            "--telegram-chats",
            metavar="IDS",
            help="Telegram chats for telegram bot to send notifications in",
        )
        parser.add_argument(
            "-r",
            "--record",
            help="should bot record what people say in a voice channel",
            action="store_true",
        )
        parser.add_argument(
            "-e",
            "--sound-encoding",
            metavar="ENC",
            help=f"Format for sound to be encoded and written in. Available: {', '.join(sink_encodings := SINKS.keys())}",
            choices=sink_encodings,
            default="ogg",
        )
        parser.add_argument(
            "-p",
            "--privacy-doorstep",
            metavar="NUM",
            help="Minimum number of people inside a voice channel for bot to connect",
            type=int,
            default=3,
        )
        parser.add_argument(
            "-c",
            "--connect-delay",
            metavar="SECS",
            help="Delay before voice channel connection",
            type=int,
            default=(60 * 5),
        )
        parser.add_argument(
            "-d",
            "--disconnect-delay",
            metavar="SECS",
            help="Delay before voice channel disconnection",
            type=int,
            default=(60 * 5),
        )

        parser.add_argument("guild", help="guild name to log")
        parser.add_argument("users", help="comma-separated names of users to be logged")

        return parser, parser.parse_args()

    logging.disable(logging.INFO)
    load_dotenv()

    cli, args = parse_args()

    if (discord_token := args.discord_token) is None and (
        discord_token := os.getenv("DISCORD_TOKEN")
    ) is None:
        cli.error("Discord token was not provided")

    notifiers = list()
    notifiers.append(BaseNotifier())

    if args.telegram_chats and (
        (token := args.discord_token) or (token := os.getenv("TELEGRAM_TOKEN"))
    ):
        notifiers.append(
            TelegramNotifier(chats=args.telegram_chats.split(","), token=token)
        )

    RecordiaBot(
        guild_name=args.guild,
        user_names=args.users.split(","),
        notifiers=notifiers,
        record=args.record,
        recorder_sink=SINKS[args.sound_encoding],
        privacy_doorstep=args.privacy_doorstep,
        disconnect_delay=args.disconnect_delay,
        connect_delay=args.connect_delay,
    ).run(discord_token)
