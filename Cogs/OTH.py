# Python Libraries
import asyncio
import subprocess

# Discord Libraries
import discord
from discord import app_commands

# Local Includes
from Shared import *
from Cogs.WoppaCup_Helper import *

class OTH(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

#region Custom cog-specific exceptions

    class WoppaCupOpponentNotFound(discord.ext.commands.CommandError):
        def __init__(self, user):
            self.message = f"Current opponent for user {user} not found."

#endregion

#region Fleaflicker Matchups and Rankings

    def run_update_current_pf_script(self):
        return subprocess.run(
            [
                "/var/www/OldTimeHockey/scripts/oth.venv/bin/python3",
                "/var/www/OldTimeHockey/scripts/UpdateCurrentPF.py"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    @app_commands.command(name="matchup", description="Check the current matchup score for a user.")
    @app_commands.describe(user="A fleaflicker username", public="Whether to post the response publicly.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def matchup(self, interaction: discord.Interaction, user: str, public: bool = False):
        await interaction.response.defer(thinking=True, ephemeral=not public)

        await asyncio.to_thread(self.run_update_current_pf_script)

        matchup = get_user_matchup_from_database(user)
        if len(matchup) == 0:
            raise UserNotFound(user)
        if len(matchup) > 1:
            raise MultipleMatchupsFound(user)
        matchup = matchup[0]

        # Format names for posting
        p1_name = f"{matchup['name']} ({matchup['wins']}-{matchup['losses']})"
        p1_PF = "{:>6.2f}".format(round(matchup['PF'], 2))
        if matchup["opp_name"] != None:
            p2_name = f"{matchup['opp_name']} ({matchup['opp_wins']}-{matchup['opp_losses']})"
            p2_PF = "{:>6.2f}".format(round(matchup['opp_PF'], 2))
            link = f"https://www.fleaflicker.com/nhl/leagues/{matchup['league_id']}/scores/{matchup['matchup_id']}"
        else:
            p2_name = "BYE"
            p1_PF = ""
            p2_PF = ""
            link = f"https://www.fleaflicker.com/nhl/leagues/{matchup['league_id']}/scores"
        if len(p1_name) > len(p2_name):
            p2_name += " "*(len(p1_name)-len(p2_name))
        else:
            p1_name += " "*(len(p2_name)-len(p1_name))

        # Format a matchup embed to send
        msg =  f"`{p1_name}` " + f"\u2002"*(24-len(p1_name)) + f"{p1_PF}\n"
        msg += f"`{p2_name}` " + f"\u2002"*(24-len(p2_name)) + f"{p2_PF}"

        tier_colors = [None, "#EFC333", "#3D99D8", "#E37E2E", "#3DCB77", "#AD1457"]
        color = discord.Color.from_str(tier_colors[matchup['tier']])
        embed = discord.Embed(title=f"{matchup['league_name']} Matchup", description=f"{msg}", url=link, color=color)
        await interaction.followup.send(embed=embed)

#endregion
#region Woppa Cup

    @app_commands.command(name="wc_bracket", description="Dumps all WoppaCup scores to the chat. Only Ro16 and later.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    @app_commands.checks.cooldown(1, 300.0)
    async def woppacup_bracket(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"OTH Cup 2026 is under construction.")
        return

        # Temp override for weeks where it's paused. Update the text as necessary.
        if not WoppaCup.has_tournament_started:
            await interaction.response.send_message(f"WoppaCup has not started yet. It will start in fleaflicker week 6")
            return

        await interaction.response.defer(thinking=True, ephemeral=False)

        participants, matches, url, winner, tourney_name = WoppaCup.get_wc_data()

        if winner != None:
            for p in participants:
                if winner == p["id"]:
                    winner = p["name"].split(".")[-1]
                    break
            embed = discord.Embed(title=tourney_name, description=f"The tournament is over. Congrats to {winner}!", url=url)
            await interaction.followup.send(embed=embed)
            return

        curr_round, is_group_stage = WoppaCup.get_round_and_stage(matches)
        matches = WoppaCup.trim_matches(matches, curr_round, is_group_stage)

        if len(matches) > 8:
            await interaction.followup.send("Too many matches remain to display full bracket. Please wait until Ro16")
            return

        embed = discord.Embed(title=f"Woppa Cup {WoppaCup.get_round_name(matches[0])}")
        for m in matches:
            embed.add_field(name="", value=WoppaCup.get_description_for_woppacup_embed(m, participants), inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="wc_all", description="Shows all scores for the current round of Woppa Cup in a pager.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def woppacup_all(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"OTH Cup 2026 is under construction.")
        return

        # Temp override for weeks where it's paused. Update the text as necessary.
        if not WoppaCup.has_tournament_started:
            await interaction.response.send_message(f"WoppaCup has not started yet. It will start in fleaflicker week 6")
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        view = WoppaCup.WCView()
        await interaction.followup.send(embed=view.embed, view=view)

    @app_commands.command(name="wc", description="Check the score for a specific manager's Woppa Cup matchup.")
    @app_commands.describe(user="A fleaflicker username, 'all', or 'bracket'")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def woppacup(self, interaction: discord.Interaction, user: str):
        await interaction.response.send_message(f"OTH Cup 2026 is under construction.")
        return

        # Temp override for weeks where it's paused. Update the text as necessary.
        if not WoppaCup.has_tournament_started:
            await interaction.response.send_message(f"WoppaCup has not started yet. It will start in fleaflicker week 6")
            return

        await interaction.response.defer(thinking=True)

        user = sanitize_user(user)
        participants, matches, url, winner, tourney_name = WoppaCup.get_wc_data()
        if winner != None:
            for p in participants:
                if winner == p["id"]:
                    winner = p["name"].split(".")[-1]
                    break

            embed = discord.Embed(title=tourney_name, description=f"The tournament is over. Congrats to {winner}!", url=url)
            await interaction.followup.send(embed=embed)
            return

        # Check that the user requested actually exists
        me = None
        for p in participants:
            if p["name"].lower().split(".")[-1] == user:
                me = p
                break

        if me == None:
            embed = discord.Embed(title=tourney_name, description=f"User {user} either doesn't exist or was never in this tournament.", url=url)
            embed.set_footer(text=url, icon_url=None)
            await interaction.followup.send(embed=embed)
            return

        curr_round, is_group_stage = WoppaCup.get_round_and_stage(matches)

        # Find the user's match from this week
        embed = None
        for m in matches:
            # Skip the group stage if necessary
            if not is_group_stage and m["group_id"] != None:
                continue

            # Skip matches for other rounds
            if m["round"] != curr_round:
                continue

            if m["player1_id"] == me["id"] or m["player2_id"] == me["id"] or m["player1_id"] in me["group_player_ids"] or m["player2_id"] in me["group_player_ids"]:
                embed = WoppaCup.get_embed_for_woppacup_match(m, participants, url)
                break

        # A few scenarios for if the user is not playing this week
        if embed == None:
            if is_group_stage:
                embed = discord.Embed(title=tourney_name, description=f"User {user} is on bye.", url=url)
            else:
                embed = discord.Embed(title=tourney_name, description=f"User {user} has been eliminated from the tournament.", url=url)

        embed.set_footer(text="Looking for more scores? Try /wc_all", icon_url=None)
        await interaction.followup.send(embed=embed)

#endregion

    @woppacup.error
    @matchup.error
    async def matchup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, self.WoppaCupOpponentNotFound):
            await interaction.followup.send(error.message)
        elif isinstance(error, UserNotFound):
            await interaction.followup.send(error.message)
        elif isinstance(error, MultipleMatchupsFound):
            await interaction.followup.send(error.message)
        else:
            await interaction.followup.send(error)

async def setup(bot):
    await bot.add_cog(OTH(bot), guild=discord.Object(id=OTH_GUILD_ID))
