# Discord Libraries
import discord
from discord.ext import commands, tasks

# Python Libraries
import pickle
import pymysql
import requests

# Local Includes
import Config
config = Config.config

######################## Team and Emoji Mappings ########################

team_map = {}
team_map["ari"] = team_map["arizona"] = team_map["phx"] = team_map["phoenix"] = team_map["coyotes"]                         = "ARI"
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
team_map["van"] = team_map["vancouver"] = team_map["canucks"] = team_map["nucks"]                                           = "VAN"
team_map["vgk"] = team_map["vegas"] = team_map["las vegas"] = team_map["golden knights"] = team_map["knights"]              = "VGK"
team_map["wsh"] = team_map["was"] = team_map["washington"] = team_map["capitals"] = team_map["caps"]                        = "WSH"
team_map["wpj"] = team_map["wpg"] = team_map["winnipeg"] = team_map["jets"]                                                 = "WPG"

emojis = {}
emojis["ARI"] = "<:ARI:269315353153110016>"
emojis["ANA"] = "<:ANA:271881573375279104>"
emojis["BOS"] = "<:BOS:269315305707143168>"
emojis["BUF"] = "<:BUF:269315526717603840>"
emojis["CGY"] = "<:CGY:269315410375999509>"
emojis["CAR"] = "<:CAR:269315433595666432>"
emojis["CHI"] = "<:CHI:269315278880505857>"
emojis["COL"] = "<:COL:269315269002919946>"
emojis["CBJ"] = "<:CBJ:269315288988647425>"
emojis["DAL"] = "<:DAL:269315550188929024>"
emojis["DET"] = "<:DET:269315577682722826>"
emojis["EDM"] = "<:EDM:269315479464706048>"
emojis["FLA"] = "<:FLO:269315494652280832>"
emojis["FLO"] = "<:FLO:269315494652280832>"
emojis["LAK"] = "<:LAK:269315457188626432>"
emojis["MIN"] = "<:MIN:269315563606507521>"
emojis["MTL"] = "<:MTL:269315427874635776>"
emojis["NSH"] = "<:NSH:269315511702126594>"
emojis["NJD"] = "<:NJD:269315361126481930>"
emojis["NYI"] = "<:NYI:269315441204264960>"
emojis["NYR"] = "<:NYR:269315518907809792>"
emojis["OTT"] = "<:OTT:269315534301036544>"
emojis["PHI"] = "<:PHI:269315418513080331>"
emojis["PIT"] = "<:PIT:269315504324214786>"
emojis["SEA"] = "<:SEA:747291968681541682>"
emojis["STL"] = "<:STL:269315296328679436>"
emojis["SJS"] = "<:SJS:269315542509289472>"
emojis["TBL"] = "<:TBL:269315471919022090>"
emojis["TOR"] = "<:TRT:805177551843885063>"
emojis["VAN"] = "<:VAN:269315315194658818>"
emojis["VGK"] = "<:VGK:363836502859448320>"
emojis["WSH"] = "<:WSH:269327070977458181>"
emojis["WPG"] = "<:WPJ:269315448833703946>"
emojis["WPJ"] = "<:WPJ:269315448833703946>"
emojis["goal"] = "<a:goalsiren:750190349963624510>"
emojis["parros"] = "<:parros:372533524286275597>"

role_ids = {}

# Returns the emoji if it's in the map, but blank if not
def get_emoji(team):
    if team in emojis:
        return emojis[team]
    return ""

######################## Global Variables ########################

# Server IDs
KK_GUILD_ID = 742845693785276576
OTH_GUILD_ID = 207634081700249601
TEST_GUILD_ID = 403805619175292929

# Channel IDs
HOCKEY_GENERAL_CHANNEL_ID = 507616755510673409
MODS_CHANNEL_ID = 220663309786021888
OTH_TECH_CHANNEL_ID = 489882482838077451
TRADEREVIEW_CHANNEL_ID = 235926223757377537
# OTH_OT_CHALLENGE_CHANNEL_ID = 207638168269225984

MAKE_A_THREAD_CATEGORY_ID = 744981120311099422
GUAVAS_AND_APPLES_CHANNEL_ID = 747906611959562280
LIVE_GAME_CHAT_CHANNEL_ID = 745031984601890906
BOTSPAM_CHANNEL_ID = 788079428629692417
# KK_OT_CHALLENGE_CHANNEL_ID = 805021649799741480

