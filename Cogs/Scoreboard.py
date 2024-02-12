# Discord Libraries
from discord.ext import tasks
from discord import app_commands

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

        self.channel_ids = LoadJsonFile(channels_datafile)
        self.debug_channel_ids = {"207634081700249601": 489882482838077451} # OldTimeHockey's #oth-tech channel

        self.channels_lock = asyncio.Lock()
        self.messages_lock = asyncio.Lock()
        self.ot_lock = asyncio.Lock()

#region Cog Startup

    async def cog_load(self):
        self.bot.loop.create_task(self.start_loops())

    async def start_loops(self):
        self.scores_loop.start()
        self.loops.append(self.scores_loop)

    @tasks.loop(seconds=15)
    async def scores_loop(self):
        games = await self.get_games_for_today()
        for game in games:
            await self.parse_game(game)

    @scores_loop.before_loop
    async def before_scores_loop(self):
        await self.bot.wait_until_ready()

        # Load any messages we've sent previously today
        async with self.messages_lock:
            self.messages = LoadJsonFile(messages_datafile)

        async with self.ot_lock:
            self.ot_guesses = LoadJsonFile(ot_datafile)

    @scores_loop.error
    async def scores_loop_error(self, error):
        await self.cog_command_error(None, error)
        self.scores_loop.restart()

#endregion
#region Date/Today Functions

    async def do_ot_rollover(self):
        has_errors = False
        async with self.ot_lock:
            ot_games = list(self.ot_guesses.keys())
            for game_id in ot_games:
                landing = make_api_call(f"https://api-web.nhle.com/v1/gamecenter/{game_id}/landing")

                if landing["gameState"] != "OFF":
                    self.log.error(f"Game state not final for {game_id}. Something is wrong.")
                    has_errors = True
                    continue

                final_period = landing["summary"]["scoring"][-1]

                if final_period["periodDescriptor"]["periodType"] != "OT":
                    self.log.info(f"Game {game_id} did not end via Overtime.")
                    del self.ot_guesses[game_id]
                    continue

                if len(final_period["goals"]) != 1:
                    self.log.error(f"Game {game_id} apparently ended in OT but has more than one goal. Something is wrong.")
                    has_errors = True
                    continue

                gwg_scorer = final_period["goals"][0]["playerId"] # Could get firstName and lastName too for reporting

                ot_standings = LoadJsonFile(otstandings_datafile)
                for guild_id in self.ot_guesses[game_id]:
                    for user_id in self.ot_guesses[game_id][guild_id]:
                        # Add the guild to standings if it doesn't exist
                        if guild_id not in ot_standings:
                            ot_standings[guild_id] = {}

                        # Add the user to the guild's standings if they don't exist
                        if user_id not in ot_standings[guild_id]:
                            ot_standings[guild_id][user_id] = {"guesses": 0, "correct": 0}

                        # Update the user's stats
                        ot_standings[guild_id][user_id]["guesses"] += 1
                        if self.ot_guesses[game_id][guild_id][user_id] == gwg_scorer:
                            ot_standings[guild_id][user_id]["correct"] += 1

                        self.log.info(f"{user_id} guessed {self.ot_guesses[game_id][guild_id][user_id]}. {self.ot_guesses[game_id][guild_id][user_id] == gwg_scorer}")
                WriteJsonFile(otstandings_datafile, ot_standings)
                del self.ot_guesses[game_id]

            WriteJsonFile(ot_datafile, self.ot_guesses)

        if has_errors:
            channel = self.bot.get_channel(OTH_TECH_CHANNEL_ID)
            await channel.send(f"<@{SPRX_USER_ID}> Error in OT Rollover. Check logs.")

    # Rolls over the date in our messages_datafile to the next one.
    # This needs to be a function so we can await it and not spam all the messages from the previous day
    # after deleting them from the datafile.
    async def do_date_rollover(self, date):
        self.messages = {"date": date}
        async with self.messages_lock:
            WriteJsonFile(messages_datafile, self.messages)

        await self.do_ot_rollover()

    # Helper function to get all of the game JSON objects for the current day
    # from the NHL.com api.
    async def get_games_for_today(self):
        # Get the week scoreboard and today's date
        root = make_api_call(f"https://api-web.nhle.com/v1/scoreboard/now")
        date = root["focusedDate"]

        # Execute rollover if the date has changed
        if "date" not in self.messages or self.messages["date"] < date:
            self.log.info(f"Date before date rollover: {self.messages['date']}, Loop Iteration: {self.scores_loop.current_loop}")
            await self.do_date_rollover(date)
            self.log.info(f"Date after date rollover: {self.messages['date']}")
            return []

        # This hack should prevent the goal from posting if the date has gone backwards
        # NHL.com backslides sometimes right around the rollover time, probably due to
        # site redundancy.
        if self.messages["date"] > date:
            self.log.info(f"WRONG DATE {self.scores_loop.current_loop} date: {date}, stored: {self.messages['date']}")
            return []

        # Get the list of games for the correct date
        for games in root["gamesByDate"]:
            if games["date"] == date:
                return games["games"]

        return []

