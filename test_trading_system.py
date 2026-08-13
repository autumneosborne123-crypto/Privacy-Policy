import asyncio
import unittest
import os
from utils.database import Database
from cogs.economy import Economy, TradeView
from unittest.mock import AsyncMock, MagicMock
import discord

class TestTradingSystem(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_trading_system.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        await self.db.init()
        
        self.bot = AsyncMock()
        self.bot.db = self.db
        self.bot.update_balance = AsyncMock(side_effect=self._mock_update_balance)
        self.bot.dispatch = MagicMock()
        
        self.economy_cog = Economy(self.bot)

    async def _mock_update_balance(self, user_id, amount):
        await self.db.update_balance(user_id, amount)
        return await self.db.get_balance(user_id)

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_execute_trade(self):
        author = MagicMock(spec=discord.Member)
        author.id = 1
        author.name = "Author"
        author.display_name = "AuthorDisp"
        
        target = MagicMock(spec=discord.Member)
        target.id = 2
        target.name = "Target"
        target.display_name = "TargetDisp"
        
        # Setup balances (taking into account the default 500 base balance)
        await self.db.update_balance(1, 500) # 500 + 500 = 1000
        await self.db.update_balance(2, 0)   # 500 + 0 = 500
        
        # Setup items
        await self.db.add_item(1, "sword", 1, rank="Epic")
        await self.db.add_item(2, "shield", 1, rank="Rare")
        
        view = TradeView(self.bot, author, target)
        view.offers[1] = {"coins": 200, "items": [("sword", 1, "Epic")]}
        view.offers[2] = {"coins": 100, "items": [("shield", 1, "Rare")]}
        
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response.edit_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        await view.execute_trade(interaction)
        
        # Check results
        bal1 = await self.db.get_balance(1)
        bal2 = await self.db.get_balance(2)
        self.assertEqual(bal1, 1000 - 200 + 100)
        self.assertEqual(bal2, 500 - 100 + 200)
        
        inv1 = await self.db.get_inventory(1)
        inv2 = await self.db.get_inventory(2)
        
        self.assertIn(("shield", 1, "Rare"), inv1)
        self.assertNotIn(("sword", 1, "Epic"), inv1)
        self.assertIn(("sword", 1, "Epic"), inv2)
        self.assertNotIn(("shield", 1, "Rare"), inv2)

if __name__ == "__main__":
    unittest.main()
