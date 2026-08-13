import asyncio
import unittest
import os
from utils.database import Database
from cogs.adventure import Adventure
from unittest.mock import AsyncMock, MagicMock
import discord

class TestAdventureUpdated(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_adventure_updated.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        await self.db.init()
        
        self.bot = AsyncMock()
        self.bot.db = self.db
        self.bot.whitelisted_bots = []
        self.bot.dispatch = MagicMock()
        self.bot.log_action = AsyncMock()
        self.bot.update_balance = AsyncMock()
        
        self.adventure_cog = Adventure(self.bot)

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_train_command_with_str_id(self):
        ctx = AsyncMock()
        ctx.author.id = 123456789
        
        # 1. Add an animal
        stats = {"hp": 100, "attack": 10, "defense": 10, "speed": 10}
        await self.db.add_animal(ctx.author.id, "leafy_rabbit", "Buns", stats)
        animals = await self.db.get_user_animals(ctx.author.id)
        animal_id = str(animals[0][0])
        
        # 2. Train the animal
        await self.adventure_cog.train.callback(self.adventure_cog, ctx, animal_id)
        
        # 3. Check stats after training
        updated_animals = await self.db.get_user_animals(ctx.author.id)
        self.assertTrue(updated_animals[0][4] > 0) # XP should increase
        self.assertTrue(ctx.defer.called)

    async def test_autocomplete(self):
        interaction = AsyncMock()
        interaction.user.id = 123456789
        
        # Add an animal
        stats = {"hp": 100, "attack": 10, "defense": 10, "speed": 10}
        await self.db.add_animal(interaction.user.id, "fire_fox", "Fluffy", stats)
        
        # Test autocomplete
        choices = await self.adventure_cog.animal_autocomplete(interaction, "Flu")
        self.assertTrue(len(choices) > 0)
        self.assertEqual(choices[0].name, "Fluffy (Fire Fox) Lvl 1")

if __name__ == "__main__":
    unittest.main()
