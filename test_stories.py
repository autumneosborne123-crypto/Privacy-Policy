import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import os

# Set dummy environment variable for bot token
os.environ['DISCORD_TOKEN'] = 'dummy_token'

from cogs.fun import Fun, STORY_DATA

class TestStoryCommands(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.config = MagicMock()
        # Mock tasks.loop to avoid RuntimeError
        with patch('discord.ext.tasks.Loop.start'):
            self.fun_cog = Fun(self.bot)

    async def test_send_story_embed_success(self):
        mock_ctx = AsyncMock()
        await self.fun_cog.send_story_embed(mock_ctx, "horror")
        
        mock_ctx.send.assert_called_once()
        args, kwargs = mock_ctx.send.call_args
        embed = kwargs['embed']
        self.assertEqual(embed.title, "📖 Horror Story")
        self.assertIn(embed.description, STORY_DATA["horror"])

    async def test_send_story_embed_invalid_genre(self):
        mock_ctx = AsyncMock()
        await self.fun_cog.send_story_embed(mock_ctx, "nonexistent")
        
        mock_ctx.send.assert_called_once()
        self.assertIn("Genre not found.", mock_ctx.send.call_args[0][0])

    async def test_story_subcommands(self):
        # Test all subcommands in the group
        subcommands = [
            (self.fun_cog.story_horror, "📖 Horror Story"),
            (self.fun_cog.story_fantasy, "📖 Fantasy Story"),
            (self.fun_cog.story_scifi, "📖 Sci-fi Story"),
            (self.fun_cog.story_mystery, "📖 Mystery Story"),
            (self.fun_cog.story_romance, "📖 Romance Story"),
            (self.fun_cog.story_adventure, "📖 Adventure Story"),
            (self.fun_cog.story_comedy, "📖 Comedy Story")
        ]
        
        for cmd, expected_title in subcommands:
            mock_ctx = AsyncMock()
            await cmd.callback(self.fun_cog, mock_ctx)
            mock_ctx.send.assert_called_once()
            self.assertEqual(mock_ctx.send.call_args[1]['embed'].title, expected_title)

    async def test_story_group_no_subcommand(self):
        mock_ctx = AsyncMock()
        mock_ctx.invoked_subcommand = None
        await self.fun_cog.story.callback(self.fun_cog, mock_ctx)
        
        mock_ctx.send.assert_called_once()
        self.assertIn("Use `/story <genre>`.", mock_ctx.send.call_args[0][0])

if __name__ == '__main__':
    unittest.main()
