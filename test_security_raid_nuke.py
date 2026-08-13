import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from datetime import datetime, timedelta, timezone
import os
import time

# Set dummy environment variable for bot token
os.environ['DISCORD_TOKEN'] = 'dummy_token'

from cogs.security import Security

class TestSecurityRaidNuke(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.db = AsyncMock()
        self.bot.db.get_all_guild_settings.return_value = {}
        self.bot.user = MagicMock(spec=discord.ClientUser)
        self.bot.user.id = 999
        self.bot.whitelisted_bots = [422087909634736160]
        self.bot.get_log_channel = AsyncMock(return_value=None)
        self.bot.log_action = AsyncMock()
        self.security_cog = Security(self.bot)

    async def test_join_raid_detection(self):
        guild = MagicMock(spec=discord.Guild)
        guild.system_channel = AsyncMock()
        
        # Simulate 10 joins
        for i in range(10):
            member = AsyncMock(spec=discord.Member)
            member.id = 1000 + i
            member.guild = guild
            member.bot = False
            member.name = f"User{i}"
            member.created_at = datetime.now(timezone.utc) - timedelta(days=1) # Not suspicious age
            member.avatar = MagicMock()
            await self.security_cog.on_member_join(member)
        
        self.assertTrue(self.security_cog.raid_modes[guild.id])
        # Check if notification was sent
        guild.system_channel.send.assert_called()
        self.assertIn("RAID DETECTED", guild.system_channel.send.call_args[0][0])

    async def test_raid_mode_auto_kick(self):
        guild = MagicMock(spec=discord.Guild)
        guild.id = 777
        self.security_cog.raid_modes[guild.id] = True
        member = AsyncMock(spec=discord.Member)
        member.guild = guild
        member.id = 2000
        member.bot = False
        member.name = "RaidUser"
        member.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        
        await self.security_cog.on_member_join(member)
        
        member.kick.assert_called_once_with(reason="Anti-Raid: Raid mode enabled")

    async def test_message_spam_timeout(self):
        message = AsyncMock(spec=discord.Message)
        message.author = AsyncMock(spec=discord.Member)
        message.author.id = 3000
        message.author.bot = False
        message.author.name = "Spammer"
        message.content = "spam"
        message.mentions = []
        message.channel = AsyncMock()
        message.guild = MagicMock(spec=discord.Guild)
        message.guild.id = 123
        
        # 5 messages in 5 seconds
        for i in range(5):
            await self.security_cog.on_message(message)
        
        message.author.timeout.assert_called_once()
        self.assertIn("Message flooding", message.author.timeout.call_args[1]['reason'])
        message.channel.purge.assert_called_once()

    async def test_mention_spam_timeout(self):
        message = AsyncMock(spec=discord.Message)
        message.author = AsyncMock(spec=discord.Member)
        message.author.id = 4000
        message.author.bot = False
        message.author.name = "MentionSpammer"
        message.content = "hey " + " ".join([f"<@{i}>" for i in range(6)])
        message.mentions = [MagicMock() for _ in range(6)]
        message.channel = AsyncMock()
        message.guild = MagicMock(spec=discord.Guild)
        message.guild.id = 456
        
        await self.security_cog.on_message(message)
        
        message.delete.assert_called_once()
        message.author.timeout.assert_called_once()
        self.assertIn("Mention spam", message.author.timeout.call_args[1]['reason'])

    async def test_anti_nuke_channel_delete(self):
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        guild.system_channel = AsyncMock()
        staff_member = MagicMock(spec=discord.Member)
        staff_member.bot = False
        staff_member.id = 5000
        staff_member.name = "BadStaff"
        staff_member.roles = [MagicMock(spec=discord.Role)]
        staff_member.roles[0].permissions.administrator = True
        
        guild.get_member.return_value = staff_member
        
        # Mock audit logs
        entry = MagicMock()
        entry.user = staff_member
        entry.created_at = discord.utils.utcnow()
        
        async def mock_audit_logs(*args, **kwargs):
            yield entry

        guild.audit_logs = mock_audit_logs
        
        channel = MagicMock(spec=discord.TextChannel)
        channel.guild = guild
        
        # 3 deletions
        for i in range(3):
            await self.security_cog.on_guild_channel_delete(channel)
            
        staff_member.remove_roles.assert_called_once()
        guild.system_channel.send.assert_called()
        self.assertIn("NUKE ATTEMPT", guild.system_channel.send.call_args[0][0])

    async def test_raidmode_command(self):
        ctx = AsyncMock()
        ctx.guild.id = 888
        ctx.guild.name = "Test Guild"
        await self.security_cog.raidmode.callback(self.security_cog, ctx, True)
        self.assertTrue(self.security_cog.raid_modes[ctx.guild.id])
        ctx.send.assert_called_with("✅ Raid Mode has been **enabled** for this server.")
        
        await self.security_cog.raidmode.callback(self.security_cog, ctx, False)
        self.assertFalse(self.security_cog.raid_modes[ctx.guild.id])
        ctx.send.assert_called_with("✅ Raid Mode has been **disabled** for this server.")

if __name__ == '__main__':
    unittest.main()