#endregion
#region Parsing Helper Functions

    # Gets the game recap video link if it's available
    def get_recap_link(self, id):
        try:
            media = make_api_call(f"https://api-web.nhle.com/v1/gamecenter/{id}/boxscore")
            recap = media["gameVideo"]["threeMinRecap"]
            return f"{self.media_link_base}{recap}"
        except:
            return None

    def get_teams_from_landing(self, landing):
        return landing["awayTeam"]["abbrev"], get_emoji(landing["awayTeam"]["abbrev"]), landing["homeTeam"]["abbrev"], get_emoji(landing["homeTeam"]["abbrev"])

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

    def goal_found_in_summary(self, logged_key, scoring):
        for period in scoring:
            # Skip shootout "periods" because we handle those separately
            if period["periodDescriptor"]["periodType"] == "SO":
                continue

            for goal in period["goals"]:
                period_num = period["period"]
                time = goal["timeInPeriod"]
                if f"{self.convert_timestamp_to_seconds(period_num, time)}" == logged_key:
                    return True

        return False

    def is_ot_challenge_window(self, play_by_play):
        if play_by_play["gameState"] not in ["LIVE", "CRIT"]:
            return False

        if "periodDescriptor" not in play_by_play or "clock" not in play_by_play:
            return False

        is_ot_period = play_by_play["periodDescriptor"]["periodType"] == "OT"
        is_intermission = play_by_play["clock"]["inIntermission"]
        is_near_end_of_third = play_by_play["clock"]["secondsRemaining"] < 60*OT_CHALLENGE_BUFFER_MINUTES and play_by_play["periodDescriptor"]["number"] == 3 and not is_intermission

        if (is_intermission and is_ot_period) or is_near_end_of_third:
            return True

        return False

    async def update_ot_thread_state(self, id, name, locked, auto_archive):
        # Create the thread if necessary
        for message_id in self.messages[id]["OT"]["message_ids"]:
            channel = message_id[0]
            message = message_id[1]

            thread = self.bot.get_channel(channel).get_thread(message)

            # Create a thread if it doesn't exist already
            if not thread:
                message = await self.bot.get_channel(channel).fetch_message(message)
                thread = await message.create_thread(name=name)

                intro = "# Welcome to OT Challenge v2 (beta)!\n\n" + \
                        "- Use /ot in this thread followed by a team abbreviation and player full name, last name, or number to guess.\n" + \
                        "- Use /ot_standings in any channel to display the scoreboard for this server.\n" + \
                        "- Use /ot_subscribe to receive a special role to be notified when each OT Challenge starts.\n" + \
                        "- Contact SPRX with any bugs or suggestions.\n"

                async with self.ot_lock:
                    ot_standings = LoadJsonFile(otstandings_datafile)
                    guild_id = str(thread.guild.id)
                    if guild_id in ot_standings and "role" in ot_standings[guild_id]:
                        intro += f"<@&{ot_standings[guild_id]['role']}>"

                await thread.send(intro)

            # Nothing to update if the thread name is identical to what we already have!
            if thread.name == name:
                return

            await thread.edit(name=name, locked=locked, auto_archive_duration=auto_archive)

