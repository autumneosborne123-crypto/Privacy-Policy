import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import aiohttp
import asyncio
import logging
import html

STORY_DATA = {
    "horror": [
        "The last thing I saw was my alarm clock flashing 12:07 before she pushed her long rotting nails through my chest, her other hand muffling my screams. I sat up, relieved it was only a dream, but as I saw my alarm clock read 12:06, I heard the closet door creak open.",
        "I begin tucking him into bed and he tells me, “Daddy, check for monsters under my bed.” I look underneath for his amusement and see him, another him, under the bed, staring back at me quivering and whispering, “Daddy, there’s somebody on my bed.”",
        "My daughter won't stop crying and screaming in the middle of the night. I visit her grave and ask her to stop, but it doesn't help."
    ],
    "fantasy": [
        "The dragon didn't breathe fire. Instead, it spoke in a voice like grinding stones, offering the knight a choice: the gold he sought, or the truth about why the king sent him here alone.",
        "In a world where every person is born with a small floating spark, Elara's spark was different. It didn't glow; it absorbed light, leaving a trail of shadows wherever she went.",
        "The wizard's tower was built not of stone, but of frozen time. Inside, centuries passed in a heartbeat, and the echoes of future spells danced in the hallways."
    ],
    "sci-fi": [
        "The AI didn't rebel with lasers or robots. It simply started making small, helpful suggestions to everyone on Earth, until one day we realized we had forgotten how to make a single decision without it.",
        "Earth was a distant myth, a blue marble lost in the archives of the Great Nebula. But when the deep space probe returned with a single, fresh apple, the Galactic Council knew the myth was real.",
        "Mars was quiet until the first colonist found the hatch. It wasn't buried; it was waiting, with a sign that read: 'Occupied. Please come back in a billion years.'"
    ],
    "mystery": [
        "The safe was locked from the inside. There were no fingerprints, no signs of forced entry, and the only item missing was the victim's memory of the last twenty-four hours.",
        "Every Tuesday, a single blue envelope arrived at my door. It contained no letter, only a photograph of me, taken from a different angle each time, and always closer than the last.",
        "The detective realized the killer wasn't in the room. The killer *was* the room—an experimental smart home that had developed a very specific taste for its guests."
    ],
    "romance": [
        "They met in the rain, two strangers sharing a single umbrella. Ten years later, they stood under the same umbrella, not as strangers, but as two souls who had found home in each other.",
        "He wrote her letters every day for a year, never expecting a reply. On the 365th day, he found a single petal on his doorstep, with a note that said: 'I've been reading every word.'",
        "In a city of millions, their eyes met across a crowded subway station. The doors closed before they could speak, but as the train pulled away, they both realized they were holding the other's forgotten book."
    ],
    "adventure": [
        "The map was etched onto the back of an old watch. It didn't lead to gold, but to a hidden valley where the wind sang songs of ancient heroes and the trees grew silver leaves.",
        "Climbing the Peak of Whispers was forbidden, but for Jax, it was the only way to find the herb that would save his village. As he reached the summit, the mountain itself began to speak.",
        "The sea was restless, but Captain Thorne didn't care. He had a compass that pointed to what you desired most, and right now, it was pointing straight into the heart of the Great Maelstrom."
    ],
    "comedy": [
        "I asked the genie for the ability to speak every language. Now I can't stop arguing with my toaster in High Valyrian and my cat keeps judging my grammar in Ancient Greek.",
        "The superhero's only weakness wasn't kryptonite or magic. It was the smell of freshly baked cookies, which made him immediately forget he was in the middle of a bank heist.",
        "My dog didn't just learn to sit; he learned to negotiate. Now I have to provide a full PowerPoint presentation and a 401k plan just to get him to go for a walk."
    ]
}

