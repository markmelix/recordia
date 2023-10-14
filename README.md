# Recordia Voice Logging Botkit
Botkit for logging and recording actions of users in voice channels in a guild.

Telegram bot notifies when specified user (dis)connects a voice channel.

Discord bot logs all voice channel (dis)connections and records all voice sounds
within specific user.


## Installation
For voice recording you must have `libffi-dev`, `python-dev` and `ffmpeg`
installed. Also having `poetry` python manager is required to install set up
everything. 

After you install everything needed, run `chmod +x recordia.py && poetry install` inside the project
root.

## Running bots
```shell
poetry shell
./recordia.py --help # see available options
./recordia.py -D "discord_token" -T "telegram_token" "Name of a guild to watch" "user1,user2,user3" # watch users user1, user2 and user3 within specified guild
```
