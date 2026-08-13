import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import time
import os
from utils.database import Database
from cogs.economy import Economy
from cogs.adventure import Adventure
from cogs.music import Music, YTDLSource, FILTERS
from cogs.premium import Premium

class TestPremiumFeatures(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.db = AsyncMock()
        self.bot.loop = asyncio.get_event_loop()
        self.bot.config = MagicMock()
        
        # Mock economy data
        self.bot.db.get_economy_data = AsyncMock(return_value={
            "coins": 1000, 
            "last_daily": 0, 
            "last_rob": 0, 
            "premium_until": 0
        })
        self.bot.db.get_balance = AsyncMock(return_value=1000)
        self.bot.update_balance = AsyncMock()
        self.bot.db.update_economy_cooldown = AsyncMock()
        self.bot.db.is_user_premium = AsyncMock(return_value=False)
        self.bot.db.is_guild_premium = AsyncMock(return_value=False)
        self.bot.db.get_guild_setting = AsyncMock(return_value=None)
        self.bot.db.get_inventory = AsyncMock(return_value=[])
        self.bot.log_action = AsyncMock()
        
        self.economy_cog = Economy(self.bot)
        self.adventure_cog = Adventure(self.bot)
        self.music_cog = Music(self.bot)
        self.premium_cog = Premium(self.bot)

    async def test_premium_daily_multiplier(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        
        # Non-premium
        self.bot.db.is_user_premium.return_value = False
        await self.economy_cog.daily.callback(self.economy_cog, mock_ctx)
        
        amount_sent = self.bot.update_balance.call_args[0][1]
        self.assertTrue(200 <= amount_sent <= 500)
        
        self.bot.update_balance.reset_mock()
        
        # Premium
        self.bot.db.is_user_premium.return_value = True
        await self.economy_cog.daily.callback(self.economy_cog, mock_ctx)
        
        amount_sent_prem = self.bot.update_balance.call_args[0][1]
        self.assertTrue(400 <= amount_sent_prem <= 1000)
        self.bot.update_balance.assert_called_once()

    async def test_premium_rob_cooldown(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.id = 456
        mock_member.display_name = "Target"
        
        # Non-premium on cooldown (30 mins passed, need 60)
        self.bot.db.get_economy_data.return_value = {
            "coins": 1000, "last_daily": 0, "last_rob": time.time() - 1800, "premium_until": 0
        }
        await self.economy_cog.rob.callback(self.economy_cog, mock_ctx, mock_member)
        self.assertIn("⏳ This command is on cooldown. Try again in **29m 59s**.", mock_ctx.send.call_args[0][0])
        self.assertIn("Premium members ($5.00/mo)", mock_ctx.send.call_args[0][0])
        # No longer ephemeral after defer()
        self.assertIsNone(mock_ctx.send.call_args[1].get('ephemeral'))
        
        mock_ctx.send.reset_mock()
        
        # Premium on same cooldown (30 mins passed, only need 30)
        self.bot.db.get_economy_data.return_value = {
            "coins": 1000, "last_daily": 0, "last_rob": time.time() - 1801, "premium_until": time.time() + 3600
        }
        await self.economy_cog.rob.callback(self.economy_cog, mock_ctx, mock_member)
        # Should proceed to rob, not send cooldown msg
        if mock_ctx.send.called:
             self.assertNotEqual(mock_ctx.send.call_args[0][0][:2], "⏳ ")

    async def test_premium_adventure_odds(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        self.bot.db.get_inventory.return_value = [('bait', 1, 'Common')]
        self.bot.db.remove_item.return_value = True
        
        with patch('random.random', side_effect=[0.95, 0.1]): # 0.95 for rarity (Legendary), 0.1 for catch success
            # Premium
            self.bot.db.is_user_premium.return_value = True
            await self.adventure_cog.catch.callback(self.adventure_cog, mock_ctx)
            # Verify it tried to add an animal
            self.bot.db.add_animal.assert_called_once()
            kwargs = self.bot.db.add_animal.call_args[1]
            self.assertEqual(kwargs.get('rarity'), "Legendary")

    async def test_music_filter_premium_check(self):
        mock_ctx = AsyncMock()
        mock_ctx.guild.id = 123
        
        # Non-premium
        self.bot.db.is_guild_premium.return_value = False
        await self.music_cog.apply_filter.callback(self.music_cog, mock_ctx, "bassboost")
        self.assertIn("Server Premium", mock_ctx.send.call_args[0][0])
        
        mock_ctx.send.reset_mock()
        
        # Premium
        self.bot.db.is_guild_premium.return_value = True
        await self.music_cog.apply_filter.callback(self.music_cog, mock_ctx, "bassboost")
        self.assertIn("Applied **bassboost**", mock_ctx.send.call_args[0][0])
        self.assertEqual(self.music_cog.active_filters.get(123), "bassboost")

    async def test_ytdl_source_filter_applied(self):
        data = {'url': 'http://example.com/stream.mp3', 'title': 'Test Song', 'formats': []}
        mock_source = MagicMock(spec=discord.AudioSource)
        mock_source.is_opus.return_value = False
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_ydl_instance = mock_ytdl.return_value.__enter__.return_value
            mock_ydl_instance.extract_info.return_value = data
            
            with patch('discord.FFmpegPCMAudio', return_value=mock_source) as mock_ffmpeg:
                await YTDLSource.from_url('http://example.com/stream.mp3', stream=True, audio_filter='bassboost')
                args, kwargs = mock_ffmpeg.call_args
                self.assertIn('aresample=async=1,bass=g=20,dynaudnorm=f=200', kwargs.get('options', ''))

    async def test_play_next_passes_filter(self):
        mock_ctx = AsyncMock()
        mock_ctx.guild.id = 123
        mock_ctx.voice_client = MagicMock()
        self.music_cog.queues[123] = [{'title': 'Song 1', 'url': 'http://link.com', 'webpage_url': 'http://web.com'}]
        self.music_cog.active_filters[123] = 'bassboost'
        
        with patch.object(YTDLSource, 'from_url', new_callable=AsyncMock) as mock_from_url:
            mock_from_url.return_value = MagicMock(spec=YTDLSource)
            await self.music_cog.play_next(mock_ctx)
            self.assertEqual(mock_from_url.call_args[1].get('audio_filter'), 'bassboost')

    async def test_music_247_premium_check(self):
        mock_ctx = AsyncMock()
        mock_ctx.guild.id = 123
        
        # Mock the music command group and 247 subcommand
        # Since it's a hybrid group, we can just call the callback
        
        # Non-premium
        self.bot.db.is_guild_premium.return_value = False
        await self.music_cog.toggle_247.callback(self.music_cog, mock_ctx)
        self.assertIn("Server Premium", mock_ctx.send.call_args[0][0])
        
        mock_ctx.send.reset_mock()
        
        # Premium
        self.bot.db.is_guild_premium.return_value = True
        await self.music_cog.toggle_247.callback(self.music_cog, mock_ctx)
        self.bot.db.set_guild_setting.assert_called()
        self.assertIn("24/7 Mode", mock_ctx.send.call_args[0][0])

    async def test_premium_status_command(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        mock_ctx.guild.id = 456
        mock_ctx.invoked_subcommand = None
        
        self.bot.db.get_economy_data.return_value = {"premium_until": time.time() + 3600}
        self.bot.db.get_guild_setting.return_value = str(time.time() + 3600)
        
        await self.premium_cog.premium.callback(self.premium_cog, mock_ctx)
        
        mock_ctx.send.assert_called_once()
        embed = mock_ctx.send.call_args[1].get('embed')
        self.assertIsNotNone(embed)
        self.assertIn("✅ Active", embed.fields[0].value) # User
        self.assertIn("✅ Active", embed.fields[1].value) # Guild

    async def test_grant_premium_command(self):
        mock_ctx = AsyncMock()
        self.bot.db.set_user_premium = AsyncMock()
        self.bot.db.set_guild_premium = AsyncMock()
        
        # Grant to user
        await self.premium_cog.grant_premium.callback(self.premium_cog, mock_ctx, "123", 30, "user")
        self.bot.db.set_user_premium.assert_called_once_with("123", 30)
        mock_ctx.send.assert_called_with("✅ Granted **30 days** of Premium to User **123**.")
        
        mock_ctx.send.reset_mock()
        
        # Grant to guild
        await self.premium_cog.grant_premium.callback(self.premium_cog, mock_ctx, "456", 30, "guild")
        self.bot.db.set_guild_premium.assert_called_once_with("456", 30)
        mock_ctx.send.assert_called_with("✅ Granted **30 days** of Premium to Guild **456**.")

    async def test_premium_buy_command(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        
        await self.premium_cog.buy_premium.callback(self.premium_cog, mock_ctx)
        
        mock_ctx.send.assert_called_once()
        embed = mock_ctx.send.call_args[1].get('embed')
        self.assertIn("CashApp", embed.description)
        self.assertIn("$Amaryyy5", embed.description)
        self.assertIn("123", embed.description) # Author ID in note instruction

if __name__ == '__main__':
    unittest.main()
