# Discord Libraries
from discord.ext import commands, tasks

# Python Libraries
import asyncio
from datetime import datetime, timedelta, timezone
import pytz

# Local Includes
from Shared import *

class Scoreboard(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

        self.scoreboard_channel_ids = LoadPickleFile(channels_datafile)
        self.channels_lock = asyncio.Lock()

        self.messages_lock = asyncio.Lock()

    async def cog_load(self):
        self.bot.loop.create_task(self.start_loops())

    async def start_loops(self):
        self.scores_loop.start()
        self.loops.append(self.scores_loop)

    class ChannelNotFound(discord.ext.commands.CommandError):
        def __init__(self, id):
            self.message = f"Could not find channel {id}."

    @commands.command(name="scoresstart")
    @commands.has_permissions(manage_guild=True)
    async def scoresstart(self, ctx, scores_channel_id):
        scores_channel_id = int(scores_channel_id)
        scores_channel = self.bot.get_channel(scores_channel_id)
        if not scores_channel:
            raise self.ChannelNotFound(scores_channel_id)

        self.scoreboard_channel_ids[ctx.guild.id] = scores_channel_id

        async with self.channels_lock:
            WritePickleFile(channels_datafile, self.scoreboard_channel_ids)

        await ctx.send("Scoreboard setup complete.")

    @scoresstart.error
    async def scoresstart_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage:\n\t`!scoresstart [Scoreboard Channel Id]`")
        elif isinstance(error, self.ChannelNotFound):
            await ctx.send(error.message)
        else:
            await ctx.send(error)

    @commands.command(name="scoresstop")
    @commands.has_permissions(manage_guild=True)
    async def scoresstop(self, ctx):
        self.scoreboard_channel_ids.pop(ctx.guild.id)

        async with self.channels_lock:
            WritePickleFile(channels_datafile, self.scoreboard_channel_ids)

        await ctx.send("Scoreboard disabled.")

    # Gets a list of games for the current date
    def get_games_for_today(self):
        date = (datetime.utcnow()-timedelta(hours=ROLLOVER_HOUR_UTC)).strftime("%Y-%m-%d")

        root = make_api_call(f"https://statsapi.web.nhl.com/api/v1/schedule?date={date}&expand=schedule.linescore")

        if len(root["dates"]) == 0:
            return []

        return root["dates"][0]["games"]

    # Gets the game recap link
    def get_recap_link(self, key):
        try:
            game_id = key.split(":")[0]
            media = make_api_call(f"https://statsapi.web.nhl.com/api/v1/game/{game_id}/content")
            for item in media["media"]["epg"]:
                if item["title"] == "Recap":
                    return item["items"][0]["playbacks"][3]["url"] #, item["items"][0]["image"]["cuts"]["640x360"]["src"]
        except:
            return None #, None

    def get_score_string(self, game):
        away = team_map[game["teams"]["away"]["team"]["name"].split(" ")[-1].lower()]
        home = team_map[game["teams"]["home"]["team"]["name"].split(" ")[-1].lower()]

        home_emoji = get_emoji(home)
        away_emoji = get_emoji(away)

        game_state = game["status"]["detailedState"]
        # Game hasn't started yet
        if game_state == "Scheduled" or game_state == "Pre-Game":
            utctime = datetime.strptime(game["gameDate"] + " +0000", "%Y-%m-%dT%H:%M:%SZ %z")
            localtime = utctime.astimezone(pytz.timezone("America/New_York"))
            time = localtime.strftime("%-I:%M%P")
            return f"{away_emoji} {away} vs {home_emoji} {home} starts at {time} ET.", None
        elif game_state == "Postponed":
            return f"{away_emoji} {away} vs {home_emoji} {home} was postponed.", None
        else:
            period = "(" + game["linescore"]["currentPeriodOrdinal"] + ")"
            away_score = game["teams"]["away"]["score"]
            home_score = game["teams"]["home"]["score"]

            # Game is over
            if game_state == "Final":
                if period == "(3rd)":
                    period = ""
                status = "Final:"
            # Game is in progress
            else:
                timeleft = game["linescore"]["currentPeriodTimeRemaining"]
                period = period[:-1] + " " + timeleft + period[-1]
                status = "Current score:"

            return f"{status} {away_emoji} {away} {away_score}, {home_emoji} {home} {home_score} {period}", self.get_recap_link(str(game["gamePk"]))

    @commands.command(name="scores")
    async def scores(self, ctx):
        # Loop through each game in today's schedule
        games = self.get_games_for_today()

        if len(games) == 0:
            msg = "No games found for today."
        else:
            msg = ""
            for game in games:
                msg += self.get_score_string(game)[0] + "\n"

        await ctx.send(msg)

    @commands.command(name="score")
    async def score(self, ctx, input, *extras):
        # Account for teams with two-word names (San Jose, St. Louis, Tampa Bay, etc)
        team = input
        if len(extras) > 0:
            team += " " + " ".join(extras)
        team = team.replace("[", "").replace("]", "")
        team = team.lower()

        if team not in team_map:
            raise NHLTeamNotFound(input)

        team = team_map[team]

        # Loop through each game in today's schedule
        games = self.get_games_for_today()
        found = False
        for game in games:
            away = team_map[game["teams"]["away"]["team"]["name"].split(" ")[-1].lower()]
            home = team_map[game["teams"]["home"]["team"]["name"].split(" ")[-1].lower()]

            # These are not the teams you are looking for 👋🏻
            if home != team and away != team:
                continue

            msg, links = self.get_score_string(game)
            embed=discord.Embed(title=msg, url=links) # links[0]
#            if links[1]:
#                embed.set_thumbnail(url=links[1])
            await ctx.send(embed=embed)

            found = True
            break

        if not found:
            raise TeamDoesNotPlayToday(team)

    @score.error
    async def score_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `!score [NHL team]`")
        elif isinstance(error, NHLTeamNotFound):
            await ctx.send(error.message)
        elif isinstance(error, LinkError):
            await ctx.send(error.message)
        elif isinstance(error, NoGamesTodayError):
            await ctx.send(error.message)
        elif isinstance(error, TeamDoesNotPlayToday):
            await ctx.send(error.message)
        else:
            await ctx.send(error)

    # Gets the highlight link for a goal
    def get_media_link(self, key):
        try:
            game_id, event_id = key.split(":")
            media = make_api_call(f"https://statsapi.web.nhl.com/api/v1/game/{game_id}/content")
            for event in media["highlights"]["scoreboard"]["items"]:
                for keyword in event["keywords"]:
                    if keyword["type"] == "statsEventId" and keyword["value"] == event_id:
                        return event["playbacks"][3]["url"] #, event["highlight"]["image"]["cuts"]["640x360"]["src"]
#            for event in media["media"]["milestones"]["items"]:
#                if event["statsEventId"] == event_id:
#                    return event["highlight"]["playbacks"][3]["url"] #, event["highlight"]["image"]["cuts"]["640x360"]["src"]
        except:
            return None #, None

    # Gets the strength (EV, PP, SH, EN) of a goal
    def get_goal_strength(self, playbyplay, goal):
        strength = f"({goal['result']['strength']['code']}) "
        if strength == "(EVEN) ":
            strength = ""
        if "emptyNet" in goal["result"] and goal["result"]["emptyNet"]:
            strength += "(EN) "

        # Check if it was a penalty shot by looking at previous play
        # Sample game: https://statsapi.web.nhl.com/api/v1/game/2020020074/feed/live
        try:
            prev_id = goal["about"]["eventIdx"] - 1
            prev_play = playbyplay["liveData"]["plays"]["allPlays"][prev_id]["result"]
            if "eventTypeId" in prev_play and prev_play["eventTypeId"] == "PENALTY" and prev_play["penaltySeverity"] == "Penalty Shot":
                strength += "(PS) "

            # For some weird reason, the penalty is reported AFTER the penalty shot in some cases, so check that too.
            # Sample game: https://statsapi.web.nhl.com/api/v1/game/2020020509/feed/live
            next_id = goal["about"]["eventIdx"] + 1
            if next_id in playbyplay["liveData"]["plays"]["allPlays"]:
                next_play = playbyplay["liveData"]["plays"]["allPlays"][next_id]["result"]
                if "eventTypeId" in next_play and next_play["eventTypeId"] == "PENALTY" and next_play["penaltySeverity"] == "Penalty Shot":
                    strength += "(PS) "
        except:
            self.log.info("Failure in PS check.")

        return strength

    # Update a message string that has already been sent
    async def update_goal(self, key, string, link, thumb):
        # Do nothing if nothing has changed, including the link.
        if string == self.messages[key]["msg_text"] and link == self.messages[key]["msg_link"]: # and thumb == self.messages[key]["msg_thumb"]:
            return

        self.messages[key]["msg_text"] = string
        self.messages[key]["msg_link"] = link
        self.messages[key]["msg_thumb"] = thumb
        embed = discord.Embed(title=string, url=link)
#        if thumb:
#            embed.set_thumbnail(url=thumb)

        # Update all the messages that have been posted containing this
        for channel_id, msg_id in self.messages[key]["msg_id"].items():
            try:
                msg = await self.bot.get_channel(channel_id).fetch_message(msg_id)
                await msg.edit(embed=embed)
                self.log.info(f"Edit: {key} {channel_id}:{msg_id} {string} {link} {thumb}")
            except Exception as e:
                self.log.warn(e)
                continue

    # Post a goal (or other related message) string to chat and track the data
    async def post_goal(self, key, string, link, thumb):
        # Add emoji to end of string to indicate a replay exists.
        if link != None:
            string += " :movie_camera:"

        # If this key already exists, we're updating, not posting
        if key in self.messages:
            await self.update_goal(key, string, link, thumb)
            return

        embed = discord.Embed(title=string, url=link)
#        if thumb:
#            embed.set_thumbnail(url=thumb)

        msgids = {}
        for channel in get_channels_from_ids(self.bot, self.scoreboard_channel_ids):
            msg = await channel.send(embed=embed)
            msgids[channel.id] = msg.id
        self.log.info(f"Post: {key} {string} {link} {thumb}")

        self.messages[key] = {"msg_id":msgids, "msg_text":string, "msg_link":link, "msg_thumb":thumb}

    # Checks for new goals in the play-by-play and posts them
    async def check_for_goals(self, key, playbyplay):
        # Get list of scoring play ids
        goals = playbyplay["liveData"]["plays"]["scoringPlays"]
        away = playbyplay["gameData"]["teams"]["away"]["abbreviation"]
        home = playbyplay["gameData"]["teams"]["home"]["abbreviation"]

        # Check all the goals to report new ones
        for goal in goals:
            goal = playbyplay["liveData"]["plays"]["allPlays"][goal]
            goal_key = f"{key}:{goal['about']['eventId']}"

            # Find the strength of the goal
            strength = self.get_goal_strength(playbyplay, goal)

            # Find the team that scored the goal
            try:
                team_code = goal["team"]["triCode"]
            except:
                team_id = goal["team"]["id"]
                if team_id == 87:
                    team_code = "ATL"
                elif team_id == 88:
                    team_code = "MET"
                elif team_id == 89:
                    team_code = "CEN"
                elif team_id == 90:
                    team_code = "PAC"
                else:
                    self.log.error(f"Unknown team of id {team_id} at link https://statsapi.web.nhl.com{playbyplay['link']}")
            team = f"{get_emoji(team_code)} {team_code}"

            # Find the period and time the goal was scored in
            time = f"{goal['about']['periodTime']} {goal['about']['ordinalNum']}"

            # Create the full string to post to chat
            # NB, the spacing after strength is handled in get_goal_strength
            goal_str = f"{get_emoji('goal')} GOAL {strength}{team} {time}: {goal['result']['description']}"
            score = f" ({away} {goal['about']['goals']['away']}, {home} {goal['about']['goals']['home']})"
            goal_str += score

            # Find the media link if we don't have one for this goal yet
            if goal_key not in self.messages or self.messages[goal_key]["msg_link"] == None: # or self.messages[goal_key]["msg_thumb"] == None:
                goal_link = self.get_media_link(goal_key)
#                goal_link, goal_thumb = self.get_media_link(goal_key)
            else:
                goal_link = self.messages[goal_key]["msg_link"]
#                goal_link, goal_thumb = self.messages[goal_key]["msg_link"], self.messages[goal_key]["msg_thumb"]

            await self.post_goal(goal_key, goal_str, goal_link, None) #goal_thumb)

    # Checks for disallowed goals (ones we have posted, but are no longer in the play-by-play) and updates them
    async def check_for_disallowed_goals(self, key, playbyplay):
        # Get list of scoring play ids
        goals = playbyplay["liveData"]["plays"]["scoringPlays"]
        all_plays = playbyplay["liveData"]["plays"]["allPlays"]

        # Skip if there aren't any plays or goals. Seems like feeds "disappear" for short periods of time occasionally,
        # and we don't want this to incorrectly trigger disallows.
        if len(all_plays) == 0:
            return

        # Loop through all of our pickled goals
     	# If one of them doesn't exist in the list of scoring plays anymore
     	# We should cross it out and notify that it was disallowed.
        for pickle_key in list(self.messages.keys()):
            game_id, event_id = pickle_key.split(":")

            # Skip goals from other games, or start, end, overtime start, and disallow events
            if game_id != key or event_id == "S" or event_id == "E" or event_id == "O" or event_id[-1] == "D":
                continue

            # Skip events for games that are already over, as these are often false alarms
            if f"{game_id}:E" in self.messages.keys():
                continue

            found = False
            for goal in goals:
                if event_id == str(all_plays[goal]["about"]["eventId"]):
                    found = True
                    break

            # This goal is still there, no need to disallow
            # Continue onto next pickle_key
            if found:
                continue

            # Skip updating goals that have already been crossed out
            if self.messages[pickle_key]["msg_text"][0] != "~":
                await self.post_goal(pickle_key, f"~~{self.messages[pickle_key]['msg_text']}~~", None, None)

            # Announce that the goal has been disallowed
            disallow_key = pickle_key + "D"
            if disallow_key not in self.messages:
                away = playbyplay["gameData"]["teams"]["away"]["abbreviation"]
                home = playbyplay["gameData"]["teams"]["home"]["abbreviation"]
                disallow_str = f"Goal disallowed in {away}-{home}."
                await self.post_goal(disallow_key, disallow_str, None, None)

    # Checks to see if OT challenge starting for a game
    def check_for_ot_challenge_start(self, key, playbyplay):
        status = playbyplay["gameData"]["status"]["detailedState"]
        # Game not in progress
        if "In Progress" not in status:
            return False

        # Game not tied
        if playbyplay["liveData"]["linescore"]["teams"]["home"]["goals"] != playbyplay["liveData"]["linescore"]["teams"]["away"]["goals"]:
            return False

        # Game not in final 5 minutes of 3rd or OT intermission
        ot = self.bot.get_cog("OTChallenge")
        ot.processot(None)
        if not ot.is_ot_challenge_window(playbyplay):
            return False

        return True

    # Parses a game play-by-play and posts start, goals, and end messages
    async def parse_game(self, game):
        # TODO: Only make this API call if the game is in certain states
        # Get the game from NHL.com
        playbyplay = make_api_call(f"https://statsapi.web.nhl.com{game['link']}")

        away = playbyplay["gameData"]["teams"]["away"]["abbreviation"]
        home = playbyplay["gameData"]["teams"]["home"]["abbreviation"]
        away_emoji = get_emoji(away)
        home_emoji = get_emoji(home)
        key = str(playbyplay["gamePk"])
        game_state = playbyplay["gameData"]["status"]["detailedState"]

        # Send game starting notification if necessary
        start_key = key + ":S"
        if game_state == "In Progress" and start_key not in self.messages: 
            start_string = away_emoji + " " + away + " at " + home_emoji + " " + home + " Starting."
            await self.post_goal(start_key, start_string, None, None)

        # Send goal and disallowed goal notifications
        await self.check_for_disallowed_goals(key, playbyplay)
        await self.check_for_goals(key, playbyplay)

        # Check for OT Challenge start notifications
        ot_key = key + ":O"
        ot_string = f"OT Challenge for {away_emoji} {away} at {home_emoji} {home} is open."
        if self.check_for_ot_challenge_start(key, playbyplay):
            await self.post_goal(ot_key, ot_string, None, None)
        elif ot_key in self.messages:
            ot_string = f"~~{ot_string}~~"
            await self.post_goal(ot_key, ot_string, None, None)

        # Check whether the game finished notification needs to be sent
        end_key = key + ":E"
        if game_state == "Final" and end_key not in self.messages:
            # Some exhibition games don't get play-by-play data. Skip these.
            all_plays = playbyplay["liveData"]["plays"]["allPlays"]
            if len(all_plays) == 0:
                return

            event_type_id = all_plays[-1]["result"]["eventTypeId"]
            if event_type_id == "GAME_END" or event_type_id == "GAME_OFFICIAL":
                away_score = all_plays[-1]["about"]["goals"]["away"]
                home_score = all_plays[-1]["about"]["goals"]["home"]

                # Sometimes shootout winners take longer to report, so allow this to defer to the next cycle
                skip = False
                if away_score == home_score: # adjust for shootout winner
                    shootout_info = playbyplay["liveData"]["linescore"]["shootoutInfo"]
                    if shootout_info["away"]["scores"] > shootout_info["home"]["scores"]:
                        away_score += 1
                    elif shootout_info["away"]["scores"] < shootout_info["home"]["scores"]:
                        home_score += 1
                    else:
                        skip = True

                if skip:
                    return

                # Report the final score, including the OT/SO tag
                period = f"({all_plays[-1]['about']['ordinalNum']})"
                if period == "(3rd)": # No additional tag for a regulation final
                    period = ""
                final_str = f"{get_emoji(away)} {away} {away_score}, {get_emoji(home)} {home} {home_score} Final {period}"
                await self.post_goal(end_key, final_str, None, None)

        # Find the game recap link if we don't have it already.
        if game_state == "Final" and end_key in self.messages and (self.messages[end_key]["msg_link"] == None): # or self.messages[end_key]["msg_thumb"] == None):
            recap_link = self.get_recap_link(end_key)
#            recap_link, recap_thumb = self.get_recap_link(end_key)
            if recap_link != None:
                await self.post_goal(end_key, self.messages[end_key]["msg_text"], recap_link, None) #recap_thumb)

        async with self.messages_lock:
            WritePickleFile(messages_datafile, self.messages)

    @tasks.loop(seconds=10.0)
    async def scores_loop(self):
        games = self.get_games_for_today()
        for game in games:
            await self.parse_game(game)

    @scores_loop.before_loop
    async def before_scores_loop(self):
        await self.bot.wait_until_ready()

        # Load any messages we've sent previously today
        async with self.messages_lock:
            self.messages = LoadPickleFile(messages_datafile)

    @scores_loop.error
    async def scores_loop_error(self, error):
        await self.cog_command_error(None, error)
        self.scores_loop.restart()

async def setup(bot):
    await bot.add_cog(Scoreboard(bot))