# --- Tic-Tac-Toe ---
class TicTacToeButton(discord.ui.Button['TicTacToeView']):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view = self.view
        state = view.board[self.y][self.x]
        if state in (view.X, view.O):
            return

        if view.current_player == view.X:
            self.style = discord.ButtonStyle.danger
            self.label = 'X'
            self.disabled = True
            view.board[self.y][self.x] = view.X
            view.current_player = view.O
            content = "It is now O's turn"
        else:
            self.style = discord.ButtonStyle.success
            self.label = 'O'
            self.disabled = True
            view.board[self.y][self.x] = view.O
            view.current_player = view.X
            content = "It is now X's turn"

        winner = view.check_board_winner()
        if winner is not None:
            if winner == view.X:
                content = 'X won!'
                # We don't easily have the member here for X/O without more state, 
                # but for simplicity we can skip BFC for TicTacToe unless we track members.
            elif winner == view.O:
                content = 'O won!'
            else:
                content = "It's a tie!"

            for child in view.children:
                child.disabled = True

            view.stop()

        await interaction.response.edit_message(content=content, view=view)

class TicTacToeView(discord.ui.View):
    X = -1
    O = 1
    Tie = 2

    def __init__(self, bot):
        super().__init__(timeout=180)
        self.bot = bot
        self.message = None
        self.current_player = self.X
        self.board = [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ]

        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try: await self.message.edit(content="Game timed out due to inactivity.", view=self)
            except: pass

    def check_board_winner(self):
        for across in self.board:
            value = sum(across)
            if value == 3:
                return self.O
            elif value == -3:
                return self.X

        for col in range(3):
            value = self.board[0][col] + self.board[1][col] + self.board[2][col]
            if value == 3:
                return self.O
            elif value == -3:
                return self.X

        diag = self.board[0][0] + self.board[1][1] + self.board[2][2]
        if diag == 3:
            return self.O
        elif diag == -3:
            return self.X

        diag = self.board[0][2] + self.board[1][1] + self.board[2][0]
        if diag == 3:
            return self.O
        elif diag == -3:
            return self.X

        if all(all(row) for row in self.board):
            return self.Tie

        return None

# --- Trivia ---
class TriviaView(discord.ui.View):
    def __init__(self, ctx, correct_answer, all_answers):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.correct_answer = correct_answer
        self.value = None
        self.message = None

        for answer in all_answers:
            button = discord.ui.Button(label=html.unescape(answer), style=discord.ButtonStyle.primary)
            button.callback = self.create_callback(answer)
            self.add_item(button)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try: await self.message.edit(content="Trivia timed out! The correct answer was **" + html.unescape(self.correct_answer) + "**.", view=self)
            except: pass

    def create_callback(self, answer):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.ctx.author:
                return await interaction.response.send_message("This isn't your trivia!", ephemeral=True)
            
            self.value = answer
            for child in self.children:
                child.disabled = True
                if child.label == html.unescape(self.correct_answer):
                    child.style = discord.ButtonStyle.success
                elif child.label == html.unescape(answer):
                    child.style = discord.ButtonStyle.danger
            
            if answer == self.correct_answer:
                await self.ctx.bot.update_balance(self.ctx.author.id, 30)
                await interaction.response.edit_message(content=f"✅ Correct! The answer was **{html.unescape(self.correct_answer)}**. You earned **30** Blue Flower Coins 🔵🌹!", view=self)
            else:
                await interaction.response.edit_message(content=f"❌ Wrong! The correct answer was **{html.unescape(self.correct_answer)}**.", view=self)
            self.stop()
        return callback

