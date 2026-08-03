import discord
from discord.ext import commands
import random
import time
import asyncio

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.shop_items = {
            "petal": {"name": "Flower Petal", "price": 100, "description": "A common petal used for basic crafting or trading.", "rank": "Common"},
            "super_petal": {"name": "Super Flower Petal", "price": 500, "description": "A rare petal with glowing properties.", "rank": "Rare"},
            "golden_flower": {"name": "Golden Flower", "price": 2000, "description": "A legendary flower that shines brightly.", "rank": "Legendary"},
            "bait": {"name": "Bait", "price": 50, "description": "Used to catch basic animals.", "rank": "Common"},
            "ultra_bait": {"name": "Ultra Bait", "price": 250, "description": "Significantly increases the chance of catching rare animals.", "rank": "Rare"},
            "medicine": {"name": "Medicine", "price": 100, "description": "Restores 50 HP to an animal.", "rank": "Common"},
            "wooden_sword": {"name": "Wooden Sword", "price": 150, "description": "A basic weapon for beginners.", "rank": "Common"},
            "iron_sword": {"name": "Iron Sword", "price": 600, "description": "A sturdy weapon for serious adventurers.", "rank": "Uncommon"},
            "excalibur": {"name": "Excalibur", "price": 5000, "description": "A mythical sword of great power.", "rank": "Legendary"},
            "apple": {"name": "Apple", "price": 20, "description": "A simple fruit that restores a bit of energy.", "rank": "Common"},
            "honey_cake": {"name": "Honey Cake", "price": 150, "description": "A delicious treat that animals love.", "rank": "Rare"},
            "super_bait": {"name": "Super Bait", "price": 150, "description": "A better bait for catching Uncommon animals.", "rank": "Uncommon"},
            "revive": {"name": "Revive", "price": 500, "description": "Fully restores a fainted animal to life.", "rank": "Rare"},
            "protein_shake": {"name": "Protein Shake", "price": 800, "description": "Permanently increases an animal's Attack by 3.", "rank": "Rare"},
            "iron_shield": {"name": "Iron Shield", "price": 800, "description": "Permanently increases an animal's Defense by 3.", "rank": "Rare"},
            "mystic_petal": {"name": "Mystic Flower Petal", "price": 1000, "description": "A magical petal available only to Premium members. Used for legendary crafting.", "rank": "Epic", "premium_only": True}
        }

    @commands.hybrid_command(name="balance", aliases=["bal"], description="Check your Rose Coins balance")
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        coins = await self.db.get_balance(member.id)
        embed = discord.Embed(title=f"<:rose_coin:1533598631612125397> {member.display_name}'s Balance", description=f"You have **{coins}** Rose Coins (RC) <:rose_coin:1533598631612125397>.", color=0x3498db)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="daily", description="Claim your daily Rose Coins")
    async def daily(self, ctx):
        await ctx.defer()
        data = await self.db.get_economy_data(ctx.author.id)
        last_daily = data['last_daily']
        current_time = time.time()
        
        if current_time - last_daily < 86400:
            remaining = 86400 - (current_time - last_daily)
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            msg = f"⏳ You've already claimed your daily reward. Try again in **{hours}h {minutes}m**."
            if not await self.db.is_user_premium(ctx.author.id):
                msg += "\n💡 *Tip: Premium members ($5.00/mo) get 2x Daily Coins!*"
            return await ctx.send(msg, ephemeral=True)
        
        amount = random.randint(200, 500)
        is_premium = await self.db.is_user_premium(ctx.author.id)
        if is_premium:
            amount *= 2
        
        await self.bot.update_balance(ctx.author.id, amount)
        await self.db.update_economy_cooldown(ctx.author.id, "daily", current_time)
        
        msg = f"🎁 You claimed your daily reward and received **{amount}** Rose Coins <:rose_coin:1533598631612125397>!"
        if is_premium:
            msg += " (2x Premium Multiplier applied! ✨)"
        await ctx.send(msg)

    @commands.hybrid_command(name="pay", description="Pay Rose Coins to another user")
    async def pay(self, ctx, member: discord.Member, amount: int):
        await ctx.defer()
        if amount <= 0:
            return await ctx.send("❌ Amount must be positive.", ephemeral=True)
        if member == ctx.author:
            return await ctx.send("❌ You cannot pay yourself.", ephemeral=True)
        
        balance = await self.db.get_balance(ctx.author.id)
        if balance < amount:
            return await ctx.send("❌ You don't have enough Rose Coins.", ephemeral=True)
        
        await self.bot.update_balance(ctx.author.id, -amount)
        await self.bot.update_balance(member.id, amount)
        
        await ctx.send(f"✅ You paid **{amount}** RC to {member.mention}.")
        await self.bot.log_action(ctx.guild, "RC Transfer", f"**{ctx.author}** paid **{amount}** RC to **{member}**.", color=0x3498db, moderator=ctx.author, user=member)

    @commands.hybrid_command(name="rob", description="Attempt to rob Rose Coins from another user")
    async def rob(self, ctx, member: discord.Member):
        await ctx.defer()
        if member == ctx.author:
            return await ctx.send("❌ You cannot rob yourself.", ephemeral=True)
        
        data = await self.db.get_economy_data(ctx.author.id)
        last_rob = data['last_rob']
        is_premium = data['premium_until'] > time.time()
        cooldown = 1800 if is_premium else 3600
        
        current_time = time.time()
        if current_time - last_rob < cooldown:
            remaining = cooldown - (current_time - last_rob)
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            msg = f"⏳ This command is on cooldown. Try again in **{minutes}m {seconds}s**."
            if not is_premium:
                msg += "\n💡 *Tip: Premium members ($5.00/mo) get 50% reduced rob cooldowns!*"
            return await ctx.send(msg, ephemeral=True)

        target_balance = await self.db.get_balance(member.id)
        my_balance = data['coins']
        
        if target_balance < 100:
            return await ctx.send(f"❌ {member.display_name} is too poor to rob!", ephemeral=True)
        
        # 40% success rate (60% for premium)
        success_chance = 0.6 if is_premium else 0.4
        success = random.random() < success_chance
        if success:
            stolen = random.randint(50, min(target_balance, 500))
            await self.bot.update_balance(ctx.author.id, stolen)
            await self.bot.update_balance(member.id, -stolen)
            await self.db.update_economy_cooldown(ctx.author.id, "rob", current_time)
            await ctx.send(f"💸 Success! You robbed **{stolen}** RC from {member.mention}!")
            self.bot.dispatch("rob_success", ctx.author.id)
            await self.bot.log_action(ctx.guild, "Robbery Success", f"**{ctx.author}** robbed **{stolen}** RC from **{member}**.", color=0xe74c3c, moderator=ctx.author, user=member)
        else:
            fine = random.randint(50, min(my_balance, 200)) if my_balance > 0 else 0
            if fine > 0:
                await self.bot.update_balance(ctx.author.id, -fine)
                await self.db.update_economy_cooldown(ctx.author.id, "rob", current_time)
                await ctx.send(f"👮 You got caught! You were fined **{fine}** RC.")
                await self.bot.log_action(ctx.guild, "Robbery Failure", f"**{ctx.author}** tried to rob **{member}** but failed and was fined **{fine}** RC.", color=0x95a5a6, moderator=ctx.author, user=member)
            else:
                await self.db.update_economy_cooldown(ctx.author.id, "rob", current_time)
                await ctx.send(f"👮 You got caught! Luckily, you have no money to pay the fine.")
                await self.bot.log_action(ctx.guild, "Robbery Failure", f"**{ctx.author}** tried to rob **{member}** but failed. No fine was issued.", color=0x95a5a6, moderator=ctx.author, user=member)

    @commands.hybrid_command(name="shop", description="Browse the Rose Store")
    async def shop(self, ctx):
        embed = discord.Embed(title="🏪 Rose Store", description="Buy items with your Rose Coins <:rose_coin:1533598631612125397>!", color=0x2ecc71)
        for item_id, details in self.shop_items.items():
            rank_str = f" [{details['rank']}]"
            embed.add_field(name=f"{details['name']}{rank_str} — {details['price']} RC <:rose_coin:1533598631612125397>", value=details['description'], inline=False)
        embed.set_footer(text="Use .buy <item_name> to purchase.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="buy", description="Buy an item from the store")
    async def buy(self, ctx, *, item_name: str):
        await ctx.defer()
        item_id = item_name.lower().replace(" ", "_")
        if item_id not in self.shop_items:
            # Try to find by name
            found = False
            for k, v in self.shop_items.items():
                if v['name'].lower() == item_name.lower():
                    item_id = k
                    found = True
                    break
            if not found:
                return await ctx.send("❌ Item not found in shop.", ephemeral=True)
        
        item = self.shop_items[item_id]
        if item.get('premium_only') and not await self.db.is_user_premium(ctx.author.id):
            return await ctx.send(f"✨ This item is exclusive to **flowerbot.gg Premium** members ($5.00/mo)!", ephemeral=True)
            
        balance = await self.db.get_balance(ctx.author.id)
        
        if balance < item['price']:
            return await ctx.send(f"❌ You don't have enough RC to buy {item['name']}.", ephemeral=True)
        
        await self.bot.update_balance(ctx.author.id, -item['price'])
        await self.db.add_item(ctx.author.id, item_id, 1, rank=item.get('rank', 'Common'))
        
        await ctx.send(f"🛒 You bought a **{item['name']}** ([{item.get('rank', 'Common')}]) for **{item['price']}** RC!")
        await self.bot.log_action(ctx.guild, "Item Purchase", f"**{ctx.author}** bought **{item['name']}** ([{item.get('rank', 'Common')}]) for **{item['price']}** RC.", color=0x2ecc71, moderator=ctx.author)
        
    @commands.hybrid_command(name="work", description="Work to earn some Rose Coins")
    @commands.cooldown(1, 300, commands.BucketType.user) # 5 minute cooldown
    async def work(self, ctx):
        await ctx.defer()
        jobs = [
            "tending to the flower gardens",
            "cleaning the rose petals",
            "helping a fellow adventurer",
            "gathering honey from the bees",
            "polishing some golden flowers",
            "watering the thirsty plants"
        ]
        job = random.choice(jobs)
        reward = random.randint(50, 150)
        
        is_premium = await self.bot.db.is_user_premium(ctx.author.id)
        if is_premium:
            reward = int(reward * 1.5)
            
        await self.bot.update_balance(ctx.author.id, reward)
        
        msg = f"🔨 You spent some time **{job}** and earned **{reward}** RC <:rose_coin:1533598631612125397>!"
        if is_premium:
            msg += " (Premium bonus included! ✨)"
        await ctx.send(msg)

    @commands.hybrid_command(name="inventory", aliases=["inv"], description="View your inventory")
    async def inventory(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        items = await self.db.get_inventory(member.id)
        
        if not items:
            return await ctx.send(f"🎒 {member.display_name}'s inventory is empty.")
        
        embed = discord.Embed(title=f"🎒 {member.display_name}'s Inventory", color=0x9b59b6)
        for item_id, quantity, rank in items:
            item_data = self.shop_items.get(item_id, {"name": item_id})
            name = item_data["name"]
            embed.add_field(name=f"{name} [{rank}]", value=f"Quantity: {quantity}", inline=True)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="gift_item", description="Gift an item to another user")
    async def gift_item(self, ctx, member: discord.Member, item_name: str, quantity: int = 1, rank: str = "Common"):
        if quantity <= 0: return await ctx.send("❌ Quantity must be positive.", ephemeral=True)
        if member == ctx.author: return await ctx.send("❌ You cannot gift to yourself.", ephemeral=True)
        
        item_id = item_name.lower().replace(" ", "_")
        # Try to find by name to get correct item_id
        for k, v in self.shop_items.items():
            if v['name'].lower() == item_name.lower():
                item_id = k
                break

        success = await self.db.remove_item(ctx.author.id, item_id, quantity, rank=rank)
        if not success:
            return await ctx.send(f"❌ You don't have {quantity} of that item with rank {rank}.", ephemeral=True)
        
        await self.db.add_item(member.id, item_id, quantity, rank=rank)
        await ctx.send(f"🎁 You gifted **{quantity}x {item_id.replace('_', ' ').title()}** [{rank}] to {member.mention}!")
        await self.bot.log_action(ctx.guild, "Item Gifted", f"**{ctx.author}** gifted **{quantity}x {item_id.replace('_', ' ').title()}** [{rank}] to **{member}**.", color=0x9b59b6, moderator=ctx.author, user=member)
        
        # Achievement for trading/gifting
        self.bot.dispatch("trade_complete", ctx.author.id)

    @commands.hybrid_command(name="trade", description="Trade items or coins with another user")
    async def trade(self, ctx, member: discord.Member):
        if member == ctx.author:
            return await ctx.send("❌ You cannot trade with yourself.", ephemeral=True)
        
        await ctx.send(f"🤝 {member.mention}, {ctx.author.mention} wants to trade with you! Type `accept` to start the trade.")
        
        def check(m):
            return m.author == member and m.channel == ctx.channel and m.content.lower() == 'accept'
        
        try:
            await self.bot.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await ctx.send("⏰ Trade request timed out.")
        
        # Simple trade interface could be complex, let's do a one-sided gift trade for now or a simple coin-item swap
        # For simplicity in this step, I'll just confirm they are ready.
        await ctx.send(f"✅ Trade started! (Trading functionality is currently limited to `pay` and `gift`, full trade UI coming soon!)")

async def setup(bot):
    await bot.add_cog(Economy(bot))
