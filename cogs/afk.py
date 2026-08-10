import discord
from discord.ext import commands
import time
import logging

class AFK(commands.Cog):
    """AFK system similar to Nekotina bot."""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="afk", description="Set your AFK status")
    async def afk(self, ctx, *, reason: str = "I am currently AFK"):
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
            
        await ctx.send(f"✅ {ctx.author.mention}, I've set your AFK: **{reason}**")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # 1. Check if the author is returning from AFK
        afk_data = await self.bot.db.get_afk(message.author.id)
        if afk_data:
            reason, timestamp = afk_data
            # Ignore if the message was the AFK command itself (approx < 2 seconds)
            if time.time() - timestamp > 5:
                await self.bot.db.remove_afk(message.author.id)
                
                # Try to remove AFK tag from nickname
                try:
                    if message.author.display_name.startswith("[AFK] "):
                        await message.author.edit(nick=message.author.display_name[6:])
                except:
                    pass
                
                duration = self.format_duration(time.time() - timestamp)
                welcome_msg = f"Welcome back {message.author.mention}! You were gone for **{duration}**."
                await message.channel.send(welcome_msg, delete_after=10)

        # 2. Check if anyone mentioned is AFK
        if message.mentions:
            for mention in message.mentions:
                if mention.id == message.author.id:
                    continue
                
                afk_data = await self.bot.db.get_afk(mention.id)
                if afk_data:
                    reason, timestamp = afk_data
                    duration = self.format_duration(time.time() - timestamp)
                    
                    await message.channel.send(
                        f"☁️ **{mention.display_name}** is AFK: {reason} - <t:{int(timestamp)}:R>", 
                        delete_after=15
                    )

    def format_duration(self, seconds):
        hours, rem = divmod(int(seconds), 3600)
        minutes, seconds = divmod(rem, 60)
        
        parts = []
        if hours: parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        if seconds or not parts: parts.append(f"{seconds}s")
        
        return " ".join(parts)

async def setup(bot):
    await bot.add_cog(AFK(bot))
