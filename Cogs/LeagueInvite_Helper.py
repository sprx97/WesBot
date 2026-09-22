import re

FF_NAME_COL = 1
FF_ID_COL = 2
DISCORD_NAME_COL = 3
CLEANED_NAME_COL = 20
LEAGUE_ASSIGN_COL = 22

def get_league_invite_url(session, league_id):
    invite_page = session.get(f"https://www.fleaflicker.com/nhl/leagues/{league_id}/invite")
    invite_page.raise_for_status()
    invite_link_match = re.search(
        rf"https://www\.fleaflicker\.com/nhl/leagues/{league_id}/invited\?eh=[a-zA-Z0-9]+",
        invite_page.text,
    )
    if invite_link_match is None:
        raise RuntimeError(f"Could not find the invite link for league {league_id}.")

    return invite_link_match.group(0)

def parse_league_assignments(rows, league_names):
    selected_leagues = {name.strip().casefold() for name in league_names}
    assignments = {name: [] for name in selected_leagues}

    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) <= LEAGUE_ASSIGN_COL:
            continue

        league_key = row[LEAGUE_ASSIGN_COL].strip().casefold()
        if league_key not in selected_leagues:
            continue

        try:
            ff_id = int(row[FF_ID_COL].strip())
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid Fleaflicker ID on registration sheet row {row_number}.") from error

        assignments[league_key].append({
            "ff_id": ff_id,
            "cleaned_name": row[CLEANED_NAME_COL].strip(),
            "ff_name": row[FF_NAME_COL].strip(),
            "discord_name": row[DISCORD_NAME_COL].strip(),
        })

    return assignments

def get_joined_owner_ids(standings):
    if not isinstance(standings, dict) or not isinstance(standings.get("divisions"), list):
        raise ValueError("Fleaflicker returned invalid league standings.")

    owner_ids = set()
    for division in standings["divisions"]:
        for team in division.get("teams", []):
            for owner in team.get("owners", []):
                if "id" in owner:
                    owner_ids.add(int(owner["id"]))

    return owner_ids

def get_unjoined_managers(assignments, joined_owner_ids):
    return [manager for manager in assignments if manager["ff_id"] not in joined_owner_ids]

def format_league_invite_report(tier, leagues, unjoined_by_league):
    tier = str(tier)
    tier_label = tier if tier.upper().startswith("D") else f"D{tier}"
    lines = [f"**{tier_label} league invite check**"]

    for league in sorted(leagues, key=lambda item: item["name"].casefold()):
        invite_url = league["invite_url"]
        lines.extend(["", f"**{league['name']}** ([Invite]({invite_url}))"])
        managers = unjoined_by_league[league["name"].strip().casefold()]
        if not managers:
            lines.append("None")
            continue

        for manager in managers:
            cleaned_name = manager["cleaned_name"] or "(blank)"
            ff_name = manager["ff_name"] or "(blank)"
            discord_name = manager["discord_name"] or "(blank)"
            dm_status = manager.get("dm_status")
            status_suffix = f" | DM: {dm_status}" if dm_status else ""
            lines.append(f"- {cleaned_name} | FF: {ff_name} | Discord: {discord_name}{status_suffix}")

    return "\n".join(lines)
