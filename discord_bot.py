from io import BytesIO
import discord

from datetime import datetime
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
    def vclient(self) -> discord.VoiceClient:
        return self.voice_clients[0] if len(self.voice_clients) != 0 else None

    def record(self, filename):
        print("Start recording")
        self.vclient.start_recording(
            discord.sinks.WaveSink(), self.stop_recording_callback, filename
        )

    async def stop_recording_callback(self, sink: discord.sinks.WaveSink, dirname):
        print("Stopping recording")
        root = f"records/{dirname}"
        os.makedirs(root, exist_ok=True)
        files = [
            (audio.file, f"{user_id}.{sink.encoding}")
            for user_id, audio in sink.audio_data.items()
        ]
        for bytes, name in files:
            bytes: BytesIO
            with open(f"{root}/{name}.wav", "wb") as file:
                file.write(bytes.read())
        await self.vclient.disconnect(force=True)

    async def record_or_stop(self, vchannel, filename: str):
        if vchannel is not None and self.vclient is None:
            await vchannel.connect()
            self.record(filename)
        elif vchannel is None and self.vclient is not None and self.vclient.recording:
            self.vclient.stop_recording()

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

        self.guild = discord.utils.get(self.guilds, name=GUILD)
        self.longcats = set(
            filter(lambda member: member.name in LONGCATS, self.guild.members)
        )
        for longcat in self.longcats:
            if longcat.voice is not None and longcat.voice.channel is not None:
                await self.record_or_stop(
                    longcat.voice.channel, datetime.now().strftime(DTFORMAT)
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
            timestamp = self.stamp_voice_state_update(member)

        await self.record_or_stop(new_voice_state.channel, timestamp.strftime(DTFORMAT))


client = MyClient()
client.run(TOKEN)
