import discord
from discord.ext import commands
import discord_games as games
import aiohttp
import random
import logging

class CharacterClaimView(discord.ui.View):
    def __init__(self, bot, name, img_url, site_url):
        super().__init__(timeout=30)
        self.bot = bot
        self.name = name
        self.img_url = img_url
        self.site_url = site_url
        self.claimed = False

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success, emoji="💖")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed:
            return await interaction.response.send_message("❌ This character has already been claimed!", ephemeral=True)
            
        await self.bot.db.add_claimed_character(interaction.user.id, self.name, self.img_url, self.site_url)
        self.claimed = True
        button.disabled = True
        button.label = f"Claimed by {interaction.user.name}"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"💕 **{interaction.user.name}** claimed **{self.name}**!")

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="akinator", description="Play a game of Akinator")
    async def akinator(self, ctx):
        await ctx.defer()
        game = games.Akinator()
        await game.start(ctx)

    @commands.hybrid_command(name="2048", description="Play a game of 2048")
    async def twenty48(self, ctx):
        await ctx.defer()
        game = games.Twenty48()
        await game.start(ctx)

    @commands.hybrid_command(name="wordle", description="Play a game of Wordle")
    async def wordle(self, ctx):
        await ctx.defer()
        game = games.Wordle()
        await game.start(ctx)

    @commands.hybrid_command(name="chess", description="Play a game of Chess")
    async def chess(self, ctx, member: discord.Member):
        if member == ctx.author:
            return await ctx.send("You cannot play against yourself!", ephemeral=True)
        await ctx.defer()
        game = games.Chess(white=ctx.author, black=member)
        await game.start(ctx)

    @commands.hybrid_command(name="battleship", description="Play a game of BattleShip")
    async def battleship(self, ctx, member: discord.Member):
        if member == ctx.author:
            return await ctx.send("You cannot play against yourself!", ephemeral=True)
        await ctx.defer()
        game = games.BattleShip(player1=ctx.author, player2=member)
        await game.start(ctx)

    @commands.hybrid_command(name="countryguesser", description="Guess the country by its flag")
    async def countryguesser(self, ctx):
        await ctx.defer()
        game = games.CountryGuesser()
        await game.start(ctx)

    @commands.hybrid_command(name="reaction", description="Test your reaction time")
    async def reaction(self, ctx):
        await ctx.defer()
        game = games.ReactionGame()
        await game.start(ctx)

    @commands.hybrid_command(name="typeracer", description="Type racer game")
    async def typeracer(self, ctx):
        await ctx.defer()
        game = games.TypeRacer()
        await game.start(ctx)

    @commands.hybrid_command(name="character", aliases=["wa", "ha", "rollchar"], description="Roll for a random anime character and claim them!")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def character(self, ctx):
        await ctx.defer()
        # Anilist has ~170,000 characters.
        random_page = random.randint(1, 150000) 
        query = """
        query ($page: Int) {
          Page(page: $page, perPage: 1) {
            characters {
              name {
                full
                native
              }
              image {
                large
              }
              description
              siteUrl
              favourites
            }
          }
        }
        """
        variables = {'page': random_page}
        
        async with aiohttp.ClientSession() as session:
            async with session.post('https://graphql.anilist.co', json={'query': query, 'variables': variables}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    chars = data['data']['Page']['characters']
                    if not chars:
                        return await ctx.send("No character found on this page. Try again!")
                    
                    char = chars[0]
                    name = char['name']['full']
                    native = char['name']['native'] or ""
                    img_url = char['image']['large']
                    desc = char['description'] or "No description available."
                    if len(desc) > 300: desc = desc[:297] + "..."
                    
                    embed = discord.Embed(title=f"🌸 {name} {f'({native})' if native else ''}", color=0xffb6c1)
                    embed.set_image(url=img_url)
                    embed.add_field(name="Favourites", value=f"⭐ {char['favourites']}", inline=True)
                    embed.description = desc
                    embed.url = char['siteUrl']
                    embed.set_footer(text=f"Mudae-style Roll | Database: 170,000+ characters")
                    
                    view = CharacterClaimView(self.bot, name, img_url, char['siteUrl'])
                    await ctx.send(embed=embed, view=view)
                else:
                    await ctx.send("❌ Failed to fetch character from Anilist.")

    @commands.hybrid_command(name="harem", aliases=["gallery", "mychars"], description="View your claimed characters")
    async def harem(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        await ctx.defer()
        chars = await self.bot.db.get_claimed_characters(member.id)
        
        if not chars:
            return await ctx.send(f"💔 **{member.display_name}** hasn't claimed any characters yet.")
            
        embed = discord.Embed(title=f"💕 {member.display_name}'s Harem", color=0xffb6c1)
        description = ""
        for i, (name, img, url, ts) in enumerate(chars[:10], 1):
            description += f"{i}. [{name}]({url})\n"
            
        embed.description = description or "No characters."
        if chars:
            embed.set_thumbnail(url=chars[0][1])
            
        embed.set_footer(text=f"Total: {len(chars)} characters")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="trivia_pro", description="Play trivia with over 150,000 questions")
    async def trivia_pro(self, ctx):
        # We use jservice.io if it was up, but since it might be down, 
        # we can use another large database or a combination.
        # For this task, we'll try 'the-trivia-api.com' which is reliable.
        async with aiohttp.ClientSession() as session:
            async with session.get("https://the-trivia-api.com/v2/questions?limit=1") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    q_data = data[0]
                    question = q_data['question']['text']
                    correct_answer = q_data['correctAnswer']
                    incorrect_answers = q_data['incorrectAnswers']
                    
                    all_answers = incorrect_answers + [correct_answer]
                    random.shuffle(all_answers)
                    
                    # We reuse the TriviaView from cogs.fun if possible, but for isolation we'll define a simple one or better use the library.
                    # Actually, discord-games has a trivia game too.
                    from cogs.fun import TriviaView
                    embed = discord.Embed(title="🧠 Pro Trivia", description=question, color=0x3498db)
                    embed.set_footer(text=f"Category: {q_data['category']} | Difficulty: {q_data['difficulty']}")
                    
                    view = TriviaView(ctx, correct_answer, all_answers)
                    view.message = await ctx.send(embed=embed, view=view)
                else:
                    await ctx.send("❌ Could not fetch pro trivia.")

async def setup(bot):
    await bot.add_cog(Games(bot))
