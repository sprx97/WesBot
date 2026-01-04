from datetime import date, datetime

# Local Includes
from Shared import *
from Cogs.Scoreboard_Helper import *

def parse_iihf_final(game, suffix = ""):
    away = game["GuestTeam"]["TeamCode"]
    home = game["HomeTeam"]["TeamCode"]
    away_emoji = get_emoji(away)
    home_emoji = get_emoji(home)
    away_score = game["GuestTeam"]["Points"]
    home_score = game["HomeTeam"]["Points"]
    away += suffix
    home += suffix

    return f"Final: {away_emoji} {away} {away_score} - {home_score} {home} {home_emoji}"

def parse_iihf_start(game, suffix = ""):
    away = game["GuestTeam"]["TeamCode"]
    home = game["HomeTeam"]["TeamCode"]
    away_emoji = get_emoji(away)
    home_emoji = get_emoji(home)
    away += suffix
    home += suffix

    return f"{away_emoji} {away} at {home_emoji} {home} Starting."

def parse_iihf_goal(goal, suffix = ""):
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

    goal_string = f"GOAL ({situation}) {get_emoji(team)} {team}{suffix} {clock} {period}: {scorer}"

    if "Assistant1" in goal:
        goal_string += f", assists: {goal['Assistant1']['ReportingName']}"
    if "Assistant2" in goal:
        goal_string += f", {goal['Assistant2']['ReportingName']}"

    return goal_string

def get_iihf_score_string(game, suffix = ""):
    away = game["GuestTeam"]["TeamCode"]
    home = game["HomeTeam"]["TeamCode"]
    away = f"{get_emoji(away)} {away}{suffix}"
    home = f"{get_emoji(home)} {home}{suffix}"

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
        return f"**{phase}** Live: {away} {away_score}, {home} {home_score}"
    # TODO: Finals disappear at different time than NHL ones roll over. Can use messages as a backup
    elif game_state == "FINAL" or game_state == "F(OT)" or game_state == "F(SO)":
        away_score = game["GuestTeam"]["Points"]
        home_score = game["HomeTeam"]["Points"]
        if game_state == "FINAL":
            game_state = "Final"
        return f"**{phase}** {game_state}: {away} {away_score}, {home} {home_score}"
    else:
        return f"{away} at {home} {game_state}"
