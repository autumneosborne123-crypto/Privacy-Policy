import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import os
import json
from datetime import datetime, timedelta, timezone

# Set dummy environment variable for bot token
os.environ['DISCORD_TOKEN'] = 'dummy_token'

from cogs.config import ConfigCog
from utils.config import Config

class TestWelcomeGoodbye(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config_file = "test_config.json"
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
            
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.config = Config(self.config_file)
        self.bot.db = AsyncMock()
        self.config_cog = ConfigCog(self.bot)

    async def asyncTearDown(self):
        if os.path.exists(self.config_file):
            os.remove(self.config_file)

    async def test_set_welcome_commands(self):
        mock_ctx = AsyncMock()
        mock_ctx.guild.id = 123
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = 111
        mock_channel.mention = "<#111>"
        
        # Test set_welcome (channel)
        await self.config_cog.set_welcome.callback(self.config_cog, mock_ctx, mock_channel)
        self.bot.db.set_guild_setting.assert_called_with(123, "welcome_channel_id", "111")
        
        # Test set_welcome_message
        await self.config_cog.set_welcome_message.callback(self.config_cog, mock_ctx, message="Welcome {member} to {guild}!")
        self.bot.db.set_guild_setting.assert_called_with(123, "welcome_message", "Welcome {member} to {guild}!")

    async def test_set_goodbye_commands(self):
        mock_ctx = AsyncMock()
        mock_ctx.guild.id = 123
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = 222
        mock_channel.mention = "<#222>"
        
        # Test set_goodbye (channel)
        await self.config_cog.set_goodbye.callback(self.config_cog, mock_ctx, mock_channel)
        self.bot.db.set_guild_setting.assert_called_with(123, "goodbye_channel_id", "222")
        
        # Test set_goodbye_message
        await self.config_cog.set_goodbye_message.callback(self.config_cog, mock_ctx, message="Bye {member}!")
        self.bot.db.set_guild_setting.assert_called_with(123, "goodbye_message", "Bye {member}!")

    async def test_on_member_join_configurable(self):
        # Setup mock db
        async def mock_get_setting(guild_id, key):
            settings = {
                "welcome_channel_id": "111",
                "welcome_message": "Welcome {member} to {guild}!"
            }
            return settings.get(key)
        self.bot.db.get_guild_setting.side_effect = mock_get_setting
        
        mock_member = MagicMock(spec=discord.Member)
        mock_member.bot = False
        mock_member.id = 123
        mock_member.name = "TestUser"
        mock_member.mention = "@User"
        mock_member.guild.id = 123
        mock_member.guild.name = "TestGuild"
        mock_member.guild.get_member.return_value = mock_member
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        self.bot.get_channel.return_value = mock_channel
        
        # We need to bypass the asyncio.sleep(1) in on_member_join
        with patch('asyncio.sleep', return_value=None):
            await self.config_cog.on_member_join(member=mock_member)
            mock_channel.send.assert_called_once_with("Welcome @User to TestGuild!")

    async def test_on_member_remove_configurable(self):
        # Setup mock db
        async def mock_get_setting(guild_id, key):
            settings = {
                "goodbye_channel_id": "222",
                "goodbye_message": "Goodbye {member} from {guild}!"
            }
            return settings.get(key)
        self.bot.db.get_guild_setting.side_effect = mock_get_setting
        
        mock_member = MagicMock(spec=discord.Member)
        mock_member.mention = "@User"
        mock_member.guild.id = 123
        mock_member.guild.name = "TestGuild"
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        self.bot.get_channel.return_value = mock_channel
        
        await self.config_cog.on_member_remove(member=mock_member)
        mock_channel.send.assert_called_once_with("Goodbye @User from TestGuild!")

    async def test_no_message_if_not_configured(self):
        # Config is empty
        self.bot.db.get_guild_setting.return_value = None
        
        mock_member = MagicMock(spec=discord.Member)
        mock_member.bot = False
        mock_member.id = 123
        mock_member.name = "TestUser"
        mock_member.guild.id = 123
        mock_member.guild.get_member.return_value = mock_member
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        self.bot.get_channel.return_value = mock_channel
        
        with patch('asyncio.sleep', return_value=None):
            await self.config_cog.on_member_join(member=mock_member)
            mock_channel.send.assert_not_called()
            
            await self.config_cog.on_member_remove(member=mock_member)
            mock_channel.send.assert_not_called()

if __name__ == '__main__':
    unittest.main()
