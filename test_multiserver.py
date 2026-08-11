import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
from main import FlowerBot
from utils.database import Database
import time
from cogs.config import ConfigCog

class MockRole:
    def __init__(self, id, name, position=1):
        self.id = id
        self.name = name
        self.position = position
        self.mention = f"<@&{id}>"
    def __ge__(self, other): return self.position >= other.position
    def __le__(self, other): return self.position <= other.position
    def __gt__(self, other): return self.position > other.position
    def __lt__(self, other): return self.position < other.position

class TestMultiServer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = FlowerBot()
        self.bot.db = AsyncMock(spec=Database)
        # Mock database settings
        self.bot.db.get_all_guild_settings = AsyncMock(return_value={})
        self.bot.db.get_guild_setting = AsyncMock(side_effect=lambda g, k, t=None: None)
        self.bot.db.set_guild_setting = AsyncMock()
        
        self.guild = MagicMock(spec=discord.Guild)
        self.guild.id = 123
        self.guild.name = "Test Guild"
        self.guild.system_channel = AsyncMock(spec=discord.TextChannel)
        self.guild.system_channel.permissions_for.return_value.send_messages = True
        self.guild.owner = AsyncMock(spec=discord.Member)
        self.guild.me = MagicMock(spec=discord.Member)
        
        # Mock the user property using patch
        patcher = patch.object(FlowerBot, 'user', new_callable=MagicMock)
        self.mock_user = patcher.start()
        self.mock_user.display_avatar.url = "http://example.com/bot.png"
        self.bot.user.display_avatar.url = "http://example.com/bot.png"
        self.addCleanup(patcher.stop)
        
        self.author = MagicMock(spec=discord.Member)
        self.author.id = 456
        self.author.roles = []
        self.author.guild_permissions.administrator = False
        
        self.ctx = MagicMock(spec=commands.Context)
        self.ctx.bot = self.bot
        self.ctx.guild = self.guild
        self.ctx.author = self.author
        self.ctx.send = AsyncMock()
        self.ctx.prefix = "."

    async def test_on_guild_join_init(self):
        print("Testing on_guild_join initialization...")
        await self.bot.on_guild_join(self.guild)
        
        # Verify settings were initialized
        self.bot.db.set_guild_setting.assert_any_call(123, "anti_spam_enabled", 1)
        self.bot.db.set_guild_setting.assert_any_call(123, "anti_scam_enabled", 1)
        self.bot.db.set_guild_setting.assert_any_call(123, "anti_raid_enabled", 1)
        self.bot.db.set_guild_setting.assert_any_call(123, "anti_nuke_enabled", 1)
        
        # Verify welcome message
        self.guild.system_channel.send.assert_called()
        self.guild.owner.send.assert_called()
        print("on_guild_join initialization: PASSED")

    async def test_enable_disable_commands(self):
        print("\nTesting Enable/Disable commands...")
        cog = ConfigCog(self.bot)
        
        # Test disable
        self.bot.db.get_all_guild_settings.return_value = {}
        await cog.disable.callback(cog, self.ctx, "moderation")
        self.bot.db.set_guild_setting.assert_any_call(123, "disabled_cogs", "moderation")
        self.ctx.send.assert_called_with("✅ Module `moderation` disabled.", ephemeral=True)
        
        # Test enable
        self.bot.db.get_all_guild_settings.return_value = {'disabled_cogs': 'moderation,fun'}
        await cog.enable.callback(cog, self.ctx, "moderation")
        self.bot.db.set_guild_setting.assert_any_call(123, "disabled_cogs", "fun")
        self.ctx.send.assert_called_with("✅ Module `moderation` enabled.", ephemeral=True)
        print("Enable/Disable commands: PASSED")

if __name__ == "__main__":
    unittest.main()
