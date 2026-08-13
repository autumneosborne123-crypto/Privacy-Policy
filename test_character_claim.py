import asyncio
import unittest
import os
from utils.database import Database
from cogs.games import Games
from unittest.mock import AsyncMock, MagicMock
import discord

class TestCharacterClaim(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_character_claim.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        await self.db.init()
        
        self.bot = AsyncMock()
        self.bot.db = self.db
        self.bot.whitelisted_bots = []
        
        self.games_cog = Games(self.bot)

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_claim_character(self):
        user_id = 123456789
        name = "Zero Two"
        img = "https://example.com/02.png"
        url = "https://anilist.co/character/123"
        
        await self.db.add_claimed_character(user_id, name, img, url)
        
        chars = await self.db.get_claimed_characters(user_id)
        self.assertEqual(len(chars), 1)
        self.assertEqual(chars[0][0], name)
        self.assertEqual(chars[0][1], img)
        self.assertEqual(chars[0][2], url)

    async def test_harem_command(self):
        ctx = AsyncMock()
        ctx.author.id = 123456789
        ctx.author.display_name = "TestUser"
        
        await self.db.add_claimed_character(ctx.author.id, "Rem", "https://example.com/rem.png", "https://anilist.co/rem")
        
        await self.games_cog.harem.callback(self.games_cog, ctx)
        
        ctx.send.assert_called_once()
        args, kwargs = ctx.send.call_args
        embed = kwargs["embed"]
        self.assertIn("Rem", embed.description)
        self.assertEqual(embed.title, "💕 TestUser's Harem")

if __name__ == "__main__":
    unittest.main()
