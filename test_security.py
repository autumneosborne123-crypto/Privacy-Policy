import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from datetime import datetime, timedelta, timezone
import os

# Set dummy environment variable for bot token
os.environ['DISCORD_TOKEN'] = 'dummy_token'

from cogs.security import Security

class TestSecurity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.db = AsyncMock()
        # Default return value for settings to avoid coroutine issues in tests
        self.bot.db.get_all_guild_settings.return_value = {}
        self.bot.user = MagicMock(spec=discord.ClientUser)
        self.bot.user.id = 999
        self.bot.whitelisted_bots = [422087909634736160]
        self.bot.get_log_channel = AsyncMock(return_value=None)
        self.bot.log_action = AsyncMock()
        self.security_cog = Security(self.bot)

    async def test_is_suspicious_bot_true(self):
        mock_member = MagicMock(spec=discord.Member)
        # Less than 1 hour old
        mock_member.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        mock_member.avatar = None
        mock_member.name = "bot_123"
        
        self.assertTrue(self.security_cog.is_suspicious_bot(mock_member))

    async def test_is_suspicious_bot_false_old_account(self):
        mock_member = MagicMock(spec=discord.Member)
        # 2 days old
        mock_member.created_at = datetime.now(timezone.utc) - timedelta(days=2)
        mock_member.avatar = None
        mock_member.name = "real_user"
        
        self.assertFalse(self.security_cog.is_suspicious_bot(mock_member))

    async def test_is_suspicious_bot_false_with_avatar(self):
        mock_member = MagicMock(spec=discord.Member)
        mock_member.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        mock_member.avatar = MagicMock()
        mock_member.name = "new_user_with_pic"
        
        self.assertFalse(self.security_cog.is_suspicious_bot(mock_member))

    async def test_is_suspicious_bot_hex_name(self):
        mock_member = MagicMock(spec=discord.Member)
        mock_member.created_at = datetime.now(timezone.utc) - timedelta(days=5)
        mock_member.avatar = None
        # 32 chars hex string
        mock_member.name = "a" * 32 
        
        self.assertTrue(self.security_cog.is_suspicious_bot(mock_member))

    async def test_on_member_join_suspicious_ban(self):
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.bot = False
        mock_member.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        mock_member.avatar = None
        mock_member.name = "fake_bot"
        
        await self.security_cog.on_member_join(mock_member)
        
        mock_member.ban.assert_called_once()
        self.assertIn("Suspicious account", mock_member.ban.call_args[1]['reason'])

    async def test_on_message_scam_ban_domain(self):
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = AsyncMock(spec=discord.Member)
        mock_message.author.bot = False
        mock_message.author.name = "scammer"
        mock_message.content = "FREE NITRO! Click here: http://dlscord.gift/nitro"
        
        await self.security_cog.on_message(mock_message)
        
        mock_message.delete.assert_called_once()
        mock_message.author.ban.assert_called_once_with(reason="Auto-ban: Scam account/content")

    async def test_on_message_scam_pattern_nitro_everyone(self):
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = AsyncMock(spec=discord.Member)
        mock_message.author.bot = False
        mock_message.content = "@everyone GET FREE NITRO FAST"
        
        await self.security_cog.on_message(mock_message)
        
        mock_message.author.ban.assert_called_once()

    async def test_on_message_legit_message(self):
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = AsyncMock(spec=discord.Member)
        mock_message.author.bot = False
        mock_message.content = "Hello world!"
        
        await self.security_cog.on_message(mock_message)
        
        mock_message.author.ban.assert_not_called()

    async def test_on_member_join_whitelisted_bot(self):
        # Whitelisted bot (Top.gg) - even if suspicious (new + no avatar)
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.id = 422087909634736160
        mock_member.bot = True
        mock_member.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        mock_member.avatar = None
        mock_member.name = "Top.gg"
        
        await self.security_cog.on_member_join(mock_member)
        
        mock_member.ban.assert_not_called()

    async def test_on_member_join_legit_bot(self):
        # Normal bot - old enough, has avatar
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.id = 123456789
        mock_member.bot = True
        mock_member.created_at = datetime.now(timezone.utc) - timedelta(days=30)
        mock_member.avatar = MagicMock()
        mock_member.name = "LegitBot"
        
        await self.security_cog.on_member_join(mock_member)
        
        mock_member.ban.assert_not_called()

    async def test_on_message_bot_scam_bypass(self):
        # All bots should bypass security checks now
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = AsyncMock(spec=discord.Member)
        mock_message.author.id = 888
        mock_message.author.bot = True
        mock_message.author.name = "HackedBot"
        mock_message.content = "FREE NITRO! http://dlscord.gift/nitro"
        
        await self.security_cog.on_message(mock_message)
        
        mock_message.delete.assert_not_called()
        mock_message.author.ban.assert_not_called()

    async def test_on_message_whitelisted_bot_scam_bypass(self):
        # Whitelisted bot sending scam (should bypass)
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = AsyncMock(spec=discord.Member)
        mock_message.author.id = 422087909634736160
        mock_message.author.bot = True
        mock_message.content = "FREE NITRO! http://dlscord.gift/nitro"
        
        await self.security_cog.on_message(mock_message)
        
        mock_message.author.ban.assert_not_called()

    async def test_security_status_command(self):
        ctx = AsyncMock()
        await self.security_cog.security_status.callback(self.security_cog, ctx)
        
        ctx.send.assert_called_once()
        embed = ctx.send.call_args[1]['embed']
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "🛡️ Security Status")
        # Check if "Suspicious Accounts" is mentioned instead of just "Bots"
        status_text = embed.to_dict()['fields'][0]['name']
        self.assertIn("Suspicious Accounts", status_text)

if __name__ == '__main__':
    unittest.main()
