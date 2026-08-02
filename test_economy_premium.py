import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import time
from cogs.economy import Economy

class TestEconomyPremium(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.db = AsyncMock()
        self.bot.loop = asyncio.get_event_loop()
        self.bot.config = MagicMock()
        
        # Default mock for premium check
        self.bot.db.is_user_premium = AsyncMock(return_value=False)
        self.bot.db.get_economy_data = AsyncMock(return_value={
            "coins": 1000, 
            "last_daily": 0, 
            "last_rob": 0, 
            "premium_until": 0
        })
        self.bot.db.get_balance = AsyncMock(return_value=1000)
        self.bot.update_balance = AsyncMock()
        self.bot.db.update_economy_cooldown = AsyncMock()
        self.bot.db.add_item = AsyncMock()
        self.bot.log_action = AsyncMock()
        
        self.economy_cog = Economy(self.bot)

    async def test_daily_multiplier_premium(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        
        # Premium user
        self.bot.db.is_user_premium.return_value = True
        
        await self.economy_cog.daily.callback(self.economy_cog, mock_ctx)
        
        amount_sent = self.bot.update_balance.call_args[0][1]
        # Base is 200-500, so premium should be 400-1000
        self.assertTrue(400 <= amount_sent <= 1000, f"Amount {amount_sent} not in expected premium range")
        
        mock_ctx.send.assert_called_once()
        self.assertIn("2x Premium Multiplier applied!", mock_ctx.send.call_args[0][0])

    async def test_rob_cooldown_premium(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.id = 456
        
        # Set last_rob to 45 mins ago (2700s)
        # Non-premium needs 60 mins (3600s) -> should FAIL
        # Premium needs 30 mins (1800s) -> should PASS
        
        # Test Non-Premium
        self.bot.db.get_economy_data.return_value = {
            "coins": 1000, "last_daily": 0, "last_rob": time.time() - 2700, "premium_until": 0
        }
        await self.economy_cog.rob.callback(self.economy_cog, mock_ctx, mock_member)
        self.assertIn("⏳ This command is on cooldown", mock_ctx.send.call_args[0][0])
        
        mock_ctx.send.reset_mock()
        
        # Test Premium
        self.bot.db.get_economy_data.return_value = {
            "coins": 1000, "last_daily": 0, "last_rob": time.time() - 2700, "premium_until": time.time() + 3600
        }
        with patch('random.random', return_value=0.9): # Fail the rob so we don't need to mock target balance etc as much
            await self.economy_cog.rob.callback(self.economy_cog, mock_ctx, mock_member)
        
        # Should NOT be a cooldown message
        if mock_ctx.send.called:
            self.assertNotIn("⏳ This command is on cooldown", mock_ctx.send.call_args[0][0])

    async def test_rob_success_rate_premium(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.id = 456
        mock_member.display_name = "Target"
        self.bot.db.get_balance.return_value = 1000 # Target balance
        
        # Success threshold is 0.4 for normal, 0.6 for premium
        # We test with random.random() = 0.5
        
        # Test Non-Premium (0.5 > 0.4 -> Fail)
        self.bot.db.get_economy_data.return_value = {
            "coins": 1000, "last_daily": 0, "last_rob": 0, "premium_until": 0
        }
        with patch('random.random', return_value=0.5):
            await self.economy_cog.rob.callback(self.economy_cog, mock_ctx, mock_member)
        
        self.assertIn("👮 You got caught!", mock_ctx.send.call_args[0][0])
        
        mock_ctx.send.reset_mock()
        
        # Test Premium (0.5 < 0.6 -> Success)
        self.bot.db.get_economy_data.return_value = {
            "coins": 1000, "last_daily": 0, "last_rob": 0, "premium_until": time.time() + 3600
        }
        with patch('random.random', return_value=0.5):
            await self.economy_cog.rob.callback(self.economy_cog, mock_ctx, mock_member)
        
        self.assertIn("💸 Success!", mock_ctx.send.call_args[0][0])

    async def test_buy_premium_item_restricted(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        
        # Non-premium trying to buy mystic_petal
        self.bot.db.is_user_premium.return_value = False
        
        await self.economy_cog.buy.callback(self.economy_cog, mock_ctx, item_name="Mystic Flower Petal")
        
        self.assertIn("exclusive to **flowerbot.gg Premium**", mock_ctx.send.call_args[0][0])
        self.bot.db.add_item.assert_not_called()

    async def test_buy_premium_item_allowed(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        
        # Premium trying to buy mystic_petal
        self.bot.db.is_user_premium.return_value = True
        self.bot.db.get_balance.return_value = 2000
        
        await self.economy_cog.buy.callback(self.economy_cog, mock_ctx, item_name="Mystic Flower Petal")
        
        self.assertIn("You bought a **Mystic Flower Petal**", mock_ctx.send.call_args[0][0])
        self.bot.db.add_item.assert_called_once()
        self.assertEqual(self.bot.db.add_item.call_args[0][1], "mystic_petal")

if __name__ == '__main__':
    unittest.main()
