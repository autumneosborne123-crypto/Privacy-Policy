import discord
from discord.ext import commands
import time
import logging

class AFK(commands.Cog):
    """AFK system similar to Dyno bot."""
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="afk", description="Set your AFK status")
    async def afk(self, ctx, *, reason: str = "AFK"):
        """Set your AFK status so others know you're away."""
        await self.bot.db.set_afk(ctx.author.id, reason, time.time())
        
        # Try to change nickname
        try:
            if not ctx.author.display_name.startswith("[AFK] "):
                new_nick = f"[AFK] {ctx.author.display_name}"
                if len(new_nick) > 32:
                    new_nick = new_nick[:29] + "..."
                await ctx.author.edit(nick=new_nick)
        except Exception as e:
            logging.debug(f"Could not change nickname for AFK: {e}")
            
        embed = discord.Embed(
            description=f"✅ {ctx.author.mention}, I've set your AFK: **{reason}**", 
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # 1. Check if the author is returning from AFK
        afk_data = await self.bot.db.get_afk(message.author.id)
        if afk_data:
            reason, timestamp = afk_data
            # Ignore if the message was the AFK command itself (approx < 2 seconds)
            if time.time() - timestamp > 2:
                await self.bot.db.remove_afk(message.author.id)
                
                # Try to remove AFK tag from nickname
                try:
                    if message.author.display_name.startswith("[AFK] "):
                        await message.author.edit(nick=message.author.display_name[6:])
                except:
                    pass
                
                duration = time.time() - timestamp
                hours, rem = divmod(int(duration), 3600)
                minutes, seconds = divmod(rem, 60)
                
                time_str = []
                if hours: time_str.append(f"{hours}h")
                if minutes: time_str.append(f"{minutes}m")
                if seconds or not time_str: time_str.append(f"{seconds}s")
                
                welcome_msg = f"Welcome back {message.author.mention}, I've removed your AFK. You were gone for **{' '.join(time_str)}**."
                await message.channel.send(welcome_msg, delete_after=10)

        # 2. Check if anyone mentioned is AFK
        if message.mentions:
            for mention in message.mentions:
                if mention.id == message.author.id:
                    continue
                
                afk_data = await self.bot.db.get_afk(mention.id)
                if afk_data:
                    reason, timestamp = afk_data
                    duration = time.time() - timestamp
                    
                    hours, rem = divmod(int(duration), 3600)
                    minutes, seconds = divmod(rem, 60)
                    
                    time_str = []
                    if hours: time_str.append(f"{hours}h")
                    if minutes: time_str.append(f"{minutes}m")
                    if seconds or not time_str: time_str.append(f"{seconds}s")
                    
                    await message.channel.send(
                        f"☁️ **{mention.display_name}** is AFK: {reason} ({' '.join(time_str)} ago)", 
                        delete_after=10
                    )

async def setup(bot):
    await bot.add_cog(AFK(bot))
