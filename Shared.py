# Discord Libraries
import discord
from discord.ext import commands

# Python Libraries
import json
import pymysql
import requests
import traceback

# Local Includes
import Config
config = Config.config

#region Emoji mappings

team_map = {}
team_map["ana"] = team_map["anaheim"] = team_map["ducks"]                                                                   = "ANA"
team_map["bos"] = team_map["boston"] = team_map["bruins"]                                                                   = "BOS"
team_map["buf"] = team_map["buffalo"] = team_map["sabres"]                                                                  = "BUF"
team_map["cgy"] = team_map["cal"] = team_map["calgary"] = team_map["flames"]                                                = "CGY"
team_map["car"] = team_map["carolina"] = team_map["canes"] = team_map["hurricanes"]                                         = "CAR"
team_map["chi"] = team_map["chicago"] = team_map["hawks"] = team_map["blackhawks"]                                          = "CHI"
team_map["col"] = team_map["colorado"] = team_map["avs"] = team_map["avalanche"]                                            = "COL"
team_map["cbj"] = team_map["columbus"] = team_map["jackets"] = team_map["blue jackets"]                                     = "CBJ"
team_map["dal"] = team_map["dallas"] = team_map["stars"]                                                                    = "DAL"
team_map["det"] = team_map["detroit"] = team_map["wings"] = team_map["red wings"]                                           = "DET"
team_map["edm"] = team_map["edmonton"] = team_map["oilers"]                                                                 = "EDM"
team_map["fla"] = team_map["flo"] = team_map["florida"] = team_map["panthers"]                                              = "FLA"
team_map["lak"] = team_map["la"] = team_map["los angeles"] = team_map["kings"]                                              = "LAK"
team_map["min"] = team_map["minnesota"] = team_map["wild"]                                                                  = "MIN"
team_map["mtl"] = team_map["mon"] = team_map["montreal"] = team_map["montréal"] = team_map["canadiens"] = team_map["habs"]  = "MTL"
team_map["nsh"] = team_map["nas"] = team_map["nashville"] = team_map["predators"] = team_map["preds"]                       = "NSH"
team_map["njd"] = team_map["nj"] = team_map["new jersey"] = team_map["jersey"] = team_map["devils"]                         = "NJD"
team_map["nyi"] = team_map["new york islanders"] = team_map["islanders"]                                                    = "NYI"
team_map["nyr"] = team_map["new york rangers"] = team_map["rangers"]                                                        = "NYR"
team_map["ott"] = team_map["ottawa"] = team_map["sens"] = team_map["senators"]                                              = "OTT"
team_map["phi"] = team_map["philadelphia"] = team_map["philly"] = team_map["flyers"]                                        = "PHI"
team_map["pit"] = team_map["pittsburgh"] = team_map["pens"] = team_map["penguins"]                                          = "PIT"
team_map["sea"] = team_map["seattle"] = team_map["kraken"]                                                                  = "SEA"
team_map["stl"] = team_map["st. louis"] = team_map["st louis"] = team_map["saint louis"] = team_map["blues"]                = "STL"
team_map["sjs"] = team_map["sj"] = team_map["san jose"] = team_map["sharks"]                                                = "SJS"
team_map["tbl"] = team_map["tb"] = team_map["tampa bay"] = team_map["tampa"] = team_map["bolts"] = team_map["lightning"]    = "TBL"
team_map["tor"] = team_map["toronto"] = team_map["leafs"] = team_map["maple leafs"]                                         = "TOR"
team_map["ari"] = team_map["arizona"] = team_map["phx"] = team_map["phoenix"] = team_map["coyotes"] = team_map["yotes"]     = "UTA"
team_map["uta"] = team_map["uch"] = team_map["utah"] = team_map["utes"] = team_map["yeti"] = team_map["yutes"]              = "UTA"
team_map["van"] = team_map["vancouver"] = team_map["canucks"] = team_map["nucks"]                                           = "VAN"
team_map["vgk"] = team_map["vegas"] = team_map["las vegas"] = team_map["golden knights"] = team_map["knights"]              = "VGK"
team_map["wsh"] = team_map["was"] = team_map["washington"] = team_map["capitals"] = team_map["caps"]                        = "WSH"
team_map["wpj"] = team_map["wpg"] = team_map["winnipeg"] = team_map["jets"]                                                 = "WPG"

