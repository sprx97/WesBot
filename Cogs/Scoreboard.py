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

        self.scoreboard_channel_ids = LoadJsonFile(channels_datafile)
        self.debug_channel_ids = {"207634081700249601": 489882482838077451} # OldTimeHockey's #oth-tech channel
        self.channels_lock = asyncio.Lock()
        self.messages_lock = asyncio.Lock()

#region Cog Startup

    async def cog_load(self):
        self.bot.loop.create_task(self.start_loops())

    async def start_loops(self):
        self.scores_loop.start()
        self.loops.append(self.scores_loop)

    @tasks.loop(seconds=5)
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

    @scores_loop.error
    async def scores_loop_error(self, error):
        await self.cog_command_error(None, error)
        self.scores_loop.restart()

#endregion
#region Date/Today Functions

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
            await self.do_date_rollover(date)
            self.log.info(f"Date after date rollover: {self.messages['date']}")
            return []

        # Get the list of games for the correct date
        for games in root["gamesByDate"]:
            if games["date"] == date:
                return games["games"]

        return []

#endregion
#region Parsing Helper Functions

    # Gets the game recap video link if it's available
    def get_recap_link(self, key):
        try:
            game_id = key.split(":")[0]
            media = make_api_call(f"https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore")
            recap = media["gameVideo"]["threeMinRecap"]
            return f"{self.media_link_base}{recap}"
        except:
            return None

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

#endregion
#region Game Parsing Sections

    async def check_game_start(self, id, teams):
        start_key = f"{id}:S"

        start_string = f"{teams['away_emoji']} {teams['away']} at {teams['home_emoji']} {teams['home']} Starting."
        await self.post_embed(start_key, start_string, desc=None, link=None)
        await self.post_embed_to_debug(start_key, start_string, desc=None, link=None) # TODO: Testing, just remove soon

    # TODO: Not Implemented
    async def check_disallowed_goals(self, id, landing, teams):
        try:
            for message in self.messages:
                # Loop through all messages
                # Compare to the goals in the corresponding game
                # Cross out any that no longer exist
                continue
        except Exception as e:
            self.log.info(f"Error checking disallowed goals {e}")

    async def check_goals(self, id, landing, teams):
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
                goal_key = f"{id}:{time_in_seconds}"

                # Get info about the goal
                strength = self.get_goal_strength(goal)
                team = goal["teamAbbrev"]["default"]
                team = f"{get_emoji(team)} {team}"
                shot_type = f" {goal['shotType']}," if "shotType" in goal else ""

                # Get the scorer and assists
                scorer = f"{goal['firstName']['default']} {goal['lastName']['default']} ({goal['goalsToDate']}){shot_type}"
                assists = []
                for assist in goal["assists"]:
                    assists.append(f"{assist['firstName']['default']} {assist['lastName']['default']} ({assist['assistsToDate']})")

                # Concatonate all the above info into the string to post
                goal_str = f"{get_emoji('goal')} GOAL{strength}{team} {time} {period_ord}: {scorer}"
                if len(assists) > 0:
                    goal_str += f" assists: {', '.join(assists)}"
                else:
                    goal_str += " unassisted"
                score_str = f"{teams['away_emoji']} {teams['away']} **{goal['awayScore']} - {goal['homeScore']}** {teams['home']} {teams['home_emoji']}"

                highlight = f"{self.media_link_base}{goal['highlightClip']}" if "highlightClip" in goal else None

                # TODO: Find better way to help with fudging this and move into helper method
                # Compare goal_key to existing keys, and replace if it's just an existing one shifted by a few seconds
                for t in range(time_in_seconds - 4, time_in_seconds + 5):
                    check_key = f"{id}:{t}"
                    if check_key == goal_key:
                        continue

                    if check_key in self.messages and score_str == self.messages[check_key]["msg_desc"]:
                        self.messages[goal_key] = self.messages[check_key]
                        del self.messages[check_key]

                await self.post_embed(goal_key, goal_str, score_str, highlight)

    # TODO: Not Implemented
    async def check_ot_challenge(self, id, landing, teams):
        pass

    # Post Shootout results in a single updating embed.
    async def check_shootout(self, id, landing, teams):
        if "summary" not in landing or "shootout" not in landing["summary"] or len(landing["summary"]["shootout"]) == 0:
            return

        so_key = f"{id}:SO"
        shootout = landing["summary"]["shootout"]

        title = f"Shootout: {teams['away_emoji']} {teams['away']} - {teams['home']} {teams['home_emoji']}"
        away_shooters = ""
        home_shooters = ""
        for shooter in shootout:
            shooter_str = ":white_check_mark:" if shooter["result"] == "goal" else ":x:"
            if "firstName" in shooter and "lastName" in shooter:
                shooter_str += f" {shooter['firstName']} {shooter['lastName']}"
            if shooter["teamAbbrev"] == teams['home']:
                home_shooters += shooter_str + "\n"
            else:
                away_shooters += shooter_str + "\n"
        away_shooters += "\u200b" # Zero-width character for spacing on mobile

        fields = [
            {"name": f"{teams['away_emoji']} {teams['away']}", "value": away_shooters, "inline": True},
            {"name": f"{teams['home_emoji']} {teams['home']}", "value": home_shooters, "inline": True}
        ]

        await self.post_embed(so_key, title, None, None, fields)

    async def check_final(self, id, landing, teams):
        end_key = id + ":E"
        if end_key in self.messages and self.messages[end_key]["content"]["url"] != None:
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

        recap_link = self.get_recap_link(end_key)

        end_string = f"Final{modifier}: {teams['away_emoji']} {teams['away']} {away_score} - {home_score} {teams['home']} {teams['home_emoji']}"

        await self.post_embed(end_key, end_string, desc=None, link=recap_link)

