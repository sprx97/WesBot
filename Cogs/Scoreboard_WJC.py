from datetime import date, datetime

# Local Includes
from Shared import *
from Cogs.Scoreboard_Helper import *

def is_wjc_dates():
    year = int(Config.config["year"])
    start = date(year, 12, 25)
    end = date(year + 1, 1, 6)

    return start <= date.today() <= end

def parse_wjc_final(game):
    away = game["GuestTeam"]["TeamCode"]
    home = game["HomeTeam"]["TeamCode"]
    away_score = game["GuestTeam"]["Points"]
    home_score = game["HomeTeam"]["Points"]

    return f"Final: {get_emoji(away)} {away} U20 {away_score} - {home_score} {home} U20 {get_emoji(home)}"

def parse_wjc_start(game):
    away = game["GuestTeam"]["TeamCode"]
    home = game["HomeTeam"]["TeamCode"]

    return f"{get_emoji(away)} {away} U20 at {get_emoji(home)} {home} U20 Starting."

def parse_wjc_goal(goal):
    situation = goal["SituationType"]
    team = goal["ExecutedByShortTeamName"]
    clock_mins, clock_secs = goal["TimeOfPlay"].split(":")
    clock_mins = int(clock_mins)

    if clock_mins >= 60:
        clock = f"{clock_mins - 60}:{clock_secs}"
        period = "OT"
    elif clock_mins >= 40:
        clock = f"{clock_mins - 40}:{clock_secs}"
        period = "3rd"
    elif clock_mins >= 20:
        clock = f"{clock_mins - 20}:{clock_secs}"
        period = "2nd"
    else:
        clock = f"{clock_mins}:{clock_secs}"
        period = "1st"

    scorer = goal["Scorer"]["ReportingName"]

    goal_string = f"GOAL ({situation}) {get_emoji(team)} {team} U20 {clock} {period}: {scorer}"

    if "Assistant1" in goal:
        goal_string += f", assists: {goal['Assistant1']['ReportingName']}"
    if "Assistant2" in goal:
        goal_string += f", {goal['Assistant2']['ReportingName']}"

    return goal_string

def get_score_string_wjc(game):
    away = game["GuestTeam"]["TeamCode"]
    home = game["HomeTeam"]["TeamCode"]
    away = f"{get_emoji(away)} {away} U20"
    home = f"{get_emoji(home)} {home} U20"

    phase = game["PhaseId"]
    if phase == "PreliminaryRound":
        phase = f"Group {game['Group']}"
    elif phase == "RelegationRound":
        phase = "Relegation"
    elif phase == "BronzeMedalGame":
        phase = ":third_place:"
    elif phase == "GoldMedalGame":
        phase = ":first_place:"

    game_state = game["Status"]
    if game_state == "UPCOMING":
        utc_time = datetime.strptime(f"{game['GameDateTimeUTC']} +0000", "%Y-%m-%dT%H:%M:%SZ %z")
        time = f"<t:{int(utc_time.timestamp())}:t>"
        return f"**{phase}** {time}: {away} at {home}"
    elif game_state == "LIVE":
        away_score = game["GuestTeam"]["Points"]
        home_score = game["HomeTeam"]["Points"]
        # TODO: Add period and time remaining here, might not have that on this object. Need to get the play-by-play from the API
        return f"**{phase}** Live: {away} {away_score}, {home}, {home_score}"
    # TODO: Finals disappear at different time than NHL ones roll over. Can use messages as a backup
    elif game_state == "FINAL" or game_state == "F(OT)" or game_state == "F(SO)":
        away_score = game["GuestTeam"]["Points"]
        home_score = game["HomeTeam"]["Points"]
        if game_state == "FINAL":
            game_state = "Final"
        return f"**{phase}** {game_state}: {away} {away_score}, {home} {home_score}"
    else:
        return f"{away} at {home} {game_state}"