# All-star teams
team_map["atl"] = team_map["atlantic"] = team_map["team atlantic"]                                                          = "ATL"
team_map["cen"] = team_map["central"] = team_map["team central"]                                                            = "CEN"
team_map["met"] = team_map["metropolitan"] = team_map["team metropolitan"]                                                  = "MET"
team_map["pac"] = team_map["pacific"] = team_map["team pacific"]                                                            = "PAC"

# 4-nations teams
team_map["can"] = team_map["canada"]                                                                                        = "CAN"
team_map["fin"] = team_map["finland"]                                                                                       = "FIN"
team_map["swe"] = team_map["sweden"]                                                                                        = "SWE"
team_map["usa"] = team_map["us"] = team_map["america"] = team_map["united states"]                                          = "USA"

emojis = {}
emojis["ANA"] = "<:ANA:1353413714505765028>"
emojis["BOS"] = "<:BOS:1353413726941745232>"
emojis["BUF"] = "<:BUF:1353413744335650819>"
emojis["CAR"] = "<:CAR:1353413753240031314>"
emojis["CBJ"] = "<:CBJ:1353413766359945318>"
emojis["CGY"] = "<:CGY:1353413772454400051>"
emojis["CHI"] = "<:CHI:1353413778296930426>"
emojis["COL"] = "<:COL:1353413783728554055>"
emojis["DAL"] = "<:DAL:1353413801931837490>"
emojis["DET"] = "<:DET:1353413809687105556>"
emojis["EDM"] = "<:EDM:1353413816620158976>"
emojis["FLA"] = emojis["FLO"] = "<:FLA:1353413824375422976>"
emojis["LAK"] = "<:LAK:1353413834580299797>"
emojis["MIN"] = "<:MIN:1353413841710481619>"
emojis["MTL"] = "<:MTL:1353413851135348806>"
emojis["NJD"] = "<:NJD:1353413858156482560>"
emojis["NSH"] = "<:NSH:1353413867325227081>"
emojis["NYI"] = "<:NYI:1353413874522525887>"
emojis["NYR"] = "<:NYR:1353413882563002550>"
emojis["OTT"] = "<:OTT:1353413889576145027>"
emojis["PHI"] = "<:PHI:1353413903689977998>"
emojis["PIT"] = "<:PIT:1353413910308589598>"
emojis["SEA"] = "<:SEA:1353413920148295821>"
emojis["SJS"] = "<:SJS:1353413929002336378>"
emojis["STL"] = "<:STL:1353413935692517397>"
emojis["TBL"] = "<:TBL:1353413942692544552>"
emojis["TOR"] = "<:TOR:1353413949265154109>"
emojis["UTA"] = emojis["ARI"] = "<:UTA:1353413956605313186>"
emojis["VAN"] = "<:VAN:1353413962561093672>"
emojis["VGK"] = "<:VGK:1353413969628364931>"
emojis["WPG"] = emojis["WPJ"] = "<:WPG:1353413976469536878>"
emojis["WSH"] = "<:WSH:1353413983440343182>"

# 4-nations
emojis["CAN"] = ":flag_ca:"
emojis["FIN"] = ":flag_fi:"
emojis["SWE"] = ":flag_se:"
emojis["USA"] = ":flag_us:"

# Other
emojis["goal"] = "<a:goalsiren:1354137595424014470>"

MEDIA_LINK_BASE = "https://players.brightcove.net/6415718365001/EXtG1xJ7H_default/index.html?videoId="

# Returns the emoji if it's in the map, and a dummy if not
def get_emoji(team):
    if team in emojis:
        return f"{emojis[team]}"
    return ":hockey:"

#endregion
#region Global Variables

# Server IDs
KK_GUILD_ID = 742845693785276576
OTH_GUILD_ID = 207634081700249601

# Channel IDs
HOCKEY_GENERAL_CHANNEL_ID = 507616755510673409
MODS_CHANNEL_ID = 220663309786021888
OTH_TECH_CHANNEL_ID = 489882482838077451
TRADEREVIEW_CHANNEL_ID = 235926223757377537

# Role IDs
TRADEREVIEW_ROLE_ID = 235926008266620929
OTH_BOX_ROLE_ID = 816888894066917407
SPRX_USER_ID = 228258453599027200

