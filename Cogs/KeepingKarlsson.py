# Discord Libraries
import discord
from discord import app_commands

# Local Includes
from Shared import *

class KeepingKarlsson(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

        self.MANAGER_CARD_URL_BASE = "https://metabase-kkupfl.herokuapp.com/public/dashboard/43c4f00d-4056-4668-b3ed-652858167dc8?discordid="
        self.FAST_TRACK_URL = "https://metabase-kkupfl.herokuapp.com/public/dashboard/20301480-3e1e-483a-8a38-3b67a2b55816"

    @app_commands.command(name="card", description="Show the link to a player's KKUPFL Manager Card.")
    @app_commands.describe(user="The user to show the card for.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def card(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.send_message(f"{self.MANAGER_CARD_URL_BASE}{user.id}")

    @app_commands.command(name="fasttrack", description="Show the link to the KKUPFL Fast Track Leaderboard.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def fasttrack(self, interaction: discord.Interaction):
        await interaction.response.send_message(self.FAST_TRACK_URL)

async def setup(bot):
    await bot.add_cog(KeepingKarlsson(bot), guild=discord.Object(id=KK_GUILD_ID))
