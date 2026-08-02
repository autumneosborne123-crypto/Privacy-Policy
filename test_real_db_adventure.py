import asyncio
import unittest
import os
import aiosqlite
from utils.database import Database
from cogs.adventure import Adventure
from unittest.mock import AsyncMock, MagicMock

class TestRealDBAdventure(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_adventure.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        await self.db.init()
        
        self.bot = AsyncMock()
        self.bot.db = self.db
        self.bot.whitelisted_bots = []
        
        self.adventure_cog = Adventure(self.bot)

    async def asyncTearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_catch_animal_flow(self):
        ctx = AsyncMock()
        ctx.author.id = 123456789
        ctx.author.display_name = "TestUser"
        ctx.guild.id = 987654321
        
        # 1. Initially should fail (no bait)
        await self.adventure_cog.catch.callback(self.adventure_cog, ctx)
        ctx.send.assert_called_with("❌ You need **Bait** to catch animals! Buy some in the `.shop`.", ephemeral=True)
        
        # 2. Add bait to inventory
        await self.db.add_item(ctx.author.id, "bait", 5)
        
        # 3. Try to catch
        ctx.send.reset_mock()
        await self.adventure_cog.catch.callback(self.adventure_cog, ctx)
        
        # Check if success or escape message was sent
        args, kwargs = ctx.send.call_args
        self.assertTrue("Success" in args[0] or "escaped" in args[0])
        
        # 4. Check animals list
        ctx.send.reset_mock()
        await self.adventure_cog.animals.callback(self.adventure_cog, ctx)
        args, kwargs = ctx.send.call_args
        # If we caught something, it should be in the embed
        if "embed" in kwargs:
            embed = kwargs["embed"]
            self.assertEqual(embed.title, "🐾 TestUser's Animals")
        else:
            # If nothing caught yet
            self.assertIn("hasn't caught any animals yet", args[0])

    async def test_quest_flow(self):
        ctx = AsyncMock()
        ctx.author.id = 123456789
        
        # 1. View quests (should assign one)
        await self.adventure_cog.quest.callback(self.adventure_cog, ctx)
        ctx.send.assert_called_once()
        args, kwargs = ctx.send.call_args
        self.assertIn("embed", kwargs)
        
        # 2. Verify quest in DB
        quests = await self.db.get_quests(ctx.author.id)
        self.assertTrue(len(quests) > 0)
        
        # 3. Mock a catch and check progress
        # We need to know which quest was assigned
        quest_type = quests[0][0] # e.g. "catch_animals"
        await self.db.update_quest_progress(ctx.author.id, quest_type)
        
        quests_after = await self.db.get_quests(ctx.author.id)
        self.assertEqual(quests_after[0][1], 1) # Progress should be 1

if __name__ == "__main__":
    unittest.main()
