# Discord Libraries
from discord.ext import commands, tasks

# Python Libraries
from datetime import datetime, timedelta
import pygsheets

# Local Includes
from Shared import *

class KeepingKarlsson(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

        self.PYGS = pygsheets.authorize(service_file="/var/www/DiscordBot/service_client_secret.json")

        self.check_threads_loop.start()

    # fasttrack leaderboard
    @commands.command(name="fasttrack", aliases=["ft"])
    @is_KK_guild()
    async def ft(self, ctx): # TODO: Optional argument to !ft <user>
        # Open the fasttrack gsheet and find the author
        sheet = self.PYGS.open_by_key("1ob_tgG0lIk7THn6V6ksWIGZNLnxEYQfRAC2n4jeiNZ4")
        worksheet = sheet.worksheet_by_title("Fasttrack2020")
        author = ctx.message.author.name + "#" + ctx.message.author.discriminator
        user = worksheet.find(author)
        if not user:
            await ctx.send("Sorry, I couldn't find your team in the list")

        rowstart = user[0].address.row-2 # two teams above the author
        rowend = user[0].address.row+2 # two teams below the author
        if rowstart < 2: # error checking for beginning of list
            rowstart = 2
            rowend = 6
        # TODO: Add error checking for end of list
        data = worksheet.get_values(f"A{rowstart}", f"G{rowend}")

        # Loop through data from the table
        teamNames = discordNames = points = ""
        for i, user in enumerate(data):
            teamID, teamName, manager, league, discordName, KKUPFLRank, pf = user

            # Format the data to display
            if discordName == author:
                teamNames += f"**{KKUPFLRank}. {teamName}**\n"
                discordNames += f"**{discordName}**\n"
                points += f"**{pf}**\n"
            else:
                teamNames += f"{KKUPFLRank}. {teamName}\n"
                discordNames += f"{discordName}\n"
                points += f"{pf}\n"

        # Create and send an embed
        embed = discord.Embed(title="FastTrack Leaderboard", description="This is your ranking in the whole wide KKUPFL", color=0x00aaff)
        embed.add_field(name="Team name", value=teamNames, inline=True)
        embed.add_field(name="Discord user", value=discordNames, inline=True)
        embed.add_field(name="Points", value=points, inline=True)
        embed.set_footer(text="See the full standings at www.kkupfl.com/stat-attack/manager-stats")
        await ctx.channel.send(embed=embed)

    # Thread management loop
    @tasks.loop(hours=1.0)
    async def check_threads_loop(self):
        for channel in self.bot.get_channel(MAKE_A_THREAD_CATEGORY_ID).text_channels[1:]:
            last_message = (await channel.history(limit=1).flatten())[0]
            last_message_delta = datetime.utcnow() - last_message.created_at

            # If the last message in the threads was more than a day ago and we aren't keeping it, lock it and mark for removal
            if last_message_delta > timedelta(hours=24) and "tkeep" not in channel.name and last_message.author != self.bot.user:
                self.log.info(f"{channel.name} is stale.")
                for role_name in [PATRONS_ROLE_ID, PARTONS_ROLE_ID]:
                        role = self.bot.get_guild(KK_GUILD_ID).get_role(role_name)
                        perms = channel.overwrites_for(role)
                        perms.send_messages=False
                        await channel.set_permissions(role, overwrite=perms)
                await channel.send("This thread has been locked due to 24h of inactivity, and will be deleted in 12 hours. Tag @zebra in #help-me if you'd like to keep the thread open longer.")
            # If the last message was more than 12 hours ago by this bot, delete the thread
            elif last_message_delta > timedelta(hours=12) and "tkeep" not in channel.name and last_message.author == self.bot.user:
                self.log.info(f"{channel.name} deleted.")
                await channel.delete()

        self.log.info("Thread check complete.")

    @check_threads_loop.before_loop
    async def before_check_threads_loop(self):
        await self.bot.wait_until_ready()

    @check_threads_loop.error
    async def check_threads_loop_error(self, error):
        self.log.error(error)

def setup(bot):
    bot.add_cog(KeepingKarlsson(bot))
