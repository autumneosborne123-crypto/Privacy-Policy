import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from cogs.moderation import Moderation
from utils.database import Database
import os

class MockRole:
    def __init__(self, name, position):
        self.name = name
        self.position = position
        self.mention = f"<@&{name}>"
    
    def __ge__(self, other):
        return self.position >= other.position
    
    def __le__(self, other):
        return self.position <= other.position
    
    def __gt__(self, other):
        return self.position > other.position
    
    def __lt__(self, other):
        return self.position < other.position

def create_mock_member(id, name, position):
    member = MagicMock(spec=discord.Member)
    member.id = id
    member.name = name
    member.mention = f"<@{id}>"
    member.top_role = MockRole(name, position)
    member.roles = []
    member.timed_out_until = None
    member.timeout = AsyncMock()
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    member.ban = AsyncMock()
    member.kick = AsyncMock()
    member.send = AsyncMock()
    return member

class MockUser:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.mention = f"<@{id}>"
        self.display_avatar = MagicMock()
        self.display_avatar.url = "http://example.com/avatar.png"
    async def send(self, **kwargs): pass

class MockCtx:
    def __init__(self, bot, author, guild):
        self.bot = bot
        self.author = author
        self.guild = guild
        self.send = AsyncMock()
        self.interaction = None
        self.prefix = "."

class TestModerationV3(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock()
        self.bot.db = AsyncMock(spec=Database)
        self.bot.log_action = AsyncMock()
        self.cog = Moderation(self.bot)
        
        self.guild = MagicMock(spec=discord.Guild)
        self.guild.name = "Test Guild"
        self.guild.id = 123
        self.guild.owner = create_mock_member(0, "Owner", 100)
        self.guild.me = create_mock_member(999, "Bot", 50)
        
        self.admin = create_mock_member(1, "Admin", 20)
        self.mod = create_mock_member(2, "Mod", 5)
        self.target = create_mock_member(3, "Target", 1)
        
    async def test_mute_id_username_prefix(self):
        print("\nTesting Mute prefix command with ID/Username support...")
        ctx = MockCtx(self.bot, self.admin, self.guild)
        
        # Test 1: Mute with duration
        # Simulate: .mute 3 1d
        await self.cog.mute.callback(self.cog, ctx, self.target, "1d", reason="Spamming")
        self.bot.log_action.assert_called()
        ctx.send.assert_called()
        self.assertIn("Successfully muted", ctx.send.call_args[0][0])
        print("Mute with duration: PASSED")

        # Test 2: Mute WITHOUT duration (duration becomes part of reason)
        # Simulate: .mute 3 stop spamming
        ctx.send.reset_mock()
        await self.cog.mute.callback(self.cog, ctx, self.target, "stop", reason="spamming")
        # In prefix, duration="stop", reason="spamming"
        # parse_duration("stop") fails -> duration becomes None, reason becomes "stop spamming"
        self.assertIn("Reason: stop spamming", ctx.send.call_args[0][0])
        print("Mute without duration (smart parsing): PASSED")

    async def test_ban_user_support(self):
        print("\nTesting Ban with User support (non-members)...")
        ctx = MockCtx(self.bot, self.admin, self.guild)
        external_user = MockUser(4, "ExternalUser")
        
        await self.cog.ban.callback(self.cog, ctx, external_user, reason="Banned from outside")
        self.guild.ban.assert_called_once_with(external_user, reason="Banned from outside", delete_message_seconds=604800)
        ctx.send.assert_called()
        self.assertIn("Successfully banned ExternalUser", ctx.send.call_args[0][0])
        print("Ban non-member User: PASSED")

    async def test_hierarchy_check(self):
        print("\nTesting Hierarchy checks...")
        # Mod trying to mute Admin (should fail)
        ctx = MockCtx(self.bot, self.mod, self.guild)
        await self.cog.mute.callback(self.cog, ctx, self.admin, "1d")
        ctx.send.assert_called_with("❌ You cannot moderate <@1> because their role is higher than or equal to yours.")
        print("Hierarchy check (Mod vs Admin): PASSED")

        # Admin trying to mute Mod (should succeed)
        ctx = MockCtx(self.bot, self.admin, self.guild)
        await self.cog.mute.callback(self.cog, ctx, self.mod, "1d")
        self.assertIn("Successfully muted", ctx.send.call_args[0][0])
        print("Hierarchy check (Admin vs Mod): PASSED")
        
        # Bot trying to mute someone higher (should fail)
        self.guild.me.top_role = MockRole("Bot", 2)
        ctx = MockCtx(self.bot, self.admin, self.guild)
        await self.cog.mute.callback(self.cog, ctx, self.mod, "1d")
        ctx.send.assert_called_with("❌ I cannot moderate <@2> because their role is higher than or equal to mine.")
        print("Hierarchy check (Bot vs Higher Role): PASSED")

    async def test_warns_user_support(self):
        print("\nTesting Warns with User support...")
        ctx = MockCtx(self.bot, self.mod, self.guild)
        external_user = MockUser(4, "ExternalUser")
        self.bot.db.get_warns.return_value = []
        
        await self.cog.warns.callback(self.cog, ctx, external_user)
        self.bot.db.get_warns.assert_called_with(4, 123)
        ctx.send.assert_called_with("ExternalUser has no warnings.")
        print("Warns non-member User: PASSED")

if __name__ == "__main__":
    unittest.main()
