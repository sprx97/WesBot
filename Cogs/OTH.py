# Python Libraries
import asyncio
import subprocess

# Discord Libraries
import discord
from discord import app_commands

# Local Includes
from Shared import *

class OTH(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

#region Fleaflicker Matchups and Rankings

    def run_update_current_pf_script(self):
        return subprocess.run(
            [
                "/var/www/OldTimeHockey/scripts/oth.venv/bin/python3",
                "/var/www/OldTimeHockey/scripts/UpdateCurrentPF.py"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    async def manager_autocomplete(self, interaction: discord.Interaction, current: str):
        # Get a list of all of this year's managers from the database,
        # filtering to the substring and returning up to 25 results (Discord max limit)
        cursor = DB.cursor()
        cursor.execute(
            """
            SELECT DISTINCT u.FFname AS manager_name
            FROM Teams t
            INNER JOIN Users u ON u.FFid=t.ownerID
            WHERE t.year=%s AND INSTR(LOWER(u.FFname), %s) > 0
            ORDER BY manager_name
            LIMIT 25
            """,
            (Config.config["year"], current.lower()),
        )
        managers = cursor.fetchall()
        cursor.close()

        return [app_commands.Choice(name=manager["manager_name"], value=manager["manager_name"]) for manager in managers]

    def format_matchup_scores(self, team_one_name, team_one_score, team_two_name, team_two_score, team_one_url=None, team_two_url=None):
        team_one_name = team_one_name or "Unknown manager"
        team_two_name = team_two_name or "Unknown manager"
        name_width = max(len(team_one_name), len(team_two_name))

        def format_line(name, score, url):
            score_text = f"{score:>6.2f}" if score is not None else ""
            if url and score is not None:
                score_text = f"[{score_text}]({url})"
            name_text = f"`{name:<{name_width}}`"
            spacer = "\u2002" * max(0, 24 - name_width)
            return f"{name_text} {spacer}{score_text}"

        return f"{format_line(team_one_name, team_one_score, team_one_url)}\n{format_line(team_two_name, team_two_score, team_two_url)}"

    @app_commands.command(name="matchup", description="Check the current matchup score for a user.")
    @app_commands.describe(user="A fleaflicker username", public="Whether to post the response publicly.")
    @app_commands.autocomplete(user=manager_autocomplete)
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def matchup(self, interaction: discord.Interaction, user: str, public: bool = False):
        await interaction.response.defer(thinking=True, ephemeral=not public)

        await asyncio.to_thread(self.run_update_current_pf_script)

        matchup = get_user_matchup_from_database(user)
        if len(matchup) == 0:
            raise UserNotFound(user)
        if len(matchup) > 1:
            raise MultipleMatchupsFound(user)
        matchup = matchup[0]

        p1_name = matchup["name"]
        p1_score = matchup["PF"]
        if matchup["opp_name"] != None:
            p2_name = matchup["opp_name"]
            p2_score = matchup["opp_PF"]
            link = f"https://www.fleaflicker.com/nhl/leagues/{matchup['league_id']}/scores/{matchup['matchup_id']}"
        else:
            p2_name = "BYE"
            p1_score = None
            p2_score = None
            link = f"https://www.fleaflicker.com/nhl/leagues/{matchup['league_id']}/scores"
        msg = self.format_matchup_scores(p1_name, p1_score, p2_name, p2_score)

        tier_colors = [None, "#EFC333", "#3D99D8", "#E37E2E", "#3DCB77", "#AD1457"]
        color = discord.Color.from_str(tier_colors[matchup['tier']])
        embed = discord.Embed(title=f"{matchup['league_name']} Matchup", description=f"{msg}", url=link, color=color)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="cup", description="Check the current OTH Cup matchup score for a manager.")
    @app_commands.describe(user="A manager", public="Whether to post the response publicly.")
    @app_commands.autocomplete(user=manager_autocomplete)
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def cup(self, interaction: discord.Interaction, user: str, public: bool = False):
        await interaction.response.defer(thinking=True, ephemeral=not public)

        year = Config.config["year"]
        title = f"OTH Cup {year}"
        description = ""
        with DB.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.teamID AS team_id, u.FFname AS manager_name, ct.team_id AS cup_team_id
                FROM Teams t
                INNER JOIN Users u ON u.FFid=t.ownerID
                LEFT JOIN OTHCupTeams ct ON ct.year=t.year AND ct.team_id=t.teamID
                WHERE t.year=%s AND LOWER(u.FFname)=LOWER(%s)
                """,
                (year, user),
            )
            current_teams = cursor.fetchall()

            # Validate that we only got one team back, since this should be a unique search
            if len(current_teams) == 0:
                description = f"ERROR: user {user} not found."
            elif len(current_teams) > 1:
                description = f"ERROR: {user} matches multiple managers."
            elif current_teams[0]["cup_team_id"] is None:
                description = f"{current_teams[0]['manager_name']} did not make the OTH Cup this year."
            else:
                manager_name = current_teams[0]["manager_name"]
                team_id = current_teams[0]["team_id"]
                cursor.execute(
                    """
                    SELECT r.stage, r.round_number, r.first_week, r.second_week,
                           COUNT(m.match_id) AS match_count
                    FROM OTHCupRounds r
                    LEFT JOIN OTHCupMatches m
                      ON m.year=r.year AND m.stage=r.stage AND m.round=r.round_number
                    WHERE r.year=%s AND r.status='in progress'
                    GROUP BY r.stage, r.round_number, r.first_week, r.second_week
                    """,
                    (year,),
                )
                active_rounds = cursor.fetchall()

                if len(active_rounds) == 0:
                    description = "There is no active OTH Cup round right now."
                elif len(active_rounds) > 1:
                    description = "ERROR: Multiple OTH Cup rounds are marked in progress."
                else:
                    active_round = active_rounds[0]
                    if active_round["stage"] == "group":
                        round_title = "Group Stage"
                    elif active_round["match_count"] == 4:
                        round_title = "Quarterfinals"
                    elif active_round["match_count"] == 2:
                        round_title = "Semifinals"
                    elif active_round["match_count"] == 1:
                        round_title = "Finals"
                    else:
                        round_title = f"Round of {active_round['match_count'] * 2}"
                    title = f"OTH Cup {year} {round_title}"
                    cursor.execute(
                        """
                        SELECT m.match_type, m.team_one_id, m.team_two_id,
                               u1.FFname AS team_one_name,
                               u2.FFname AS team_two_name
                        FROM OTHCupMatches m
                        LEFT JOIN Teams t1 ON t1.year=m.year AND t1.teamID=m.team_one_id
                        LEFT JOIN Users u1 ON u1.FFid=t1.ownerID
                        LEFT JOIN Teams t2 ON t2.year=m.year AND t2.teamID=m.team_two_id
                        LEFT JOIN Users u2 ON u2.FFid=t2.ownerID
                        WHERE m.year=%s AND m.stage=%s AND m.round=%s
                          AND (m.team_one_id=%s OR m.team_two_id=%s)
                        """,
                        (
                            Config.config["year"],
                            active_round["stage"],
                            active_round["round_number"],
                            team_id,
                            team_id,
                        ),
                    )
                    matches = cursor.fetchall()

                    if len(matches) == 0:
                        description = f"{manager_name} has been eliminated from the OTH Cup."
                    elif len(matches) > 1:
                        description = f"ERROR: {manager_name} matches multiple active OTH Cup matchups."
                    else:
                        matchup = matches[0]
                        if matchup["match_type"] == "bye":
                            description = f"{manager_name} has a bye this round."
                        else:
                            weeks = [active_round["first_week"]]
                            if active_round["second_week"] is not None:
                                weeks.append(active_round["second_week"])
                            cursor.execute(
                                """
                                SELECT teamID AS team_id, leagueID AS league_id, matchupID AS matchup_id,
                                       currentWeekPF, prevWeekPF
                                FROM Teams
                                WHERE year=%s AND teamID IN (%s, %s)
                                """,
                                (Config.config["year"], matchup["team_one_id"], matchup["team_two_id"]),
                            )
                            score_rows = cursor.fetchall()
                            team_data = {row["team_id"]: row for row in score_rows}
                            scores = {
                                row["team_id"]: float(row["currentWeekPF"] or 0)
                                + (float(row["prevWeekPF"] or 0) if active_round["second_week"] is not None else 0)
                                for row in score_rows
                            }
                            team_one_score = scores.get(matchup["team_one_id"], 0)
                            team_two_score = scores.get(matchup["team_two_id"], 0)
                            team_one = team_data.get(matchup["team_one_id"], {})
                            team_two = team_data.get(matchup["team_two_id"], {})
                            team_one_url = f"https://www.fleaflicker.com/nhl/leagues/{team_one['league_id']}/scores/{team_one['matchup_id']}" if team_one.get("league_id") and team_one.get("matchup_id") else None
                            team_two_url = f"https://www.fleaflicker.com/nhl/leagues/{team_two['league_id']}/scores/{team_two['matchup_id']}" if team_two.get("league_id") and team_two.get("matchup_id") else None
                            description = self.format_matchup_scores(
                                matchup["team_one_name"],
                                team_one_score,
                                matchup["team_two_name"],
                                team_two_score,
                                team_one_url,
                                team_two_url,
                            )

        embed = discord.Embed(title=title, description=description, url="https://roldtimehockey.com/othcup")
        await interaction.followup.send(embed=embed)

#endregion

    @matchup.error
    async def matchup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, UserNotFound):
            await interaction.followup.send(error.message)
        elif isinstance(error, MultipleMatchupsFound):
            await interaction.followup.send(error.message)
        else:
            await interaction.followup.send(error)

async def setup(bot):
    await bot.add_cog(OTH(bot), guild=discord.Object(id=OTH_GUILD_ID))
