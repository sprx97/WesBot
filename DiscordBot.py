# Python Libaries
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import sys

# Discord Libraries
import discord
from discord.ext import commands

# Local Includes
import Shared

class Wes(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.killed = False
        self.start_timestamp = datetime.utcnow()
        self.log = self.create_log("Bot")
        super(Wes, self).__init__(*args, **kwargs)

    # Returns the days, hours, minutes, and seconds since the bot was last initialized
    def calculate_uptime(self):
        uptime = (datetime.utcnow() - self.start_timestamp)
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return uptime.days, hours, minutes, seconds

    # Creates or returns a log file of the given name.
    def create_log(self, name):
        logger = logging.getLogger(name)

        # Only create file handlers if the log doesn't have any, not on reload
        if not logger.hasHandlers():
            logger.setLevel(logging.INFO)

            # Create <Cog>.log log file
            fh = RotatingFileHandler(f"Logs/{name}.log", "a+", maxBytes=1000000, backupCount=1) # one file, max size of 4mb
            fh.setLevel(logging.INFO)
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(filename)s %(lineno)d %(message)s"))
            logger.addHandler(fh)

        return logger

    async def sync_command_trees(self):
        self.log.info("OTH Commands")
        for command in self.tree.get_commands(guild=discord.Object(id=Shared.OTH_GUILD_ID)):
            self.log.info(f"\t{command.name}")
        await self.tree.sync(guild=discord.Object(id=Shared.OTH_GUILD_ID))
        self.log.info("Synced OTH")

        self.log.info("KK Commands")
        for command in self.tree.get_commands(guild=discord.Object(id=Shared.KK_GUILD_ID)):
            self.log.info(f"\t{command.name}")
        await self.tree.sync(guild=discord.Object(id=Shared.KK_GUILD_ID))
        self.log.info("Synced KK")

    async def setup_hook(self):
        await bot.load_extension("Cogs.Debug")
        await bot.load_extension("Cogs.KeepingKarlsson")
        await bot.load_extension("Cogs.Memes")
        await bot.load_extension("Cogs.OTChallenge")
        await bot.load_extension("Cogs.OTH")
        await bot.load_extension("Cogs.Scoreboard")

intents = discord.Intents.default()
intents.members = True
intents.reactions = True
intents.message_content = True

bot = Wes(command_prefix="!", case_insensitive=True, help_command=None, intents=intents, heartbeat_timeout=120)

@bot.event
async def on_connect():
    Shared.start_timestamp = datetime.utcnow()
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Game(name="NHL '94"))
    await bot.user.edit(username="Wes McCauley")
    # avatar=fp.read()
    bot.log.info("Bot started.")

@bot.event
async def on_disconnect():
    days, hours, minutes, seconds = bot.calculate_uptime()
    bot.log.info(f"Bot disconnected after {days} day(s), {hours} hour(s), {minutes} minute(s), {seconds} seconds(s).")

@bot.event
async def on_ready():
    await bot.sync_command_trees()
    bot.log.info("Bot ready.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            bot.run(Shared.config["beta_discord_token"], reconnect=True)
    else:
        bot.run(Shared.config["discord_token"], reconnect=True)

# Hang if bot was killed by command to prevent recreation by pm2
if bot.killed:
    while True:
        continue
