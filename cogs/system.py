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

    @commands.command(name="sync")
    @is_admin()
    async def sync(self, ctx, guild_id: str = None):
        """Sync slash commands. Use 'guild' as argument to sync to current guild."""
        try:
            if guild_id == "guild":
                self.bot.tree.copy_global_to(guild=ctx.guild)
                fmt = await self.bot.tree.sync(guild=ctx.guild)
                await ctx.send(f"✅ Synced {len(fmt)} commands to current guild.")
            elif guild_id:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    return await ctx.send("❌ Guild not found.")
                self.bot.tree.copy_global_to(guild=guild)
                fmt = await self.bot.tree.sync(guild=guild)
                await ctx.send(f"✅ Synced {len(fmt)} commands to guild {guild.name}.")
            else:
                fmt = await self.bot.tree.sync()
                await ctx.send(f"✅ Synced {len(fmt)} global commands.")
        except Exception as e:
            await ctx.send(f"❌ Failed to sync: {e}")

async def setup(bot):
    await bot.add_cog(System(bot))
