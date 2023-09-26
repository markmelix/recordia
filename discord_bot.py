from datetime import datetime
import discord

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
        self.longcats = {}

    async def setup_hook(self):
        self.background_task.start()

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member not in self.longcats:
            return

        print(f"VoiceState changed, user: {member}")

        utc = int(datetime.utcnow().timestamp())
        nickname = member.name

        try:
            fullname = member.global_name
        except AttributeError:
            fullname = member.display_name

        try:
            channel = after.channel.name
        except AttributeError:
            channel = None

        cur = con.cursor()
        cur.execute(
            "INSERT INTO history (utc, nickname, fullname, channel) VALUES (?, ?, ?, ?)",
            (utc, nickname, fullname, channel),
        )
        con.commit()
        cur.close()

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

        self.guild = discord.utils.get(self.guilds, name=GUILD)
        self.longcats = set(
            filter(lambda member: member.name in LONGCATS, self.guild.members)
        )


client = MyClient()
client.run(TOKEN)