#endregion
#region Core Parsing/Posting Functions

    async def post_embed_to_debug(self, key, string, desc, link, fields=[]):
        await self.post_embed(key, string, desc, link, fields, True)

    async def post_embed(self, key, string, desc, link, fields=[], debug=False):
       # Add emoji to end of string to indicate a replay exists.
        if link != None:
            string += " :movie_camera:"

        # There is a "video" embed object, ie content["video"]["url"], but it doesn't seem to work right now. IIRC bots are prevented from posting videos
        content = {"title": string, "description": desc, "type": "video", "fields": fields, "url": link}
        embed_dict = {"message_ids": [], "content": content}

        # Bail if this message has already been sent and hasn't changed.
        if key in self.messages and self.messages[key]["content"] == embed_dict["content"]:
            return

        embed = discord.Embed.from_dict(embed_dict["content"])

        # Update the goal if it's already been posted, but changed.
        if key in self.messages:
            post_type = "EDITING"
            embed_dict["message_ids"] = self.messages[key]["message_ids"]
            for msg in embed_dict["message_ids"]:
                msg = await self.bot.get_channel(msg[0]).fetch_message(msg[1])
                await msg.edit(embed=embed)
        else:
            post_type = "POSTING"
            channels = self.scoreboard_channel_ids
            
            # Modify slightly for debug features
            if debug:
                channels = self.debug_channel_ids
                post_type += " DEBUG"
            
            for channel in get_channels_from_ids(self.bot, channels):
                msg = await channel.send(embed=embed)
                embed_dict["message_ids"].append((msg.channel.id, msg.id))

        # TODO: Use a more-sane json key here
        self.log.info(f"{self.scores_loop.current_loop} {post_type} {key}: {embed_dict['content']}")
        self.messages[key] = embed_dict
        async with self.messages_lock:
            WriteJsonFile(messages_datafile, self.messages)

    async def parse_game(self, game):
        state = game["gameState"]
        id = str(game["id"])

        if state not in ["LIVE", "CRIT", "OVER", "FINAL", "OFF"]:
            return

        landing = make_api_call(f"https://api-web.nhle.com/v1/gamecenter/{id}/landing")
        teams = {
            "away": landing["awayTeam"]["abbrev"], 
            "home": landing["homeTeam"]["abbrev"], 
            "away_emoji": get_emoji(landing["awayTeam"]["abbrev"]), 
            "home_emoji": get_emoji(landing["homeTeam"]["abbrev"])
        }

        # This hack should prevent the goal from posting if the date has gone backwards
        # NHL.com backslides sometimes right around the rollover time, probably due to
        # site redundancy.
        if self.messages["date"] != landing["gameDate"]:
            self.log.info(f"WRONG START DATE {self.scores_loop.current_loop} {self.messages}")
            return

        await self.check_game_start(id, teams)
        await self.check_disallowed_goals(id, landing, teams)
        await self.check_goals(id, landing, teams)
        await self.check_ot_challenge(id, landing, teams)
        await self.check_shootout(id, landing, teams)
        if state in ["FINAL", "OFF"]:
            await self.check_final(id, landing, teams)

#endregion
#region Scoreboard Setup Commands

    @app_commands.command(name="scores_start", description="Start the live scoreboard in this channel.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def scores_start(self, interaction: discord.Interaction):
        self.scoreboard_channel_ids[str(interaction.guild.id)] = interaction.channel.id

        async with self.channels_lock:
            WriteJsonFile(channels_datafile, self.scoreboard_channel_ids)

        await interaction.response.send_message("Scoreboard setup complete.")

    @app_commands.command(name="scores_stop", description="Stop the live scoreboard in this server.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def scores_stop(self, interaction: discord.Interaction):
        id = str(interaction.guild_id)
        if id not in self.scoreboard_channel_ids:
            await interaction.response.send_message("Scoreboard is not active in this server.")
            return
        
        self.scoreboard_channel_ids.pop(str(interaction.guild_id))

        async with self.channels_lock:
            WriteJsonFile(channels_datafile, self.scoreboard_channel_ids)

        await interaction.response.send_message("Scoreboard disabled.")

#endregion
#region Scoreboard Slash Commands

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

#endregion

async def setup(bot):
    await bot.add_cog(Scoreboard(bot))