#endregion
#region Game Parsing Sections

    async def check_game_start(self, id, landing):
        start_key = f"Start"

        away, away_emoji, home, home_emoji = self.get_teams_from_landing(landing)
        start_string = f"{away_emoji}{away} at {home_emoji}{home} Starting."
        await self.post_embed(self.messages[id], start_key, start_string)

    async def check_goals(self, id, landing):
        if "summary" not in landing or "scoring" not in landing["summary"]:
            return

        for period in landing["summary"]["scoring"]:
            # Skip shootout "periods" because we handle those separately
            if period["periodDescriptor"]["periodType"] == "SO":
                continue

            for goal in period["goals"]:
                # Get the timing info for the goal to create the key
                period_num = period["period"]
                period_ord = self.get_period_ordinal(period["period"])
                time = goal["timeInPeriod"]
                time_in_seconds = self.convert_timestamp_to_seconds(period_num, time)
                goal_key = f"{time_in_seconds}"

                # Get info about the goal
                strength = self.get_goal_strength(goal)
                team = goal["teamAbbrev"]["default"]
                team = f"{get_emoji(team)}{team}"
                shot_type = f" {goal['shotType']}," if "shotType" in goal else ""

                # Get the scorer and assists
                scorer = f"{goal['firstName']['default']} {goal['lastName']['default']} ({goal['goalsToDate']}){shot_type}"
                assists = []
                for assist in goal["assists"]:
                    assists.append(f"{assist['firstName']['default']} {assist['lastName']['default']} ({assist['assistsToDate']})")

                # Concatonate all the above info into the string to post
                goal_str = f"{get_emoji('goal')}GOAL{strength}{team} {time} {period_ord}: {scorer}"
                if len(assists) > 0:
                    goal_str += f" assists: {', '.join(assists)}"
                else:
                    goal_str += " unassisted"
                away, away_emoji, home, home_emoji = self.get_teams_from_landing(landing)
                score_str = f"{away_emoji}{away} **{goal['awayScore']} - {goal['homeScore']}** {home} {home_emoji}"

                highlight = f"{self.media_link_base}{goal['highlightClip']}" if "highlightClip" in goal else None

                # Compare goal_key to existing keys, and replace if it's just an existing one shifted by a few seconds
                for t in range(time_in_seconds - 4, time_in_seconds + 5):
                    check_key = f"{t}"
                    if check_key == goal_key:
                        continue

                    if check_key in self.messages[id]["Goals"] and score_str == self.messages[id]["Goals"][check_key]["content"]["description"]:
                        self.messages[id]["Goals"][goal_key] = self.messages[id]["Goals"][check_key]
                        del self.messages[id]["Goals"][check_key]
                        self.log.info(f"Timestamp corrected in {away}-{home} key {goal_key}")

                await self.post_embed(self.messages[id]["Goals"], goal_key, goal_str, highlight, score_str)

    async def check_disallowed_goals(self, id, landing):
        if "summary" not in landing or "scoring" not in landing["summary"]:
            return

        for logged_key, logged_value in self.messages[id]["Goals"].items():
            if logged_value["content"]["title"][0] == "~" or self.goal_found_in_summary(logged_key, landing["summary"]["scoring"]):
                continue # Goal still exists or is already disallowed, we're good!

            # If we get here, we want to cross out that goal key and change it to a *D key
            await self.post_embed(self.messages[id]["Goals"], logged_key, f"~~{logged_value['content']['title']}~~", logged_value["content"]["url"], f"~~{logged_value['content']['description']}~~")

    async def check_ot_challenge(self, id):
        play_by_play = make_api_call(f"https://api-web.nhle.com/v1/gamecenter/{id}/play-by-play")

        ot_key = "OT"
        away, away_emoji, home, home_emoji = self.get_teams_from_landing(play_by_play)

        is_ot_challenge_window = self.is_ot_challenge_window(play_by_play)
        is_in_ot = "periodDescriptor" in play_by_play and play_by_play["periodDescriptor"]["periodType"] == "OT"

        # Open the OT Challenge or update the message if needed
        if is_ot_challenge_window and play_by_play["homeTeam"]["score"] == play_by_play["awayTeam"]["score"]:
            time_remaining = "INT" if play_by_play['clock']['inIntermission'] else f"~{play_by_play['clock']['timeRemaining']} left"
            ot_string = f"OT Challenge for {away_emoji}{away} - {home} {home_emoji}is now open ({time_remaining})"
            await self.post_embed(self.messages[id], ot_key, ot_string)
            await self.update_ot_thread_state(id, f"⏳ {away}-{home} {self.messages['date'][2:]}", False, 1440)

        elif ot_key in self.messages[id] and play_by_play["gameState"] in ["OVER", "FINAL", "OFF"]:
            await self.update_ot_thread_state(id, f"🥅 {away}-{home} {self.messages['date'][2:]}", True, 1440)

        elif ot_key in self.messages[id] and not is_ot_challenge_window and is_in_ot:
            await self.update_ot_thread_state(id, f"🔒 {away}-{home} {self.messages['date'][2:]}", True, 1440)

    # Post Shootout results in a single updating embed.
    async def check_shootout(self, id, landing):
        if "summary" not in landing or "shootout" not in landing["summary"] or len(landing["summary"]["shootout"]) == 0:
            return

        so_key = f"Shootout"
        shootout = landing["summary"]["shootout"]
        away, away_emoji, home, home_emoji = self.get_teams_from_landing(landing)

        title = f"Shootout: {away_emoji}{away} - {home} {home_emoji}"
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

        fields = [
            {"name": f"{away_emoji}{away}", "value": away_shooters, "inline": True},
            {"name": f"{home_emoji}{home}", "value": home_shooters, "inline": True}
        ]

        await self.post_embed(self.messages[id], so_key, title, fields=fields)

    async def check_final(self, id, landing):
        end_key = "End"
        if end_key in self.messages[id] and self.messages[id][end_key]["content"]["url"] != None:
            return

        linescore = landing["summary"]["linescore"]

        away_score = linescore["totals"]["away"]
        home_score = linescore["totals"]["home"]

        # Set the modifier for the final, ie (OT), (2OT), (SO), etc
        modifier = ""
        last_period = linescore["byPeriod"][-1]["periodDescriptor"]
        if last_period["periodType"] == "OT":
            ot_num = last_period["number"] - 3
            if ot_num == 1:
                ot_num = ""
            modifier = f" ({ot_num}OT)"
        elif last_period["periodType"] == "SO":
            modifier = " (SO)"

        recap_link = self.get_recap_link(id)

        away, away_emoji, home, home_emoji = self.get_teams_from_landing(landing)
        end_string = f"Final{modifier}: {away_emoji}{away} {away_score} - {home_score} {home} {home_emoji}"

        await self.post_embed(self.messages[id], end_key, end_string, recap_link)