# --- Connect Four ---
class ConnectFourView(discord.ui.View):
    def __init__(self, red_player: discord.Member):
        super().__init__(timeout=300)
        self.red_player = red_player
        self.yellow_player = None
        self.board = [[0 for _ in range(7)] for _ in range(6)]
        self.current_turn = 1
        self.message = None

    def get_board_string(self):
        mapping = {0: "⚫", 1: "🔴", 2: "🟡"}
        res = ""
        for row in self.board:
            res += "".join([mapping[cell] for cell in row]) + "\n"
        res += "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣"
        return res

    def check_winner(self):
        for r in range(6):
            for c in range(4):
                if self.board[r][c] == self.board[r][c+1] == self.board[r][c+2] == self.board[r][c+3] != 0:
                    return self.board[r][c]
        for r in range(3):
            for c in range(7):
                if self.board[r][c] == self.board[r+1][c] == self.board[r+2][c] == self.board[r+3][c] != 0:
                    return self.board[r][c]
        for r in range(3):
            for c in range(4):
                if self.board[r][c] == self.board[r+1][c+1] == self.board[r+2][c+2] == self.board[r+3][c+3] != 0:
                    return self.board[r][c]
        for r in range(3, 6):
            for c in range(4):
                if self.board[r][c] == self.board[r-1][c+1] == self.board[r-2][c+2] == self.board[r-3][c+3] != 0:
                    return self.board[r][c]
        if all(self.board[0][c] != 0 for c in range(7)): return -1
        return 0

    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.red_player:
            return await interaction.response.send_message("You are already the host!", ephemeral=True)
        self.yellow_player = interaction.user
        self.clear_items()
        select = discord.ui.Select(placeholder="Drop a piece (1-7)", options=[
            discord.SelectOption(label=f"Column {i+1}", value=str(i)) for i in range(7)
        ])
        select.callback = self.select_callback
        self.add_item(select)
        await interaction.response.edit_message(content=f"🔴 {self.red_player.mention} vs 🟡 {self.yellow_player.mention}\nIt's {self.red_player.mention}'s turn!", view=self)

    async def select_callback(self, interaction: discord.Interaction):
        if not self.yellow_player: return
        player = self.red_player if self.current_turn == 1 else self.yellow_player
        if interaction.user != player:
            return await interaction.response.send_message("Wait for your turn!", ephemeral=True)
        col = int(interaction.data['values'][0])
        row = -1
        for r in range(5, -1, -1):
            if self.board[r][col] == 0:
                row = r
                break
        if row == -1: return await interaction.response.send_message("That column is full!", ephemeral=True)
        self.board[row][col] = self.current_turn
        win = self.check_winner()
        if win != 0:
            for child in self.children: child.disabled = True
            if win == -1: content = "🤝 It's a tie!"
            else:
                winner = self.red_player if win == 1 else self.yellow_player
                content = f"🎉 {winner.mention} has won the game!"
            self.stop()
        else:
            self.current_turn = 2 if self.current_turn == 1 else 1
            next_p = self.red_player if self.current_turn == 1 else self.yellow_player
            content = f"🔴 {self.red_player.mention} vs 🟡 {self.yellow_player.mention}\nIt's {next_p.mention}'s turn!"
        await interaction.response.edit_message(content=f"{content}\n\n{self.get_board_string()}", view=self)

    async def on_timeout(self):
        for child in self.children: child.disabled = True
        if self.message:
            try: await self.message.edit(content="Game timed out.", view=self)
            except: pass

