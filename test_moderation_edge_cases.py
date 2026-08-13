import asyncio
import os
import discord
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from utils.database import Database
from cogs.moderation import Moderation
from utils.permissions import is_staff
from datetime import datetime

class MockPermissions:
    def __init__(self, administrator=False, ban_members=True):
        self.administrator = administrator
        self.ban_members = ban_members

class MockRole:
    def __init__(self, name, id=None, position=0):
        self.name = name
        self.id = id or hash(name)
        self.mention = f"<@&{self.id}>"
        self.position = position
    def __eq__(self, other):
        return isinstance(other, MockRole) and self.id == other.id
    def __lt__(self, other):
        if not isinstance(other, MockRole): return NotImplemented
        return self.position < other.position
    def __le__(self, other):
        if not isinstance(other, MockRole): return NotImplemented
        return self.position <= other.position

class MockMember:
    def __init__(self, id, name, roles=None, administrator=False):
        self.id = id
        self.name = name
        self.mention = f"<@{id}>"
        self.roles = roles or [MockRole("@everyone", position=0)]
        self.guild_permissions = MockPermissions(administrator=administrator)
        self.timed_out_until = None
        self.display_avatar = MagicMock()
        self.display_avatar.url = "http://example.com/avatar.png"

    @property
    def top_role(self):
        return max(self.roles)

    async def timeout(self, until, reason=None):
        self.timed_out_until = until
        return True

    async def add_roles(self, role, reason=None):
        if role not in self.roles:
            self.roles.append(role)
        return True

    async def remove_roles(self, role, reason=None):
        if role in self.roles:
            self.roles.remove(role)
        return True

    async def ban(self, reason=None):
        return True

    def __str__(self):
        return self.name

class TestModerationEdgeCases(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_edge_mod.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        await self.db.init()
        
        self.bot = AsyncMock()
        self.bot.db = self.db
        self.bot.log_action = AsyncMock()
        self.cog = Moderation(self.bot)
        
        self.guild = MagicMock()
        self.guild.id = 123
        self.guild.name = "Test Guild"
        self.guild.members = []
        self.guild.owner = MockMember(0, "Owner", roles=[MockRole("Owner", position=100)])
        self.guild.me = MockMember(99, "Bot", roles=[MockRole("Bot", position=50)])
        
        self.author = MockMember(1, "Staff", roles=[MockRole("admin", position=60)], administrator=True)
        self.target = MockMember(2, "User")
        self.guild.members.append(self.target)
        
        self.ctx = AsyncMock()
        self.ctx.bot = self.bot
        self.ctx.guild = self.guild
        self.ctx.author = self.author
        self.ctx.send = AsyncMock()
        self.ctx.interaction = None

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_mute_already_muted(self):
        # Setup: already has mute role
        mute_role = MockRole("Muted", id=999)
        self.guild.get_role.return_value = mute_role
        await self.db.set_mute_role(self.guild.id, mute_role.id)
        self.target.roles.append(mute_role)
        
        # Action: Mute again
        await self.cog.mute.callback(self.cog, self.ctx, self.target, reason="Already muted")
        
        # Verification: Should still report success or at least not fail
        self.ctx.send.assert_called()
        args, kwargs = self.ctx.send.call_args
        self.assertIn("Successfully muted", args[0])
        self.assertIn(mute_role.mention, args[0])

    async def test_unmute_not_muted(self):
        # Setup: Target has no restrictions
        self.target.timed_out_until = None
        self.target.roles = []
        mute_role = MockRole("Muted", id=999)
        self.guild.get_role.return_value = mute_role
        await self.db.set_mute_role(self.guild.id, mute_role.id)

        # Action: Unmute
        await self.cog.unmute.callback(self.cog, self.ctx, self.target)
        
        # Verification: Should report "cleared all restrictions"
        args, kwargs = self.ctx.send.call_args
        self.assertIn("cleared all restrictions", args[0])

    async def test_remove_nonexistent_warn(self):
        # Action: Remove warn ID 9999 (doesn't exist)
        await self.cog.removewarn.callback(self.cog, self.ctx, 9999)
        
        # Verification: Should report success (as per current implementation, it just runs the query)
        # or we might want it to check if it existed. 
        # Currently Moderation.py:159 just says "Warning ID {warn_id} removed."
        self.ctx.send.assert_called_with("✅ Warning ID `9999` removed.")

    async def test_clear_warns_no_warns(self):
        # Action: Clear warns for user with 0 warns
        await self.cog.clearwarns.callback(self.cog, self.ctx, self.target)
        self.ctx.send.assert_called_with(f"✅ All warnings for {self.target.mention} have been cleared.")

    async def test_staff_role_case_insensitivity(self):
        # Setup: Author has "SR.MOD" role
        sr_mod_role = MockRole("SR.MOD")
        author = MockMember(10, "SrMod", roles=[sr_mod_role])
        ctx = MagicMock()
        ctx.guild = self.guild
        ctx.author = author
        ctx.bot = self.bot # self.bot has self.db (AsyncMock)
        
        # Check predicate
        predicate = is_staff().predicate
        result = await predicate(ctx)
        self.assertTrue(result)

    async def test_ban_already_banned(self):
        # Setup: guild.ban raises discord.Forbidden or similar
        self.guild.ban = AsyncMock(side_effect=Exception("Already banned"))
        await self.cog.ban.callback(self.cog, self.ctx, self.target, reason="Testing failure")
        self.ctx.send.assert_called_with("❌ Failed to ban member: Already banned")

if __name__ == "__main__":
    unittest.main()
