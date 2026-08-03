import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import os
import re

# Set dummy environment variable for bot token
os.environ['DISCORD_TOKEN'] = 'dummy_token'

from cogs.music import Music
from utils.database import Database

class TestLyricsEdgeCases(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.loop = asyncio.get_running_loop()
        self.bot.config = MagicMock()
        self.bot.config.get = MagicMock(return_value=None)
        self.bot.db = AsyncMock(spec=Database)
        
        self.music_cog = Music(self.bot)
        
        self.guild_id = 123
        self.guild = MagicMock(spec=discord.Guild)
        self.guild.id = self.guild_id
        
        self.vc = MagicMock(spec=discord.VoiceClient)
        self.vc.is_connected.return_value = True
        self.vc.is_playing.return_value = True
        
    def mock_context(self):
        ctx = AsyncMock()
        ctx.bot = self.bot
        ctx.guild = self.guild
        ctx.voice_client = self.vc
        ctx.send = AsyncMock()
        ctx.defer = AsyncMock()
        return ctx

    async def test_lyrics_no_track_no_name(self):
        ctx = self.mock_context()
        ctx.voice_client = None
        self.music_cog.current_tracks[self.guild_id] = None
        
        await self.music_cog.lyrics.callback(self.music_cog, ctx, song_name=None)
        
        ctx.send.assert_called_with("❌ Nothing playing and no song name provided.")

    @patch('syncedlyrics.search')
    async def test_lyrics_with_song_name_no_follow(self, mock_synced):
        ctx = self.mock_context()
        mock_synced.return_value = "[00:01.00] Line 1\n[00:02.00] Line 2"
        
        with patch.object(self.music_cog, 'show_synced_lyrics', AsyncMock()) as mock_show:
            await self.music_cog.lyrics.callback(self.music_cog, ctx, song_name="Test Song", offset=0.0)
            
            mock_show.assert_called_once()
            args, kwargs = mock_show.call_args
            self.assertEqual(kwargs['follow'], False)
            self.assertEqual(args[1], [(1.0, "Line 1"), (2.0, "Line 2")])
            ctx.send.assert_any_call("🎤 **Synced lyrics found!** Starting karaoke display...", delete_after=5)

    @patch('syncedlyrics.search', return_value=None)
    @patch('lyricsgenius.Genius.search_song')
    async def test_lyrics_no_lyrics_found(self, mock_genius_search, mock_synced):
        ctx = self.mock_context()
        mock_genius_search.return_value = None
        
        await self.music_cog.lyrics.callback(self.music_cog, ctx, song_name="Nonexistent Song", offset=0.0)
        
        ctx.send.assert_called_with("❌ Could not find lyrics for **Nonexistent Song**.")

    async def test_lyrics_task_cancellation(self):
        ctx = self.mock_context()
        mock_task = MagicMock(spec=asyncio.Task)
        self.music_cog.lyrics_tasks[self.guild_id] = mock_task
        
        # We need to make it fail early or mock the rest to avoid starting a new task properly
        with patch.object(self.music_cog, '_fetch_synced_lyrics', AsyncMock(return_value=None)):
            with patch.object(self.music_cog.genius, 'search_song', return_value=None):
                await self.music_cog.lyrics.callback(self.music_cog, ctx, song_name="Test", offset=0.0)
                
        mock_task.cancel.assert_called_once()
        self.assertNotIn(self.guild_id, self.music_cog.lyrics_tasks)

    @patch('syncedlyrics.search', return_value=None)
    @patch('lyricsgenius.Genius.search_song')
    async def test_lyrics_long_text_truncation(self, mock_genius_search, mock_synced):
        ctx = self.mock_context()
        mock_song = MagicMock()
        mock_song.title = "Long Song"
        mock_song.artist = "Artist"
        mock_song.lyrics = "A" * 5000
        mock_song.song_art_image_url = None
        mock_genius_search.return_value = mock_song
        
        await self.music_cog.lyrics.callback(self.music_cog, ctx, song_name="Long Song", offset=0.0)
        
        # Once for fallback message, once for embed
        self.assertEqual(ctx.send.call_count, 2)
        embed = ctx.send.call_args[1]['embed']
        self.assertTrue(embed.description.endswith("..."))
        self.assertEqual(len(embed.description), 4000)

    @patch('asyncio.sleep', AsyncMock())
    async def test_show_synced_lyrics_track_change_follow(self):
        ctx = self.mock_context()
        initial_track = {'title': 'Song 1', 'duration': 100}
        new_track = {'title': 'Song 2', 'duration': 100}
        self.music_cog.current_tracks[self.guild_id] = initial_track
        
        lyrics1 = [(1.0, "Line 1")]
        lyrics2 = [(1.0, "New Line")]
        
        # Setup sequence for current_tracks
        # First call to while loop check: current_track = Song 1 (same as initial)
        # Second call to while loop check: current_track = Song 2 (different)
        # Third call to while loop check: exit loop via side effect
        
        # But wait, current_track is fetched at the start of loop.
        # We need to control self.current_tracks[self.guild_id]
        
        # We'll use a side effect for get_elapsed to control loop iterations or just mock while loop logic
        # Actually, show_synced_lyrics is a while True loop. 
        # We can use a side effect on ctx.voice_client.is_connected to break it.
        self.vc.is_connected.side_effect = [True, True, False] 
        
        # mock _fetch_synced_lyrics for the track change
        with patch.object(self.music_cog, '_fetch_synced_lyrics', AsyncMock()) as mock_fetch:
            mock_fetch.side_effect = [lyrics2] # For the track change to Song 2
            
            # Simulate track change after first iteration
            def track_changer(*args, **kwargs):
                self.music_cog.current_tracks[self.guild_id] = new_track
                return 0.5 # Progress bar progress
                
            with patch.object(self.music_cog, 'get_elapsed', side_effect=track_changer):
                await self.music_cog.show_synced_lyrics(ctx, lyrics1, follow=True)
                
            mock_fetch.assert_called_with('Song 2', None)
            ctx.channel.send.assert_any_call("⏭️ **Lyrics following track change:** Song 2", delete_after=5)

    @patch('asyncio.sleep', AsyncMock())
    async def test_show_synced_lyrics_message_deleted(self):
        ctx = self.mock_context()
        self.music_cog.current_tracks[self.guild_id] = {'title': 'Song', 'duration': 100}
        lyrics = [(1.0, "Line 1"), (2.0, "Line 2")]
        
        self.vc.is_connected.side_effect = [True, True, False]
        
        mock_msg = AsyncMock(spec=discord.Message)
        mock_msg.edit.side_effect = [discord.NotFound(MagicMock(), "Not Found"), None]
        ctx.send.side_effect = [mock_msg, mock_msg]
        
        # Change elapsed time so current_index changes from 0 to 1
        with patch.object(self.music_cog, 'get_elapsed', side_effect=[1.5, 2.5]):
            await self.music_cog.show_synced_lyrics(ctx, lyrics, follow=True)
            
        # Should be called twice: once initially, once after NotFound
        self.assertEqual(ctx.send.call_count, 2)

    @patch('asyncio.sleep', AsyncMock())
    async def test_show_synced_lyrics_disconnect(self):
        ctx = self.mock_context()
        self.music_cog.current_tracks[self.guild_id] = {'title': 'Song', 'duration': 100}
        lyrics = [(1.0, "Line 1")]
        
        # Disconnect immediately
        self.vc.is_connected.return_value = False
        
        await self.music_cog.show_synced_lyrics(ctx, lyrics, follow=True)
        
        ctx.send.assert_not_called()

if __name__ == '__main__':
    unittest.main()
