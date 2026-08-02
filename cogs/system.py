import discord
from discord.ext import commands
import logging

from utils.permissions import is_admin

class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="reload")
    @is_admin()
    async def reload(self, ctx, extension: str):
        try:
            await self.bot.reload_extension(f"cogs.{extension}")
            await ctx.send(f"✅ Reloaded {extension}")
        except Exception as e:
            await ctx.send(f"❌ Failed to reload {extension}: {e}")

    @commands.command(name="load")
    @is_admin()
    async def load(self, ctx, extension: str):
        try:
            await self.bot.load_extension(f"cogs.{extension}")
            await ctx.send(f"✅ Loaded {extension}")
        except Exception as e:
            await ctx.send(f"❌ Failed to load {extension}: {e}")

    @commands.command(name="unload")
    @is_admin()
    async def unload(self, ctx, extension: str):
        try:
            await self.bot.unload_extension(f"cogs.{extension}")
            await ctx.send(f"✅ Unloaded {extension}")
        except Exception as e:
            await ctx.send(f"❌ Failed to unload {extension}: {e}")

async def setup(bot):
    await bot.add_cog(System(bot))
