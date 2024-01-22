# Python Libraries
import asyncio
import os
from datetime import datetime, timedelta
from distutils.log import debug
from xmlrpc.client import Boolean

# Discord Libraries
import challonge
import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands, tasks

# Local Includes
from Shared import *


class OTH(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

    async def cog_load(self):
        self.bot.loop.create_task(self.start_loops())

    async def start_loops(self):
        self.trades_loop.start()
        self.loops.append(self.trades_loop)

        self.inactives_loop.start()
        self.loops.append(self.inactives_loop)

######################## Cog-specific Exceptions ########################

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

######################## Inactives ########################

    # Checks all OTH leagues for inactive managers and abandoned teams
    async def check_inactives(self):
        channel = self.bot.get_channel(MODS_CHANNEL_ID)
        leagues = get_leagues_from_database(Config.config["year"])
        for league in leagues:
            msg = ""
            standings = make_api_call(f"https://www.fleaflicker.com/api/FetchLeagueStandings?sport=NHL&league_id={league['id']}")

            for team in standings["divisions"][0]["teams"]:
                # If there's no owners, mark as inactive
                if "owners" not in team:
                    msg += f"**{league['name']}**: *Unowned team: {team['name']}*\n"
                    continue

                # If there are owners, check if the primary one has been seen in the last MIN_INACTIVE_DAYS days
                last_seen = team["owners"][0]["lastSeenIso"]
                last_seen = datetime.strptime(last_seen, "%Y-%m-%dT%H:%M:%SZ")
                time_since_seen = datetime.utcnow()-last_seen
                if time_since_seen.days > MIN_INACTIVE_DAYS:
                    msg += f"**{league['name']}**: *Owner {team['owners'][0]['displayName']} not seen in last {time_since_seen.days} days*\n"

            if msg != "":
                await channel.send(msg)
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

    # Checks for any inactive OTH teams on FF
    @commands.command(name="inactives")
    @is_mods_channel()
    async def inactives(self, ctx):
        await self.check_inactives()

######################## Trade Review ########################

    # Formats a json trade into a discord embed
    def format_trade(self, league, trade):
        embed = discord.Embed(url=f"https://www.fleaflicker.com/nhl/leagues/{league['id']}/trades/{trade['id']}")
        embed.title = "Trade in " + league["name"]
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

            embed.add_field(name=f"**{team['team']['name']}** gets", value=players)

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
                await hockey_general_channel.send(embed=trade_embed)

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

    # Checks for any new OTH trades
    @commands.command(name="trades")
    @is_tradereview_channel()
    async def trades(self, ctx):
        await self.check_trades(True)

######################## Matchup ########################

    # Posts the current matchup score for the given user
    @commands.command(name="matchup")
    @is_OTH_guild()
    async def matchup(self, ctx, user, division=None):
        user = user.replace("[", "").replace("]", "")

        matchup = get_user_matchup_from_database(user, division)
        if len(matchup) == 0:
            raise self.UserNotFound(user, division)
        if len(matchup) > 1:
            raise self.MultipleMatchupsFound(user)
        matchup = matchup[0]

        # Format a matchup embed to send
        msg = "```{:<22} {:6.2f}\n".format(f"{matchup['name']} ({matchup['wins']}-{matchup['losses']})", matchup["PF"])
        if matchup["opp_name"] == None:
            msg += "BYE```"
            link = f"https://www.fleaflicker.com/nhl/leagues/{matchup['league_id']}/scores"
        else:
            msg += "{:<22} {:6.2f}```".format(f"{matchup['opp_name']} ({matchup['opp_wins']}-{matchup['opp_losses']})", matchup["opp_PF"])
            link = f"https://www.fleaflicker.com/nhl/leagues/{matchup['league_id']}/scores/{matchup['matchup_id']}"
      
        tier_colors = [None, "#EFC333", "#3D99D8", "#E37E2E", "#3DCB77"]
        color = discord.Color.from_str(tier_colors[matchup['tier']])
        embed = discord.Embed(title=f"{matchup['league_name']} Matchup", description=f"{msg}", url=link, color=color)
        await ctx.send(embed=embed)

    @matchup.error
    async def matchup_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `!matchup [fleaflicker username]`")
        elif isinstance(error, self.UserNotFound):
            await ctx.send(error.message)
        elif isinstance(error, self.MultipleMatchupsFound):
            await ctx.send(error.message)
        else:
            await ctx.send(error)

####################### Member Management (Box and Roles) ##########################

    @commands.command(name="box", aliases=["penalty", "penaltybox"])
    @commands.is_owner()
    async def box(self, ctx, member: discord.Member):
        boxrole = self.bot.get_guild(OTH_GUILD_ID).get_role(OTH_BOX_ROLE_ID)
        for role in member.roles:
            if role == boxrole:
                await member.remove_roles(boxrole)
                return
        await member.add_roles(boxrole)

    @box.error
    async def box_error(self, ctx, error):
        await ctx.send(error)

    def roles_scope_choices_helper():
        choices = [Choice(name="All", value="All")]

        for division in ["D1", "D2", "D3", "D4"]:
            choices.append(Choice(name=division, value=division))

        for league in get_leagues_from_database(Config.config["year"]):
            choices.append(Choice(name=league["name"], value=league["name"]))

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

        # Early return if the roles assignment file is missing
        assignments = self.get_role_assignments()
        if assignments == None:
            await interaction.response.send_message("Could not find role assignments list.")
            return

        await interaction.response.send_message(f"Removing all league/division roles.")
        if debug:
            await interaction.channel.send(f"Debug mode -- reading roles from file but not setting them. Check the bot's logs for output.")

        league_roles = get_roles_from_ids(self.bot)

        count = 0
        members = self.bot.get_guild(OTH_GUILD_ID).members
        for member in members:
            for league_role in league_roles.values():
                if league_role in member.roles:
                    count += 1
                    self.log.info(f"Removing all league/division roles from {member.name}.")
                    if not debug:
                        await member.remove_roles(*league_roles.values())
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

                count += 1
                self.log.info(f"Adding roles {division} and {league} to {member.name}")
                if not debug:
                    await member.add_roles(league_roles[division], league_roles[league])

        self.log.info(f"Added league/division roles to {count} members.")
        if not debug:
            await interaction.channel.send(f"Added league/division roles to {count} members.")

        await interaction.channel.send(f"Completed.")

######################## Woppa Cup ########################

    def get_embed_for_woppacup_match(self, match, participants):
        p1_id = match["player1_id"]
        p2_id = match["player2_id"]
        p1_name = p2_name = p1_div = p2_div = None
        p1_prev = p2_prev = 0

        if match["scores_csv"] != "":
            scores = match["scores_csv"].split("-")
            p1_prev = int(scores[0])/100.0
            p2_prev = int(scores[1])/100.0

        # Get the opponent from the participants list
        for p in participants:
            if p1_id == p["id"] or p1_id in p["group_player_ids"]:
                p1_div = p["name"].split(".")[0]
                p1_name = p["name"].split(".")[-1]
            elif p2_id == p["id"] or p2_id in p["group_player_ids"]:
                p2_div = p["name"].split(".")[0]
                p2_name = p["name"].split(".")[-1]

            # Found both names!
            if p1_name != None and p2_name != None:
                break

        # Get p1's matchup from the database
        p1_matchup = get_user_matchup_from_database(p1_name, p1_div)
        if len(p1_matchup) == 0:
            raise self.UserNotFound(p1_name, p1_div)
        if len(p1_matchup) > 1:
            raise self.MultipleMatchupsFound(p1_name)
        p1_matchup = p1_matchup[0]

        # Get p2's matchup from the database
        p2_matchup = get_user_matchup_from_database(p2_name, p2_div)
        if len(p2_matchup) == 0:
            raise self.UserNotFound(p2_name, p2_div)
        if len(p2_matchup) > 1:
            raise self.MultipleMatchupsFound(p2_name)
        p2_matchup = p2_matchup[0]

        # Format a matchup embed to send
        msg = "```{:<14} {:6.2f}\n".format(f"{p1_name}", round(p1_matchup['PF'] + p1_prev, 2))
        msg += "{:<14} {:6.2f}```".format(f"{p2_name}", round(p2_matchup['PF'] + p2_prev, 2))

        # TODO: Consider re-enabling links to matchups

        if match["group_id"] != None:
            round_name = f"Group Stage Week {match['round']}"
        else:
            week_in_matchup = 1 if p1_prev == 0 and p2_prev == 0 else 2
            rounds = [0, "Round of 128", 
                         "Round of 64", 
                         "Round of 32", 
                         "Round of 16", 
                         f"Quarterfinal (Week {week_in_matchup} of 2)", 
                         f"Semifinal (Week {week_in_matchup} of 2)", 
                         f"Championship (Week {week_in_matchup} of 2)"]
            round_name = rounds[match["round"]]

        embed = discord.Embed(title=f"Woppa Cup {round_name}", description=msg)
        return embed

    @app_commands.command(name="wc", description="Check the score for a specific manager's Woppa Cup matchup.")
    @app_commands.describe(user="An fleaflicker username, or ALL.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def woppacup(self, interaction: discord.Interaction, user: str):
        # Temp override for weeks where it's paused. Update the text as necessary.
        # await interaction.response.send_message(f"WoppaCup is on pause due to the short All-Star week. It will resume in fleaflicker week 18. Contact Woppa for more info.")
        # return

        user = sanitize_user(user)
        post_all = user.lower() == "all"

        challonge.set_credentials(Config.config["challonge_username"], Config.config["challonge_api_key"])
        wc_id = int(Config.config["woppa_cup_id"]) # This can be found here: https://username:api-key@api.challonge.com/v1/tournaments.json. Don't forget to update both config files each year.

        participants = challonge.participants.index(wc_id)
        me = None
        for p in participants:
            if p["name"].lower().split(".")[-1] == user:
                me = p
                break

        if me == None and not post_all:
            await interaction.response.send_message(discord.Embed(title=f"User {user} is no longer in tournament."))

        curr_round = None
        is_group_stage = True
        embed_list = []
        for m in challonge.matches.index(wc_id):
            # Skip completed matches, because we only want the current ones
            if m["state"] != "open":
                continue

            # Assume the first open match has the correct round, and set for the entire bracket
            if curr_round == None:
                curr_round = m["round"]
                is_group_stage = m["group_id"] != None

            # Don't allow the "All" command when it could be too spammy
            if post_all and curr_round < 5:
                await interaction.response.send_message("'All' command only available in quarterfinals and later.")
                return

            # Skip matches for other rounds
            if m["round"] != curr_round:
                break

            if post_all or m["player1_id"] == me["id"] or m["player2_id"] == me["id"] or m["player1_id"] in me["group_player_ids"] or m["player2_id"] in me["group_player_ids"]:
                embed_list.append(self.get_embed_for_woppacup_match(m, participants))

        if len(embed_list) == 0:
            if is_group_stage:
                embed_list.append(discord.Embed(title=f"User {user} is on bye."))
            else:
                embed_list.append(discord.Embed(title=f"User {user} has been eliminated from the tournament."))

        self.log.info(len(embed_list))
        await interaction.response.send_message(embeds=embed_list)

    @woppacup.error
    async def woppacup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, commands.MissingRequiredArgument):
            await interaction.response.send_message("Usage: `!wc [fleaflicker username]`")
        elif isinstance(error, self.WoppaCupOpponentNotFound):
            await interaction.response.send_message(error.message)
        elif isinstance(error, self.MultipleMatchupsFound):
            await interaction.response.send_message(error.message)
        else:
            await interaction.response.send_message(error)

async def setup(bot):
    await bot.add_cog(OTH(bot), guild=discord.Object(id=OTH_GUILD_ID))
