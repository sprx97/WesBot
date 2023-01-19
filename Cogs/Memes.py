# Python includes
import random

# Local Includes
from Shared import *

class Memes(WesCog):
    def __init__(self, bot):
        super().__init__(bot)

    memes_group = app_commands.Group(name="memes", description="Mmmmm fresh pasta.")

    @memes_group.command(name="bryz")
    @app_commands.checks.cooldown(1, 60.0)
    async def bryz(self, interaction: discord.Interaction):
        await interaction.response.send_message("http://2.bp.blogspot.com/-ut7bwg8rrp8/UCFRrZinwVI/AAAAAAAACNw/M6LRPCMuUtg/s1600/its-only-game.gif")

    @memes_group.command(name="cat")
    @app_commands.checks.cooldown(1, 60.0)
    async def cat(self, interaction: discord.Interaction):
        await interaction.response.send_message("https://images-ext-1.discordapp.net/external/jqBbbyFVQk10FI3TZlQS1GV2LNg8COT2TLw-9ckFqWM/https/media.discordapp.net/attachments/507616755510673409/744726226786320454/3x.gif")

    @memes_group.command(name="dahlin")
    @app_commands.checks.cooldown(1, 60.0)
    async def dahlin(self, interaction: discord.Interaction):
        await interaction.response.send_message("https://i.imgur.com/Nsf5hkz.mp4")

    @memes_group.command(name="darn")
    @app_commands.checks.cooldown(1, 60.0)
    async def darn(self, interaction: discord.Interaction):
        darns = ["https://media1.tenor.com/images/192264256befe5ba70487b0d60ee7832/tenor.gif", "https://i.redd.it/wdhnfsxdl3v91.gif", "https://media.discordapp.net/attachments/489882482838077451/1062867025787113542/ezgif-3-93e35eb357.gif"]
        await interaction.response.send_message(random.choice(darns))

    @memes_group.command(name="fifi")
    @app_commands.checks.cooldown(1, 60.0)
    async def fifi(self, interaction: discord.Interaction):
        await interaction.response.send_message("Aw yeah buddy we need way more Kevin “Fifi” Fiala up in this thread, all that animal does is rip shelfies buddy, " + \
                    "pops bottles pops pussies so keep your finger on that lamp light limpdick cause the forecast is goals. Fuck your cookie jar and your water bottles, " + \
                    "you better get quality rubbermaids bud cause she's gonna spend a lot of time hitting the fucking ice if Fifi has anything to say about it. " + \
                    "Blistering Wristers or fat clappers, this fuckin guy can't be stopped. If I had a choice of one attack to use to kill Hitler I would choose a " + \
                    "Kevin Fiala snipe from the top of the circle because you fucking know his evil dome would be bouncing off the end boards after that puck is loosed " + \
                    "like lightning from the blade of God's own CCM. I'd just pick up the phone and call Kevin Fiala at 1-800-TOP-TITS where he can be found earning his " + \
                    "living at the back of the goddamn net. The world record for a recorded sniper kill is 3,540m, but that's only because nobody has asked ya boi Fifi to " + \
                    "rip any wristers at ISIS yet. If i had three wishes, the first would be to live forever, the second would be for Kevin Fiala to live forever, " + \
                    "and the third would be for a trillion dollars so I could pay to watch ol Fifi Score top cheddar magic for all eternity.")

    @memes_group.command(name="fuck")
    @app_commands.checks.cooldown(1, 60.0)
    async def fuck(self, interaction: discord.Interaction):
        await interaction.response.send_message("Bruce Boudreau would not approve of such language. Please try `memes darn` instead.")

    @memes_group.command(name="laine")
    @app_commands.checks.cooldown(1, 60.0)
    async def laine(self, interaction: discord.Interaction):
        await interaction.response.send_message("Yeah, fuck off buddy we absolutely need more Laine clips. Fuckin every time this kid steps on the ice someone scores. " + \
                        "kids fuckin dirt nasty man. Does fuckin ovi have 14 goals this season I dont fuckin think so bud. I'm fuckin tellin ya Patrik 'golden flow' " + \
                        "Laine is pottin 50 in '17 fuckin callin it right now. Clap bombs, fuck moms, wheel, snipe, and fuckin celly boys fuck")

    @memes_group.command(name="mcavoy")
    @app_commands.checks.cooldown(1, 60.0)
    async def mcavoy(self, interaction: discord.Interaction):
        await interaction.response.send_message("WTF you say he hasn’t done anything notable he only the best baddest defenseman you ever seen. " + \
                       "Now that Krug is out of the way he is going to tear it up and show that top tier fantasy D man you all wish you could have drafted. " + \
                        "Big brains got in the ground floor while you’ll have to overpay next year admitting your wrongs as you wallow in self pity " + \
                        "from your relegation only asking yourself why, why didn’t I draft McAvoy")

    @memes_group.command(name="ned")
    @app_commands.checks.cooldown(1, 60.0)
    async def ned(self, interaction: discord.Interaction):
        await interaction.response.send_message("That's no surprise. He's on the third axis of transcendence right now. Alex Nedeljkovic moves in anti-planar reality " + \
                       "(or prime-planar reality, shouts to my qmech nerds who really buy Frisch-Hayes.) While goalies like Thomas Greiss or Andrei Vasilevskiy " + \
                       "see the game from an x and o perspective, Alex has vision of the omega and delta factors surrounding any given hockey event. " + \
                       "There's a reason Alex was able to lead Martin Necas to the 2019 Calder Cup. Put simply, Nedeljkovic is visuospatial jazz. " + \
                       "Think of Ornette Coleman or Buddy Rich, not Henrik Lundqvist or Tuukka Rask. The dorian stylings of a Eric Dolphy better describe Ned's game " + \
                       "than a monotone listing-off of conventional goalie skills. Puck handles? When you're in constant tune with the precise Hz pitch of the ice like Nedeljkovic, " + \
                       "English words like 'good save' cannot encapsulate even a fractoid of the scientific and metaphysical majesty of Alex.")

    @memes_group.command(name="pathetic")
    @app_commands.checks.cooldown(1, 60.0)
    async def pathetic(self, interaction: discord.Interaction, user: discord.Member):
        if user == None:
            user = interaction.user
        await interaction.response.send_message(f"I don’t know what’s more pathetic <@{user.id}>, that you actually took the time out of your afternoon to do this, " + \
                        " or that you waited several minutes after the conversation and it still bothers you enough to provoke you to do this")

    @memes_group.command(name="petey")
    @app_commands.checks.cooldown(1, 60.0)
    async def petey(self, interaction: discord.Interaction):
        await interaction.response.send_message("Kid might look like if Malfoy was a Hufflepuff but he plays like if Potter was a Slytherin the kids absolutely fucking nasty. " + \
                        "If there was a fourth unforgiveable curse it would be called petterssaucious or some shit because this kids dishes are absolutely team killing, " + \
                        "SHL, AHL, NHL it doesn't fucking matter 100 points to Pettersson because he's winning the House Cup, The Calder Cup, " + \
                        "The Stanley Cup and whatever fucking cup is in Sweden. Game Over.")

    @memes_group.command(name="price")
    @app_commands.checks.cooldown(1, 60.0)
    async def price(self, interaction: discord.Interaction):
        await interaction.response.send_message("Carey Price has a $10.5 million cap hit through 2025-26. The Price is WRONG, Bob Barker.")

    @memes_group.command(name="toughguy")
    @app_commands.checks.cooldown(1, 60.0)
    async def toughguy(self, interaction: discord.Interaction, user: discord.Member):
        if user == None:
            user = interaction.user
        await interaction.response.send_message(f"<@{user.id}> watch your mouth. Just cuz you tell me to do something doesn't " + \
                                    "mean I'm going to do it. Being a keyboard tough guy making smart ass remarks doesn't " + \
                                    "make you funny or clever, just a coward hiding behind a computer")

    @memes_group.command(name="tuukka")
    @app_commands.checks.cooldown(1, 60.0)
    async def tuukka(self, interaction: discord.Interaction):
        await interaction.response.send_message("https://media.discordapp.net/attachments/507616755510673409/933173217781219338/unknown.gif")

    @memes_group.command(name="xfactor")
    @app_commands.checks.cooldown(1, 60.0)
    async def xfactor(self, interaction: discord.Interaction):
        await interaction.response.send_message("I have studied tapes of him and I must disagree. While he is highly skilled, he does not have 'it' if you know what I mean. " + \
                       "That 'x-factor'. The 'above and beyond' trait.")

    @bryz.error
    @cat.error
    @dahlin.error
    @darn.error
    @fifi.error
    @fuck.error
    @laine.error
    @mcavoy.error
    @ned.error
    @petey.error
    @price.error
    @toughguy.error
    @tuukka.error
    @xfactor.error
    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"Command on cooldown. Try in {error.retry_after} seconds.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Memes(bot), guild=discord.Object(id=OTH_GUILD_ID))
