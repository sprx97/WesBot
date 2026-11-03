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
        self.manager_names_by_year = {}

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
        year = Config.config["year"]
        if year not in self.manager_names_by_year:
            with DB.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT u.FFname AS manager_name
                    FROM Teams t
                    INNER JOIN Users u ON u.FFid=t.ownerID
                    WHERE t.year=%s
                    ORDER BY manager_name
                    """,
                    (year,),
                )
                self.manager_names_by_year[year] = [row["manager_name"] for row in cursor.fetchall()]

        search = current.casefold()
        matching_managers = [
            manager for manager in self.manager_names_by_year[year]
            if search in manager.casefold()
        ][:25]
        return [app_commands.Choice(name=manager, value=manager) for manager in matching_managers]

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

    @app_commands.command(name="cup_group", description="Show live standings for a manager's OTH Cup group.")
    @app_commands.describe(manager="A manager in the group", public="Whether to post the response publicly.")
    @app_commands.autocomplete(manager=manager_autocomplete)
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def cup_group(self, interaction: discord.Interaction, manager: str, public: bool = False):
        await interaction.response.defer(thinking=True, ephemeral=not public)
        year = Config.config["year"]

        with DB.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ct.`group` AS group_id
                FROM OTHCupTeams ct
                INNER JOIN Teams t ON t.year=ct.year AND t.teamID=ct.team_id
                INNER JOIN Users u ON u.FFid=t.ownerID
                WHERE ct.year=%s AND LOWER(u.FFname)=LOWER(%s)
                """,
                (year, manager),
            )
            manager_groups = cursor.fetchall()
            if not manager_groups:
                await interaction.followup.send(f"{manager} was not found in an OTH Cup group.")
                return
            if len(manager_groups) != 1:
                await interaction.followup.send(f"{manager} is listed in multiple OTH Cup groups.")
                return
            group_id = manager_groups[0]["group_id"]

            cursor.execute(
                """
                SELECT ct.team_id, u.FFname AS manager_name,
                       t.leagueID AS league_id, t.matchupID AS matchup_id,
                       t.currentWeekPF, t.prevWeekPF
                FROM OTHCupTeams ct
                INNER JOIN Teams t ON t.year=ct.year AND t.teamID=ct.team_id
                INNER JOIN Users u ON u.FFid=t.ownerID
                WHERE ct.year=%s AND ct.`group`=%s
                ORDER BY manager_name
                """,
                (year, group_id),
            )
            teams = {
                row["team_id"]: {
                    "team_id": row["team_id"],
                    "manager_name": row["manager_name"],
                    "league_id": row["league_id"],
                    "matchup_id": row["matchup_id"],
                    "currentWeekPF": float(row["currentWeekPF"] or 0),
                    "prevWeekPF": float(row["prevWeekPF"] or 0),
                    "wins": 0,
                    "losses": 0,
                    "ties": 0,
                    "for": 0.0,
                    "against": 0.0,
                }
                for row in cursor.fetchall()
            }
            cursor.execute(
                """
                SELECT r.first_week, r.second_week, r.status,
                       m.team_one_id, m.team_two_id, m.match_type
                FROM OTHCupRounds r
                INNER JOIN OTHCupMatches m
                  ON m.year=r.year AND m.stage=r.stage AND m.round=r.round_number
                INNER JOIN OTHCupTeams ct1
                  ON ct1.year=m.year AND ct1.team_id=m.team_one_id AND ct1.`group`=%s
                INNER JOIN OTHCupTeams ct2
                  ON ct2.year=m.year AND ct2.team_id=m.team_two_id AND ct2.`group`=%s
                WHERE r.year=%s AND r.stage='group'
                """,
                (group_id, group_id, year),
            )
            matches = cursor.fetchall()

        results = []
        for match in matches:
            one_id, two_id = match["team_one_id"], match["team_two_id"]
            if match["match_type"] == "bye" or one_id not in teams or two_id not in teams:
                continue
            if match["status"] == "in progress":
                continue
            one = teams[one_id]
            two = teams[two_id]
            weeks = [match["first_week"]]
            if match["second_week"] is not None:
                weeks.append(match["second_week"])
            placeholders = ", ".join(["%s"] * len(weeks))
            with DB.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT team_id, SUM(points) AS score
                    FROM Scoring
                    WHERE year=%s AND week IN ({placeholders}) AND team_id IN (%s, %s)
                    GROUP BY team_id
                    """,
                    (year, *weeks, one_id, two_id),
                )
                historical_scores = cursor.fetchall()
            if not historical_scores:
                continue
            historical_scores = {row["team_id"]: float(row["score"] or 0) for row in historical_scores}
            one_score = historical_scores.get(one_id, 0.0)
            two_score = historical_scores.get(two_id, 0.0)
            results.append((one_id, two_id, one_score, two_score))
            one["for"] += one_score
            one["against"] += two_score
            two["for"] += two_score
            two["against"] += one_score
            if one_score > two_score:
                one["wins"] += 1
                two["losses"] += 1
            elif two_score > one_score:
                two["wins"] += 1
                one["losses"] += 1
            else:
                one["ties"] += 1
                two["ties"] += 1

        records = {}
        for team_id, team in teams.items():
            records.setdefault((team["wins"], team["losses"], team["ties"]), set()).add(team_id)
        standings = []
        for record in sorted(records, key=lambda row: (-row[0], row[1], -row[2])):
            tied_ids = records[record]
            head_to_head = {team_id: [0, 0, 0] for team_id in tied_ids}
            for one_id, two_id, one_score, two_score in results:
                if one_id not in tied_ids or two_id not in tied_ids:
                    continue
                if one_score > two_score:
                    head_to_head[one_id][0] += 1
                    head_to_head[two_id][1] += 1
                elif two_score > one_score:
                    head_to_head[two_id][0] += 1
                    head_to_head[one_id][1] += 1
                else:
                    head_to_head[one_id][2] += 1
                    head_to_head[two_id][2] += 1
            standings.extend(
                teams[team_id]
                for team_id in sorted(
                    tied_ids,
                    key=lambda team_id: (
                        -head_to_head[team_id][0],
                        head_to_head[team_id][1],
                        -head_to_head[team_id][2],
                        -teams[team_id]["for"],
                        teams[team_id]["manager_name"],
                    ),
                )
            )
        name_width = max((len(team["manager_name"]) for team in standings), default=len("Manager"))
        header = f"`{'Manager':<{name_width}}`\u2003`{'W-L-T':>5}`\u2003`{'PF':>7}`"
        lines = []
        for team in standings:
            record = f"{team['wins']}-{team['losses']}-{team['ties']}"
            team_url = f"https://www.fleaflicker.com/nhl/leagues/{team['league_id']}/teams/{team['team_id']}"
            name_cell = f"[`{team['manager_name']:<{name_width}}`]({team_url})"
            record_cell = f"`{record:>5}`"
            points_for = f"{team['for']:>7.2f}"
            points_cell = f"`{points_for}`"
            lines.append(f"{name_cell}\u2003{record_cell}\u2003{points_cell}")
        table = f"{header}\n\n" + "\n".join(lines)
        group_number = int(group_id)
        group_label = ""
        while group_number > 0:
            group_number, remainder = divmod(group_number - 1, 26)
            group_label = chr(ord("A") + remainder) + group_label
        group_label = group_label or str(group_id)

        embed = discord.Embed(
            title=f"OTH Cup {year} — Group {group_label}",
            description=table if standings else "No teams found in this group.",
            url="https://roldtimehockey.com/othcup",
        )
        if not results:
            embed.set_footer(text="No completed group match results are available yet.")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="cup_bracket", description="Check when the OTH Cup knockout phase starts.")
    @app_commands.describe(public="Whether to post the response publicly.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(send_messages=True)
    async def cup_bracket(self, interaction: discord.Interaction, public: bool = False):
        await interaction.response.defer(thinking=True, ephemeral=not public)

        year = Config.config["year"]
        with DB.cursor() as cursor:
            cursor.execute(
                """
                SELECT MIN(first_week) AS start_week
                FROM OTHCupRounds
                WHERE year=%s AND stage <> 'group'
                """,
                (year,),
            )
            row = cursor.fetchone()

        start_week = row["start_week"] if row else None
        if start_week is None:
            description = "The OTH Cup knockout phase has not started yet. Check back later."
        else:
            description = f"The OTH Cup knockout phase has not started yet. Check back week {start_week}."
        embed = discord.Embed(title=f"OTH Cup {year} Bracket", description=description, url="https://roldtimehockey.com/othcup")
        await interaction.followup.send(embed=embed)

    @cup_group.error
    async def cup_group_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        self.log.error("cup_group command failed: %s", error)
        await interaction.followup.send("I couldn't load the OTH Cup group standings. Please try again later.")

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