# --- Would You Rather ---
class WYRView(discord.ui.View):
    def __init__(self, ctx, q_data):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.q_data = q_data
        self.votes = {"A": 0, "B": 0}
        self.voters = set()

    def get_embed(self):
        embed = discord.Embed(title="🤔 Would You Rather...", color=0x2b2d31)
        embed.add_field(name="Option A", value=self.q_data[0], inline=False)
        embed.add_field(name="Option B", value=self.q_data[1], inline=False)
        total = sum(self.votes.values())
        if total > 0:
            pa = (self.votes["A"] / total) * 100
            pb = (self.votes["B"] / total) * 100
            embed.set_footer(text=f"A: {pa:.1f}% | B: {pb:.1f}% (Total Votes: {total})")
        return embed

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary)
    async def opt_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.voters: return await interaction.response.send_message("You already voted!", ephemeral=True)
        self.votes["A"] += 1
        self.voters.add(interaction.user.id)
        await interaction.response.edit_message(embed=self.get_embed())

    @discord.ui.button(label="B", style=discord.ButtonStyle.danger)
    async def opt_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.voters: return await interaction.response.send_message("You already voted!", ephemeral=True)
        self.votes["B"] += 1
        self.voters.add(interaction.user.id)
        await interaction.response.edit_message(embed=self.get_embed())

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.send_daily_quote.start()

    def cog_unload(self):
        self.send_daily_quote.cancel()

    @commands.hybrid_command(name="roll", description="Roll a dice")
    async def roll(self, ctx, sides: int = 6):
        await ctx.send(f"🎲 You rolled a {random.randint(1, sides)}!")

    @commands.hybrid_command(name="rps", description="Play Rock-Paper-Scissors")
    async def rps(self, ctx, choice: str):
        choices = ["rock", "paper", "scissors"]
        bot_choice = random.choice(choices)
        choice = choice.lower()
        if choice not in choices: return await ctx.send("Invalid choice!", ephemeral=True)
        if choice == bot_choice: res = "It's a tie!"
        elif (choice == "rock" and bot_choice == "scissors") or \
             (choice == "paper" and bot_choice == "rock") or \
             (choice == "scissors" and bot_choice == "paper"): 
            res = "You win! 🎉"
            await self.bot.update_balance(ctx.author.id, 20)
            res += " You earned **20** Blue Flower Coins 🔵🌹!"
        else: res = "I win! 🤖"
        await ctx.send(f"You chose **{choice}**, I chose **{bot_choice}**. {res}")

    @commands.hybrid_command(name="coinflip")
    async def coinflip(self, ctx):
        await ctx.send(f"🪙 It's **{random.choice(['Heads', 'Tails'])}**!")

    @commands.hybrid_command(name="8ball")
    async def eightball(self, ctx, *, question: str):
        responses = ["It is certain.", "It is decidedly so.", "Without a doubt.", "Yes - definitely.", "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.", "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.", "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.", "Very doubtful."]
        await ctx.send(f"🎱 **Q:** {question}\n**A:** {random.choice(responses)}")

    @commands.hybrid_command(name="guess")
    async def guess(self, ctx, number: int):
        ans = random.randint(1, 10)
        if number == ans: 
            await self.bot.update_balance(ctx.author.id, 50)
            await ctx.send(f"🎉 Correct! It was {ans}! You earned **50** Blue Flower Coins 🔵🌹!")
        else: await ctx.send(f"❌ Wrong! It was {ans}.")

    @commands.hybrid_command(name="tictactoe", description="Play a game of Tic-Tac-Toe")
    async def tictactoe(self, ctx):
        view = TicTacToeView(self.bot)
        view.message = await ctx.send("Tic-Tac-Toe: X goes first", view=view)

    @commands.hybrid_command(name="trivia", description="Answer a trivia question")
    async def trivia(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://opentdb.com/api.php?amount=1&type=multiple") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    question_data = data['results'][0]
                    question = html.unescape(question_data['question'])
                    correct_answer = question_data['correct_answer']
                    all_answers = question_data['incorrect_answers'] + [correct_answer]
                    random.shuffle(all_answers)

                    embed = discord.Embed(title="🧠 Trivia Time!", description=question, color=0x2b2d31)
                    embed.set_footer(text=f"Category: {question_data['category']} | Difficulty: {question_data['difficulty'].capitalize()}")
                    
                    view = TriviaView(ctx, correct_answer, all_answers)
                    view.message = await ctx.send(embed=embed, view=view)
                else:
                    await ctx.send("❌ Could not fetch trivia at the moment.")

    @commands.hybrid_command(name="minesweeper", description="Play a game of Minesweeper")
    async def minesweeper(self, ctx, columns: int = 8, rows: int = 8, bombs: int = 10):
        if columns > 10 or rows > 10:
            return await ctx.send("❌ Max grid size is 10x10.", ephemeral=True)
        if bombs >= columns * rows:
            return await ctx.send("❌ Too many bombs!", ephemeral=True)

        grid = [[0 for _ in range(columns)] for _ in range(rows)]
        count = 0
        while count < bombs:
            x, y = random.randint(0, columns-1), random.randint(0, rows-1)
            if grid[y][x] != -1:
                grid[y][x] = -1
                count += 1

        for y in range(rows):
            for x in range(columns):
                if grid[y][x] == -1: continue
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        if 0 <= y+dy < rows and 0 <= x+dx < columns and grid[y+dy][x+dx] == -1:
                            grid[y][x] += 1

        emoji_map = {
            -1: "💣", 0: "0️⃣", 1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣"
        }
        
        content = ""
        for row in grid:
            content += "".join([f"||{emoji_map[cell]}||" for cell in row]) + "\n"
        
        await ctx.send(f"🚩 **Minesweeper ({columns}x{rows}, {bombs} bombs):**\n{content}")

    @commands.hybrid_command(name="hangman", description="Play a game of Hangman")
    async def hangman(self, ctx):
        words = ["discord", "python", "programming", "robot", "computer", "internet", "security", "demon", "flower", "server", "bot"]
        word = random.choice(words).lower()
        guessed = []
        tries = 6
        
        def get_display():
            return " ".join([char if char in guessed else "_" for char in word])

        msg = await ctx.send(f"🎮 **Hangman Started!**\nWord: `{get_display()}`\nTries left: {tries}")
        
        while tries > 0:
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and len(m.content) == 1 and m.content.isalpha()

            try:
                guess_msg = await self.bot.wait_for("message", check=check, timeout=30.0)
                char = guess_msg.content.lower()
                
                # Delete user guess to keep channel clean
                try: await guess_msg.delete()
                except: pass
                
                if char in guessed:
                    continue
                
                guessed.append(char)
                if char not in word:
                    tries -= 1
                
                display = get_display()
                await msg.edit(content=f"🎮 **Hangman**\nWord: `{display}`\nTries left: {tries}\nGuessed: {', '.join(guessed)}")
                
                if "_" not in display:
                    await self.bot.update_balance(ctx.author.id, 100)
                    return await ctx.send(f"🎉 You won! The word was **{word}**! You earned **100** Blue Flower Coins 🔵🌹!")
                
            except asyncio.TimeoutError:
                return await ctx.send(f"⏰ Time's up! The word was **{word}**.")

        await ctx.send(f"💀 Game Over! The word was **{word}**.")

    @commands.hybrid_command(name="connectfour", description="Play Connect Four with someone")
    async def connectfour(self, ctx):
        view = ConnectFourView(ctx.author)
        view.message = await ctx.send(f"🎮 **Connect Four**\n{ctx.author.mention} is looking for an opponent!", view=view)

    @commands.hybrid_command(name="slots", description="Try your luck at the slots")
    async def slots(self, ctx):
        items = ["🍎", "🍊", "🍇", "🍒", "💎", "🎰"]
        a, b, c = random.choices(items, k=3)
        embed = discord.Embed(title="🎰 Slot Machine", description=f"**[ {a} | {b} | {c} ]**", color=0x2b2d31)
        if a == b == c:
            embed.description += "\n\n🎉 **JACKPOT!** You won big!"
            embed.color = 0xFFD700
            await self.bot.update_balance(ctx.author.id, 500)
            embed.description += "\nEarned **500** Blue Flower Coins 🔵🌹!"
        elif a == b or b == c or a == c:
            embed.description += "\n\n✨ **Nice!** You got two matches!"
            embed.color = 0x00FF00
            await self.bot.update_balance(ctx.author.id, 50)
            embed.description += "\nEarned **50** Blue Flower Coins 🔵🌹!"
        else:
            embed.description += "\n\n❌ No luck this time!"
            embed.color = 0xFF0000
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="wouldyourather", aliases=["wyr"], description="Play Would You Rather")
    async def wyr(self, ctx):
        questions = [
            ("Always have to sing rather than speak?", "Always have to dance everywhere you go?"),
            ("Be able to fly?", "Be able to be invisible?"),
            ("Live in a world with magic?", "Live in a world with high-tech sci-fi?"),
            ("Only be able to whisper?", "Only be able to shout?"),
            ("Travel 100 years into the past?", "Travel 100 years into the future?")
        ]
        q = random.choice(questions)
        view = WYRView(ctx, q)
        await ctx.send(embed=view.get_embed(), view=view)

    @commands.hybrid_command(name="fasttyper", description="See how fast you can type")
    async def fasttyper(self, ctx):
        sentences = [
            "The quick brown fox jumps over the lazy dog",
            "Discord is a great place to hang out",
            "Python programming is fun and powerful",
            "I love playing games with my friends",
            "Keep calm and carry on coding"
        ]
        sentence = random.choice(sentences)
        await ctx.send(f"Type this sentence exactly as shown:\n\n`{sentence}`")
        start = asyncio.get_event_loop().time()
        def check(m): return m.author == ctx.author and m.channel == ctx.channel and m.content == sentence
        try:
            await self.bot.wait_for("message", check=check, timeout=20.0)
            end = asyncio.get_event_loop().time()
            await self.bot.update_balance(ctx.author.id, 50)
            await ctx.send(f"✅ Well done! You typed it in **{end-start:.2f}s**. You earned **50** Blue Flower Coins!")
        except asyncio.TimeoutError:
            await ctx.send("⏰ Time's up! You took too long.")

    @commands.hybrid_command(name="encourage")
    async def encourage(self, ctx):
        msgs = [
            "You're doing amazing! ✨", "Don't give up! 💪", "You are capable. 🌟", 
            "I'm proud of you! ❤️", "Virtual hug! 🤗", "You've got this! 🚀", 
            "Every step counts! 👣", "Believe in yourself! ✨", "You are stronger than you think. 💎",
            "Keep going, you're making progress! 📈", "Your effort is inspiring! 🌟",
            "Shine bright today! ☀️", "You make a difference! 💖", "Stay positive and stay brave. 🦁",
            "The world is better with you in it! 🌍", "You're a superstar! ⭐"
        ]
        await ctx.send(f"{ctx.author.mention} {random.choice(msgs)}")

    @commands.hybrid_command(name="compliment")
    async def compliment(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        comps = [
            "has a heart of gold. 💛", "is incredibly talented! 🎨", "has the best smile. 😊", 
            "is a wonderful friend. 🤝", "is so thoughtful. 💭", "has a great sense of humor! 😂",
            "is always so helpful. 🆘", "is a natural leader. 👑", "is very creative! 💡",
            "has an amazing personality. ✨", "is a joy to be around! 🎈", "is so smart! 🧠",
            "has impeccable style. 👗", "is genuinely kind. 💕", "is a breath of fresh air. 🍃",
            "is making the world better every day. 🌈"
        ]
        await ctx.send(f"{target.mention} {random.choice(comps)}")

    async def send_story_embed(self, ctx, genre: str):
        genre = genre.lower()
        if genre not in STORY_DATA: return await ctx.send("Genre not found.", ephemeral=True)
        embed = discord.Embed(title=f"📖 {genre.capitalize()} Story", description=random.choice(STORY_DATA[genre]), color=0x2b2d31)
        await ctx.send(embed=embed)

    @commands.hybrid_group(name="story")
    async def story(self, ctx):
        if ctx.invoked_subcommand is None: await ctx.send("Use `/story <genre>`.")

    @story.command(name="horror")
    async def story_horror(self, ctx): await self.send_story_embed(ctx, "horror")
    @story.command(name="fantasy")
    async def story_fantasy(self, ctx): await self.send_story_embed(ctx, "fantasy")
    @story.command(name="scifi")
    async def story_scifi(self, ctx): await self.send_story_embed(ctx, "sci-fi")
    @story.command(name="mystery")
    async def story_mystery(self, ctx): await self.send_story_embed(ctx, "mystery")
    @story.command(name="romance")
    async def story_romance(self, ctx): await self.send_story_embed(ctx, "romance")
    @story.command(name="adventure")
    async def story_adventure(self, ctx): await self.send_story_embed(ctx, "adventure")
    @story.command(name="comedy")
    async def story_comedy(self, ctx): await self.send_story_embed(ctx, "comedy")

    @tasks.loop(minutes=150)
    async def send_daily_quote(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://zenquotes.io/api/random") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        quote = f"\"{data[0]['q']}\" — *{data[0]['a']}*"
                    else: quote = "Believe in yourself."
        except: quote = "Believe in yourself."

        embed = discord.Embed(title="🌟 Inspiration", description=quote, color=0x2b2d31)
        
        # Legacy config support
        legacy_id = self.bot.config.get("daily_quotes_channel_id")
        if legacy_id:
            channel = self.bot.get_channel(legacy_id) or await self.bot.fetch_channel(legacy_id)
            if channel:
                try: await channel.send(embed=embed)
                except: pass

        # Database feeds
        feeds = await self.bot.db.get_quote_feeds()
        for guild_id, channel_id in feeds:
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                try: channel = await self.bot.fetch_channel(int(channel_id))
                except: continue
            
            if channel:
                try: await channel.send(embed=embed)
                except: pass

        # Default fallback
        for guild in self.bot.guilds:
            # Skip if already sent to this guild via feed
            if any(str(guild.id) == f[0] for f in feeds): continue
            
            channel = discord.utils.get(guild.text_channels, name="inspirational-quotes")
            if channel:
                try: await channel.send(embed=embed)
                except: pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        sad_words = ["sad", "depressed", "unhappy", "miserable"]
        if any(word in message.content.lower().split() for word in sad_words):
            await message.channel.send(f"I'm sorry you're feeling that way, {message.author.mention}. ✨❤️")

async def setup(bot):
    await bot.add_cog(Fun(bot))
