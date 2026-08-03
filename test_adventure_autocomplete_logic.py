import asyncio
import unittest
import os
from utils.database import Database
from cogs.adventure import Adventure
from unittest.mock import AsyncMock, MagicMock
import discord

class TestAdventureAutocomplete(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_adventure_autocomplete.db"
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

    async def test_train_command_still_works_with_id(self):
        ctx = AsyncMock()
        ctx.author.id = 123456789
        ctx.prefix = "."
        
        # Add an animal
        stats = {"hp": 100, "attack": 10, "defense": 10, "speed": 10}
        await self.db.add_animal(ctx.author.id, "leafy_rabbit", "Buns", stats)
        animals = await self.db.get_user_animals(ctx.author.id)
        animal_id = animals[0][0]
        
        # Call train
        await self.adventure_cog.train.callback(self.adventure_cog, ctx, animal_id)
        
        # Verify
        updated_animals = await self.db.get_user_animals(ctx.author.id)
        self.assertTrue(updated_animals[0][4] > 0) # XP increased

if __name__ == "__main__":
    unittest.main()