# Config settings
MIN_INACTIVE_DAYS = 7 # Number of days where we deem a team to be "inactive" on fleaflicker
OT_CHALLENGE_BUFFER_MINUTES = 5 # Mintues left in the 3rd at which OT challenge submissions are accepted
ROLLOVER_HOUR_UTC = 11 # 11am UTC = 6am EST = 3am PST

all_cogs = ["Cogs.Debug",
            "Cogs.KeepingKarlsson",
            "Cogs.Memes",
            "Cogs.OTH",
            "Cogs.Scoreboard"]

#endregion

# Base cog class
class WesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log = self.bot.create_log(self.__class__.__name__)
        self.log.info(f"{self.__class__.__name__} cog initialized.")
        self.loops = []

    # Cancels all running tasks
    async def cog_unload(self):
        for loop in self.loops:
            loop.cancel()

    # Generic error handler for all Discord Command Exceptions. Just logs the error,
    # but can override this method or specific commands' error handlers in cogs
    async def cog_command_error(self, ctx, error):
        try:
            for line in traceback.format_stack():
                self.log.error(line.strip())
        except:
            self.log.error(error)

# Custom exception for a failure to fetch a link
class LinkError(discord.ext.commands.CommandError):
    def __init__(self, url):
        self.message = f"Could not open url {url}."

class DataFileNotFound(discord.ext.commands.CommandError):
    def __init(self, file):
        self.message = f"Could not find file {file}."

#region Database helper functions

DB = pymysql.connect(host=Config.config["sql_hostname"], user=Config.config["sql_username"], passwd=Config.config["sql_password"], db=Config.config["sql_dbname"], cursorclass=pymysql.cursors.DictCursor)
DB.autocommit(True)

# Grabs the list of OTH leagues for the given year
# from the SQL database
def get_leagues_from_database(year):
    cursor = DB.cursor()
    cursor.execute(f"SELECT id, name from Leagues where year={year}")
    leagues = cursor.fetchall()
    cursor.close()

    return leagues

def sanitize_user(user):
    user = user.lower()

    # For the lulz
    if user == "doodoosteve" or user == "dookie":
        user = "stevenrj"
    elif user == "sprx":
        user = "sprx97"
    elif user == "planks":
        user = "twoplanks"
    elif user == "yoshi" or user == "yoshirider2709":
        user = "yoshirider2136"
    elif user == "coyle":
        user = "coyle1096"
    elif user == "chizzle":
        user = "ch1zzle"
    elif user == "edge":
        user = "edgies"

    return user

# Grabs the current score and opponent's current score for the given username
def get_user_matchup_from_database(user, division=None):
    user = sanitize_user(user)

    cursor = DB.cursor()

    year = Config.config["year"]

    query = "SELECT l.name as league_name, l.tier as tier, me_u.FFname as name, me.currentWeekPF as PF, opp_u.FFname as opp_name, opp.currentWeekPF as opp_PF, " + \
                          "me.leagueID as league_id, me.matchupID as matchup_id, " + \
                          "me.wins as wins, me.losses as losses, opp.wins as opp_wins, opp.losses as opp_losses, me.year as year, " + \
                          f"(select count(1) FROM Teams t where t.currentWeekPF > PF and t.year={year})+1 as ranking, " + \
                          f"(select count(1) FROM Teams t where t.currentWeekPF > opp_PF and t.year={year})+1 as opp_ranking " + \
                          "FROM Teams AS me " + \
                          "LEFT JOIN Teams AS opp ON (me.CurrOpp=opp.teamID AND me.year=opp.year) " + \
                          "INNER JOIN Users AS me_u ON me.ownerID=me_u.FFid " + \
                          "LEFT JOIN Users AS opp_u ON opp.ownerID=opp_u.FFid " + \
                          "INNER JOIN Leagues AS l ON (me.leagueID=l.id AND me.year=l.year) "

    if division == None:
        query += "WHERE me.replacement != 1 "
    else:
        query += f"WHERE LOWER(l.name)='{division.lower()}' "

    query += f"AND LOWER(me_u.FFname)='{user}' AND l.year={year}"

    cursor.execute(query)

    matchup = cursor.fetchall()
    cursor.close()

    return matchup

# Gets the JSON data from the given fleaflicker.com/api call
def make_api_call(link):
    try:
        with requests.get(link, headers={"Cache-Control": "must-revalidate, max-age=0", "Pragma": "no-cache"}) as response:
            data = response.json()
    except Exception:
        raise LinkError(link)

    return data

