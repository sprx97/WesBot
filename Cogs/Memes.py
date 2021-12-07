# Discord Libraries
from discord.ext import commands

# Local Includes
from Shared import *

class Memes(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command(name="memes")
    @is_OTH_guild()
    async def memes(self, ctx):
        await ctx.send("Try the following meme commands: *bob, bryz, cat, dahlin, fifi, laine, mcavoy, ned, petey, price, xfactor*")

    @commands.command(name="fifi")
    @commands.cooldown(1, 60.0, commands.BucketType.guild) # 1 use per minute per guild
    @is_OTH_guild()
    async def fifi(self, ctx):
        await ctx.send("Aw yeah buddy we need way more Kevin “Fifi” Fiala up in this thread, all that animal does is rip shelfies buddy, " + \
                       "pops bottles pops pussies so keep your finger on that lamp light limpdick cause the forecast is goals. Fuck your cookie jar and your water bottles, " + \
                       "you better get quality rubbermaids bud cause she's gonna spend a lot of time hitting the fucking ice if Fifi has anything to say about it. " + \
                       "Blistering Wristers or fat clappers, this fuckin guy can't be stopped. If I had a choice of one attack to use to kill Hitler I would choose a " + \
                       "Kevin Fiala snipe from the top of the circle because you fucking know his evil dome would be bouncing off the end boards after that puck is loosed " + \
                       "like lightning from the blade of God's own CCM. I'd just pick up the phone and call Kevin Fiala at 1-800-TOP-TITS where he can be found earning his " + \
                       "living at the back of the goddamn net. The world record for a recorded sniper kill is 3,540m, but that's only because nobody has asked ya boi Fifi to " + \
                       "rip any wristers at ISIS yet. If i had three wishes, the first would be to live forever, the second would be for Kevin Fiala to live forever, " + \
                       "and the third would be for a trillion dollars so I could pay to watch ol Fifi Score top cheddar magic for all eternity.")

    @commands.command(name="laine")
    @commands.cooldown(1, 60.0, commands.BucketType.guild) # 1 use per minute per guild
    @is_OTH_guild()
    async def laine(self, ctx):
        await ctx.send("Yeah, fuck off buddy we absolutely need more Laine clips. Fuckin every time this kid steps on the ice someone scores. " + \
                       "kids fuckin dirt nasty man. Does fuckin ovi have 14 goals this season I dont fuckin think so bud. I'm fuckin tellin ya Patrik 'golden flow' " + \
                       "Laine is pottin 50 in '17 fuckin callin it right now. Clap bombs, fuck moms, wheel, snipe, and fuckin celly boys fuck")

    @commands.command(name="xfactor", aliases=["groodles"])
    @commands.cooldown(1, 60.0, commands.BucketType.guild) # 1 use per minute per guild
    @is_OTH_guild()
    async def xfactor(self, ctx):
        await ctx.send("I have studied tapes of him and I must disagree. While he is highly skilled, he does not have 'it' if you know what I mean. " + \
                       "That 'x-factor'. The 'above and beyond' trait.")

    @commands.command(name="petey")
    @commands.cooldown(1, 60.0, commands.BucketType.guild) # 1 use per minute per guild
    @is_OTH_guild()
    async def petey(self, ctx):
        await ctx.send("Kid might look like if Malfoy was a Hufflepuff but he plays like if Potter was a Slytherin the kids absolutely fucking nasty. " + \
                        "If there was a fourth unforgiveable curse it would be called petterssaucious or some shit because this kids dishes are absolutely team killing, " + \
                        "SHL, AHL, NHL it doesn't fucking matter 100 points to Pettersson because he's winning the House Cup, The Calder Cup, " + \
                        "The Stanley Cup and whatever fucking cup is in Sweden. Game Over.")

    @commands.command(name="mcavoy")
    @commands.cooldown(1, 60.0, commands.BucketType.guild) # 1 use per minute per guild
    @is_OTH_guild()
    async def mcavoy(self, ctx):
        await ctx.send("WTF you say he hasn’t done anything notable he only the best baddest defenseman you ever seen. " + \
                       "Now that Krug is out of the way he is going to tear it up and show that top tier fantasy D man you all wish you could have drafted. " + \
                        "Big brains got in the ground floor while you’ll have to overpay next year admitting your wrongs as you wallow in self pity " + \
                        "from your relegation only asking yourself why, why didn’t I draft McAvoy")

    @commands.command(name="bryz")
    @commands.cooldown(1, 60.0, commands.BucketType.guild) # 1 use per minute per guild
    @is_OTH_guild()
    async def bryz(self, ctx):
        await ctx.send("http://2.bp.blogspot.com/-ut7bwg8rrp8/UCFRrZinwVI/AAAAAAAACNw/M6LRPCMuUtg/s1600/its-only-game.gif")

    @commands.command(name="price")
    @commands.cooldown(1, 60.0, commands.BucketType.guild) # 1 use per minute per guild
    @is_OTH_guild()
    async def price(self, ctx):
        await ctx.send("Carey Price has a $10.5 million cap hit through 2025-26.")

    @commands.command(name="bob", aliases=["bobrovsky"])
    @commands.cooldown(1, 60.0, commands.BucketType.guild) # 1 use per minute per guild
    @is_OTH_guild()
    async def bob(self, ctx):
        await ctx.send("Sergei Bobrovsky has a $10 million cap hit through 2025-26.")

    @commands.command(name="ned")
    @commands.cooldown(1, 60.0, commands.BucketType.guild) # 1 use per minute per guild
    @is_OTH_guild()
    async def ned(self, ctx):
        await ctx.send("That's no surprise. He's on the third axis of transcendence right now. Alex Nedeljkovic moves in anti-planar reality " + \
                       "(or prime-planar reality, shouts to my qmech nerds who really buy Frisch-Hayes.) While goalies like Thomas Greiss or Andrei Vasilevskiy " + \
                       "see the game from an x and o perspective, Alex has vision of the omega and delta factors surrounding any given hockey event. " + \
                       "There's a reason Alex was able to lead Martin Necas to the 2019 Calder Cup. Put simply, Nedeljkovic is visuospatial jazz. " + \
                       "Think of Ornette Coleman or Buddy Rich, not Henrik Lundqvist or Tuukka Rask. The dorian stylings of a Eric Dolphy better describe Ned's game " + \
                       "than a monotone listing-off of conventional goalie skills. Puck handles? When you're in constant tune with the precise Hz pitch of the ice like Nedeljkovic, " + \
                       "English words like 'good save' cannot encapsulate even a fractoid of the scientific and metaphysical majesty of Alex.")

    @commands.command(name="dahlin")
    @commands.cooldown(1, 60.0, commands.BucketType.guild) # 1 use per minute per guild
    @is_OTH_guild()
    async def dahlin(self, ctx):
        await ctx.send("https://i.imgur.com/Nsf5hkz.mp4")

    @commands.command(name="cat", aliases=["debrincat"])
    @commands.cooldown(1, 60.0, commands.BucketType.user) # 1 use per minute per user
    @is_OTH_guild()
    async def cat(self, ctx):
        await ctx.send("https://images-ext-1.discordapp.net/external/jqBbbyFVQk10FI3TZlQS1GV2LNg8COT2TLw-9ckFqWM/https/media.discordapp.net/attachments/507616755510673409/744726226786320454/3x.gif")

    @commands.command(name="darn", aliases=["bruce", "gabby", "brucedarn"])
    @commands.cooldown(1, 60.0, commands.BucketType.user) # 1 use per minute per user
    @is_OTH_guild()
    async def darn(self, ctx):
        await ctx.send("https://media1.tenor.com/images/192264256befe5ba70487b0d60ee7832/tenor.gif")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == MINNE_USER_ID and " wes " in (message.content + " ").lower().replace(".", " "):
            await message.channel.send("<@" + str(MINNE_USER_ID) + "> watch your mouth. Just cuz you tell me to do something doesn't " + \
                                       "mean I'm going to do it. Being a keyboard tough guy making smart ass remarks doesn't " + \
                                       "make you funny or clever, just a coward hiding behind a computer")

def setup(bot):
    bot.add_cog(Memes(bot))
