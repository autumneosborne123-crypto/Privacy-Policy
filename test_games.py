import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
import asyncio
import html
from cogs.fun import Fun, TicTacToeView, TriviaView

class TestGames(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock(spec=commands.Bot)
        self.bot.config = MagicMock()
        self.bot.update_balance = AsyncMock()
        with patch('discord.ext.tasks.Loop.start'):
            self.fun_cog = Fun(self.bot)

    async def test_tictactoe_command(self):
        ctx = AsyncMock()
        await self.fun_cog.tictactoe.callback(self.fun_cog, ctx)
        ctx.send.assert_called_once()
        args, kwargs = ctx.send.call_args
        self.assertIsInstance(kwargs['view'], TicTacToeView)

    @patch('aiohttp.ClientSession.get')
    async def test_trivia_command_success(self, mock_get):
        ctx = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            'results': [{
                'question': 'What is 2+2?',
                'correct_answer': '4',
                'incorrect_answers': ['3', '5', '6'],
                'category': 'Math',
                'difficulty': 'easy'
            }]
        }
        mock_get.return_value.__aenter__.return_value = mock_response

        await self.fun_cog.trivia.callback(self.fun_cog, ctx)
        ctx.send.assert_called_once()
        args, kwargs = ctx.send.call_args
        self.assertIn("🧠 Trivia Time!", kwargs['embed'].title)
        self.assertIsInstance(kwargs['view'], TriviaView)

    async def test_minesweeper_command(self):
        ctx = AsyncMock()
        await self.fun_cog.minesweeper.callback(self.fun_cog, ctx, columns=5, rows=5, bombs=3)
        ctx.send.assert_called_once()
        content = ctx.send.call_args[0][0]
        self.assertIn("🚩 **Minesweeper", content)
        self.assertIn("||", content) # Check for spoilers

    async def test_hangman_command_timeout(self):
        ctx = AsyncMock()
        ctx.author = MagicMock()
        ctx.channel = MagicMock()
        
        # Mock wait_for to timeout
        self.bot.wait_for.side_effect = asyncio.TimeoutError()
        
        await self.fun_cog.hangman.callback(self.fun_cog, ctx)
        # Should send start message and then timeout message
        self.assertEqual(ctx.send.call_count, 2)
        self.assertIn("⏰ Time's up!", ctx.send.call_args_list[1][0][0])

    async def test_slots_command(self):
        ctx = AsyncMock()
        await self.fun_cog.slots.callback(self.fun_cog, ctx)
        ctx.send.assert_called_once()
        args, kwargs = ctx.send.call_args
        self.assertIn("Slot Machine", kwargs['embed'].title)

    async def test_wyr_command(self):
        ctx = AsyncMock()
        await self.fun_cog.wyr.callback(self.fun_cog, ctx)
        ctx.send.assert_called_once()
        args, kwargs = ctx.send.call_args
        self.assertIn("🤔 Would You Rather...", kwargs['embed'].title)

    async def test_fasttyper_command_timeout(self):
        ctx = AsyncMock()
        ctx.author = MagicMock()
        ctx.channel = MagicMock()
        self.bot.wait_for.side_effect = asyncio.TimeoutError()
        await self.fun_cog.fasttyper.callback(self.fun_cog, ctx)
        self.assertIn("⏰ Time's up!", ctx.send.call_args_list[1][0][0])

    async def test_connectfour_command(self):
        ctx = AsyncMock()
        await self.fun_cog.connectfour.callback(self.fun_cog, ctx)
        ctx.send.assert_called_once()
        content = ctx.send.call_args[0][0]
        self.assertIn("Connect Four", content)

if __name__ == '__main__':
    unittest.main()
