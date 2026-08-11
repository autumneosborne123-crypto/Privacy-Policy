import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import os
import json
import aiohttp

# Set dummy environment variable for bot token
os.environ['DISCORD_TOKEN'] = 'dummy_token'

from cogs.fun import Fun
from cogs.config import ConfigCog
from utils.config import Config
from utils.database import Database

class TestDailyEncouragement(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_file = "test_quotes_legacy.db"
        if os.path.exists(self.db_file):
            os.remove(self.db_file)
            
        self.db = Database(self.db_file)
        await self.db.init()
        
        self.config_file = "test_config_daily.json"
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
            
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.db = self.db
        self.bot.config = Config(self.config_file)
        
        self.config_cog = ConfigCog(self.bot)
        with patch('discord.ext.tasks.Loop.start'):
            self.fun_cog = Fun(self.bot)

    async def asyncTearDown(self):
        if os.path.exists(self.db_file):
            os.remove(self.db_file)
        if os.path.exists(self.config_file):
            os.remove(self.config_file)

    async def test_set_inspirational_quotes_command(self):
        mock_ctx = AsyncMock()
        mock_ctx.guild.id = 123
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = 123456789
        mock_channel.mention = "<#123456789>"
        
        await self.config_cog.quotes.callback(self.config_cog, mock_ctx, channel=mock_channel)
        
        # Check if DB was updated
        feeds = await self.db.get_quote_feeds()
        self.assertIn(("123", "123456789"), feeds)
        
        mock_ctx.send.assert_called_once()
        self.assertIn("Inspirational quotes will now be sent to <#123456789>", mock_ctx.send.call_args[0][0])

    @patch('aiohttp.ClientSession.get')
    async def test_send_daily_quote_task_logic_success(self, mock_get):
        # Setup DB feed
        await self.db.set_quote_feed("123", "123")
        
        # Mock successful API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = [{"q": "Test Quote", "a": "Test Author"}]
        mock_get.return_value.__aenter__.return_value = mock_response
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        self.bot.get_channel.return_value = mock_channel
        
        await self.fun_cog.send_daily_quote()
        
        mock_channel.send.assert_called_once()
        embed = mock_channel.send.call_args[1]['embed']
        self.assertEqual(embed.title, "🌟 Inspiration")
        self.assertEqual(embed.description, '"Test Quote" — *Test Author*')

    @patch('aiohttp.ClientSession.get')
    async def test_send_daily_quote_task_logic_failure(self, mock_get):
        # Setup DB feed
        await self.db.set_quote_feed("123", "123")
        
        # Mock failed API response
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_get.return_value.__aenter__.return_value = mock_response
        
        mock_channel = AsyncMock(spec=discord.TextChannel)
        self.bot.get_channel.return_value = mock_channel
        
        await self.fun_cog.send_daily_quote()
        
        mock_channel.send.assert_called_once()
        embed = mock_channel.send.call_args[1]['embed']
        self.assertIn("Believe in yourself", embed.description)

    def test_quote_loop_interval(self):
        self.assertEqual(self.fun_cog.send_daily_quote.minutes, 150)

    async def test_permissions(self):
        from utils.permissions import is_admin_or_moderator
        
        # Mock Context
        ctx = AsyncMock()
        ctx.guild = MagicMock()
        
        # 1. Administrator permission
        ctx.author.guild_permissions.administrator = True
        predicate = is_admin_or_moderator().predicate
        self.assertTrue(await predicate(ctx))
        
        # 2. "Admins" role
        ctx.author.guild_permissions.administrator = False
        admin_role = MagicMock()
        admin_role.name = "Admins"
        ctx.guild.roles = [admin_role]
        ctx.author.roles = [admin_role]
        with patch('discord.utils.get', return_value=admin_role):
            self.assertTrue(await predicate(ctx))
            
        # 3. No permission/role
        ctx.author.roles = []
        with patch('discord.utils.get', return_value=None):
            self.assertFalse(await predicate(ctx))

if __name__ == '__main__':
    unittest.main()
