import discord
from discord.ext import commands
import datetime

class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.achievements_list = {
            "first_catch": {"name": "First Catch", "description": "Catch your very first animal!"},
            "battle_winner": {"name": "Battle Winner", "description": "Win your first animal battle."},
            "rich_user": {"name": "Rising Star", "description": "Reach 1,000 Blue Flower Coins 🔵🌹."},
            "medalist": {"name": "Blue Flower Medalist", "description": "Complete 5 quests."},
            "trader": {"name": "Merchant", "description": "Complete your first trade."},
            "highwayman": {"name": "Highwayman", "description": "Successfully rob another user."}
        }

    @commands.hybrid_command(name="achievements", description="View your earned achievements")
    async def achievements(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        earned = await self.db.get_achievements(member.id)
        earned_ids = [a[0] for a in earned]
        
        embed = discord.Embed(title=f"🏆 {member.display_name}'s Achievements", color=0xf1c40f)
        
        for aid, data in self.achievements_list.items():
            status = "✅ Earned" if aid in earned_ids else "❌ Locked"
            embed.add_field(name=data['name'], value=f"{data['description']}\n*{status}*", inline=False)
            
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_animal_catch(self, user_id):
        await self.db.add_achievement(user_id, "first_catch")

    @commands.Cog.listener()
    async def on_battle_win(self, user_id):
        await self.db.add_achievement(user_id, "battle_winner")

    @commands.Cog.listener()
    async def on_trade_complete(self, user_id):
        await self.db.add_achievement(user_id, "trader")

    @commands.Cog.listener()
    async def on_rob_success(self, user_id):
        await self.db.add_achievement(user_id, "highwayman")

    @commands.Cog.listener()
    async def on_quest_completion(self, user_id):
        quests = await self.db.get_quests(user_id)
        completed_count = sum(1 for q in quests if q[5])
        if completed_count >= 5:
            await self.db.add_achievement(user_id, "medalist")

    @commands.Cog.listener()
    async def on_balance_change(self, user_id, new_balance):
        if new_balance >= 1000:
            await self.db.add_achievement(user_id, "rich_user")

async def setup(bot):
    await bot.add_cog(Achievements(bot))
