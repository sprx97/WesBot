import time

from Shared import *

# TODO: Possibly move get_score_string and get_games_for_today into here.

def get_teams_from_landing(landing):
    return landing["awayTeam"]["abbrev"], get_emoji(landing["awayTeam"]["abbrev"]), landing["homeTeam"]["abbrev"], get_emoji(landing["homeTeam"]["abbrev"])        

def get_period_ordinal(period):
    period_ordinals = [None, "1st", "2nd", "3rd", "OT"]
    if period <= 4:
        period = period_ordinals[period]
    else:
        period = f"{period-3}OT"

    return period

def get_goal_strength(event, is_home_team):
    situation = event["situationCode"]
    if not is_home_team:
        situation = situation[::-1]

    strength = " "

    # TODO: Need to check previous event for strength on PS
    # TODO: Lose out on (OG) here
    if situation == "1010":
        strength += "(PS) "

    if (int(situation[0])+int(situation[1])) < (int(situation[2])+int(situation[3])):
        strength += "(PP) "
    if (int(situation[0])+int(situation[1])) > (int(situation[2])+int(situation[3])):
        strength += "(SH) "

    if situation[0] == "0":
        strength += "(EN) "

    return strength

def get_player_name_from_id(player_id, rosters):
    for player in rosters:
        if player["playerId"] == player_id:
            return player["firstName"]["default"] + " " + player["lastName"]["default"]

    return "UNKNOWN PLAYER"

def is_ot_challenge_window(play_by_play):
    if play_by_play["gameState"] not in ["LIVE", "CRIT"]:
        return False

    if "periodDescriptor" not in play_by_play or "clock" not in play_by_play:
        return False

    is_intermission = play_by_play["clock"]["inIntermission"]
    last_play_was_in_third_period = len(play_by_play["plays"]) > 0 and play_by_play["plays"][-1]["periodDescriptor"]["number"] == 3
    last_play_was_in_ot_period = len(play_by_play["plays"]) > 0 and play_by_play["plays"][-1]["periodDescriptor"]["periodType"] == "OT"
    is_playoff_game = play_by_play["gameType"] == 3

    # Need to be a bit careful here because sometimes period rolls over from 2nd to 3rd during the intermission
    is_third_intermission = is_intermission and last_play_was_in_third_period

    # Need to be a bit careful here because sometimes period changes over from OT to SO late and re-opens
    is_ot_intermission = is_intermission and last_play_was_in_ot_period and is_playoff_game

    # Open in a close game late in the third too
    is_near_end_of_third = play_by_play["clock"]["secondsRemaining"] < 60*OT_CHALLENGE_BUFFER_MINUTES and play_by_play["periodDescriptor"]["number"] == 3 and not is_intermission

    if is_third_intermission or is_ot_intermission or is_near_end_of_third:
        return True

    return False

# Gets the game recap video link if it's available
def get_recap_link(id):
    try:
        scoreboard = make_api_call(f"https://api-web.nhle.com/v1/score/now")
        for game in scoreboard["games"]:
            if game["id"] == int(id):
                video_id = game["threeMinRecap"].split("-")[-1]
                return f"{MEDIA_LINK_BASE}{video_id}"
    except:
        return None
