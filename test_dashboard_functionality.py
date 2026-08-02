import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
import discord
import os
import sys

# Add project root to path to ensure imports work
sys.path.append(os.getcwd())

from cogs.dashboard import Dashboard

class TestDashboardFunctionality(unittest.IsolatedAsyncioTestCase):
    @patch('cogs.dashboard.Dashboard.start_server', return_value=AsyncMock())
    async def asyncSetUp(self, mock_start):
        self.bot = MagicMock()
        self.bot.db = AsyncMock()
        self.bot.loop = MagicMock()
        self.bot.cogs = {}
        
        # Mock DISCORD_CLIENT_ID to avoid error in init if needed
        with patch.dict(os.environ, {"DISCORD_CLIENT_ID": "123", "DISCORD_CLIENT_SECRET": "secret"}):
            self.cog = Dashboard(self.bot)
            
        # Patch get_admin_member globally for tests
        self.cog.get_admin_member = AsyncMock()
        self.mock_member = MagicMock()
        self.cog.get_admin_member.return_value = self.mock_member

    async def test_handle_guild_update(self):
        # Test with values
        request = MagicMock(spec=web.Request)
        request.match_info = {'guild_id': '123456789'}
        request.query = {'token': 'fake_token'}
        request.post = AsyncMock(return_value={
            'log_channel_id': '987654321',
            'mute_role_id': '1122334455'
        })

        response = await self.cog.handle_guild_update(request)

        self.bot.db.set_guild_setting.assert_any_call('123456789', 'log_channel_id', '987654321')
        self.bot.db.set_guild_setting.assert_any_call('123456789', 'mute_role_id', '1122334455')
        self.assertIsInstance(response, web.HTTPFound)
        self.assertEqual(response.location, '/guild/123456789?token=fake_token&success=true')

        # Test with empty strings (should become None)
        request.post = AsyncMock(return_value={
            'log_channel_id': '',
            'mute_role_id': ''
        })
        await self.cog.handle_guild_update(request)
        self.bot.db.set_guild_setting.assert_any_call('123456789', 'log_channel_id', None)
        self.bot.db.set_guild_setting.assert_any_call('123456789', 'mute_role_id', None)

    async def test_handle_guild_update_modules(self):
        request = MagicMock(spec=web.Request)
        request.match_info = {'guild_id': '123456789'}
        request.query = {'token': 'fake_token'}
        
        # Mock cogs
        cog1 = MagicMock()
        cog1.qualified_name = "Moderation"
        cog1.__module__ = "cogs.moderation"
        
        cog2 = MagicMock()
        cog2.qualified_name = "Music"
        cog2.__module__ = "cogs.music"

        cog3 = MagicMock()
        cog3.qualified_name = "Dashboard"
        cog3.__module__ = "cogs.dashboard"
        
        cog4 = MagicMock()
        cog4.qualified_name = "System"
        cog4.__module__ = "cogs.system"
        
        self.bot.cogs = {
            "Moderation": cog1, 
            "Music": cog2, 
            "Dashboard": cog3,
            "System": cog4
        }
        self.bot.get_cog.side_effect = lambda name: self.bot.cogs.get(name)

        # Disable Moderation (cog_Moderation not in POST), keep Music
        # Dashboard and System should be ignored even if not in POST
        request.post = AsyncMock(return_value={
            'cog_Music': 'on'
        })

        response = await self.cog.handle_guild_update_modules(request)

        # Result should only contain Moderation's module
        self.bot.db.set_guild_setting.assert_called_with('123456789', 'disabled_cogs', 'cogs.moderation')
        self.assertIsInstance(response, web.HTTPFound)

    async def test_handle_guild_update_welcome(self):
        request = MagicMock(spec=web.Request)
        request.match_info = {'guild_id': '123456789'}
        request.query = {'token': 'fake_token'}
        request.post = AsyncMock(return_value={
            'welcome_channel_id': '111',
            'welcome_message': 'Welcome {user}!',
            'goodbye_channel_id': '222',
            'goodbye_message': 'Bye {user}!'
        })

        response = await self.cog.handle_guild_update_welcome(request)

        self.bot.db.set_guild_setting.assert_any_call('123456789', 'welcome_channel_id', '111')
        self.bot.db.set_guild_setting.assert_any_call('123456789', 'welcome_message', 'Welcome {user}!')
        self.bot.db.set_guild_setting.assert_any_call('123456789', 'goodbye_channel_id', '222')
        self.bot.db.set_guild_setting.assert_any_call('123456789', 'goodbye_message', 'Bye {user}!')
        self.assertIsInstance(response, web.HTTPFound)

    async def test_handle_send_embed(self):
        request = MagicMock(spec=web.Request)
        request.match_info = {'guild_id': '123456789'}
        request.query = {'token': 'fake_token'}
        request.post = AsyncMock(return_value={
            'channel_id': '444',
            'title': 'Test Title',
            'description': 'Test Description',
            'color': '#ff0000',
            'footer': 'Test Footer'
        })

        guild = MagicMock()
        channel = AsyncMock()
        self.mock_member.guild = guild
        guild.get_channel.return_value = channel

        response = await self.cog.handle_send_embed(request)

        guild.get_channel.assert_called_with(444)
        
        # Verify channel.send was called with an embed
        args, kwargs = channel.send.call_args
        embed = kwargs.get('embed')
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, 'Test Title')
        self.assertEqual(embed.description, 'Test Description')
        self.assertEqual(embed.color.value, 0xff0000)
        self.assertEqual(embed.footer.text, 'Test Footer')
        
        self.assertIsInstance(response, web.HTTPFound)

if __name__ == '__main__':
    unittest.main()
