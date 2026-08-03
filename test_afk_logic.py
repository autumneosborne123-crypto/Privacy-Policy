import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
import asyncio
import time
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from cogs.afk import AFK

class TestAFK(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = MagicMock(spec=commands.Bot)
        self.bot.db = AsyncMock()
        self.cog = AFK(self.bot)
        self.ctx = AsyncMock(spec=commands.Context)
        self.ctx.author.id = 123
        self.ctx.author.mention = "<@123>"
        self.ctx.author.display_name = "User123"
        self.ctx.guild.id = 456

    async def test_afk_command(self):
        await self.cog.afk.callback(self.cog, self.ctx, reason="Sleeping")
        
        self.bot.db.set_afk.assert_called_once()
        args = self.bot.db.set_afk.call_args[0]
        self.assertEqual(args[0], 123)
        self.assertEqual(args[1], "Sleeping")
        self.ctx.send.assert_called_once()
        self.ctx.author.edit.assert_called_once()

    async def test_on_message_returns_from_afk(self):
        message = AsyncMock(spec=discord.Message)
        message.author.id = 123
        message.author.bot = False
        message.author.display_name = "[AFK] User123"
        message.guild = MagicMock()
        message.channel.send = AsyncMock()
        
        # Mock AFK data (reason, timestamp)
        # Set timestamp to 5 seconds ago
        self.bot.db.get_afk.return_value = ("Sleeping", time.time() - 5)
        
        await self.cog.on_message(message)
        
        self.bot.db.remove_afk.assert_called_once_with(123)
        message.author.edit.assert_called_once_with(nick="User123")
        message.channel.send.assert_called()
        self.assertIn("Welcome back", message.channel.send.call_args[0][0])

    async def test_on_message_mention_afk(self):
        message = AsyncMock(spec=discord.Message)
        message.author.id = 789
        message.author.bot = False
        message.guild = MagicMock()
        
        mention = MagicMock(spec=discord.Member)
        mention.id = 123
        mention.display_name = "User123"
        message.mentions = [mention]
        message.channel.send = AsyncMock()
        
        self.bot.db.get_afk.side_effect = [None, ("Working", time.time() - 10)]
        
        await self.cog.on_message(message)
        
        message.channel.send.assert_called()
        self.assertIn("is AFK: Working", message.channel.send.call_args[0][0])

if __name__ == '__main__':
    unittest.main()
