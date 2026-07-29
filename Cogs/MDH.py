# Discord Libraries
import discord
from discord import app_commands

# Python Libraries
import asyncio

# Local Includes
from Shared import *

class ConfirmationView(discord.ui.View):
    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Processing...", view=None)

        process = await asyncio.create_subprocess_exec(
            "/home/jeremy/mdh.venv/bin/python",
            "/home/jeremy/mdh-hockey/Extensions/main.py",
            "--process",
            "--post",
        )
        return_code = await process.wait()

        if return_code == 0:
            await interaction.followup.send("Done", ephemeral=True)
        else:
            await interaction.followup.send(
                f"Processing failed with exit code {return_code}.",
                ephemeral=True,
            )

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Cancelled.", view=None)

class MDH(WesCog):
    @app_commands.command(name="button", description="Processes MDH bids for free agent frenzy")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.check(lambda interaction: interaction.created_at.month in (7, 8))
    async def button(self, interaction: discord.Interaction):
        if interaction.user.id not in (228258453599027200, 243201978191052800):
            await interaction.response.send_message(
                "This command can only be run by MDH commissioners.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Are you sure?",
            view=ConfirmationView(),
            ephemeral=True,
        )

    @button.error
    async def button_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure) and interaction.created_at.month not in (7, 8):
            await interaction.response.send_message(
                "This command can only be run in July or August.",
                ephemeral=True,
            )
            return

        raise error

async def setup(bot):
    await bot.add_cog(MDH(bot), guild=discord.Object(id=OTH_GUILD_ID))
