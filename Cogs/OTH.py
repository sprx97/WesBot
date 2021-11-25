# Discord Libraries
import discord
from discord.ext import commands, tasks

# Python Libraries
import asyncio
import challonge
from datetime import datetime, timedelta
import pygsheets

# Local Includes
from Shared import *

class OTH(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

        self.trades_loop.start()
        self.inactives_loop.start()
        self.loops = [self.trades_loop, self.inactives_loop]

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
                    msg += f"**{league['name']}**: *Owner {team['owners'][0]['displayName']} not seen in last {MIN_INACTIVE_DAYS} days*\n"

            if msg != "":
                await channel.send(msg)
        self.log.info("Inactives check complete.")

    # Check fleaflicker for recent trades
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
                players += "**Dropping**\n"
                for player in team["playersReleased"]:
                    players += player["proPlayer"]["nameFull"] + "\n"

            embed.add_field(name=f"**{team['team']['name']}**", value=players)

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

    @inactives_loop.error
    async def inactives_loop_error(self, error):
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
        msg = f"{matchup['name']} ({matchup['wins']}-{matchup['losses']}): **{matchup['PF']}**\n"
        if matchup['opp_name'] == None:
            msg += "BYE"
            link = f"https://www.fleaflicker.com/nhl/leagues/{matchup['league_id']}/scores"
        else:
            msg += f"{matchup['opp_name']} ({matchup['opp_wins']}-{matchup['opp_losses']}): **{matchup['opp_PF']}**"
            link = f"https://www.fleaflicker.com/nhl/leagues/{matchup['league_id']}/scores/{matchup['matchup_id']}"
        embed = discord.Embed(title=msg, url=link)
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

    @commands.command(name="roles")
    @commands.is_owner()
    @is_tech_channel()
    async def roles(self, ctx, scope=""):
        PYGS = pygsheets.authorize(service_file="/var/www/DiscordBot/service_client_secret_OTH.json")
        sheet = PYGS.open_by_key("1jC3zHsRuB6IawR-AM5ZtAOl360pCdjqUk230NiWPYbo")
        worksheet = sheet.worksheet_by_title("LeagueAssignments")

        values = worksheet.get_values("A2", "D225")
        members = self.bot.get_guild(OTH_GUILD_ID).members
        for member in members:
            for team in values:
                if team[1] == "" or "#" not in team[1]:
                    continue

                name, discrim = team[1].split("#")

                if name.lower() == member.name.lower() and discrim == member.discriminator:
                    div = team[2]
                    league = team[3]
                    if scope == "" or scope == div or scope == league:
                        self.log.info(f"Removing all division/league roles from {member.name}")
                        await member.remove_roles(*role_ids.values())

                        self.log.info(f"Adding roles {div} and {league} to {name}")
                        await member.add_roles(role_ids[div], role_ids[league])
                    break
  
    @roles.error
    async def roles_error(self, ctx, error):
        await ctx.send(error)

    @commands.command(name="rolesclear")
    @commands.is_owner()
    @is_tech_channel()
    async def rolesclear(self, ctx):
       members = self.bot.get_guild(OTH_GUILD_ID).members
       for member in members:
            self.log.info(f"Removing all division/league roles from {member.name}")
            await member.remove_roles(*role_ids.values())

    @rolesclear.error
    async def roles_error(self, ctx, error):
        await ctx.send(error)

######################## Woppa Cup ########################

    # Posts the current woppacup matchup score for the given user
    @commands.command(name="woppacup", aliases=["cup", "wc"])
    async def woppacup(self, ctx, user, division = None):
        user = user.lower()
        if division != None:
            division = division.lower()

        challonge.set_credentials(Config.config["challonge_username"], Config.config["challonge_api_key"])
        wc22_id = 10278241 # TODO: hard-coded for now. Need a way to update annually easily.

        participants = challonge.participants.index(wc22_id)
        me = opp = None
        for p in participants:
            if p["name"].lower().split(".")[-1] == user and (division == None or division == p["name"].lower().split(".")[0]):
                me = p
                break

        if me == None:
            raise self.UserNotFound(user, division)

        for m in challonge.matches.index(wc22_id):
            # Skip completed matches, because we only want the current one
            if m["state"] != "open":
                continue

            # See if this match has the right player
            p1id = m["player1_id"]
            p2id = m["player2_id"]
            opp_id = None

            if p1id == me["id"] or p1id in me["group_player_ids"]:
                opp_id = p2id
            elif p2id == me["id"] or p2id in me["group_player_ids"]:
                opp_id = p1id
            else:
                continue

            # Get the opponent from the participants list
            for p in participants:
                if opp_id == p["id"] or opp_id in p["group_player_ids"]:
                    opp = p
                    break

            if opp == None:
                raise self.WoppaCupOpponentNotFound(user)

            me_div, _, me_name = me["name"].split(".")
            opp_div, _, opp_name = opp["name"].split(".")

            if me_div == "Luuuuu":
                me_div = "Luuuuuuu"
            if opp_div == "Luuuuu":
                opp_div = "Luuuuuuu"

            # Get the user matchup from the database
            me_matchup = get_user_matchup_from_database(me_name, me_div)
            if len(me_matchup) == 0:
                raise self.UserNotFound(me_name, me_div)
            if len(me_matchup) > 1:
                raise self.MultipleMatchupsFound(me_name)
            me_matchup = me_matchup[0]

            # Get the opponent matchup from the database
            opp_matchup = get_user_matchup_from_database(opp_name, opp_div)
            if len(opp_matchup) == 0:
                raise self.UserNotFound(opp_name, opp_div)
            if len(opp_matchup) > 1:
                raise self.MultipleMatchupsFound(opp_name)
            opp_matchup = opp_matchup[0]

            # Format a matchup embed to send
            msg = f"{me_matchup['name']}: **{me_matchup['PF']}**\n"
            msg += f"{opp_matchup['name']}: **{opp_matchup['PF']}**"
            # TODO: Add link to one of both of the matchups
            embed = discord.Embed(title=msg, url=None)

            await ctx.send(embed=embed)
            break # Only show the first "open" match because that's the one happening this week. Should work the whole way through...

    # TODO: Special casing for two-week matchups.

    @woppacup.error
    async def woppacup_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `!matchup [fleaflicker username]`")
        elif isinstance(error, self.UserNotFound):
            await ctx.send(error.message)
        elif isinstance(error, self.WoppaCupOpponentNotFound):
            await ctx.send(error.message)
        elif isinstance(error, self.MultipleMatchupsFound):
            await ctx.send(error.message)
        else:
            await ctx.send(error)

def setup(bot):
    bot.add_cog(OTH(bot))
