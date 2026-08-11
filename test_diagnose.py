import asyncio
import discord
from discord.ext import commands
from cogs.tools import Tools
import unittest
from unittest.mock import AsyncMock, MagicMock

class TestDiagnose(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock()
        self.bot.db = AsyncMock()
        self.bot.user = MagicMock()
        self.bot.user.display_avatar.url = "https://example.com/avatar.png"
        self.cog = Tools(self.bot)
        
        self.guild = MagicMock()
        self.guild.name = "Test Guild"
        self.guild.id = 123
        
        # Default mock permissions (All True)
        self.perms = MagicMock()
        self.perms.view_channel = True
        self.perms.send_messages = True
        self.perms.embed_links = True
        self.perms.attach_files = True
        self.perms.use_external_emojis = True
        self.perms.read_message_history = True
        self.perms.add_reactions = True
        self.perms.ban_members = True
        self.perms.kick_members = True
        self.perms.manage_messages = True
        self.perms.moderate_members = True
        self.perms.manage_roles = True
        self.perms.view_audit_log = True
        self.perms.manage_nicknames = True
        self.perms.connect = True
        self.perms.speak = True
        self.perms.priority_speaker = True
        self.perms.manage_webhooks = True
        self.perms.administrator = False
        
        self.me = MagicMock()
        self.me.guild_permissions = self.perms
        self.me.top_role.name = "Bot Role"
        self.me.top_role.position = 5
        self.guild.me = self.me
        
        self.ctx = AsyncMock()
        self.ctx.guild = self.guild
        self.ctx.author = MagicMock()
        self.ctx.author.guild_permissions.manage_guild = True
        self.ctx.send = AsyncMock()
        self.ctx.defer = AsyncMock()
        self.ctx.interaction = None

    async def test_diagnose_all_pass(self):
        # Mock get_log_channel to return a mock channel with correct perms
        log_chan = MagicMock(spec=discord.TextChannel)
        log_chan.mention = "#flower-logs"
        log_perms = MagicMock()
        log_perms.view_channel = True
        log_perms.send_messages = True
        log_perms.embed_links = True
        log_chan.permissions_for.return_value = log_perms
        self.bot.get_log_channel = AsyncMock(return_value=log_chan)
        
        await self.cog.diagnose.callback(self.cog, self.ctx)
        
        self.ctx.defer.assert_called_once()
        self.ctx.send.assert_called_once()
        args, kwargs = self.ctx.send.call_args
        embed = kwargs.get('embed') or args[0]
        
        self.assertIn("All permissions are correctly configured", embed.description)
        self.assertIn("✅ View Channels", [f.value for f in embed.fields if f.name == "Core Features"][0])
        self.assertIn("✅ #flower-logs", [f.value for f in embed.fields if f.name == "Logging System"][0])

    async def test_diagnose_missing_perms(self):
        # Set some permissions to False
        self.perms.ban_members = False
        self.perms.kick_members = False
        
        self.bot.get_log_channel = AsyncMock(return_value=None)
        
        await self.cog.diagnose.callback(self.cog, self.ctx)
        
        args, kwargs = self.ctx.send.call_args
        embed = kwargs.get('embed') or args[0]
        
        self.assertIn("Found **2** missing permissions", embed.description)
        self.assertIn("❌ Ban Members", [f.value for f in embed.fields if f.name == "Moderation & Security"][0])
        self.assertIn("❌ Kick Members", [f.value for f in embed.fields if f.name == "Moderation & Security"][0])
        self.assertIn("❌ Not Found", [f.value for f in embed.fields if f.name == "Logging System"][0])

    async def test_diagnose_logging_missing_perms(self):
        # Mock logging channel found but missing perms
        log_chan = MagicMock(spec=discord.TextChannel)
        log_chan.mention = "#flower-logs"
        log_perms = MagicMock()
        log_perms.view_channel = True
        log_perms.send_messages = False # Missing Send
        log_perms.embed_links = True
        log_chan.permissions_for.return_value = log_perms
        self.bot.get_log_channel = AsyncMock(return_value=log_chan)
        
        await self.cog.diagnose.callback(self.cog, self.ctx)
        
        args, kwargs = self.ctx.send.call_args
        embed = kwargs.get('embed') or args[0]
        self.assertIn("⚠️ #flower-logs (Missing perms)", [f.value for f in embed.fields if f.name == "Logging System"][0])

    async def test_diagnose_admin_role(self):
        # Admin bypass
        self.perms.administrator = True
        self.bot.get_log_channel = AsyncMock(return_value=None)
        
        await self.cog.diagnose.callback(self.cog, self.ctx)
        
        args, kwargs = self.ctx.send.call_args
        embed = kwargs.get('embed') or args[0]
        self.assertIn("Administrator enabled", [f.value for f in embed.fields if f.name == "Role Hierarchy"][0])

if __name__ == "__main__":
    unittest.main()
