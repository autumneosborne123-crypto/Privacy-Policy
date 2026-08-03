import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import os
import json

# Set dummy environment variable for bot token
os.environ['DISCORD_TOKEN'] = 'dummy_token'

from cogs.music import Music, YTDLSource

class TestMusicUpdates(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.loop = asyncio.get_running_loop()
        self.bot.config = MagicMock()
        self.bot.config.get = MagicMock(return_value=None)
        self.bot.db = AsyncMock() # Mock the database
        self.music_cog = Music(self.bot)

    def mock_context(self):
        mock_ctx = AsyncMock()
        mock_ctx.bot = self.bot
        mock_ctx.guild.id = 123
        mock_ctx.guild.roles = []
        mock_ctx.author.id = 456
        mock_ctx.author.roles = []
        mock_ctx.author.guild_permissions.administrator = False
        mock_ctx.channel.name = 'music'
        return mock_ctx

    async def test_dj_restriction_fail(self):
        mock_ctx = self.mock_context()
        # Create a DJ role that the user doesn't have
        dj_role = MagicMock(spec=discord.Role)
        dj_role.name = "DJ"
        mock_ctx.guild.roles = [dj_role]
        
        # Test skip command which is restricted
        check = Music.is_dj().predicate
        result = await check(mock_ctx)
        self.assertFalse(result)
        mock_ctx.send.assert_called_with("❌ This command is restricted to DJs.", ephemeral=True)

    async def test_dj_restriction_pass_with_role(self):
        mock_ctx = self.mock_context()
        dj_role = MagicMock(spec=discord.Role)
        dj_role.name = "DJ"
        mock_ctx.guild.roles = [dj_role]
        mock_ctx.author.roles = [dj_role]
        
        check = Music.is_dj().predicate
        result = await check(mock_ctx)
        self.assertTrue(result)

    async def test_dj_restriction_pass_admin(self):
        mock_ctx = self.mock_context()
        mock_ctx.author.guild_permissions.administrator = True
        
        check = Music.is_dj().predicate
        result = await check(mock_ctx)
        self.assertTrue(result)

    async def test_autoplay_toggle(self):
        mock_ctx = self.mock_context()
        await self.music_cog.autoplay.callback(self.music_cog, mock_ctx)
        self.assertTrue(self.music_cog.autoplays[123])
        mock_ctx.send.assert_called_with("📻 Autoplay is now **enabled**")

    @patch('yt_dlp.YoutubeDL')
    async def test_autoplay_logic(self, mock_ytdl_class):
        mock_ctx = self.mock_context()
        mock_vc = MagicMock(spec=discord.VoiceClient)
        mock_ctx.voice_client = mock_vc
        
        self.music_cog.autoplays[123] = True
        self.music_cog.current_tracks[123] = {'title': 'Song A', 'webpage_url': 'urlA', 'uploader': 'artistA'}
        
        mock_extract = mock_ytdl_class.return_value.__enter__.return_value.extract_info
        mock_extract.return_value = {'entries': [{'title': 'Song B', 'webpage_url': 'urlB', 'url': 'streamB'}]}
        
        with patch.object(self.bot.loop, 'run_in_executor', AsyncMock(return_value=mock_extract.return_value)):
             with patch.object(YTDLSource, 'from_url', AsyncMock()) as mock_from_url:
                # We need to mock YTDLSource.from_url to return something with a volume property
                mock_player = MagicMock()
                mock_from_url.return_value = mock_player
                
                await self.music_cog.play_next(mock_ctx)
                
                # Check if it was called (it might be called twice, we just check if it was called at all or check the last one)
                self.assertEqual(self.music_cog.current_tracks[123]['title'], 'Song B')
                mock_ctx.send.assert_any_call(f"📻 **Autoplay:** Now playing **Song B**")
                mock_ctx.send.assert_called_with(f"🎶 **Now playing:** Song B")

    async def test_playlist_save(self):
        mock_ctx = self.mock_context()
        self.music_cog.current_tracks[123] = {'title': 'Current', 'webpage_url': 'url1'}
        self.music_cog.queues[123] = [{'title': 'Next', 'webpage_url': 'url2'}]
        
        await self.music_cog.playlist_save.callback(self.music_cog, mock_ctx, name="my_list")
        
        self.bot.db.save_playlist.assert_called_once()
        args = self.bot.db.save_playlist.call_args[0]
        self.assertEqual(args[0], 456) # author id
        self.assertEqual(args[1], "my_list")
        self.assertEqual(len(args[2]), 2)
        mock_ctx.send.assert_called_with("✅ Playlist **my_list** saved with 2 songs.")

    async def test_playlist_load(self):
        mock_ctx = self.mock_context()
        mock_ctx.author.voice.channel = MagicMock()
        mock_vc = MagicMock(spec=discord.VoiceClient)
        mock_vc.is_playing.return_value = True
        mock_ctx.voice_client = mock_vc
        
        self.bot.db.get_playlist.return_value = [{'title': 'Saved 1', 'webpage_url': 'url1'}]
        
        await self.music_cog.playlist_load.callback(self.music_cog, mock_ctx, name="my_list")
        
        self.assertIn({'title': 'Saved 1', 'webpage_url': 'url1'}, self.music_cog.queues[123])
        mock_ctx.send.assert_called_with("📥 Loaded 1 songs from playlist **my_list**.")

    @patch('lyricsgenius.Genius')
    async def test_lyrics_command(self, mock_genius_class):
        mock_ctx = self.mock_context()
        self.music_cog.current_tracks[123] = {'title': 'Song Title'}
        
        mock_genius = self.music_cog.genius
        mock_song = MagicMock()
        mock_song.title = "Song Title"
        mock_song.artist = "Artist"
        mock_song.lyrics = "These are the lyrics\n1Embed"
        mock_song.song_art_image_url = "http://art.com"
        
        with patch.object(self.music_cog, '_fetch_synced_lyrics', AsyncMock(return_value=None)):
            with patch.object(self.bot.loop, 'run_in_executor', AsyncMock(return_value=mock_song)):
                await self.music_cog.lyrics.callback(self.music_cog, mock_ctx, song_name=None, offset=0.0)
                
                # Called once for "synced lyrics not found" and once for embed
                self.assertEqual(mock_ctx.send.call_count, 2)
                embed = mock_ctx.send.call_args[1]['embed']
                self.assertEqual(embed.title, "Song Title")
                self.assertIn("These are the lyrics", embed.description)

if __name__ == '__main__':
    unittest.main()
