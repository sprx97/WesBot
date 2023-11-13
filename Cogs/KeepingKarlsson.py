# Discord Libraries
import discord
from discord.ext import commands, tasks

# Python Libraries
import asyncio
from datetime import datetime, timedelta, timezone
import pygsheets

# Local Includes
from Shared import *

class KeepingKarlsson(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

        self.MANAGER_CARD_URL_BASE = "https://metabase-kkupfl.herokuapp.com/public/dashboard/43c4f00d-4056-4668-b3ed-652858167dc8?discordid="
        self.PYGS = pygsheets.authorize(service_file="/var/www/DiscordBot/service_client_secret_KK.json")

    async def cog_load(self):
        self.bot.loop.create_task(self.start_loops())

    async def start_loops(self):
        self.check_league_activity_loop.start()
        self.loops.append(self.check_league_activity_loop)

    @app_commands.command(name="card", description="Show the link to a player's KKUPFL Manager Card.")
    @app_commands.describe(user="The user to show the card for.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def card(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.send_response(f"{self.MANAGER_CARD_URL_BASE}/{user.id}")

    # fasttrack leaderboard
    async def fasttrack_core(self, worksheet, author, rowstart, rowend):
        data = worksheet.get_values(f"A{rowstart}", f"G{rowend}")

        # Loop through data from the table
        line = "```diff\n"
        for i, user in enumerate(data):
            teamID, teamName, manager, league, discordName, KKUPFLRank, pf = user

            if discordName == author:
                line += "+"
            else:
                line += " "
            
            rank_width = len(str(rowend-1)) + 2

            MAX_NAME_WIDTH = 18
            line += (KKUPFLRank + ".").ljust(rank_width) + discordName[:MAX_NAME_WIDTH].ljust(MAX_NAME_WIDTH) + " " + pf.ljust(7) + "\n"

        line += "```"

        embed = discord.Embed(title="FastTrack Leaderboard", description="This is your ranking in the whole wide KKUPFL", color=0x00aaff)
        embed.add_field(name="Rank", value=line)
        embed.add_field(name="Info", value="Try the commands `!ft @user` or `!fttop` too!", inline=False)
        embed.set_footer(text="See the full standings at www.kkupfl.com/stat-attack/manager-stats")

        return embed

    @commands.command(name="fttop", aliases=["fasttracktop"])
    @is_KK_guild()
    @is_botspam_channel()
    async def fttop(self, ctx, year=None):
        # Open the fasttrack gsheet
        sheet = self.PYGS.open_by_key("1ob_tgG0lIk7THn6V6ksWIGZNLnxEYQfRAC2n4jeiNZ4")

        # Get the right year's fasttrack
        if year == None:
            year = Config.config["year"]
        worksheet = sheet.worksheet_by_title(f"Fasttrack{year}")      

        embed = await self.fasttrack_core(worksheet, None, 2, 6)
        await ctx.channel.send(embed=embed)

    @commands.command(name="ft", aliases=["fasttrack"])
    @is_KK_guild()
    @is_botspam_channel()
    async def ft(self, ctx, member: discord.Member=None, year=None):
        # Open the fasttrack gsheet and find the author
        sheet = self.PYGS.open_by_key("1ob_tgG0lIk7THn6V6ksWIGZNLnxEYQfRAC2n4jeiNZ4")

        # Get the right year's fasttrack
        if year == None:
            year = Config.config["year"]
        worksheet = sheet.worksheet_by_title(f"Fasttrack{year}")

        author = ctx.message.author.name + "#" + ctx.message.author.discriminator
        if member != None:
            author = member.name + "#" + member.discriminator
        
        user = worksheet.find(author)
        if not user:
            pronoun = "your" if member == None else "that"
            await ctx.send(f"Sorry, I couldn't find {pronoun} team in the list.")

        rowstart = user[0].address.row - 2 # two teams above the author
        rowend = user[0].address.row + 2 # two teams below the author
        if rowstart < 2: # error checking for beginning of list
            rowstart = 2
            rowend = 6
        # TODO: Add error checking for end of list

        embed = await self.fasttrack_core(worksheet, author, rowstart, rowend)
        await ctx.channel.send(embed=embed)

    # League activity checker loop
    @tasks.loop(hours=24.0)
    async def check_league_activity_loop(self):
        return # Disabled for offseason -- should be able to put a command to enable/disable this and give Brelan permissions too

        cocommishes_channel = self.bot.get_guild(KK_GUILD_ID).get_channel(COCOMMISHES_CHANNEL_ID)
        for channel in self.bot.get_guild(KK_GUILD_ID).channels:
            # Only look at league-specific chat channels
            channel_name = channel.name
            if not channel_name.startswith("tier-"):
                continue
            channel_name = channel_name.split("-")[2]

            # If the last message in the league channel was more than 3 days ago, ping the zebra channel
            last_message = [messages async for messages in channel.history(limit=1)][0]
            last_message_delta = datetime.now(timezone.utc) - last_message.created_at
            if last_message_delta > timedelta(hours=120):
                found = False
                for role in self.bot.get_guild(KK_GUILD_ID).roles:
                    role_name = role.name.lower()
                    if channel_name in role_name:
                        await cocommishes_channel.send(f"No activity in last 5 days in {role.mention}")
                        found = True
                        break
                if not found:
                    self.log.error(f"No matching role found for channel {channel_name}")

        self.log.info("League activity check complete.")

    @check_league_activity_loop.before_loop
    async def before_check_league_activity_loop(self):
        await self.bot.wait_until_ready()

        # Sleep until midnight Sunday (Sat night) to call at the same time every week
        curr_time = datetime.utcnow()-timedelta(hours=ROLLOVER_HOUR_UTC)
        target_time = curr_time + timedelta(days=1.0)
        target_time = target_time.replace(hour=0, minute=0, second=0, microsecond=0)
        delta = target_time-curr_time

        self.log.info("Sleeping league activity loop for " + str(delta))
        await asyncio.sleep(delta.total_seconds())

    @check_league_activity_loop.error
    async def check_league_activity_loop_error(self, error):
        self.log.error(error)

async def setup(bot):
    await bot.add_cog(KeepingKarlsson(bot), guild=discord.Object(id=KK_GUILD_ID))
