import time

from Shared import *

# TODO: Possibly move get_score_string and get_games_for_today into here.

def get_teams_from_json(json):
    return json["awayTeam"]["abbrev"], get_emoji(json["awayTeam"]["abbrev"]), json["homeTeam"]["abbrev"], get_emoji(json["homeTeam"]["abbrev"])        

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

    # if the sum of the "situation bits" is less than 8 and it isn't a penalty shot (1010),
    # then skip it because this is broken in the olympics
    if (int(situation[0])+int(situation[1])+int(situation[2])+int(situation[3])) < 8 and situation != "1010":
        return strength

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