#endregion
#region Core Parsing/Posting Functions

    async def post_embed_to_debug(self, parent, key, title, link=None, desc=None, fields=[]):
        await self.post_embed(parent, key, title, desc, link, fields, True)

    async def post_embed(self, parent, key, title, link=None, desc=None, fields=[], debug=False):
       # Add emoji to end of string to indicate a replay exists.
        if link != None:
            title += " :movie_camera:"

        # There is a "video" embed object, ie content["video"]["url"], but it doesn't seem to work right now. IIRC bots are prevented from posting videos
        content = {"title": title, "description": desc, "fields": fields, "url": link}
        embed_dict = {"message_ids": [], "content": content}

        # Bail if this message has already been sent and hasn't changed.
        if key in parent and parent[key]["content"] == embed_dict["content"]:
            return

        embed = discord.Embed.from_dict(embed_dict["content"])

        # Update the goal if it's already been posted, but changed.
        if key in parent:
            post_type = "EDITING"
            embed_dict["message_ids"] = parent[key]["message_ids"]
            for msg in embed_dict["message_ids"]:
                msg = await self.bot.get_channel(msg[0]).fetch_message(msg[1])
                await msg.edit(embed=embed)
        else:
            post_type = "POSTING"
            channels = self.channel_ids

            # Modify slightly for debug features
            if debug:
                channels = self.debug_channel_ids
                post_type += "_DEBUG"

            for channel in get_channels_from_ids(self.bot, channels):
                msg = await channel.send(embed=embed)
                embed_dict["message_ids"].append([msg.channel.id, msg.id])

        self.log.info(f"{self.scores_loop.current_loop} {post_type} {key}: {embed_dict['content']}")
        parent[key] = embed_dict

        # Parent should always be some subkey of self.messages, so write it out
        async with self.messages_lock:
            WriteJsonFile(messages_datafile, self.messages)

    async def parse_game(self, game):
        state = game["gameState"]
        id = str(game["id"])

        if state not in ["LIVE", "CRIT", "OVER", "FINAL", "OFF"]:
            return

        landing = make_api_call(f"https://api-web.nhle.com/v1/gamecenter/{id}/landing")

        # Add all games to the messages list
        if id not in self.messages:
            self.messages[id] = {"awayTeam": landing["awayTeam"]["abbrev"], "homeTeam": landing["homeTeam"]["abbrev"], "Goals": {}}

        await self.check_game_start(id, landing)
        await self.check_goals(id, landing)
        await self.check_disallowed_goals(id, landing)
        await self.check_ot_challenge(id)
        await self.check_shootout(id, landing)
        if state in ["FINAL", "OFF"]:
            await self.check_final(id, landing)

