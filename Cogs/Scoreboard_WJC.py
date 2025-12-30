from datetime import date

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

    return f"Final: {emojis[away]} {away} U20 {away_score} - {home_score} {home} U20 {emojis[home]}"

def parse_wjc_start(game):
    away = game["GuestTeam"]["TeamCode"]
    home = game["HomeTeam"]["TeamCode"]

    return f"{emojis[away]} {away} U20 at {emojis[home]} {home} U20 Starting."

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

    goal_string = f"GOAL ({situation}) {emojis[team]} {team} U20 {clock} {period}: {scorer}"

    if "Assistant1" in goal:
        goal_string += f", assists: {goal['Assistant1']['ReportingName']}"
    if "Assistant2" in goal:
        goal_string += f", {goal['Assistant2']['ReportingName']}"

    return goal_string
