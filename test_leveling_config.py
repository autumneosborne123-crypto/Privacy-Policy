import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import os
from cogs.leveling import Leveling
from cogs.config import ConfigCog
from utils.database import Database

class TestLevelingConfig(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_file = "test_leveling_config.db"
        if os.path.exists(self.db_file):
            os.remove(self.db_file)
            
        self.db = Database(self.db_file)
        await self.db.init()
        
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.db = self.db
        self.bot.log_action = AsyncMock()
        self.bot.fetch_channel = AsyncMock()
        self.bot.get_channel = MagicMock()
        self.bot.wait_until_ready = AsyncMock()
        self.bot.config = MagicMock()
        self.bot.user = MagicMock(spec=discord.ClientUser)
        self.bot.user.display_avatar.url = "http://example.com/avatar.png"
        self.bot.loop = asyncio.get_event_loop()
        
        self.leveling_cog = Leveling(self.bot)
        # Stop the task to avoid it running during tests and failing on mocks
        if hasattr(self.leveling_cog, 'voice_xp_task'):
            self.leveling_cog.voice_xp_task.cancel()
        
        self.config_cog = ConfigCog(self.bot)

    async def asyncTearDown(self):
        self.leveling_cog.cog_unload()
        if os.path.exists(self.db_file):
            os.remove(self.db_file)

    async def test_levelupchannel_set(self):
        """Test the levelupchannel command in Leveling cog."""
        ctx = AsyncMock()
        ctx.guild.id = 123
        ctx.author.id = 456
        ctx.author.display_name = "AdminUser"
        
        target_channel = MagicMock(spec=discord.TextChannel)
        target_channel.id = 789
        target_channel.mention = "<#789>"
        
        # Test setting the channel
        await self.leveling_cog.levelupchannel.callback(self.leveling_cog, ctx, channel=target_channel)
        
        setting = await self.db.get_guild_setting(123, "level_up_channel_id", int)
        self.assertEqual(setting, 789)
        ctx.send.assert_called_with(f"✅ Level-up notifications will now be sent to {target_channel.mention}.", ephemeral=True)
        self.bot.log_action.assert_called_with(ctx.guild, "📈 Level-Up Channel Set", f"**Channel:** {target_channel.mention}", color=0x3498db, moderator=ctx.author)

    async def test_levelupchannel_reset(self):
        """Test resetting the levelupchannel in Leveling cog."""
        ctx = AsyncMock()
        ctx.guild.id = 123
        ctx.author.id = 456
        
        # Pre-set the channel
        await self.db.set_guild_setting(123, "level_up_channel_id", "789")
        
        # Test resetting the channel
        await self.leveling_cog.levelupchannel.callback(self.leveling_cog, ctx, channel=None)
        
        setting = await self.db.get_guild_setting(123, "level_up_channel_id", int)
        self.assertIsNone(setting)
        ctx.send.assert_called_with("✅ Level-up notifications will now be sent in the channel where the user leveled up.", ephemeral=True)
        self.bot.log_action.assert_called_with(ctx.guild, "📈 Level-Up Channel Reset", "Notifications will now be sent in the original channel.", color=0xe74c3c, moderator=ctx.author)

    async def test_award_xp_notification_routing(self):
        """Test that award_xp sends notifications to the configured channel."""
        guild = MagicMock(spec=discord.Guild)
        guild.id = 123
        guild.text_channels = []
        
        member = MagicMock(spec=discord.Member)
        member.id = 456
        member.guild = guild
        member.bot = False
        member.roles = []
        member.display_avatar.url = "http://example.com/avatar.png"
        member.mention = "<@456>"
        
        target_channel = MagicMock(spec=discord.TextChannel)
        target_channel.id = 789
        target_channel.send = AsyncMock()
        
        self.bot.get_channel.side_effect = lambda cid: target_channel if cid == 789 else None
        
        await self.db.set_guild_setting(123, "level_up_channel_id", "789")
        
        # Set user level close to leveling up
        # XP to level 0 -> 1 is 100
        await self.db.update_user_data(456, 90, 0, 0, 0, 0)
        
        # Award 20 XP to trigger level up
        await self.leveling_cog.award_xp(member, 20, is_message=True, channel=MagicMock(spec=discord.TextChannel))
        
        # Check if notification was sent to target_channel
        target_channel.send.assert_called_once()
        embed = target_channel.send.call_args[1]['embed']
        self.assertIn("reached **Level 1**", embed.description)
        self.assertIn(member.mention, embed.description)

    async def test_set_leveling_channel_command(self):
        """Test the set_leveling_channel command in Config cog."""
        ctx = AsyncMock()
        ctx.guild.id = 123
        
        target_channel = MagicMock(spec=discord.TextChannel)
        target_channel.id = 111
        target_channel.mention = "<#111>"
        
        # Set channel
        await self.config_cog.set_leveling_channel.callback(self.config_cog, ctx, channel=target_channel)
        setting = await self.db.get_guild_setting(123, "leveling_channel_id", int)
        self.assertEqual(setting, 111)
        ctx.send.assert_called_with(f"Leveling commands are now restricted to {target_channel.mention}!", ephemeral=True)
        
        # Reset channel
        await self.config_cog.set_leveling_channel.callback(self.config_cog, ctx, channel=None)
        setting = await self.db.get_guild_setting(123, "leveling_channel_id", int)
        self.assertIsNone(setting)
        ctx.send.assert_called_with("Leveling commands can now be used in any channel.", ephemeral=True)

    async def test_leveling_command_restriction(self):
        """Test the is_leveling_channel check logic."""
        ctx = AsyncMock()
        ctx.bot = self.bot
        ctx.guild.id = 123
        ctx.channel.id = 888 # Current channel
        
        # Set restricted channel to 999
        await self.db.set_guild_setting(123, "leveling_channel_id", "999")
        
        restricted_channel = MagicMock(spec=discord.TextChannel)
        restricted_channel.mention = "<#999>"
        self.bot.get_channel.side_effect = lambda cid: restricted_channel if cid == 999 else None
        
        # Test the predicate
        check_decorator = Leveling.is_leveling_channel()
        predicate = check_decorator.predicate
        
        # In wrong channel
        result = await predicate(ctx)
        self.assertFalse(result)
        ctx.send.assert_called_with("❌ Leveling commands are restricted to <#999>.", ephemeral=True)
        
        # In right channel
        ctx.channel.id = 999
        result = await predicate(ctx)
        self.assertTrue(result)
        
        # When no restriction is set
        await self.db.set_guild_setting(123, "leveling_channel_id", None)
        ctx.channel.id = 888
        result = await predicate(ctx)
        self.assertTrue(result)

    async def test_settings_display(self):
        """Test that the settings command correctly displays leveling configurations."""
        ctx = AsyncMock()
        ctx.guild.id = 123
        
        # Set settings
        await self.db.set_guild_setting(123, "level_up_channel_id", "789")
        await self.db.set_guild_setting(123, "leveling_channel_id", "111")
        
        # Mock bot.get_channel
        l_chan = MagicMock(spec=discord.TextChannel)
        l_chan.mention = "<#789>"
        lc_chan = MagicMock(spec=discord.TextChannel)
        lc_chan.mention = "<#111>"
        
        def get_chan_mock(cid):
            if cid == 789: return l_chan
            if cid == 111: return lc_chan
            return None
        
        self.bot.get_channel.side_effect = get_chan_mock
        
        await self.config_cog.settings.callback(self.config_cog, ctx)
        
        ctx.send.assert_called_once()
        embed = ctx.send.call_args[1]['embed']
        
        leveling_field = next(f for f in embed.fields if f.name == "📈 Leveling")
        self.assertIn("<#789>", leveling_field.value)
        self.assertIn("<#111>", leveling_field.value)

    async def test_award_xp_fallback_to_original(self):
        """Test that award_xp falls back to original channel if target channel is missing."""
        guild = MagicMock(spec=discord.Guild)
        guild.id = 123
        guild.text_channels = []
        
        member = MagicMock(spec=discord.Member)
        member.id = 456
        member.guild = guild
        member.bot = False
        member.roles = []
        member.display_avatar.url = "http://example.com/avatar.png"
        member.mention = "<@456>"
        
        original_channel = MagicMock(spec=discord.TextChannel)
        original_channel.id = 111
        original_channel.send = AsyncMock()
        
        # Configure target channel ID in DB but make bot not find it
        await self.db.set_guild_setting(123, "level_up_channel_id", "999")
        self.bot.get_channel.return_value = None
        self.bot.fetch_channel.side_effect = Exception("Channel not found")
        
        # Set user level close to leveling up
        await self.db.update_user_data(456, 90, 0, 0, 0, 0)
        
        # Award XP
        await self.leveling_cog.award_xp(member, 20, is_message=True, channel=original_channel)
        
        # Should fallback to original_channel
        original_channel.send.assert_called_once()
        embed = original_channel.send.call_args[1]['embed']
        self.assertIn("reached **Level 1**", embed.description)

    async def test_award_xp_forbidden_target(self):
        """Test that award_xp doesn't crash if it cannot send to target channel."""
        guild = MagicMock(spec=discord.Guild)
        guild.id = 123
        guild.text_channels = []
        
        member = MagicMock(spec=discord.Member)
        member.id = 456
        member.guild = guild
        member.bot = False
        member.roles = []
        member.display_avatar.url = "http://example.com/avatar.png"
        
        target_channel = MagicMock(spec=discord.TextChannel)
        target_channel.id = 789
        target_channel.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Forbidden"))
        
        self.bot.get_channel.return_value = target_channel
        await self.db.set_guild_setting(123, "level_up_channel_id", "789")
        
        await self.db.update_user_data(456, 90, 0, 0, 0, 0)
        
        # Should not raise exception
        await self.leveling_cog.award_xp(member, 20, is_message=True, channel=MagicMock(spec=discord.TextChannel))
        
        target_channel.send.assert_called_once()

    async def test_is_leveling_channel_missing_channel_mention(self):
        """Test is_leveling_channel check when the restricted channel is deleted."""
        ctx = AsyncMock()
        ctx.bot = self.bot
        ctx.guild.id = 123
        ctx.channel.id = 888
        
        await self.db.set_guild_setting(123, "leveling_channel_id", "999")
        self.bot.get_channel.return_value = None
        
        check_decorator = Leveling.is_leveling_channel()
        predicate = check_decorator.predicate
        
        result = await predicate(ctx)
        self.assertFalse(result)
        ctx.send.assert_called_with("❌ Leveling commands are restricted to <#999>.", ephemeral=True)

if __name__ == '__main__':
    unittest.main()