#endregion
#region Server helper functions

# Gets discord channel objects from a list of ids
def get_channels_from_ids(bot, ids):
    channels = []
    for id in ids.values():
        chan = bot.get_channel(id)
        if chan:
            channels.append(chan)
        else:
            bot.log.error(f"Could not find channel {id}. Does the bot have access to it?")
    return channels

def get_offseason_league_role(bot):
    return bot.get_guild(OTH_GUILD_ID).get_role(1274113360170061925)

def get_roles_from_ids(bot):
    league_role_ids = {}
    league_role_ids["D1"] = bot.get_guild(OTH_GUILD_ID).get_role(340870807137812480)
    league_role_ids["D2"] = bot.get_guild(OTH_GUILD_ID).get_role(340871193039208452)
    league_role_ids["D3"] = bot.get_guild(OTH_GUILD_ID).get_role(340871418453426177)
    league_role_ids["D4"] = bot.get_guild(OTH_GUILD_ID).get_role(340871648313868291)
    league_role_ids["WAITLIST"] = bot.get_guild(OTH_GUILD_ID).get_role(1290010111598657567)
    league_role_ids["Gretzky"] = bot.get_guild(OTH_GUILD_ID).get_role(479121618224807947)
    league_role_ids["Brodeur"] = bot.get_guild(OTH_GUILD_ID).get_role(479133674282024960)
    league_role_ids["Hasek"] = bot.get_guild(OTH_GUILD_ID).get_role(479133581822918667)
    league_role_ids["Roy"] = bot.get_guild(OTH_GUILD_ID).get_role(479133440902561803)
    league_role_ids["Lemieux"] = bot.get_guild(OTH_GUILD_ID).get_role(479133957288493056)
    league_role_ids["Jagr"] = bot.get_guild(OTH_GUILD_ID).get_role(479133917325033472)
    league_role_ids["Yzerman"] = bot.get_guild(OTH_GUILD_ID).get_role(479133873658396683)
    league_role_ids["Howe"] = bot.get_guild(OTH_GUILD_ID).get_role(479134018546302977)
    league_role_ids["Dionne"] = bot.get_guild(OTH_GUILD_ID).get_role(479133989559599135)
    league_role_ids["Bourque"] = bot.get_guild(OTH_GUILD_ID).get_role(496384675141648385)
    league_role_ids["Orr"] = bot.get_guild(OTH_GUILD_ID).get_role(496384733228564530)
    league_role_ids["Lidstrom"] = bot.get_guild(OTH_GUILD_ID).get_role(496384804359766036)
    league_role_ids["Niedermayer"] = bot.get_guild(OTH_GUILD_ID).get_role(496384857648267266)
    league_role_ids["Leetch"] = bot.get_guild(OTH_GUILD_ID).get_role(496384959720718348)
    league_role_ids["Chelios"] = bot.get_guild(OTH_GUILD_ID).get_role(496385004574605323)
    league_role_ids["Pronger"] = bot.get_guild(OTH_GUILD_ID).get_role(496385073507991552)
    league_role_ids["Coffey"] = bot.get_guild(OTH_GUILD_ID).get_role(1026259761265651742)
    
    return league_role_ids

def sanitize(name):
    name = name.replace("è", "e") # Lafrenière
    name = name.replace("ü", "u") # Stützle
    name = name.replace("'", "") # O'Reilly
    name = name.replace("’", "") # O’Reilly
    return name

#endregion
#region Datafile helper functions

channels_datafile = "data/channels.json"
messages_datafile = "data/messages.json"
ot_datafile = "data/ot.json"
otstandings_datafile = "data/otstandings.json"
pickems_datafile = "data/pickems.json"
pickemsstandings_datafile = "data/pickemsstandings.json"

def WriteJsonFile(file, data):
    try:
        with open(f"{Config.config['srcroot']}/{file}", "w") as f:
            json.dump(data, f, indent=4)
    except:
        raise DataFileNotFound(file)
    
def LoadJsonFile(file):
    try:
        with open(f"{Config.config['srcroot']}/{file}", "r") as f:
            try:
                return json.load(f)
            except:
                return {}
    except:
        raise DataFileNotFound(file)

#endregion
#region AppCommand Checks

def is_bot_owner(interaction: discord.Interaction) -> bool:
    return interaction.user.id == 228258453599027200 # My user ID

#endregion