TEST_GENERAL_CHANNEL_ID = 403805619175292931

# Role IDs
TRADEREVIEW_ROLE_ID = 235926008266620929
OTH_BOX_ROLE_ID = 816888894066917407

PATRONS_ROLE_ID = 747514745891979324
PARTONS_ROLE_ID = 784239280591601694

TEST_ROLE_ROLE_ID = 801477256744403025

# User IDs
MINNE_USER_ID = 144483356531228672

# Config settings
MIN_INACTIVE_DAYS = 7 # Number of days where we deem a team to be "inactive" on fleaflicker
OT_CHALLENGE_BUFFER_MINUTES = 2 # Mintues left in the 3rd at which OT challenge submissions are accepted
ROLLOVER_HOUR_UTC = 11 # 11am UTC = 6am EST = 3am PST

######################## Base Cog Class ########################

# Base cog class
class WesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log = self.bot.create_log(self.__class__.__name__)
        self.log.info(f"{self.__class__.__name__} cog initialized.")
        self.populate_roles()
        self.loops = []

    def populate_roles(self):
        role_ids["D1"] = self.bot.get_guild(OTH_GUILD_ID).get_role(340870807137812480)
        role_ids["D2"] = self.bot.get_guild(OTH_GUILD_ID).get_role(340871193039208452)
        role_ids["D3"] = self.bot.get_guild(OTH_GUILD_ID).get_role(340871418453426177)
        role_ids["D4"] = self.bot.get_guild(OTH_GUILD_ID).get_role(340871648313868291)
        role_ids["Gretzky"] = self.bot.get_guild(OTH_GUILD_ID).get_role(479121618224807947)
        role_ids["Brodeur"] = self.bot.get_guild(OTH_GUILD_ID).get_role(479133674282024960)
        role_ids["Hasek"] = self.bot.get_guild(OTH_GUILD_ID).get_role(479133581822918667)
        role_ids["Roy"] = self.bot.get_guild(OTH_GUILD_ID).get_role(479133440902561803)
        role_ids["Lemieux"] = self.bot.get_guild(OTH_GUILD_ID).get_role(479133957288493056)
        role_ids["Jagr"] = self.bot.get_guild(OTH_GUILD_ID).get_role(479133917325033472)
        role_ids["Yzerman"] = self.bot.get_guild(OTH_GUILD_ID).get_role(479133873658396683)
        role_ids["Howe"] = self.bot.get_guild(OTH_GUILD_ID).get_role(479134018546302977)
        role_ids["Dionne"] = self.bot.get_guild(OTH_GUILD_ID).get_role(479133989559599135)
        role_ids["Bourque"] = self.bot.get_guild(OTH_GUILD_ID).get_role(496384675141648385)
        role_ids["Orr"] = self.bot.get_guild(OTH_GUILD_ID).get_role(496384733228564530)
        role_ids["Lidstrom"] = self.bot.get_guild(OTH_GUILD_ID).get_role(496384804359766036)
        role_ids["Niedermayer"] = self.bot.get_guild(OTH_GUILD_ID).get_role(496384857648267266)
        role_ids["Leetch"] = self.bot.get_guild(OTH_GUILD_ID).get_role(496384959720718348)
        role_ids["Chelios"] = self.bot.get_guild(OTH_GUILD_ID).get_role(496385004574605323)
        role_ids["Pronger"] = self.bot.get_guild(OTH_GUILD_ID).get_role(496385073507991552)

    # Cancels all running loops
    def cog_unload(self):
        for loop in self.loops:
            loop.cancel()

    # Generic error handler for all Discord Command Exceptions. Just logs the error,
    # but can override this method or specific commands' error handlers in cogs
    async def cog_command_error(self, ctx, error):
        try:
            self.log.error(error.message, stacklevel=2)
        except:
            self.log.error(error, stacklevel=2)

######################## Custom Exceptions ########################

# Custom exception for a failure to fetch a link
class LinkError(discord.ext.commands.CommandError):
    def __init__(self, url):
        self.message = f"Could not open url {url}."

# Custom exception for an invalid NHL team
class NHLTeamNotFound(discord.ext.commands.CommandError):
    def __init__(self, team):
        self.message = f"Team {team} not recognized."

