import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import os
import shutil

# Set dummy environment variable for bot token
os.environ['DISCORD_TOKEN'] = 'dummy_token'

from cogs.music import Music

class TestMusicCommands(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.loop = asyncio.get_running_loop()
        self.bot.db = AsyncMock()
        self.bot.db.get_guild_setting = AsyncMock(return_value=None)
        self.bot.get_channel = MagicMock() # get_channel is not async
        self.music_cog = Music(self.bot)

    def mock_context(self):
        mock_ctx = AsyncMock()
        mock_ctx.bot = self.bot
        mock_ctx.guild.id = 123
        mock_ctx.channel.name = 'music' # Pass is_music_channel check
        return mock_ctx

    @patch('shutil.which', return_value='/usr/bin/ffmpeg')
    async def test_music_play_no_voice(self, mock_which):
        mock_ctx = self.mock_context()
        mock_ctx.author.voice = None
        await self.music_cog.play.callback(self.music_cog, mock_ctx, query="test song")
        mock_ctx.send.assert_called_with("❌ You must be in a voice channel!")

    @patch('shutil.which', return_value='/usr/bin/ffmpeg')
    @patch('yt_dlp.YoutubeDL')
    async def test_music_play_success(self, mock_ytdl_class, mock_which):
        mock_ctx = self.mock_context()
        mock_ctx.author.voice.channel = AsyncMock()
        
        # typing() returns an async context manager
        mock_ctx.typing = MagicMock()
        mock_ctx.typing.return_value = AsyncMock()
        
        # Mock voice client
        mock_vc = MagicMock(spec=discord.VoiceClient)
        mock_vc.is_playing.return_value = False
        mock_vc.is_paused.return_value = False
        mock_ctx.voice_client = mock_vc
        
        mock_extract = mock_ytdl_class.return_value.__enter__.return_value.extract_info
        mock_extract.return_value = {'title': 'Test Song', 'webpage_url': 'http://test.com', 'thumbnail': 'http://thumb.com', 'url': 'http://stream.com'}
        
        with patch.object(self.bot.loop, 'run_in_executor', AsyncMock(return_value=mock_extract.return_value)):
            with patch.object(self.music_cog, 'play_next', AsyncMock()) as mock_play_next:
                await self.music_cog.play.callback(self.music_cog, mock_ctx, query="test song")
                mock_play_next.assert_called_once()

    async def test_music_skip_no_playing(self):
        mock_ctx = self.mock_context()
        mock_vc = MagicMock(spec=discord.VoiceClient)
        mock_vc.is_playing.return_value = False
        mock_ctx.voice_client = mock_vc
        await self.music_cog.skip.callback(self.music_cog, mock_ctx)
        mock_ctx.send.assert_called_with("❌ Nothing is playing.")

    async def test_music_skip_success(self):
        mock_ctx = self.mock_context()
        mock_vc = MagicMock(spec=discord.VoiceClient)
        mock_vc.is_playing.return_value = True
        mock_ctx.voice_client = mock_vc
        await self.music_cog.skip.callback(self.music_cog, mock_ctx)
        mock_vc.stop.assert_called_once()
        mock_ctx.send.assert_called_with("⏭️ Skipped!")

    async def test_music_stop_success(self):
        mock_ctx = self.mock_context()
        mock_vc = AsyncMock(spec=discord.VoiceClient)
        mock_ctx.voice_client = mock_vc
        await self.music_cog.stop.callback(self.music_cog, mock_ctx)
        mock_vc.disconnect.assert_called_once()
        mock_ctx.send.assert_called_with("⏹️ Stopped and disconnected.")

    async def test_music_shuffle_empty(self):
        mock_ctx = self.mock_context()
        await self.music_cog.shuffle.callback(self.music_cog, mock_ctx)
        mock_ctx.send.assert_called_with("❌ Empty queue.")

    async def test_music_clear_queue(self):
        mock_ctx = self.mock_context()
        self.music_cog.queues[123] = [{'title': 'Song 1'}]
        await self.music_cog.clear.callback(self.music_cog, mock_ctx)
        self.assertEqual(self.music_cog.queues[123], [])
        mock_ctx.send.assert_called_with("🗑️ Queue cleared!")

    async def test_music_queue_empty(self):
        mock_ctx = self.mock_context()
        await self.music_cog.queue.callback(self.music_cog, mock_ctx)
        mock_ctx.send.assert_called_with("❌ Queue is empty.")

    async def test_music_nowplaying_empty(self):
        mock_ctx = self.mock_context()
        mock_vc = MagicMock()
        mock_vc.is_playing.return_value = False
        mock_ctx.voice_client = mock_vc
        await self.music_cog.nowplaying.callback(self.music_cog, mock_ctx)
        mock_ctx.send.assert_called_with("❌ Nothing playing.")

    async def test_is_music_channel_failure(self):
        mock_ctx = self.mock_context()
        mock_ctx.channel.name = 'general'
        mock_ctx.author.voice = None
        
        # Test the decorator predicate directly
        check = Music.is_music_channel().predicate
        result = await check(mock_ctx)
        self.assertFalse(result)
        mock_ctx.send.assert_called()

    async def test_music_volume_command(self):
        mock_ctx = self.mock_context()
        mock_ctx.voice_client = MagicMock()
        mock_ctx.voice_client.source = MagicMock()
        
        await self.music_cog.volume.callback(self.music_cog, mock_ctx, level=75)
        self.assertEqual(self.music_cog.volumes[123], 0.75)
        self.assertEqual(mock_ctx.voice_client.source.volume, 0.75)
        mock_ctx.send.assert_called_with("🔊 Volume set to **75%**")

    async def test_music_loop_command(self):
        mock_ctx = self.mock_context()
        # Toggle on
        await self.music_cog.loop.callback(self.music_cog, mock_ctx)
        self.assertTrue(self.music_cog.loops[123])
        mock_ctx.send.assert_called_with("🔄 Loop **enabled**")
        # Toggle off
        await self.music_cog.loop.callback(self.music_cog, mock_ctx)
        self.assertFalse(self.music_cog.loops[123])
        mock_ctx.send.assert_called_with("🔄 Loop **disabled**")

    @patch('shutil.which', return_value='/usr/bin/ffmpeg')
    @patch('yt_dlp.YoutubeDL')
    async def test_music_playnext_command(self, mock_ytdl_class, mock_which):
        mock_ctx = self.mock_context()
        mock_ctx.author.voice.channel = AsyncMock()
        
        # Correctly mock typing as an async context manager
        mock_ctx.typing = MagicMock()
        mock_ctx.typing.return_value = AsyncMock()
        
        mock_vc = MagicMock(spec=discord.VoiceClient)
        mock_vc.is_playing.return_value = True
        mock_ctx.voice_client = mock_vc
        
        mock_extract = mock_ytdl_class.return_value.__enter__.return_value.extract_info
        mock_extract.return_value = {'title': 'Next Song', 'webpage_url': 'http://test.com', 'url': 'http://stream.com'}
        self.music_cog.queues[123] = [{'title': 'Existing Song'}]
        
        with patch.object(self.bot.loop, 'run_in_executor', AsyncMock(return_value=mock_extract.return_value)):
            await self.music_cog.playnext.callback(self.music_cog, mock_ctx, query="next song")
            # Check if it was inserted at the beginning
            self.assertEqual(self.music_cog.queues[123][0]['title'], 'Next Song')
            mock_ctx.send.assert_called_with("⏭️ Playing **Next Song** next.")

if __name__ == '__main__':
    unittest.main()
