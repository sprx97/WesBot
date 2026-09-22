# Python Libraries
import asyncio
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import requests

# Discord Libraries
import discord
from discord import app_commands
from discord.app_commands import Choice

# Local Includes
from Shared import *
from Cogs.LeagueInvite_Helper import format_league_invite_report, get_joined_owner_ids, get_league_invite_url, get_unjoined_managers, parse_league_assignments

class OTH_Registration(WesCog):

#region Member Management (Box and Roles)

    @app_commands.command(name="box", description="Send another user to the penalty box.")
    @app_commands.describe(user="A discord user to put in the box.", duration="How long, in minutes.")
    @app_commands.guild_only()
    @app_commands.default_permissions(send_messages=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def box(self, interaction: discord.Interaction, user: discord.Member, duration: int = 2, reason: str = ""):
        boxrole = self.bot.get_guild(OTH_GUILD_ID).get_role(OTH_BOX_ROLE_ID)
        await user.add_roles(boxrole)

        if reason != "":
            reason = f" for {reason}"
        await interaction.response.send_message(f"{duration} minute penalty to {user.display_name}{reason}.")

        await asyncio.sleep(60*duration)
        await user.remove_roles(boxrole)

    @app_commands.command(name="unbox", description="Release another user from the penalty box.")
    @app_commands.describe(user="A discord user to release from the box.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def unbox(self, interaction: discord.Interaction, user: discord.Member):
        boxrole = self.bot.get_guild(OTH_GUILD_ID).get_role(OTH_BOX_ROLE_ID)
        await user.remove_roles(boxrole)
        await interaction.response.send_message(f"{user.display_name} unboxed.", ephemeral=True)

    @box.error
    @unbox.error
    async def box_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, discord.ext.commands.MissingPermissions):
            await interaction.send_response("You do not have permissions to do this. You played yourself.")

            boxrole = self.bot.get_guild(OTH_GUILD_ID).get_role(OTH_BOX_ROLE_ID)
            await interaction.user.add_roles(boxrole)
            asyncio.sleep(120)
            await interaction.user.remove_roles(boxrole)

    def registration_scope_choices_helper():
        return [Choice(name=division, value=division) for division in ["D1", "D2", "D3", "D4", "D5"]]

    def get_role_assignments(self):
        credentials_file = os.path.join(Config.config["srcroot"], "service_client_secret_OTH.json")
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

        try:
            credentials = service_account.Credentials.from_service_account_file(credentials_file, scopes=scopes)
            sheets = build("sheets", "v4", credentials=credentials).spreadsheets()
            rows = sheets.values().get(spreadsheetId=Config.config["reg_sheet_id"], range="Responses!A:W").execute()
        except Exception:
            self.log.exception("Could not read role assignments from the registration sheet.")
            return None

        assignments = {}
        discord_name_col = 3 # D
        division_assignment_col = 21 # V
        league_assignment_col = 22 # W
        for row in rows.get("values", [])[1:]:
            if len(row) <= league_assignment_col:
                continue

            league = row[league_assignment_col].strip()
            if league.upper() in {"DECLINED", "NO RESPONSE", "QUITTER"}:
                continue

            name = row[discord_name_col].strip()
            if name == "":
                continue

            division = row[division_assignment_col]
            if division == "NEW":
                division = "D5"

            assignments[name.lower()] = (division, league)

        return assignments

    roles_group = app_commands.Group(name="roles", description="Help the OTH Server with setting league/division roles.")

    @roles_group.command(name="clear", description="Clear all league and division roles from all users.")
    @app_commands.describe(debug="Debug mode. Log but don't set roles.")
    @app_commands.choices(debug=[Choice(name="True", value=1), Choice(name="False", value=0)])
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roles_clear(self, interaction: discord.Interaction, debug: Choice[int]):
        debug = (debug.value == 1)

        await interaction.response.send_message(f"Removing all league/division roles.")
        if debug:
            await interaction.channel.send(f"Debug mode -- reading roles from file but not setting them. Check the bot's logs for output.")

        league_roles = get_roles_from_ids(self.bot)
        offseason_role = get_offseason_league_role(self.bot)

        if offseason_role == None:
            self.log.warning("Could not find offseason role. Aborting.")
            return

        count = 0
        members = self.bot.get_guild(OTH_GUILD_ID).members
        for member in members:
            for league_role in league_roles.values():
                if league_role in member.roles:
                    count += 1
                    self.log.info(f"Removing all league/division roles from {member.name}.")

                    # TODO: Could try using asyncio.gather to parallelize this.
                    # Something like `await asyncio.gather(*(update_member(member) for member in members))`

                    if not debug:
                        await member.remove_roles(*league_roles.values())
                        self.log.info("Roles removed")
                        try:
                            await member.add_roles(offseason_role)
                            self.log.info("Offseason role added")
                        except Exception as e:
                            await interaction.channel.send(f"Could not add offseason role to {member.name}: {e}")
                            return
                    break

        self.log.info(f"Found league/division roles on {count} members.")
        if not debug:
            await interaction.channel.send(f"Removed league/division roles from {count} members.")

        await interaction.channel.send(f"Completed.")

    @roles_group.command(name="assign", description="Assign league and division roles to a subset of members.")
    @app_commands.describe(debug="Debug mode. Log but don't set roles.", scope="Which league or division to assign roles for.")
    @app_commands.choices(
        debug=[Choice(name="True", value=1), Choice(name="False", value=0)],
        scope=registration_scope_choices_helper() + [Choice(name="Waitlist", value="WAITLIST")],
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roles_assign(self, interaction: discord.Interaction, debug: Choice[int], scope: Choice[str]):
        debug = (debug.value == 1)
        scope = scope.value

        await interaction.response.defer()

        assignments = await asyncio.to_thread(self.get_role_assignments)
        if assignments == None:
            await interaction.edit_original_response(content="Could not read role assignments from the registration sheet.")
            return

        await interaction.edit_original_response(content=f"Assigning roles for scope '{scope}'.")
        if debug:
            await interaction.channel.send(f"Debug mode -- reading roles from the registration sheet but not setting them. Check the bot's logs for output.")

        league_roles = get_roles_from_ids(self.bot)
        offseason_role = get_offseason_league_role(self.bot)
        nonmember_role = get_nonmember_league_role(self.bot)
        waitlist_role = get_waitlist_league_role(self.bot)
        retired_role = get_retired_league_role(self.bot)

        count = 0
        members = self.bot.get_guild(OTH_GUILD_ID).members
        for member in members:
            key = member.name.lower()
            if key not in assignments:
                key = member.display_name.lower()

            if key in assignments:
                division = assignments[key][0]
                league = assignments[key][1]

                # Skip members that are not in our desired scope
                if scope != division and scope != league:
                    continue

                roles_to_add = [league_roles[league]]
                if league_roles[league].name != "Waitlist":
                    roles_to_add.append(league_roles[division])

                count += 1
                self.log.info(f"Adding roles {roles_to_add} to {member.name}")
                if not debug:
                    await member.add_roles(*roles_to_add)
                    await member.remove_roles(offseason_role)
                    await member.remove_roles(nonmember_role)
                    await member.remove_roles(waitlist_role)
                    await member.remove_roles(retired_role)

        self.log.info(f"Added league/division roles to {count} members.")
        if not debug:
            await interaction.channel.send(f"Added league/division roles to {count} members.")

        await interaction.channel.send(f"Completed.")

    def get_league_invite_report_data(self, scope):
        year = int(Config.config["year"]) + 1
        if scope in ["D1", "D2", "D3", "D4", "D5"]:
            leagues = get_leagues_from_database(year, scope[-1])
        else:
            leagues = [league for league in get_leagues_from_database(year) if league["name"].strip().casefold() == scope.strip().casefold()]

        if not leagues:
            raise ValueError(f"No leagues found for scope {scope!r} in {year}.")

        credentials_file = os.path.join(Config.config["srcroot"], "service_client_secret_OTH.json")
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        credentials = service_account.Credentials.from_service_account_file(credentials_file, scopes=scopes)
        sheets = build("sheets", "v4", credentials=credentials).spreadsheets()
        rows = sheets.values().get(spreadsheetId=Config.config["reg_sheet_id"], range="Responses!A:W").execute()
        assignments = parse_league_assignments(rows.get("values", []), [league["name"] for league in leagues])

        unjoined_by_league = {}
        for league in leagues:
            standings = make_api_call(f"https://www.fleaflicker.com/api/FetchLeagueStandings?sport=NHL&league_id={league['id']}&season={year}", self.log)
            joined_owner_ids = get_joined_owner_ids(standings)
            league_key = league["name"].strip().casefold()
            unjoined_by_league[league_key] = get_unjoined_managers(assignments[league_key], joined_owner_ids)

        session = requests.session()
        login_response = session.post(
            "https://www.fleaflicker.com/nhl/login",
            data={
                "email": Config.config["fleaflicker_email"],
                "password": Config.config["fleaflicker_password"],
                "keepMe": "true",
            },
        )
        login_response.raise_for_status()
        for league in leagues:
            league["invite_url"] = get_league_invite_url(session, league["id"])

        return leagues, unjoined_by_league

    def get_league_invite_report(self, scope):
        leagues, unjoined_by_league = self.get_league_invite_report_data(scope)
        return format_league_invite_report(leagues[0]["tier"], leagues, unjoined_by_league)

    @app_commands.command(name="league_invite", description="List assigned managers who have not joined their Fleaflicker league.")
    @app_commands.describe(scope="Which league or division to check.")
    @app_commands.choices(scope=registration_scope_choices_helper())
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def league_invite(self, interaction: discord.Interaction, scope: Choice[str]):
        await interaction.response.defer(ephemeral=True)

        try:
            leagues, unjoined_by_league = await asyncio.to_thread(self.get_league_invite_report_data, scope.value)
            guild = self.bot.get_guild(OTH_GUILD_ID)
            for league in leagues:
                invite_url = league["invite_url"]
                league_key = league["name"].strip().casefold()
                for manager in unjoined_by_league[league_key]:
                    discord_name = manager["discord_name"].strip().lstrip("@").casefold()
                    member = discord.utils.find(lambda item: item.name.casefold() == discord_name, guild.members)
                    if member is None:
                        member = discord.utils.find(lambda item: item.display_name.casefold() == discord_name, guild.members)
                    if member is None:
                        manager["dm_status"] = "❌ Discord member not found"
                        continue

#                    reminder = f"Reminder: Please join {league['name']} on Fleaflicker: {invite_url}"
#                    try:
#                        await member.send(reminder)
#                    except discord.Forbidden:
#                        manager["dm_status"] = "❌ Forbidden"
#                    except discord.HTTPException:
#                        manager["dm_status"] = "❌ Failed"
#                    else:
#                        manager["dm_status"] = "✅"

            report = format_league_invite_report(leagues[0]["tier"], leagues, unjoined_by_league)
            sprx = self.bot.get_user(SPRX_USER_ID)
            if sprx is None:
                sprx = await self.bot.fetch_user(SPRX_USER_ID)
            await sprx.send(report)
        except Exception:
            self.log.exception(f"Could not create or send league invite report for scope {scope.value!r}.")
            await interaction.edit_original_response(content=f"Could not create or send the league invite report for {scope.value!r}.")
            return

        await interaction.edit_original_response(content=f"Sent the league invite report for {scope.value!r} to SPRX.")

#endregion

async def setup(bot):
    await bot.add_cog(OTH_Registration(bot), guild=discord.Object(id=OTH_GUILD_ID))
