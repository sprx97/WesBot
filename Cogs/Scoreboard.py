# Discord Libraries
import traceback
from discord.ext import tasks
from discord import app_commands

# Python Libraries
import asyncio
from datetime import date, datetime, timedelta
from functools import reduce
from zoneinfo import ZoneInfo

# Local Includes
from Shared import *
from Cogs.Scoreboard_Helper import *
from Cogs.Scoreboard_IIHF import *

class Scoreboard(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

        self.channel_ids = LoadJsonFile(channels_datafile)
        self.debug_channel_ids = {"207634081700249601": 489882482838077451} # OldTimeHockey's #oth-tech channel

        self.channels_lock = asyncio.Lock()
        self.messages_lock = asyncio.Lock()

        self.cooldown = 0

#region Cog Startup

    async def cog_load(self):
        self.bot.loop.create_task(self.start_loops())

    async def start_loops(self):
        self.scores_loop.start()
        self.loops.append(self.scores_loop)

    @tasks.loop(seconds=30)
    async def scores_loop(self):
        if self.cooldown > 0:
            self.cooldown -= 1
            self.log.info(f"Scores loop on cooldown, skipping iteration. Cooldown remaining: {self.cooldown} cycles.")
            return

        games = await self.get_games_for_today()
        for game in games:
            await self.parse_game(game)

        try:
            for id, tourney_type in Config.config["active_iihf_tourneys"].items():
                root = make_api_call(f"https://realtime.iihf.com/gamestate/GetLatestScoresState/{id}", self.log)
                if root == None:
                    return

                for game in root:
                    # Skip upcoming games
                    if game["Status"] == "UPCOMING":
                        continue

                    game_id = game["GameId"]
                    away = game["GuestTeam"]["TeamCode"]
                    home = game["HomeTeam"]["TeamCode"]
                    away_emoji = get_emoji(away)
                    home_emoji = get_emoji(home)
                    if tourney_type.lower() == "wjc":
                        away += " U20"
                        home += " U20"
                    elif tourney_type.lower() == "og-w":
                        away += " W"
                        home += " W"

                    # Add iihf game to messages if it doesn't exist
                    if "iihf" not in self.messages:
                            self.messages["iihf"] = {}
                    if game_id not in self.messages["iihf"]:
                        self.messages["iihf"][game_id] = {"homeTeam": f"{home}", "awayTeam": f"{away}", "events": {}}

                    breadcrumbs = ["iihf", game_id, "events"]

                    if game["Status"] == "FINAL" or game["Status"] == "F(OT)" or game["Status"] == "F(SO)":
                        end_string = parse_iihf_final(game, " U20" if tourney_type.lower() == "wjc" else "")
                        await self.post_embed(breadcrumbs, "end", end_string)

                    start_string = parse_iihf_start(game, " U20" if tourney_type.lower() == "wjc" else "")
                    await self.post_embed(breadcrumbs, "start", start_string)

                    play_by_play = make_api_call(f"https://realtime.iihf.com/gamestate/GetLatestState/{game_id}", self.log)
                    if play_by_play == None:
                        return

                    for period in play_by_play["Periods"]:
                        for goal in period["ScoringActions"]:
                            goal_string = parse_iihf_goal(goal, " U20" if tourney_type.lower() == "wjc" else "")
                            score_string = f"{away_emoji} {away} {goal['NewScore']['Away']} - {goal['NewScore']['Home']} {home} {home_emoji}"
                            await self.post_embed(breadcrumbs, goal["Id"], goal_string, None, score_string)

        except Exception as e:
            self.log.error(f"Error in IIHF Scoreboard parsing: {e}.")

        flush_telemetry()

    @scores_loop.before_loop
    async def before_scores_loop(self):
        await self.bot.wait_until_ready()

        # Load any messages we've sent previously today
        async with self.messages_lock:
            self.messages = LoadJsonFile(messages_datafile)

    @scores_loop.error
    async def scores_loop_error(self, error):
        tb = traceback.extract_tb(error.__traceback__)
        filename, lineno, _func, _text = tb[-1]
        self.log.error(f"Error in scores_loop at {filename}:{lineno} — {type(error).__name__}: {error}")
        if type(error).__name__ == "LinkError":
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
        root = make_api_call(f"https://api-web.nhle.com/v1/scoreboard/now", self.log)
        if root == None:
            self.cooldown = 4 # Skip 4 cycles (2 mins) as cooldown
            return []

        curr_date = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
        # date = self.messages["date"] # I think this works just as well, and apparently "focusedDate" breaks near the end of the SCF

        # Execute rollover if the date has changed
        if "date" not in self.messages or self.messages["date"] < curr_date:
            self.log.info(f"Date before date rollover: {self.messages['date']}, Loop Iteration: {self.scores_loop.current_loop}")
            await self.do_date_rollover(curr_date)
            self.log.info(f"Date after date rollover: {self.messages['date']}")
            return []

        # This hack should prevent the goal from posting if the date has gone backwards
        # NHL.com backslides sometimes right around the rollover time, probably due to
        # site redundancy.
        if self.messages["date"] > curr_date:
            self.log.error(f"WRONG DATE {self.scores_loop.current_loop} date: {curr_date}, stored: {self.messages['date']}")
            return []

        # Get the list of games for the correct date
        for games in root["gamesByDate"]:
            if games["date"] == curr_date:
                return games["games"]

        return []

#endregion
#region Game Parsing Sections

    def format_goal_embed(self, event, play_by_play):
        away, away_emoji, home, home_emoji = get_teams_from_json(play_by_play)

        # Get the timing info for the goal to create the key
        period_ord = get_period_ordinal(event["periodDescriptor"]["number"])
        time = event["timeInPeriod"]

        # Get the team that scored the goal
        team_id = event["details"]["eventOwnerTeamId"]
        is_home_team = True
        if play_by_play["awayTeam"]["id"] == team_id:
            team = play_by_play["awayTeam"]["abbrev"]
            is_home_team = False
        else:
            team = play_by_play["homeTeam"]["abbrev"]
        team = f"{get_emoji(team)} {team}"

        # Get the strength (PP, SH, EN, PS, etc)
        strength = get_goal_strength(event, is_home_team)

        # get the shot type
        shot_type = f" {event['details']['shotType']}," if "shotType" in event["details"] else ""

        # Get the scorer and assists
        scorer = get_player_name_from_id(event["details"]["scoringPlayerId"], play_by_play["rosterSpots"])
        scorer += f" ({event['details']['scoringPlayerTotal']}"

        scorer += ")"
        scorer += f"{shot_type}"

        goal_str = f"{get_emoji('goal')} GOAL{strength}{team} {time} {period_ord}: {scorer}"
        if "assist1PlayerId" in event["details"]:
            goal_str += f" assists: {get_player_name_from_id(event['details']['assist1PlayerId'], play_by_play['rosterSpots'])} ({event['details']['assist1PlayerTotal']})"

            # We'll only have an assist2 if we had an assist1
            if "assist2PlayerId" in event["details"]:
                goal_str += f", {get_player_name_from_id(event['details']['assist2PlayerId'], play_by_play['rosterSpots'])} ({event['details']['assist2PlayerTotal']})"
        else:
            goal_str += " unassisted"

        score_str = f"{away_emoji} {away} **{event['details']['awayScore']} - {event['details']['homeScore']}** {home} {home_emoji}"

        try:
            highlight = f"{MEDIA_LINK_BASE}{event['details']['highlightClip']}"
        except:
            highlight = None

        return goal_str, highlight, score_str

    async def check_disallowed_goals(self, game_id, play_by_play):
        # TODO: Implement this based on what happens to a goal event when its disallowed.
        #       Challenge events exist, but unsure if they replace the goal one or if the goal one gets deleted.
        # [typeDescKey] == "stoppage" and [details][reason] = "chlg-vis-off-side", and the original goal even disappears
        # In one such case, the goal event changed from a goal to a shot-on-goal
        # The following event then was a clg-vis-goal-interference
        # Later that event completely disappeared

        # Look through all event ids we've logged for this game, and make sure they still exist in the API.
        # If they've disappeared it means something got disallowed.
        for logged_event_id, logged_message in self.messages[game_id]["events"].items():
            # Skip non-goal events or already-disallowed ones
            if logged_event_id == "OT" or \
                logged_event_id == "Shootout" or \
                logged_message["content"]["title"][0] == "~" or \
                logged_message["content"]["title"].startswith("Final") or \
                logged_message["content"]["title"].endswith("Starting."):
                continue

            found = list(filter(lambda event: (str(event["eventId"]) == logged_event_id), play_by_play["plays"]))
            if len(found) == 0 or found[0]["typeDescKey"] != "goal":
                # TODO: Edit with the actual reason for disallowing -- will involve scanning the rest of the events
                # If we get here, we want to cross out that goal key and change it to a disallowed
                await self.post_embed([game_id, "events"], logged_event_id, f"~~{logged_message['content']['title']}~~", logged_message["content"]["url"], f"~~{logged_message['content']['description']}~~")

    async def check_ot_start(self, game_id, play_by_play):
        if play_by_play["gameState"] not in ["LIVE", "CRIT"]:
            return

        if "periodDescriptor" not in play_by_play or "clock" not in play_by_play or not play_by_play["plays"]:
            return

        if play_by_play["homeTeam"]["score"] != play_by_play["awayTeam"]["score"]:
            return

        is_intermission = play_by_play["clock"]["inIntermission"]
        last_play_was_in_third_period = play_by_play["plays"][-1]["periodDescriptor"]["number"] == 3

        # Need to be a bit careful here because sometimes period rolls over from 2nd to 3rd during the intermission
        is_third_intermission = is_intermission and last_play_was_in_third_period
        is_near_end_of_third = not is_intermission and \
            play_by_play["periodDescriptor"]["number"] == 3 and \
            play_by_play["clock"]["secondsRemaining"] < 60

        if is_third_intermission or is_near_end_of_third:
            away, away_emoji, home, home_emoji = get_teams_from_json(play_by_play)
            ot_string = f"{away_emoji} {away} at {home_emoji} {home} is about to enter overtime!"
            await self.post_embed([game_id, "events"], "OT", ot_string)

    def format_game_end_embed(self, event, play_by_play):
        away, away_emoji, home, home_emoji = get_teams_from_json(play_by_play)

        # Set the modifier for the final, ie (OT), (2OT), (SO), etc
        modifier = ""
        last_period = event["periodDescriptor"]
        if last_period["periodType"] == "OT":
            ot_num = last_period["number"] - 3
            if ot_num == 1:
                ot_num = ""
            modifier = f" ({ot_num}OT)"
        elif last_period["periodType"] == "SO":
            modifier = " (SO)"

        # Get the score of the game
        away_score = play_by_play["awayTeam"]["score"]
        home_score = play_by_play["homeTeam"]["score"]

        end_string = f"Final{modifier}: {away_emoji} {away} {away_score} - {home_score} {home} {home_emoji}"

        return end_string

#endregion
#region Core Parsing/Posting Functions

    async def post_embed(self, breadcrumbs, key, title, link=None, desc=None, fields=[], debug=False):
        parent = reduce(lambda d, key: d[key], breadcrumbs, self.messages)

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

            game = self.messages[breadcrumbs[0]]
            for channel in get_channels_from_ids(self.bot, channels):
                reference = None
                last_msg_ids = game["last_msg_ids"] if "last_msg_ids" in game else None
                if last_msg_ids:
                    msg_id = next((msg_id for channel_id, msg_id in last_msg_ids if channel_id == channel.id), None)
                    if msg_id:
                        reference = await channel.fetch_message(msg_id)

                msg = await channel.send(embed=embed, reference=reference)
                embed_dict["message_ids"].append([msg.channel.id, msg.id])

            # Turn off reply chaining for debug
            if not debug:
                game["last_msg_ids"] = embed_dict["message_ids"]

        self.log.info(f"{self.scores_loop.current_loop} {post_type} {key}: {embed_dict['content']}")
        parent[key] = embed_dict

        # All these chanegs will affect self.messages, because of how assigining dicts to variables works
        # So write it out to our datafile
        async with self.messages_lock:
            WriteJsonFile(messages_datafile, self.messages)

    async def parse_game(self, game):
        state = game["gameState"]
        game_id = str(game["id"])

        # Early return to avoid doing work before a game has actually started
        if state not in ["LIVE", "CRIT", "OVER", "FINAL", "OFF"]:
            return

        play_by_play = make_api_call(f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play", self.log)
        if play_by_play == None:
            return

        away, away_emoji, home, home_emoji = get_teams_from_json(play_by_play)
        home_team_id = play_by_play["homeTeam"]["id"]
        away_team_id = play_by_play["awayTeam"]["id"]

        # Add game to messages list
        if game_id not in self.messages:
            self.messages[game_id] = {"awayTeam": away, "homeTeam": home, "events": {}}

        try:
            await self.check_disallowed_goals(game_id, play_by_play)
            await self.check_ot_start(game_id, play_by_play)

            breadcrumbs = [game_id, "events"]
            shootout_home_str = ""
            shootout_away_str = ""
            for event in play_by_play["plays"]:
                event_id = str(event["eventId"])

                # Game Starting Message
                if event["typeDescKey"] == "period-start" and event["periodDescriptor"]["number"] == 1:
                    start_string = f"{away_emoji} {away} at {home_emoji} {home} Starting."
                    await self.post_embed(breadcrumbs, event_id, start_string)

                # Goal Message
                if event["typeDescKey"] == "goal":
                    # Skip shootout goals because those are handled separately
                    if event["periodDescriptor"]["periodType"] == "SO":
                        continue

                    goal_str, highlight, score_str = self.format_goal_embed(event, play_by_play)
                    await self.post_embed(breadcrumbs, event_id, goal_str, highlight, score_str)

                if event["periodDescriptor"]["periodType"] == "SO":
                    if event["typeDescKey"] in ["period-start", "shootout-complete", "period-end", "game-end"]:
                        continue

                    event_result = ":white_check_mark:" if event["typeDescKey"] == "goal" else ":x:"
                    event_result += f" {get_player_name_from_id(event['details']['shootingPlayerId'], play_by_play['rosterSpots'])}"

                    if event["details"]["eventOwnerTeamId"] == home_team_id:
                        shootout_home_str += event_result + "\n"
                    else:
                        shootout_away_str += event_result + "\n"

                # Game Ending Message
                if event["typeDescKey"] == "game-end":
                    # Return if we've already handled this and have the recap video.
                    if event_id in self.messages[game_id]["events"] and self.messages[game_id]["events"][event_id]["content"]["url"] != None:
                        return

                    end_string = self.format_game_end_embed(event, play_by_play)
                    recap_link = get_recap_link(game_id)
                    await self.post_embed(breadcrumbs, event_id, end_string, recap_link)

            if shootout_home_str != "" or shootout_away_str != "":
                title = f"Shootout: {away_emoji} {away} - {home} {home_emoji}"
                shootout_away_str += "\u200b" # Zero-width character for spacing on mobile
                fields = [
                    {"name": f"{away_emoji} {away}", "value": shootout_away_str, "inline": True},
                    {"name": f"{home_emoji} {home}", "value": shootout_home_str, "inline": True}
                ]
                await self.post_embed(breadcrumbs, "Shootout", title, fields=fields)

        except Exception as e:
            self.log.error(f"ERROR: {e}")

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

        await interaction.response.send_message("Scoreboard disabled.", ephemeral=True)

    # Helper function to parse a game JSON object into a score string
    # Works for games that haven't started, are in progress, or are finished
    def get_score_string(self, game):
        away = game["awayTeam"]["abbrev"]
        home = game["homeTeam"]["abbrev"]

        away = f"{get_emoji(away)} {away}"
        home = f"{get_emoji(home)} {home}"

        # First check for TBD, PPD, SUSP, or CNCL because it's behind a different key
        game_state = game["gameScheduleState"]
        if game_state != "OK":
            return f"{away} at {home} {game_state}"

        # Now check for "normal" states
        game_state = game["gameState"]
        game_type = game["gameType"]

        if game_state == "FUT" or game_state == "PRE": # Game hasn't started yet
            utc_time = datetime.strptime(f"{game['startTimeUTC']} +0000", "%Y-%m-%dT%H:%M:%SZ %z")
            time = f"<t:{int(utc_time.timestamp())}:t>"

            if game_type == 2: # Regular season
                away_record = game["awayTeam"]["record"].split("-")
                home_record = game["homeTeam"]["record"].split("-")
                away_points = 2*int(away_record[0]) + int(away_record[2])
                home_points = 2*int(home_record[0]) + int(home_record[2])

            score_string = f"{time}: {away}"
            if game_type == 2: # Regular season
                score_string += f" ({away_points} pts)"
            score_string += f" at {home}"
            if game_type == 2: # Regular season
                score_string += f" ({home_points} pts)"
        elif game_state == "OVER" or game_state == "FINAL" or game_state == "OFF":
            away_score = game["awayTeam"]["score"]
            home_score = game["homeTeam"]["score"]

            score_string = f"Final: {away} {away_score}, {home} {home_score}"
        elif game_state == "LIVE" or game_state == "CRIT":
            away_score = game["awayTeam"]["score"]
            home_score = game["homeTeam"]["score"]

            period = get_period_ordinal(game["period"])

            if game["clock"]["inIntermission"]:
                time = "INT"
            else:
                time = game["clock"]["timeRemaining"]

            score_string = f"Live: {away} {away_score}, {home} {home_score} ({period} {time})"
        else:
            raise Exception(f"Unrecognized game state {game_state}")

        # Show series score for playoffs in all states
        if game_type == 3:
            lower_seed = game["seriesStatus"]["bottomSeedTeamAbbrev"]
            higher_seed = game["seriesStatus"]["topSeedTeamAbbrev"]

            lower_seed = f"{get_emoji(lower_seed)} {lower_seed}"
            higher_seed = f"{get_emoji(higher_seed)} {higher_seed}"

            lower_wins = game["seriesStatus"]["bottomSeedWins"]
            higher_wins = game["seriesStatus"]["topSeedWins"]

            if lower_wins > higher_wins:
                verb = "**wins**" if lower_wins == 4 else "**leads**"
                score_string += f" ({lower_seed} {verb} {lower_wins}-{higher_wins})"
            elif higher_wins > lower_wins:
                verb = "**wins**" if higher_wins == 4 else "**leads**"
                score_string += f" ({higher_seed} {verb} {higher_wins}-{lower_wins})"
            else:
                score_string += f" (Series **tied** {lower_wins}-{higher_wins})"

        return score_string

    @app_commands.command(name="playoffs", description="List the playoff series.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def playoffs(self, interaction: discord.Interaction):
        try:
            year = Config.config["year"]
            playoffs = make_api_call(f"https://api-web.nhle.com/v1/playoff-series/carousel/{year}{int(year)+1}/", self.log)
            if playoffs == None:
                return

            if not playoffs or not playoffs["rounds"]:
                await interaction.response.send_message(f"No playoffs found for {year}-{year+1}")
                return

            msg = ""
            for round in playoffs["rounds"]:
                msg += f"**Round {round['roundNumber']}**\n"
                for series in round["series"]:
                    lower = series["bottomSeed"]["abbrev"]
                    higher = series["topSeed"]["abbrev"]

                    lower = f"{get_emoji(lower)} {lower}"
                    higher = f"{get_emoji(higher)} {higher}"

                    lower_wins = series["bottomSeed"]["wins"]
                    higher_wins = series["topSeed"]["wins"]

                    if lower_wins > higher_wins:
                        verb = "defeats" if lower_wins == 4 else "leads"
                        msg += f"{lower} {verb} {higher} {lower_wins}-{higher_wins}\n"
                    elif higher_wins > lower_wins:
                        verb = "defeats" if higher_wins == 4 else "leads"
                        msg += f"{higher} {verb} {lower} {higher_wins}-{lower_wins}\n"
                    else:
                        msg += f"{lower}-{higher} tied {lower_wins}-{higher_wins}\n"

                msg += "\n"

            await interaction.response.send_message(msg)

        except Exception as e:
            await interaction.response.send_message(f"Error in `/playoffs` function: {e}")

    @app_commands.command(name="scoreboard", description="Check out today's full scoreboard.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def scoreboard(self, interaction: discord.Interaction):
        msg = ""
        try:
            games = await self.get_games_for_today()
            for game in games:
                msg += self.get_score_string(game) + "\n"
        except Exception as e:
            await interaction.response.send_message(f"Error in NHL scores for `/scoreboard` function: {e}")
            return

        try:
            for id, tourney_type in Config.config["active_iihf_tourneys"].items():
                is_first_of_type = True
                root = make_api_call(f"https://realtime.iihf.com/gamestate/GetLatestScoresState/{id}", self.log)
                if root == None:
                    return

                for game in root:
                    game_dt_utc = datetime.strptime(f"{game['GameDateTimeUTC']} +0000", "%Y-%m-%dT%H:%M:%SZ %z")
                    game_dt_est = game_dt_utc - timedelta(hours=5)
                    date_dt = datetime.strptime(self.messages['date'], "%Y-%m-%d").date()

                    if game_dt_est.date() == date_dt:
                        if is_first_of_type:
                            msg += "\n"
                            is_first_of_type = False
                        suffix = " U20" if tourney_type.lower() == "wjc" else " W" if tourney_type.lower() == "og-w" else ""
                        msg += get_iihf_score_string(game, suffix) + "\n"
        except Exception as e:
            await interaction.response.send_message(f"Error in IIHF scores for `/scoreboard` function: {e}")
            return

        if msg == "":
            msg = "No games found for today."

        await interaction.response.send_message(msg)

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
            team_emoji = get_emoji(team)
            if team == None:
                await interaction.response.send_message(f"Team '{team}' not found.")
                return

            # Loop through the games searching for this team
            games = await self.get_games_for_today()
            found = False
            for game in games:
                if game["awayTeam"]["abbrev"] == team or game["homeTeam"]["abbrev"] == team:
                    found = True
                    msg = self.get_score_string(game)
                    link = get_recap_link(str(game["id"]))
                    break

            for id, tourney_type in Config.config["active_iihf_tourneys"].items():
                root = make_api_call(f"https://realtime.iihf.com/gamestate/GetLatestScoresState/{id}", self.log)
                if root == None:
                    return

                for game in root:
                    if game["GuestTeam"]["TeamCode"] == team or game["HomeTeam"]["TeamCode"] == team:
                        found = True
                        msg = get_iihf_score_string(game, " U20" if tourney_type.lower() == "wjc" else "")
                        link = None
                        if tourney_type.lower() == "wjc":
                            team += " U20"
                        break

            # If the team doesn't play today, return
            if not found:
                await interaction.response.send_message(f"{team_emoji} {team} does not play today.")
                return

            # Create and send the embed
            embed=discord.Embed(title=msg, url=link)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"Error in `/scores score` function: {e}")

    @scores_start.error
    @scores_stop.error
    @scoreboard.error
    @score.error
    @playoffs.error
    async def score_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await interaction.response.send_message(f"{error}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Scoreboard(bot))
