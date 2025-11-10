import challonge
import discord

from Shared import *

class WoppaCup():
    has_tournament_started = True

    class WCView(discord.ui.View):
        def __init__(self):
            super().__init__()

            # Get info about the tournament
            self.participants, self.matches, self.url = WoppaCup.get_wc_data()
            self.curr_round, self.is_group_stage = WoppaCup.get_round_and_stage(self.matches)
            self.matches = WoppaCup.trim_matches(self.matches, self.curr_round, self.is_group_stage)
            self.round_name = WoppaCup.get_round_name(self.matches[0])

            # Group stage has 3 matches per group, so display them together
            # Knockout round display 4 for bracket purposes
            self.matches_per_page = 3 if self.is_group_stage else 4
            self.current = 0
            self.embed = None

            self.update_embed()

            # Remove the buttons if there's only one page
            if len(self.matches) <= self.matches_per_page:
                self.clear_items()

        def update_embed(self):
            # Wraparound
            if self.current == -1:
                self.current = int(len(self.matches)/self.matches_per_page-1)
            if self.current == len(self.matches)/self.matches_per_page:
                self.current = 0

            self.embed = discord.Embed(title=f"Woppa Cup {self.round_name}", url=self.url)
            start_match = self.current * self.matches_per_page
            end_match = (self.current + 1) * self.matches_per_page
            for m in self.matches[start_match:end_match]:
                self.embed.add_field(name="", value=WoppaCup.get_description_for_woppacup_embed(m, self.participants), inline=False)

            # Add a page count to the footer
            if len(self.matches) > self.matches_per_page:
                self.embed.set_footer(text=f"{self.current+1}/{int(len(self.matches)/self.matches_per_page)}", icon_url=None)

        @discord.ui.button(label="Prev", style=discord.ButtonStyle.green)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            self.current -= 1
            self.update_embed()
            await interaction.response.edit_message(embed=self.embed)

        @discord.ui.button(label="Next", style=discord.ButtonStyle.green)
        async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            self.current += 1
            self.update_embed()
            await interaction.response.edit_message(embed=self.embed)

    def get_wc_data():
        challonge.set_credentials(Config.config["challonge_username"], Config.config["challonge_api_key"])
        wc_id = Config.config["woppa_cup_id"]

        participants = challonge.participants.index(wc_id)

        # Sort the matches by round to ensure finding the current round works
        matches = challonge.matches.index(wc_id)
        matches = sorted(matches, key=lambda x: x["round"])

        url = challonge.tournaments.show(wc_id)["full_challonge_url"]

        return participants, matches, url

    def trim_matches(matches, round, is_group_stage):
        matching_matches = []
        for m in matches:
            # Skip matches where the round doesn't match
            if m["round"] != round:
                continue

            # Skip non-group-stage matches if we're looking for a group stage round
            if is_group_stage and m["group_id"] == None:
                continue

            # Skip group-stage matches if we are looking for a group stage round
            if not is_group_stage and m["group_id"] != None:
                continue

            # if the match passes the filters add it to the new list
            matching_matches.append(m)

        return matching_matches

    def get_round_name(match):
        round_id = match["round"]
        is_group_stage = match["group_id"] != None
        week_in_matchup = 1 if match["scores_csv"] == "" else 2

        if is_group_stage:
            return f"Group Stage Week {round_id}"
        else:
            rounds = [0, "Round of 128",
                         "Round of 64",
                         "Round of 32",
                         "Round of 16",
                         f"Quarterfinal",
                         f"Semifinal (Week {week_in_matchup} of 2)",
                         f"Championship (Week {week_in_matchup} of 2)"]
            return rounds[round_id]

    def get_round_and_stage(matches):
        for m in matches:
            # Skip completed matches, because we only want the current ones
            if m["state"] != "open":
                continue

            # Assume the first open match has the correct round, and set for the entire bracket
            return m["round"], (m["group_id"] != None)

        return 999, False

    def get_description_for_woppacup_embed(match, participants):
        p1_id = match["player1_id"]
        p2_id = match["player2_id"]
        p1_name = p2_name = p1_div = p2_div = None
        p1_prev = p2_prev = 0

        # Check for existing scores
        if match["scores_csv"] != "":
            scores = match["scores_csv"].split("-")
            p1_prev = int(scores[0])/100.0
            p2_prev = int(scores[1])/100.0

        # Get the particpants from the participants list
        for p in participants:
            if p1_id == p["id"] or p1_id in p["group_player_ids"]:
                p1_div = p["name"].split(".")[0]
                p1_name = p["name"].split(".")[-1]
            elif p2_id == p["id"] or p2_id in p["group_player_ids"]:
                p2_div = p["name"].split(".")[0]
                p2_name = p["name"].split(".")[-1]

            # Found both names!
            if p1_name != None and p2_name != None:
                break

        # Get p1's matchup from the database
        p1_matchup = get_user_matchup_from_database(p1_name, p1_div)
        if len(p1_matchup) == 0:
            raise OTH.UserNotFound(p1_name, p1_div)
        if len(p1_matchup) > 1:
            raise OTH.MultipleMatchupsFound(p1_name)
        p1_matchup = p1_matchup[0]

        # Get p2's matchup from the database
        p2_matchup = get_user_matchup_from_database(p2_name, p2_div)
        if len(p2_matchup) == 0:
            raise OTH.UserNotFound(p2_name, p2_div)
        if len(p2_matchup) > 1:
            raise OTH.MultipleMatchupsFound(p2_name)
        p2_matchup = p2_matchup[0]

        # Format names for posting
        p1_name = f"{p1_div[:8]}.{p1_name}"
        p2_name = f"{p2_div[:8]}.{p2_name}"
        if len(p1_name) > len(p2_name):
            p2_name += " "*(len(p1_name)-len(p2_name))
        else:
            p1_name += " "*(len(p2_name)-len(p1_name))

        # Format a matchup embed to send
        msg =  f"`{p1_name}` " + f"\u2002"*(24-len(p1_name)) + "[{:>6.2f}]({})\n".format(round(p1_matchup['PF'] + p1_prev, 2), f"https://www.fleaflicker.com/nhl/leagues/{p1_matchup['league_id']}/scores/{p1_matchup['matchup_id']}")
        msg += f"`{p2_name}` "+ f"\u2002"*(24-len(p2_name)) + "[{:>6.2f}]({})".format(round(p2_matchup['PF'] + p2_prev, 2), f"https://www.fleaflicker.com/nhl/leagues/{p2_matchup['league_id']}/scores/{p2_matchup['matchup_id']}")

        return msg

    # Creates an embed for a given woppa cup matchup
    def get_embed_for_woppacup_match(match, participants, url):
        embed = discord.Embed(title=f"Woppa Cup {WoppaCup.get_round_name(match)}", description=WoppaCup.get_description_for_woppacup_embed(match, participants), url=url)
        # embed.set_footer(text=url, icon_url=None)
        return embed
