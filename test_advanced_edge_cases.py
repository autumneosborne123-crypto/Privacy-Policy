import asyncio
import os
import discord
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from utils.database import Database
from cogs.moderation import Moderation
from cogs.music import Music
from cogs.economy import Economy
from cogs.security import Security
from cogs.leveling import Leveling
from utils.permissions import is_staff
from datetime import datetime, timedelta

class MockPermissions:
    def __init__(self, administrator=False, ban_members=True, manage_messages=True):
        self.administrator = administrator
        self.ban_members = ban_members
        self.manage_messages = manage_messages

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
    def __hash__(self):
        return self.id

class MockMember:
    def __init__(self, id, name, roles=None, administrator=False):
        self.id = id
        self.name = name
        self.display_name = name
        self.mention = f"<@{id}>"
        self.roles = roles or [MockRole("@everyone", position=0)]
        self.guild_permissions = MockPermissions(administrator=administrator)
        self.timed_out_until = None
        self.display_avatar = MagicMock()
        self.display_avatar.url = "http://example.com/avatar.png"
        self.voice = None

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

class TestAdvancedEdgeCases(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_adv_edge.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        await self.db.init()
        
        self.bot = AsyncMock()
        self.bot.dispatch = MagicMock()
        self.bot.db = self.db
        self.bot.config = MagicMock()
        self.bot.config.get = MagicMock(return_value=None)
        self.bot.update_balance = AsyncMock()
        self.bot.log_action = AsyncMock()
        self.bot.latency = 0.05
        self.bot.loop = asyncio.get_event_loop()
        self.bot.whitelisted_bots = []
        
        self.mod_cog = Moderation(self.bot)
        self.music_cog = Music(self.bot)
        self.econ_cog = Economy(self.bot)
        self.sec_cog = Security(self.bot)
        self.lvl_cog = Leveling(self.bot)
        
        self.guild = MagicMock()
        self.guild.id = 123
        self.guild.name = "Test Guild"
        self.guild.members = []
        self.guild.owner = MockMember(0, "Owner", roles=[MockRole("Owner", position=100)])
        self.guild.me = MockMember(999, "Bot", roles=[MockRole("Bot", position=50)])
        
        self.author = MockMember(1, "Staff", roles=[MockRole("admin", position=60)], administrator=True)
        self.target = MockMember(2, "User")
        self.guild.members.append(self.target)
        
        self.ctx = AsyncMock()
        self.ctx.bot = self.bot
        self.ctx.guild = self.guild
        self.ctx.author = self.author
        self.ctx.channel.mention = "#general"
        self.ctx.send = AsyncMock()
        self.ctx.prefix = "."
        self.ctx.interaction = None

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    # --- Moderation Edge Cases ---

    async def test_timeout_zero_minutes(self):
        await self.mod_cog.timeout.callback(self.mod_cog, self.ctx, self.target, 0)
        self.ctx.send.assert_called()
        args, _ = self.ctx.send.call_args
        self.assertIn("Successfully timed out", args[0])

    async def test_timeout_too_long(self):
        await self.mod_cog.timeout.callback(self.mod_cog, self.ctx, self.target, 40321)
        self.ctx.send.assert_called()
        args, kwargs = self.ctx.send.call_args
        self.assertIn("cannot exceed 28 days", args[0])
        # No longer ephemeral for prefix command

    async def test_mute_no_role_no_duration(self):
        # Ensure no mute role is set
        await self.db.set_mute_role(self.guild.id, None)
        await self.mod_cog.mute.callback(self.mod_cog, self.ctx, self.target, minutes=None)
        self.ctx.send.assert_called()
        args, kwargs = self.ctx.send.call_args
        self.assertIn("no mute role configured", args[0])

    async def test_clear_invalid_amounts(self):
        # Test 0
        await self.mod_cog.clear.callback(self.mod_cog, self.ctx, 0)
        self.ctx.channel.purge.assert_called_with(limit=1)
        
        # Test negative
        await self.mod_cog.clear.callback(self.mod_cog, self.ctx, -5)
        self.ctx.channel.purge.assert_called_with(limit=-4)

    async def test_logs_boundary_limits(self):
        self.guild.audit_logs = MagicMock()
        async def mock_audit_logs(*args, **kwargs):
            yield MagicMock(user="User", action=discord.AuditLogAction.ban, target="Target", reason="Test", created_at=datetime.utcnow())
        
        self.guild.audit_logs.side_effect = mock_audit_logs
        
        # Limit 0
        await self.mod_cog.logs.callback(self.mod_cog, self.ctx, limit=0)
        # Should not send embed or send "No logs"
        
        # Limit 200 (cog has break if len(logs) >= limit)
        await self.mod_cog.logs.callback(self.mod_cog, self.ctx, limit=200)
        self.ctx.send.assert_called()

    # --- Music Edge Cases ---

    async def test_music_volume_boundaries(self):
        # 0 <= level <= 100 check in Music.py
        await self.music_cog.volume.callback(self.music_cog, self.ctx, 150)
        self.ctx.send.assert_called_with("❌ Level must be 0-100.", ephemeral=True)
        
        await self.music_cog.volume.callback(self.music_cog, self.ctx, -10)
        self.ctx.send.assert_called_with("❌ Level must be 0-100.", ephemeral=True)

    async def test_music_skip_empty_queue(self):
        self.music_cog.queues[self.guild.id] = []
        self.music_cog.current_tracks[self.guild.id] = None
        self.ctx.voice_client = MagicMock()
        self.ctx.voice_client.is_playing.return_value = False
        await self.music_cog.skip.callback(self.music_cog, self.ctx)
        self.ctx.send.assert_called_with("❌ Nothing is playing.")

    async def test_music_shuffle_one_song(self):
        self.music_cog.queues[self.guild.id] = ["Song1"]
        await self.music_cog.shuffle.callback(self.music_cog, self.ctx)
        self.ctx.send.assert_called_with("🔀 Shuffled!")

    async def test_music_remove_out_of_range(self):
        self.music_cog.queues[self.guild.id] = ["Song1", "Song2"]
        await self.music_cog.remove.callback(self.music_cog, self.ctx, 5)
        self.ctx.send.assert_called_with("❌ Invalid index (1-2).")

    # --- Economy Edge Cases ---

    async def test_economy_rob_exactly_100(self):
        await self.db.update_balance(self.target.id, 100)
        await self.db.update_balance(self.author.id, 500)
        # Success is random, but the check for 100 should pass
        with patch('random.random', return_value=0.1): # Success
            with patch('random.randint', return_value=50):
                await self.econ_cog.rob.callback(self.econ_cog, self.ctx, self.target)
                self.ctx.send.assert_called()
                args, _ = self.ctx.send.call_args
                self.assertIn("Success", args[0])

    async def test_economy_gift_insufficient_quantity(self):
        # Gift 5 petals when I have 2
        await self.db.add_item(self.author.id, "petal", 2, rank="Common")
        await self.econ_cog.gift_item.callback(self.econ_cog, self.ctx, self.target, "petal", 5, rank="Common")
        self.ctx.send.assert_called()
        args, _ = self.ctx.send.call_args
        self.assertIn("You don't have 5 of that item", args[0])

    # --- Security & Leveling ---

    async def test_security_raidmode_toggle(self):
        self.sec_cog.raid_modes[self.guild.id] = False
        await self.sec_cog.raidmode.callback(self.sec_cog, self.ctx, True)
        self.assertTrue(self.sec_cog.raid_modes[self.guild.id])
        self.ctx.send.assert_called()
        args, _ = self.ctx.send.call_args
        self.assertIn("enabled", args[0])
    
    async def test_leveling_add_xp_negative(self):
        # Setup user data
        await self.db.update_user_data(str(self.target.id), 100, 1, 0, 0, 0)
        await self.lvl_cog.add_xp.callback(self.lvl_cog, self.ctx, self.target, -50)
        
        user_data = await self.db.get_user_data(str(self.target.id))
        self.assertEqual(user_data['xp'], 50)
        self.ctx.send.assert_called()
        args, _ = self.ctx.send.call_args
        self.assertIn("Added **-50** XP", args[0])

    async def test_leveling_set_level_negative(self):
        await self.lvl_cog.set_level.callback(self.lvl_cog, self.ctx, self.target, -1)
        self.ctx.send.assert_called_with("Level cannot be negative!", ephemeral=True)

if __name__ == "__main__":
    unittest.main()