#endregion
#region Scoreboard Slash Commands

    @app_commands.command(name="scores_start", description="Start the live scoreboard in this channel.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def scores_start(self, interaction: discord.Interaction):
        self.channel_ids[str(interaction.guild_id)] = interaction.channel.id

        async with self.channels_lock:
            WriteJsonFile(channels_datafile, self.channel_ids)

        await interaction.response.send_message("Scoreboard setup complete.", ephemeral=True)

    @app_commands.command(name="scores_stop", description="Stop the live scoreboard in this server.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def scores_stop(self, interaction: discord.Interaction):
        id = str(interaction.guild_id)
        if id not in self.channel_ids:
            await interaction.response.send_message("Scoreboard is not active in this server.", ephemeral=True)
            return

        self.channel_ids.pop(str(interaction.guild_id))

        async with self.channels_lock:
            WriteJsonFile(channels_datafile, self.channel_ids)

        await interaction.response.send_message("Scoreboard disabled. This will also disable OT Challenge until the scoreboard is re-enabled.", ephemeral=True)

    # Helper function to parse a game JSON object into a score string
    # Works for games that haven't started, are in progress, or are finished
    def get_score_string(self, game):
        away = game["awayTeam"]["abbrev"]
        home = game["homeTeam"]["abbrev"]

        away = f"{get_emoji(away)}{away}"
        home = f"{get_emoji(home)}{home}"

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
        await interaction.response.send_message(f"{error}", ephemeral=True)

#endregion
#region OT Challenge Slash Commands

    @app_commands.command(name="ot", description="Make a guess in an OT Challenge Thread.")
    @app_commands.describe(team="An NHL team", player="A player full name, last name, or number.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def ot(self, interaction: discord.Interaction, team: str, player: str):
        await interaction.response.defer(thinking=True)

        # Ensure this message was sent in an OT Challenge Thread
        # The last here condition isn't the greatest, but currently that's how we can identify if this is an OT Challenge thread as opposed to a different thread
        if not isinstance(interaction.channel, discord.Thread) or interaction.channel.owner_id != self.bot.user.id or interaction.channel.name[0] not in ["⏳", "🥅", "🔒"]:
            await interaction.followup.send(f"This is not a valid OT Challenge thread.")
            return

        # Check that the team is valid
        team = team.lower().strip()
        if team not in team_map.keys():
            await interaction.followup.send(f"{team} is not a valid team.")
            return
        team = team_map[team]

        if team not in interaction.channel.name[:10]:
            await interaction.followup.send(f"Team {team} is not in this game.")
            return

        if interaction.channel.locked:
            await interaction.followup.send(f"OT has started. No more guesses allowed.")
            return

        # Get correct game_id from messages
        game_id = None
        for id in self.messages:
            if "awayTeam" not in self.messages[id]:
                continue
            if team == self.messages[id]["awayTeam"] or team == self.messages[id]["homeTeam"]:
                game_id = id
                break

        if game_id == None:
            await interaction.followup.send(f"Trouble finding game id for {team}. This should not happen.")
            return

        # Find the team ID from the play-by-play
        play_by_play = make_api_call(f"https://api-web.nhle.com/v1/gamecenter/{id}/play-by-play")
        if play_by_play["awayTeam"]["abbrev"] == team:
            team_id = play_by_play["awayTeam"]["id"]
        elif play_by_play["homeTeam"]["abbrev"] == team:
            team_id = play_by_play["homeTeam"]["id"]
        else:
            await interaction.followup.send(f"Trouble finding team {team} in play-by-play. This should not happen.")
            return

        # Loop through the rosters in the play-by-play
        player_name = player_num = None
        try:
            player_num = int(player)
        except:
            player_name = player.lower().strip()

        found = False
        for roster_player in play_by_play["rosterSpots"]:
            if roster_player["teamId"] == team_id and (roster_player["lastName"]["default"].lower() == player_name or f"{roster_player['firstName']['default']} {roster_player['lastName']['default']}".lower() == player_name or roster_player["sweaterNumber"] == player_num):
                found = True
                break

        if found:
            async with self.ot_lock:
                if game_id not in self.ot_guesses:
                    self.ot_guesses[game_id] = {}
                if interaction.guild_id not in self.ot_guesses[game_id]:
                    self.ot_guesses[game_id][interaction.guild.id] = {}

                self.ot_guesses[game_id][interaction.guild.id][interaction.user.id] = roster_player["playerId"]

                WriteJsonFile(ot_datafile, self.ot_guesses)

            self.log.info(f"User {interaction.user.display_name} has guessed {roster_player['firstName']['default']} {roster_player['lastName']['default']}")
            await interaction.followup.send(f"{interaction.user.display_name} has guessed {roster_player['firstName']['default']} {roster_player['lastName']['default']}")
        else:
            self.log.info(f"Could not find {interaction.user.display_name} guess {team} {team_id} {player_num if player_num else player_name}")
            await interaction.followup.send(f"Could not find player {player} on team {team}.")

    @app_commands.command(name="ot_standings", description="Check the OT Challenge standings for this server.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def ot_standings(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        async with self.ot_lock:
            ot_standings = LoadJsonFile(otstandings_datafile)

        guild_id = str(interaction.guild_id)
        if guild_id not in ot_standings:
            await interaction.followup.send("No standings found for this server.", ephemeral=True)
            return

        message = "```{:<15} {:>4} {:>4}\n\n".format("User", "✅", "Tot")

        if "role" in ot_standings[guild_id]:
            del ot_standings[guild_id]["role"]
        standings = sorted(ot_standings[guild_id].items(), key=lambda x:(x[1]["correct"], -x[1]["guesses"]), reverse=True)
        for user in standings:
            user_name = self.bot.get_user(int(user[0])).display_name[:14]
            message += "{:<15} {:>4} {:>4}\n".format(user_name, user[1]["correct"], user[1]["guesses"])

        message += "```"
        embed = discord.Embed(title="OT Challenge Standings", description=message)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ot_subscribe", description="Add or remove the role to be notified when each OT Challenge starts.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def ot_subscribe(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)

        # TODO: Remove when enabling for other servers
        if interaction.guild.id != OTH_GUILD_ID:
            await interaction.followup.send(f"OT Subscribe is not yet available in this server. Check back soon.")
            return

        async with self.ot_lock:
            ot_standings = LoadJsonFile(otstandings_datafile)

            guild_id = str(interaction.guild_id)
            if guild_id not in ot_standings:
                ot_standings[guild_id] = {}

            # Check if ot_standings[guild_id]["role"] exists, and create a role if necessary
            otc_role = None
            if "role" in ot_standings[guild_id]:
                otc_role = interaction.guild.get_role(ot_standings[guild_id]["role"])

            # Create a new role if necessary
            if otc_role == None:
                otc_role = await interaction.guild.create_role(name="OT Challenge", mentionable=True)
                ot_standings[guild_id]["role"] = otc_role.id
                WriteJsonFile(otstandings_datafile, ot_standings)

            # If we still don't have a role, abort
            if otc_role == None:
                await interaction.followup.send("Error creating/finding OT Challenge role. Please contact the bot owner or try again later.")
                return

            # Toggle the role on the user that sent this message
            if interaction.user.get_role(otc_role.id):
                await interaction.user.remove_roles(otc_role)
                await interaction.followup.send(f"{interaction.user.display_name} unsubscribed from OT Challenge.")
            else:
                await interaction.user.add_roles(otc_role)
                await interaction.followup.send(f"{interaction.user.display_name} subscribed to OT Challenge.")

    @app_commands.command(name="ot_rollover", description="Admin function to test the OT rollover rapidly")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.check(is_bot_owner)
    async def ot_rollover(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await self.do_ot_rollover()
        await interaction.followup.send("Complete")

    @ot.error
    @ot_standings.error
    @ot_subscribe.error
    @ot_rollover.error
    async def ot_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await interaction.followup.send(f"{error}")

#endregion

async def setup(bot):
    await bot.add_cog(Scoreboard(bot))
