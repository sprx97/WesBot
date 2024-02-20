# Discord Libraries
import discord
from discord import app_commands
from discord.ext import tasks


# Python Libraries
import asyncio
from datetime import datetime, timedelta
import importlib

# Local Includes
Shared = importlib.import_module("Shared")
from Shared import *

class Debug(WesCog):
#region Basic debug commands

    @app_commands.command(name="ping", description="Checks the bot for a response.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("pong", ephemeral=True)

    @app_commands.command(name="pong", description="Checks the bot for a response.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def pong(self, interaction: discord.Interaction):
        await interaction.response.send_message("ping", ephemeral=True)

    @app_commands.command(name="uptime", description="Displays how long since the bot last crashed/restarted.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def uptime(self, interaction: discord.Interaction):
        days, hours, minutes, seconds = self.bot.calculate_uptime() 

        msg = "It has been "
        if days > 0:
            msg += str(days) + " day(s), "
        if days > 0 or hours > 0:
            msg += str(hours) + " hour(s), "
        if days > 0 or hours > 0 or minutes > 0:
            msg += str(minutes) + " minute(s), "
        msg += str(seconds) + " second(s) since last accident."

        await interaction.response.send_message(msg, ephemeral=True)

#endregion
#region Bot admin commands

    cog_choices = []
    cog_choices.append(discord.app_commands.Choice(name="All", value="All"))
    for cog in all_cogs:
        cog_choices.append(discord.app_commands.Choice(name=cog, value=cog))

    @app_commands.command(name="kill", description="Shuts down a cog.")
    @app_commands.describe(cog="Which cog to shut down.")
    @app_commands.choices(cog=cog_choices)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.check(is_bot_owner)
    async def kill(self, interaction: discord.Interaction, cog: discord.app_commands.Choice[str]):
        if not await self.bot.is_owner(interaction.user):
            raise Exception("This command can only be run by the bot owner.")

        cog = cog.value
        if cog == "All":
            self.bot.killed = True
            await interaction.response.send_message("⚔️ Committing honorable sudoku...")
            await self.bot.close()
            self.log.info("Manually killed bot.")
        else:
            await self.bot.unload_extension(cog)
            await interaction.response.send_message(f"{cog} successfully unloaded.")
            self.log.info(f"Unloaded {cog}.")

    @kill.error
    async def kill_error(self, interaction, error):
        await interaction.response.send_message(f"Failure in kill: {error}", ephemeral=True)

    async def reload_single_cog(self, interaction, cog):
        await self.bot.reload_extension(cog)
        self.log.info(f"Reloaded {cog}.")

    @app_commands.command(name="reload", description="Reloads a cog.")
    @app_commands.describe(cog="Which cog to reload.")
    @app_commands.choices(cog=cog_choices)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.check(is_bot_owner)
    async def reload(self, interaction: discord.Interaction, cog: discord.app_commands.Choice[str]):
        await interaction.response.defer(thinking=True, ephemeral=True)

        if not await self.bot.is_owner(interaction.user):
            raise Exception("This command can only be run by the bot owner.")

        importlib.reload(Shared)

        cog = cog.value
        if cog == "All":
            for cog in all_cogs:
                await self.reload_single_cog(interaction, cog)
            await interaction.edit_original_response(content="All cogs successfully reloaded.")
        else:
            await self.reload_single_cog(interaction, cog)
            await interaction.edit_original_response(content=f"{cog} successfully reloaded.")

    @reload.error
    async def reload_error(self, interaction, error):
        await interaction.followup.send(f"Failure in reload: {error}")

    @app_commands.command(name="log", description="Displays recent lines in the log file for a cog.")
    @app_commands.describe(cog="Which log to view.", num_lines="How many lines to display.")
    @app_commands.choices(cog=cog_choices)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.check(is_bot_owner)
    async def log(self, interaction: discord.Interaction, cog: discord.app_commands.Choice[str], num_lines: int=5):
        if not await self.bot.is_owner(interaction.user):
            raise Exception("This command can only be run by the bot owner.")

        await interaction.response.defer(ephemeral=False, thinking=True)

        cog = cog.value
        if cog == "All":
            cog = "Bot"
        else:
            cog = cog[5:]

        try:
            f = open(f"{config['srcroot']}Logs/{cog}.log")
            lines = f.readlines()[-num_lines:] # Last num_lines lines
            for line in lines:
                await interaction.channel.send(line)
            await interaction.edit_original_response(content=f"Request complete.")
        except:
            await interaction.edit_original_response(content=f"Could not find file {cog}.log.")

    @app_commands.command(name="ot_rollover", description="Admin function to test the OT rollover rapidly")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.check(is_bot_owner)
    async def ot_rollover(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        scoreboard_cog = self.bot.get_cog("Scoreboard")
        await scoreboard_cog.do_ot_rollover()
        await interaction.followup.send("Complete")

#endregion

async def setup(bot):
    await bot.add_cog(Debug(bot), guild=discord.Object(id=OTH_GUILD_ID))