# Custom exception for an invalid NHL team
class DataFileNotFound(discord.ext.commands.CommandError):
    def __init__(self, file):
        self.message = f"File {file} not found."

# Custom exception for a failure to fetch a link
class NoGamesTodayError(discord.ext.commands.CommandError):
    def __init__(self, date):
        self.message = f"No games found today ({date})."

# Custom exception for when a team doesn't play today
class TeamDoesNotPlayToday(discord.ext.commands.CommandError):
    def __init__(self, team):
        self.message = f"I do not think {team} plays today."

######################## Helper functions ########################

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

# Grabs the current score and opponent's current score for the given username
def get_user_matchup_from_database(user):
    user = user.lower()

    # For the lulz
    if user == "doodoosteve":
        user = "voodoosteve"

    cursor = DB.cursor()

    cursor.execute("SELECT me_u.FFname as name, me.currentWeekPF as PF, opp_u.FFname as opp_name, opp.currentWeekPF as opp_PF, me.leagueID as league_id, me.matchupID as matchup_id, " + \
                          "me.wins as wins, me.losses as losses, opp.wins as opp_wins, opp.losses as opp_losses, me.year as year " + \
                          "FROM Teams AS me " + \
                          "LEFT JOIN Teams AS opp ON (me.CurrOpp=opp.teamID AND me.year=opp.year) " + \
                          "INNER JOIN Users AS me_u ON me.ownerID=me_u.FFid " + \
                          "LEFT JOIN Users AS opp_u ON opp.ownerID=opp_u.FFid " + \
                          "INNER JOIN Leagues AS l ON (me.leagueID=l.id AND me.year=l.year) " + \
                          "WHERE me.replacement != 1 AND LOWER(me_u.FFname)='" + user + "' AND l.year=" + Config.config["year"])

    matchup = cursor.fetchall()
    cursor.close()

    return matchup

# Gets the JSON data from the given fleaflicker.com/api call
def make_api_call(link):
    try:
        with requests.get(link) as response: # Throws HTTPError if page fails to open
            data = response.json()
    except requests.exceptions.HTTPError:
        raise LinkError(link)

    return data

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

def sanitize(name):
    name = name.replace("è", "e") # Lafreniere
    name = name.replace("ü", "u") # Stutzle
    name = name.replace("'", "") # O'Reilly
    name = name.replace("’", "") # O’Reilly
    return name

######################## Pickle File commands ########################

channels_datafile = "data/channels.pickle"
messages_datafile = "data/messages.pickle"
ot_datafile = "data/ot.pickle"
otstandings_datafile = "data/otstandings.pickle"
pickems_datafile = "data/pickems.pickle"
pickemsstandings_datafile = "data/pickemsstandings.pickle"

def WritePickleFile(file, data):
    try:
        with open(file, "wb") as f:
            pickle.dump(data, f)
    except:
        raise DataFileNotFound(file)

def LoadPickleFile(file):
    try:
        with open(file, "rb") as f:
            try:
                data = pickle.load(f)
            except EOFError:
                data = {}
    except:
        raise DataFileNotFound(file)

    return data

######################## Decorator command checks ########################

def is_OTH_guild():
    def check(ctx):
        return ctx.message.guild.id == OTH_GUILD_ID or ctx.message.guild.id == TEST_GUILD_ID
    return commands.check(check)

def is_KK_guild():
    def check(ctx):
        return ctx.message.guild.id == KK_GUILD_ID or ctx.message.guild.id == TEST_GUILD_ID
    return commands.check(check)

def is_tech_channel():
    def check(ctx):
        return ctx.message.channel.id == OTH_TECH_CHANNEL_ID or ctx.message.channel.id == BOTSPAM_CHANNEL_ID or ctx.message.guild.id == TEST_GUILD_ID
    return commands.check(check)

def is_tradereview_channel():
    def check(ctx):
        return ctx.message.channel.id == TRADEREVIEW_CHANNEL_ID or commands.check(is_tech_channel())
    return commands.check(check)

def is_otchallenge_channel():
    def check(ctx):
        return ctx.message.channel.name == "ot-challenge"
    return commands.check(check)

def is_mods_channel():
    def check(ctx):
        return ctx.message.channel.id == MODS_CHANNEL_ID or commands.check(is_tech_channel())
    return commands.check(check)
