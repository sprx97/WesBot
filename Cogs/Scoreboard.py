# Discord Libraries
from discord.ext import tasks

# Python Libraries
import asyncio
from datetime import datetime
import pytz

# Local Includes
from Shared import *

class Scoreboard(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

        self.media_link_base = "https://players.brightcove.net/6415718365001/EXtG1xJ7H_default/index.html?videoId="

        self.scoreboard_channel_ids = LoadPickleFile(channels_datafile)
        self.channels_lock = asyncio.Lock()
        self.messages_lock = asyncio.Lock()

    async def cog_load(self):
        self.bot.loop.create_task(self.start_loops())

    async def start_loops(self):
        self.scores_loop.start()
        self.loops.append(self.scores_loop)

    # TODO: I think multiple loops are running at once and it's not waiting for the previous to finish.
    @tasks.loop(seconds=5)
    async def scores_loop(self):
#        self.log.info(f"Starting scores loop {self.scores_loop.current_loop}")
        games = await self.get_games_for_today()
        for game in games:
            await self.parse_game(game)
#        self.log.info(f"Finishing scores loop {self.scores_loop.current_loop}")

    @scores_loop.before_loop
    async def before_scores_loop(self):
        await self.bot.wait_until_ready()

        # Load any messages we've sent previously today
        async with self.messages_lock:
            self.messages = LoadJsonFile(messages_datafile)

    @scores_loop.error
    async def scores_loop_error(self, error):
        await self.cog_command_error(None, error)
        self.scores_loop.restart()

    @app_commands.command(name="scores_start", description="Start the live scoreboard in a channel.")
    @app_commands.describe(channel="The channel to start the scoreboard in.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def scores_start(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel):
        self.scoreboard_channel_ids[channel.guild.id] = channel.id

        async with self.channels_lock:
            WritePickleFile(channels_datafile, self.scoreboard_channel_ids)

        await interaction.response.send_message("Scoreboard setup complete.")

    @app_commands.command(name="scores_stop", description="Stop the live scoreboard in this server.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def scores_stop(self, interaction: discord.Interaction):
        self.scoreboard_channel_ids.pop(interaction.guild_id)

        async with self.channels_lock:
            WritePickleFile(channels_datafile, self.scoreboard_channel_ids)

        await interaction.response.send_message("Scoreboard disabled.")

    # Helper function to parse a game JSON object into a score string
    # Works for games that haven't started, are in progress, or are finished
    def get_score_string(self, game):
        away = game["awayTeam"]["abbrev"]
        home = game["homeTeam"]["abbrev"]

        away = get_emoji(away) + " " + away
        home = get_emoji(home) + " " + home

        # First check for TBD, PPD, SUSP, or CNCL because it's behind a different key
        game_state = game["gameScheduleState"]
        if game_state != "OK":
            return f"{away} at {home} {game_state}"

        # Now check for "normal" states
        game_state = game["gameState"]
        if game_state == "FUT" or game_state == "PRE": # Game hasn't started yet
            utc_time = datetime.strptime(game["startTimeUTC"] + " +0000", "%Y-%m-%dT%H:%M:%SZ %z")
            local_time = utc_time.astimezone(pytz.timezone("America/New_York"))
            time = local_time.strftime("%-I:%M%P")

            away_record = game["awayTeam"]["record"].split("-")
            home_record = game["homeTeam"]["record"].split("-")
            away_points = 2*int(away_record[0]) + int(away_record[2])
            home_points = 2*int(home_record[0]) + int(home_record[2])

            return f"{time}: {away} ({away_points} pts) at {home} ({home_points} pts)"
        elif game_state == "OVER" or game_state == "FINAL" or game_state == "OFF":
            away_score = game["awayTeam"]["score"]
            home_score = game["homeTeam"]["score"]

            return f"Final: {away} {away_score}, {home} {home_score}"
        elif game_state == "LIVE" or game_state == "CRIT":
            away_score = game["awayTeam"]["score"]
            home_score = game["homeTeam"]["score"]

            period = self.get_period_ordinal(game["period"])

            if game["clock"]["inIntermission"]:
                time = "INT"
            else:
                time = game["clock"]["timeRemaining"]

            return f"Live: {away} {away_score}, {home} {home_score} ({period} {time})"
        else:
            raise Exception(f"Unrecognized game state {game_state}")

    # Rolls over the date in our messages_datafile to the next one.
    # This needs to be a function so we can await it and not spam all the messages from the previous day
    # after deleting them from the datafile.
    async def do_date_rollover(self, date):
        self.messages = {"date": date}
        async with self.messages_lock:
            WriteJsonFile(messages_datafile, self.messages)

    # Helper function to get all of the game JSON objects for the current day
    # from the NHL.com api.
    async def get_games_for_today(self):
        # Get the week scoreboard and today's date
        root = make_api_call(f"https://api-web.nhle.com/v1/scoreboard/now")
        date = root["focusedDate"]

        # Execute rollover if the date has changed
        if "date" not in self.messages or self.messages["date"] < date:
            self.log.info(f"Date before date rollover: {self.messages['date']}, Loop Iteration: {self.scores_loop.current_loop}")
            await self.do_date_rollover(date) # Needs to be awaited to prevent spam from the previous date
            self.log.info(f"Date after date rollover: {self.messages['date']}")
            return []

        # Get the list of games for the correct date
        for games in root["gamesByDate"]:
            if games["date"] == date:
                return games["games"]

        return []

    # Gets the game recap video link if it's available
    def get_recap_link(self, key):
        try:
            game_id = key.split(":")[0]
            media = make_api_call(f"https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore")
            recap = media["gameVideo"]["threeMinRecap"]
            return f"{self.media_link_base}{recap}"
        except:
            return None

    @app_commands.command(name="scoreboard", description="Check out today's full scoreboard.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def scoreboard(self, interaction: discord.Interaction):
        try:
            games = await self.get_games_for_today()

            if len(games) == 0:
                msg = "No games found for today."
            else:
                msg = ""
                for game in games:
                    msg += self.get_score_string(game) + "\n"

            await interaction.response.send_message(msg)

        except Exception as e:
            await interaction.response.send_message(f"Error in `/scores scoreboard` function: {e}")

    @app_commands.command(name="score", description="Check the score for a specific team.")
    @app_commands.describe(team="An NHL team abbreviation, name, or nickname.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def score(self, interaction: discord.Interaction, team: str):
        try:
            # Get the proper abbreviation from our aliases
            team = team.lower()
            team = team_map.get(team)
            if team == None:
                await interaction.response.send_message(f"Team '{team}' not found.")
                return

            # Loop through the games searching for this team
            games = await self.get_games_for_today()
            found = False
            for game in games:
                if game["awayTeam"]["abbrev"] == team or game["homeTeam"]["abbrev"] == team:
                    found = True
                    break

            # If the team doesn't play today, return
            if not found:
                await interaction.response.send_message(f"{emojis[team]} {team} does not play today.")
                return

            # Get the score and recap
            msg = self.get_score_string(game)
            link = self.get_recap_link(str(game["id"]))

            # Create and send the embed
            embed=discord.Embed(title=msg, url=link)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"Error in `/scores score` function: {e}")

    @scores_start.error
    @scores_stop.error
    @scoreboard.error
    @score.error
    async def score_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await interaction.response.send_message(f"{error}")

    async def post_goal(self, key, string, desc, link):
        # Add emoji to end of string to indicate a replay exists.
        if link != None:
            string += " :movie_camera:"

        # Bail if this message has already been sent and hasn't changed.
        if key in self.messages and string == self.messages[key]["msg_text"] and link == self.messages[key]["msg_link"]:
            return

        embed = discord.Embed(title=string, description=desc, url=link)

        # Update the goal if it's already been posted, but changed.
        if key in self.messages:
            post_type = "EDITING"
            msgs = self.messages[key]["msg_id"]
            for msg in msgs:
                msg = await self.bot.get_channel(msg[0]).fetch_message(msg[1])
                await msg.edit(embed=embed)
        else:
            post_type = "POSTING"
            msgs = []
            for channel in get_channels_from_ids(self.bot, self.scoreboard_channel_ids):
                msg = await channel.send(embed=embed)
                msgs.append((msg.channel.id, msg.id))

        # TODO: Store a more-sane json struct here, and reconstrcut the embed from it each time
        #       This will allow for easier of comparisons between events
        self.log.info(f"{self.scores_loop.current_loop} {post_type} {key}: {string} {desc} {link}")
        self.messages[key] = {"msg_id":msgs, "msg_text":string, "msg_desc":desc, "msg_link":link}

    def get_period_ordinal(self, period):
        period_ordinals = [None, "1st", "2nd", "3rd", "OT"]
        if period <= 4:
            period = period_ordinals[period]
        else:
            period = f"{period-3}OT"

        return period

    def get_goal_strength(self, goal):
        strength = goal["strength"] if "strength" in goal else "ev"
        modifier = goal["goalModifier"]

        ret = " "
        if strength != "ev":
            ret += f"({strength.upper()}) "

        if modifier == "penalty-shot":
            ret += "(PS) "

        if modifier == "empty-net":
            ret += "(EN) "

        return ret

    def convert_timestamp_to_seconds(self, period, time):
        mins, secs = time.split(":")
        return 20*60*(period-1) + (60*int(mins) + int(secs))

    # TODO: Break this down into a few more helper methods
    async def parse_game(self, game):
        state = game["gameState"]
        id = str(game["id"])

        # First check all the goals in a game if the game is live or even after it ends
        # It's bit inefficient to continue doing, but scoring changes and highlight links
        #  can sometimes come after the game is over.
        if state == "LIVE" or state == "CRIT" or state == "OVER" or state == "FINAL" or state == "OFF":
            landing = make_api_call(f"https://api-web.nhle.com/v1/gamecenter/{id}/landing")

            away = landing["awayTeam"]["abbrev"]
            home = landing["homeTeam"]["abbrev"]
            away_emoji = get_emoji(away)
            home_emoji = get_emoji(home)
            # TODO: May need some special handling for ASG emoji

            # Post the game starting notification
            start_key = f"{id}:S"
            if start_key not in self.messages:
                start_string = f"{away_emoji} {away} at {home_emoji} {home} Starting."
                # TODO: This hack should prevent the goal from posting if the date has been changed
                if self.messages["date"] == landing["gameDate"]:
                    await self.post_goal(start_key, start_string, desc=None, link=None)
                else:
                    self.log.info(f"WRONG DATE {self.scores_loop.current_loop} {self.messages}")

            # TODO: Check for Disallowed Goals and strikethrough the message
            # TODO: Remove Try once it's working
            try:
                for message in self.messages:
                    # Loop through all messages
                    # Compare to the goals in the corresponding game
                    # Cross out any that no longer exist
                    continue
            except Exception as e:
                self.log.info(f"Error checking disallowed goals {e}")

            # Check for Goals
            if "summary" in landing and "scoring" in landing["summary"]:
                for period in landing["summary"]["scoring"]:
                    # Skip shootout "periods" because we handle those separately
                    if period["periodDescriptor"]["periodType"] == "SO":
                        continue

                    for goal in period["goals"]:
                        period_num = period["period"]
                        period_ord = self.get_period_ordinal(period["period"])
                        time = goal["timeInPeriod"]
                        time_in_seconds = self.convert_timestamp_to_seconds(period_num, time)
                        goal_key = f"{id}:{time_in_seconds}"

                        strength = self.get_goal_strength(goal)
                        team = goal["teamAbbrev"]
                        team = f"{get_emoji(team)} {team}"
                        shot_type = f" {goal['shotType']}," if "shotType" in goal else ""

                        scorer = f"{goal['firstName']} {goal['lastName']} ({goal['goalsToDate']}){shot_type}"
                        assists = []
                        for assist in goal["assists"]:
                            assists.append(f"{assist['firstName']} {assist['lastName']} ({assist['assistsToDate']})")

                        goal_str = f"{get_emoji('goal')} GOAL{strength}{team} {time} {period_ord}: {scorer}"
                        if len(assists) > 0:
                            goal_str += f" assists: {', '.join(assists)}"
                        else:
                            goal_str += " unassisted"
                        score_str = f"{away_emoji} {away} **{goal['awayScore']} - {goal['homeScore']}** {home} {home_emoji}"

                        highlight = f"{self.media_link_base}{goal['highlightClip']}" if "highlightClip" in goal else None

                        # Compare goal_key to existing keys, and replace if it's just an existing one shifted by a few seconds
                        for t in range(time_in_seconds - 4, time_in_seconds + 5):
                            check_key = f"{id}:{t}"
                            if check_key == goal_key:
                                continue

                            if check_key in self.messages and score_str == self.messages[check_key]["msg_desc"]:
                                self.messages[goal_key] = self.messages[check_key]
                                del self.messages[check_key]

                        # TODO: This hack should prevent the goal from posting if the date has been changed
                        if self.messages["date"] == landing["gameDate"]:
                            await self.post_goal(goal_key, goal_str, score_str, highlight)

            # TODO: Start OT Challenge in a Thread (maybe move logic to OTChallenge.cog)

            # Post Shootout results in a single updating embed.
            if "summary" in landing and "shootout" in landing["summary"] and len(landing["summary"]["shootout"]) > 0:
                so_key = f"{id}:SO"
                shootout = landing["summary"]["shootout"]

                title = f"Shootout: {away_emoji} {away} - {home} {home_emoji}"
                away_shooters = ""
                home_shooters = ""
                for shooter in shootout:
                    shooter_str = ":white_check_mark:" if shooter["result"] == "goal" else ":x:"
                    if "firstName" in shooter and "lastName" in shooter:
                        shooter_str += f" {shooter['firstName']} {shooter['lastName']}"
                    if shooter["teamAbbrev"] == home:
                        home_shooters += shooter_str + "\n"
                    else:
                        away_shooters += shooter_str + "\n"
                away_shooters += "\u200b" # Zero-width character for spacing on mobile

                if so_key not in self.messages or self.messages[so_key]["msg_text"] != (away_shooters, home_shooters):
                    embed=discord.Embed(title=title)
                    embed.add_field(name=f"{away_emoji} {away}", value=away_shooters, inline=True)
                    embed.add_field(name=f"{home_emoji} {home}", value=home_shooters, inline=True)

                    # TODO: This is duplicated from post_goal, I can probably extract that part even further
                    #       out into a post_embed submethod
                    # TODO: This hack should prevent the goal from posting if the date has been changed
                    if self.messages["date"] == landing["gameDate"]:
                        if so_key in self.messages:
                            post_type = "EDITING"
                            msgs = self.messages[so_key]["msg_id"]
                            for msg in msgs:
                                msg = await self.bot.get_channel(msg[0]).fetch_message(msg[1])
                                await msg.edit(embed=embed)
                        else:
                            post_type = "POSTING"
                            msgs = []
                            for channel in get_channels_from_ids(self.bot, self.scoreboard_channel_ids):
                                msg = await channel.send(embed=embed)
                                msgs.append((msg.channel.id, msg.id))

                    # Replace newlines for single-line logging
                    away_shooters_log = away_shooters.replace("\n", "\\n")
                    home_shooters_log = home_shooters.replace("\n", "\\n")

                    self.log.info(f"{post_type} {so_key}: {away_shooters_log} {home_shooters_log}")
                    self.messages[so_key] = {"msg_id":msgs, "msg_text":(away_shooters, home_shooters), "msg_link":None}

            # If the game is over, announce the final.
            if state == "FINAL" or state == "OFF":
                end_key = id + ":E"
                if end_key not in self.messages or self.messages[end_key]["msg_link"] == None:
                    linescore = landing["summary"]["linescore"]

                    away_score = linescore["totals"]["away"]
                    home_score = linescore["totals"]["home"]

                    modifier = ""
                    last_period = linescore["byPeriod"][-1]["periodDescriptor"]
                    if last_period["periodType"] == "OT":
                        ot_num = last_period["number"] - 3
                        if ot_num == 1:
                            ot_num = ""
                        modifier = f" ({ot_num}OT)"
                    elif last_period["periodType"] == "SO":
                        modifier = " (SO)"

                    recap_link = self.get_recap_link(end_key)

                    end_string = f"Final{modifier}: {away_emoji} {away} {away_score} - {home_score} {home} {home_emoji}"

                    # TODO: This hack should prevent the goal from posting if the date has been changed
                    if self.messages["date"] == landing["gameDate"]:
                        await self.post_goal(end_key, end_string, desc=None, link=recap_link)

        # TODO: Consider writing after EVERY message post, to avoid potential spam
        async with self.messages_lock:
            WriteJsonFile(messages_datafile, self.messages)

###############################################################################################################################
#
# Old stuff I'm keeping around for later to help with implementing
#
###############################################################################################################################

    # # Checks for disallowed goals (ones we have posted, but are no longer in the play-by-play) and updates them
    # async def check_for_disallowed_goals(self, key, playbyplay):
    #     # Get list of scoring play ids
    #     goals = playbyplay["liveData"]["plays"]["scoringPlays"]
    #     all_plays = playbyplay["liveData"]["plays"]["allPlays"]

    #     # Skip if there aren't any plays or goals. Seems like feeds "disappear" for short periods of time occasionally,
    #     # and we don't want this to incorrectly trigger disallows.
    #     if len(all_plays) == 0:
    #         return

    #     # Loop through all of our pickled goals
    #  	# If one of them doesn't exist in the list of scoring plays anymore
    #  	# We should cross it out and notify that it was disallowed.
    #     for pickle_key in list(self.messages.keys()):
    #         game_id, event_id = pickle_key.split(":")

    #         # Skip goals from other games, or start, end, overtime start, and disallow events
    #         if game_id != key or event_id == "S" or event_id == "E" or event_id == "O" or event_id[-1] == "D":
    #             continue

    #         # Skip events for games that are already over, as these are often false alarms
    #         if f"{game_id}:E" in self.messages.keys():
    #             continue

    #         found = False
    #         for goal in goals:
    #             if event_id == str(all_plays[goal]["about"]["eventId"]):
    #                 found = True
    #                 break

    #         # This goal is still there, no need to disallow
    #         # Continue onto next pickle_key
    #         if found:
    #             continue

    #         # Skip updating goals that have already been crossed out
    #         if self.messages[pickle_key]["msg_text"][0] != "~":
    #             await self.post_goal(pickle_key, f"~~{self.messages[pickle_key]['msg_text']}~~", None, None)

    #         # Announce that the goal has been disallowed
    #         disallow_key = pickle_key + "D"
    #         if disallow_key not in self.messages:
    #             away = playbyplay["gameData"]["teams"]["away"]["abbreviation"]
    #             home = playbyplay["gameData"]["teams"]["home"]["abbreviation"]
    #             disallow_str = f"Goal disallowed in {away}-{home}. *Editor's Note, this may be broken currently*"
    #             await self.post_goal(disallow_key, disallow_str, None, None)

    # # Checks to see if OT challenge starting for a game
    # async def check_for_ot_challenge_start(self, key, playbyplay):
    #     status = playbyplay["gameData"]["status"]["detailedState"]
    #     # Game not in progress
    #     if "In Progress" not in status:
    #         return False

    #     # Game not tied
    #     if playbyplay["liveData"]["linescore"]["teams"]["home"]["goals"] != playbyplay["liveData"]["linescore"]["teams"]["away"]["goals"]:
    #         return False

    #     # Game not in final 5 minutes of 3rd or OT intermission
    #     ot = self.bot.get_cog("OTChallenge")
    #     await ot.processot(None) # TODO: Why is this here?
    #     if not ot.is_ot_challenge_window(playbyplay):
    #         return False

    #     return True
 
###############################################################################################################################

async def setup(bot):
    await bot.add_cog(Scoreboard(bot))
