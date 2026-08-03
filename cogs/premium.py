import discord
from discord.ext import commands
import time
from datetime import datetime
from utils.permissions import is_admin

class Premium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @commands.hybrid_group(name="premium", description="Premium features and status")
    async def premium(self, ctx):
        if ctx.invoked_subcommand is None:
            # Show status
            embed = discord.Embed(title="✨ flowerbot.gg Premium", color=0xffd700)
            
            # User Status
            user_data = await self.db.get_economy_data(ctx.author.id)
            user_prem_until = user_data.get('premium_until', 0)
            user_status = "❌ Inactive"
            if user_prem_until > time.time():
                dt = datetime.fromtimestamp(user_prem_until)
                user_status = f"✅ Active until {dt.strftime('%Y-%m-%d %H:%M')}"
            
            embed.add_field(name="👤 Your Premium Status", value=user_status, inline=False)
            
            # Guild Status
            guild_status = "❌ Inactive"
            if ctx.guild:
                guild_prem_until = await self.db.get_guild_setting(ctx.guild.id, "premium_until")
                if guild_prem_until and float(guild_prem_until) > time.time():
                    dt = datetime.fromtimestamp(float(guild_prem_until))
                    guild_status = f"✅ Active until {dt.strftime('%Y-%m-%d %H:%M')}"
                embed.add_field(name="🏠 Server Premium Status", value=guild_status, inline=False)

            embed.description = (
                "**Premium Benefits:**\n"
                "• 2x Daily Coins 💰\n"
                "• 50% Reduced Rob Cooldown ⏳\n"
                "• Higher Animal Rarity Chances 🐾\n"
                "• 24/7 Music Mode (Server) 🕒\n"
                "• Exclusive Audio Filters (Server) 🎵\n\n"
                "**Pricing:**\n"
                "• 1 Month: **$5.00**\n"
                "• 3 Months: **$12.00**\n"
                "• Lifetime: **$35.00**\n\n"
                "**Get Premium:**\n"
                "Send payment via [**CashApp ($Amaryyy5)**](https://cash.app/$Amaryyy5)\n"
                f"**Crucial:** Include your User ID (`{ctx.author.id}`) in the payment note!\n"
                "Use `.premium buy` for more detailed instructions."
            )
            
            await ctx.send(embed=embed)

    @premium.command(name="buy", description="Get instructions to purchase Premium")
    async def buy_premium(self, ctx):
        embed = discord.Embed(title="💎 Buy flowerbot.gg Premium", color=0x00d632)
        embed.description = (
            f"You can purchase Premium via CashApp! Benefits are applied globally to your account.\n\n"
            "**💎 Premium Pricing:**\n"
            "• **1 Month:** $5.00\n"
            "• **3 Months:** $12.00 (Save $3!)\n"
            "• **Lifetime:** $35.00 (Best Value!)\n\n"
            "**📲 How to pay via CashApp:**\n"
            "1. Send the chosen amount to: [**$Amaryyy5**](https://cash.app/$Amaryyy5)\n"
            f"2. **⚠️ CRUCIAL:** Include your User ID: `{ctx.author.id}` in the payment note!\n"
            "3. Benefits will be applied within 24 hours of verification.\n\n"
            "*Need help? Join our [Support Server](https://discord.gg/mXtvjGpQmM)*"
        )
        embed.set_footer(text="Thank you for supporting flowerbot.gg!")
        await ctx.send(embed=embed)

    @premium.command(name="check", description="Check a user's premium status")
    @is_admin()
    async def check_premium(self, ctx, member: discord.Member):
        is_prem = await self.db.is_user_premium(member.id)
        status = "is a Premium member! ✨" if is_prem else "is not a Premium member."
        await ctx.send(f"👤 {member.mention} {status}")

    @commands.command(name="grantpremium", hidden=True)
    @is_admin()
    async def grant_premium(self, ctx, target_id: str, days: int, type: str = "user"):
        """Grant premium status to a user or guild (Admin only)"""
        if type.lower() == "user":
            await self.db.set_user_premium(target_id, days)
            await ctx.send(f"✅ Granted **{days} days** of Premium to User **{target_id}**.")
        elif type.lower() == "guild" or type.lower() == "server":
            await self.db.set_guild_premium(target_id, days)
            await ctx.send(f"✅ Granted **{days} days** of Premium to Guild **{target_id}**.")
        else:
            await ctx.send("❌ Type must be 'user' or 'guild'.")

async def setup(bot):
    await bot.add_cog(Premium(bot))
