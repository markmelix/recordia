import discord

from datetime import datetime
from discord.ext.audiorec import NativeVoiceClient
from discord.ext import tasks
from dotenv import load_dotenv
from common import *

load_dotenv()
TOKEN = getenv("DISCORD_TOKEN")

# GUILD, LONGCATS = "Простое Сообщество", {"agent_of_silence", "а.т.#2766"}
GUILD, LONGCATS = "Mark's Testing Polygon", {"markmelix2"}

create_common_tables()


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

        self.guild = discord.utils.get(self.guilds, name=GUILD)
        self.longcats = set(
            filter(lambda member: member.name in LONGCATS, self.guild.members)
        )

    def stamp_voice_state_update(self, member: discord.Member):
        utc = int(datetime.utcnow().timestamp())
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

        return datetime.now()

    @property
    def vclient(self) -> NativeVoiceClient:
        return self.voice_clients[0] if len(self.voice_clients) != 0 else None

    async def stop_recording(self, filename):
        print("Running stop recording checks")
        print(self.vclient)
        print(self.vclient.is_recording())
        if (
            self.vclient is not None
            and self.vclient.is_recording()
            and (bytes := (await self.vclient.stop_record())) is not None
        ):
            print("Stop recording")
            try:
                os.mkdir("records")
            except FileExistsError:
                pass
            with open(f"records/{filename}.wav", "wb") as file:
                file.write(bytes)

    def record(self):
        print("Start recording")
        print(self.vclient._connection)
        self.vclient.record(lambda e: print(f"Error happened while recording: {e}"))

    @tasks.loop(seconds=1)
    async def recording_checker(self):
        if self.vclient is not None and not self.vclient.is_recording():
            self.record()

    async def record_or_stop(self, vchannel, filename: str):
        if vchannel is not None and self.vclient is None:
            self.recording_checker.start()
            await vchannel.connect(cls=NativeVoiceClient)
            await self.vclient.connect()
        elif vchannel is None and self.vclient is not None:
            self.recording_checker.stop()
            await self.stop_recording(filename)
            await self.vclient.disconnect(force=True)

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
            timestamp = datetime.now()
            # timestamp = self.stamp_voice_state_update(member)

        await self.record_or_stop(new_voice_state.channel, timestamp.strftime(DTFORMAT))


client = MyClient()
client.run(TOKEN)
