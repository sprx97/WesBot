# Python Libraries
import asyncio
from datetime import datetime, timedelta
import os
import pygsheets

# Discord Libraries
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands, tasks

# Local Includes
from Shared import *
from Cogs.WoppaCup_Helper import *

class OTH(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

    async def cog_load(self):
        self.bot.loop.create_task(self.start_loops())

    async def start_loops(self):
        self.trades_loop.start()
        self.loops.append(self.trades_loop)

# Disabled for the summer
        self.inactives_loop.start()
        self.loops.append(self.inactives_loop)

#region Custom cog-specific exceptions

    # Custom exception for an invalid fleaflicker username
    class UserNotFound(discord.ext.commands.CommandError):
        def __init__(self, user, division):
            self.message = f"Matchup for user {user} in division {division} not found."

    class WoppaCupOpponentNotFound(discord.ext.commands.CommandError):
        def __init__(self, user):
            self.message = f"Current opponent for user {user} not found."

    # Custom exception for finding multiple matchups for a user
    class MultipleMatchupsFound(discord.ext.commands.CommandError):
        def __init__(self, user):
            self.message = f"Multiple matchups found for user {user}."

#endregion
#region Member Management (Box and Roles)

    @app_commands.command(name="box", description="Send another user to the penalty box.")
    @app_commands.describe(user="A discord user to put in the box.", duration="How long, in minutes.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def box(self, interaction: discord.Interaction, user: discord.Member, duration: int = 2, reason: str = ""):
        boxrole = self.bot.get_guild(OTH_GUILD_ID).get_role(OTH_BOX_ROLE_ID)
        await user.add_roles(boxrole)

        if reason != "":
            reason = f" for {reason}"
        await interaction.response.send_message(f"{duration} minute penalty to {user.display_name}{reason}.")

        await asyncio.sleep(60*duration)
        await user.remove_roles(boxrole)

    @app_commands.command(name="unbox", description="Release another user from the penalty box.")
    @app_commands.describe(user="A discord user to release from the box.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def unbox(self, interaction: discord.Interaction, user: discord.Member):
        boxrole = self.bot.get_guild(OTH_GUILD_ID).get_role(OTH_BOX_ROLE_ID)
        await user.remove_roles(boxrole)
        await interaction.response.send_message(f"{user.display_name} unboxed.", ephemeral=True)

    @box.error
    @unbox.error
    async def box_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, discord.ext.commands.MissingPermissions):
            await interaction.send_response("You do not have permissions to do this. You played yourself.")

            boxrole = self.bot.get_guild(OTH_GUILD_ID).get_role(OTH_BOX_ROLE_ID)
            await interaction.user.add_roles(boxrole)
            asyncio.sleep(120)
            await interaction.user.remove_roles(boxrole)

    def roles_scope_choices_helper():
        choices = [Choice(name="All", value="All")]

        for division in ["D1", "D2", "D3", "D4", "D5"]:
            choices.append(Choice(name=division, value=division))

        for league in get_leagues_from_database(int(Config.config["year"])+1):
            choices.append(Choice(name=league["name"], value=league["name"]))

        choices.append(Choice(name="Waitlist", value="WAITLIST"))

        return choices

    # TODO: Move the Emailer to a shared location instead of the other project, and use direct sheet access instead of the rolesfile

    def get_role_assignments(self):
        rolesfile = Config.config["srcroot"] + "/Roles.txt"

        if not os.path.isfile(rolesfile):
            return None

        assignments = {}
        f = open(rolesfile)
        for line in f.readlines():
            name, division, league = line.strip().split("\t")
            assignments[name.lower()] = (division, league)

        return assignments

    roles_group = app_commands.Group(name="roles", description="Help the OTH Server with setting league/division roles.")

    @roles_group.command(name="clear", description="Clear all league and division roles from all users.")
    @app_commands.describe(debug="Debug mode. Log but don't set roles.")
    @app_commands.choices(debug=[Choice(name="True", value=1), Choice(name="False", value=0)])
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roles_clear(self, interaction: discord.Interaction, debug: Choice[int]):
        debug = (debug.value == 1)

        await interaction.response.send_message(f"Removing all league/division roles.")
        if debug:
            await interaction.channel.send(f"Debug mode -- reading roles from file but not setting them. Check the bot's logs for output.")

        league_roles = get_roles_from_ids(self.bot)
        offseason_role = get_offseason_league_role(self.bot)

        if offseason_role == None:
            self.log.warning("Could not find offseason role. Aborting.")
            return

        count = 0
        members = self.bot.get_guild(OTH_GUILD_ID).members
        for member in members:
            for league_role in league_roles.values():
                if league_role in member.roles:
                    count += 1
                    self.log.info(f"Removing all league/division roles from {member.name}.")
                    if not debug:
                        await member.remove_roles(*league_roles.values())
                        self.log.info("Roles removed")
                        try:
                            await member.add_roles(offseason_role)
                            self.log.info("Offseason role added")
                        except Exception as e:
                            await interaction.channel.send(f"Could not add offseason role to {member.name}: {e}")
                            return
                    break

        self.log.info(f"Found league/division roles on {count} members.")
        if not debug:
            await interaction.channel.send(f"Removed league/division roles from {count} members.")

        await interaction.channel.send(f"Completed.")

    @roles_group.command(name="assign", description="Assign league and division roles to a subset of members.")
    @app_commands.describe(debug="Debug mode. Log but don't set roles.", scope="Which league or division to assign roles for.")
    @app_commands.choices(debug=[Choice(name="True", value=1), Choice(name="False", value=0)], scope=roles_scope_choices_helper())
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roles_assign(self, interaction: discord.Interaction, debug: Choice[int], scope: Choice[str]):
        debug = (debug.value == 1)
        scope = scope.value

        # Early return if the roles assignment file is missing
        assignments = self.get_role_assignments()
        if assignments == None:
            await interaction.response.send_message("Could not find role assignments list.")
            return

        await interaction.response.send_message(f"Assigning roles for scope '{scope}'.")
        if debug:
            await interaction.channel.send(f"Debug mode -- reading roles from file but not setting them. Check the bot's logs for output.")

        league_roles = get_roles_from_ids(self.bot)
        offseason_role = get_offseason_league_role(self.bot)
        nonmember_role = get_nonmember_league_role(self.bot)
        waitlist_role = get_waitlist_league_role(self.bot)
        retired_role = get_retired_league_role(self.bot)

        count = 0
        members = self.bot.get_guild(OTH_GUILD_ID).members
        for member in members:
            key = member.name.lower()
            if key in assignments:
                division = assignments[key][0]
                league = assignments[key][1]

                # Skip members that are not in our desired scope
                if scope != division and scope != league:
                    continue

                roles_to_add = [league_roles[league]]
                if league_roles[league].name != "Waitlist":
                    roles_to_add.append(league_roles[division])

                count += 1
                self.log.info(f"Adding roles {roles_to_add} to {member.name}")
                if not debug:
                    await member.add_roles(*roles_to_add)
                    await member.remove_roles(offseason_role)
                    await member.remove_roles(nonmember_role)
                    await member.remove_roles(waitlist_role)
                    await member.remove_roles(retired_role)

        self.log.info(f"Added league/division roles to {count} members.")
        if not debug:
            await interaction.channel.send(f"Added league/division roles to {count} members.")

        await interaction.channel.send(f"Completed.")

#endregion
#region League management tools (inactives and trade review)

    # Checks all OTH leagues for inactive managers and abandoned teams
    async def check_inactives(self):
        return # disabled for offseason. TODO: Add a weekvar check here once I get my shared config file

        channel = self.bot.get_channel(MODS_CHANNEL_ID)
        leagues = get_leagues_from_database(Config.config["year"])
        for league in leagues:
            msg = ""
            standings = make_api_call(f"https://www.fleaflicker.com/api/FetchLeagueStandings?sport=NHL&league_id={league['id']}")

            for team in standings["divisions"][0]["teams"]:
                team_url = f"https://www.fleaflicker.com/nhl/leagues/{league['id']}/teams/{team['id']}"

                # If there's no owners, mark as inactive
                if "owners" not in team:
                    msg += f"**{league['name']}**: *Unowned team: {team['name']}* {team_url}\n"
                    continue

                # If there are owners, check if the primary one has been seen in the last MIN_INACTIVE_DAYS days
                last_seen = team["owners"][0]["lastSeenIso"]
                last_seen = datetime.strptime(last_seen, "%Y-%m-%dT%H:%M:%SZ")
                time_since_seen = datetime.utcnow()-last_seen
                if time_since_seen.days > MIN_INACTIVE_DAYS:
                    msg += f"**{league['name']}**: *Owner {team['owners'][0]['displayName']} not seen in last {time_since_seen.days} days* {team_url}\n"

            if msg != "":
                await channel.send(msg, suppress_embeds=True)
        self.log.info("Inactives check complete.")

    @tasks.loop(hours=7*24.0) # weekly -- could check more often if MIN_INACTIVE_DAYS is set to smaller
    async def inactives_loop(self):
        await self.check_inactives()

    @inactives_loop.before_loop
    async def before_inactives_loop(self):
        await self.bot.wait_until_ready()

        # Sleep until midnight Sunday (Sat night) to call at the same time every week
        curr_time = datetime.utcnow()-timedelta(hours=ROLLOVER_HOUR_UTC)
        days_delta = timedelta((13-curr_time.weekday()) % 7)
        target_time = curr_time + days_delta
        target_time = target_time.replace(hour=0, minute=0, second=0, microsecond=0)
        delta = target_time-curr_time
        while delta.days < 0:
            delta += timedelta(days=7)

        self.log.info("Sleeping inactives_loop for " + str(delta))
        await asyncio.sleep(delta.total_seconds())

    @inactives_loop.error
    async def inactives_loop_error(self, error):
        await self.cog_command_error(None, error)

    def is_mods_channel(interaction: discord.Interaction) -> bool:
        return interaction.channel.id == MODS_CHANNEL_ID or interaction.channel.id == OTH_TECH_CHANNEL_ID

    @app_commands.command(name="inactives", description="Checks for any inactive OTH teams on FF.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.check(is_mods_channel)
    async def inactives(self, interaction: discord.Interaction):
        await interaction.response.send_message("Checking inactives.", ephemeral=True)
        await self.check_inactives()

    # Formats a json trade into a discord embed
    def format_trade(self, league, trade):
        embed = discord.Embed(url=f"https://www.fleaflicker.com/nhl/leagues/{league['id']}/trades/{trade['id']}")
        embed.title = "Trade in " + league["name"]
        n_teams = 1
        for team in trade["teams"]:
            if "playersObtained" not in team:
                embed.add_field(name=f"**{team['team']['name']}**", value="No players going to this team -- please investigate.")
                continue

            players = ""
            for player in team["playersObtained"]:
                players += player["proPlayer"]["nameFull"] + "\n"

            # Display drops too
            if "playersReleased" in team:
                for player in team["playersReleased"]:
                    players += "*Dropping* " + player["proPlayer"]["nameFull"] + "\n"

            embed.add_field(name=f"**[{n_teams}] {team['team']['name']}** gets", value=players)
            n_teams += 1

        if "tentativeExecutionTime" in trade:
            time_secs = int(trade["tentativeExecutionTime"])/1000.0
            embed.set_footer(text="Processes " + datetime.fromtimestamp(time_secs).strftime("%A, %B %d, %Y %H:%M ET"))

        return embed

    # Function that checks all OTH fleaflicker leagues for new trades
    async def check_trades(self, verbose=False):
        # Find the list of trades that have already been posted so that we can ignore them.
        f = open("data/posted_trades.txt", "a+")
        f.seek(0)
        posted = [int(x.strip()) for x in f.readlines()]

        # Get the list of leagueIds for this year from the database
        leagues = get_leagues_from_database(Config.config["year"])

        trades_channel = self.bot.get_channel(TRADEREVIEW_CHANNEL_ID)
        hockey_general_channel = self.bot.get_channel(HOCKEY_GENERAL_CHANNEL_ID)

        # Make Fleaflicker API calls to get pending trades in all the leagues
        count = 0
        for league in leagues:
            trades = make_api_call(f"https://www.fleaflicker.com/api/FetchTrades?sport=NHL&league_id={league['id']}&filter=TRADES_UNDER_REVIEW")

            # No trades in this league
            if "trades" not in trades:
                continue

            # Post each trade in this league
            for trade in trades["trades"]:
                if trade["id"] in posted:
                    continue

                trade_embed = self.format_trade(league, trade)
                await trades_channel.send(f"<@&{TRADEREVIEW_ROLE_ID}>", embed=trade_embed)
                msg = await hockey_general_channel.send(embed=trade_embed)

                # Add reactions to the message for each team in the trade
                number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
                if len(trade["teams"]) < len(number_emojis):
                    for n in range(len(trade["teams"])):
                        await msg.add_reaction(number_emojis[n])

                count += 1

                # Append this trade ID to the list of trades already covered
                f.write(str(trade["id"]) + "\n")

        # Message if no trades were found
        if count == 0 and verbose:
            await trades_channel.send("No pending trades in any league.")

        f.close()

        self.log.info("Trades check complete.")

    # Check fleaflicker for recent trades
    @tasks.loop(hours=1.0)
    async def trades_loop(self):
        await self.check_trades()

    @trades_loop.before_loop
    async def before_trades_loop(self):
        await self.bot.wait_until_ready()

    @trades_loop.error
    async def trades_loop_error(self, error):
        await self.cog_command_error(None, error)

    @app_commands.command(name="trades", description="Checks for any new OTH trades.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    async def trades(self, interaction: discord.Interaction):
        await interaction.response.send_message("Checking trades.", ephemeral=True)
        await self.check_trades(True)

#endregion
#region Fleaflicker Matchups and Rankings

    @app_commands.command(name="matchup", description="Check the current matchup score for a user.")
    @app_commands.describe(user="A fleaflicker username", division="(Optional) User's division")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def matchup(self, interaction: discord.Interaction, user: str, division: str = None):
        await interaction.response.defer(thinking=True)

        matchup = get_user_matchup_from_database(user, division)
        if len(matchup) == 0:
            raise self.UserNotFound(user, division)
        if len(matchup) > 1:
            raise self.MultipleMatchupsFound(user)
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
        # Temp override for weeks where it's paused. Update the text as necessary.
        if not WoppaCup.has_tournament_started:
            await interaction.response.send_message(f"WoppaCup has not started yet. It will start in fleaflicker week 6")
            return

        await interaction.response.defer(thinking=True, ephemeral=False)

        participants, matches, url = WoppaCup.get_wc_data()
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
        # Temp override for weeks where it's paused. Update the text as necessary.
        if not WoppaCup.has_tournament_started:
            await interaction.response.send_message(f"WoppaCup has not started yet. It will start in fleaflicker week 6")
            return

        await interaction.response.defer(thinking=True)

        user = sanitize_user(user)
        participants, matches, url = WoppaCup.get_wc_data()

        # Check that the user requested actually exists
        me = None
        for p in participants:
            if p["name"].lower().split(".")[-1] == user:
                me = p
                break

        if me == None:
            embed = embed=discord.Embed(title=f"User {user} either doesn't exist or was never in this tournament.")
            embed.set_footer(text=url, icon_url=None)
            await interaction.followup.send(embed=embed)
            return

        curr_round, is_group_stage = WoppaCup.get_round_and_stage(matches)
        if curr_round == 999:
            embed = embed=discord.Embed(title=f"This tournament appears to be over.")
            embed.set_footer(text=url, icon_url=None)
            await interaction.followup.send(embed=embed)
            return

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
                embed = discord.Embed(title=f"User {user} is on bye.")
            else:
                embed = discord.Embed(title=f"User {user} has been eliminated from the tournament.")

        embed.set_footer(text="Looking for more scores? Try /wc_all", icon_url=None)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="playoffpool", description="Formats the playoff pool standings.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def playoffpool(self, interaction: discord.Interaction):
        client = pygsheets.authorize()
        sh = client.open()

#endregion

    @woppacup.error
    @matchup.error
    async def matchup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, self.WoppaCupOpponentNotFound):
            await interaction.followup.send(error.message)
        elif isinstance(error, self.UserNotFound):
            await interaction.followup.send(error.message)
        elif isinstance(error, self.MultipleMatchupsFound):
            await interaction.followup.send(error.message)
        else:
            await interaction.followup.send(error)

async def setup(bot):
    await bot.add_cog(OTH(bot), guild=discord.Object(id=OTH_GUILD_ID))
