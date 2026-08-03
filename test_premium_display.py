import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import time
from cogs.economy import Economy
from cogs.music import Music
from cogs.premium import Premium
from main import HelpView

class TestPremiumDisplay(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.db = AsyncMock()
        self.bot.loop = asyncio.get_event_loop()
        self.bot.config = MagicMock()
        self.bot.user = MagicMock(spec=discord.ClientUser)
        self.bot.user.display_avatar = MagicMock()
        self.bot.user.display_avatar.url = "https://example.com/avatar.png"
        
        # Mock database responses
        self.bot.db.get_economy_data = AsyncMock(return_value={
            "coins": 1000, 
            "last_daily": time.time(), # Already claimed to trigger cooldown
            "last_rob": time.time(),   # Already robbed to trigger cooldown
            "premium_until": 0
        })
        self.bot.db.get_balance = AsyncMock(return_value=1000)
        self.bot.db.is_user_premium = AsyncMock(return_value=False)
        self.bot.db.is_guild_premium = AsyncMock(return_value=False)
        self.bot.db.get_guild_setting = AsyncMock(return_value=None)
        
        self.economy_cog = Economy(self.bot)
        self.music_cog = Music(self.bot)
        self.premium_cog = Premium(self.bot)

    async def test_premium_command_display(self):
        """Test the .premium command shows correct prices."""
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        mock_ctx.guild = None
        mock_ctx.invoked_subcommand = None
        
        await self.premium_cog.premium.callback(self.premium_cog, mock_ctx)
        
        # Check if ctx.send was called with an embed containing the prices
        self.assertTrue(mock_ctx.send.called)
        args, kwargs = mock_ctx.send.call_args
        embed = kwargs.get('embed') or args[0]
        
        self.assertIn("$5.00", embed.description)
        self.assertIn("$12.00", embed.description)
        self.assertIn("$35.00", embed.description)

    async def test_premium_buy_display(self):
        """Test the .premium buy command shows correct prices and highlights."""
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        
        # The method name is buy_premium, although the command name is buy
        await self.premium_cog.buy_premium.callback(self.premium_cog, mock_ctx)
        
        self.assertTrue(mock_ctx.send.called)
        args, kwargs = mock_ctx.send.call_args
        embed = kwargs.get('embed') or args[0]
        
        self.assertIn("$5.00", embed.description)
        self.assertIn("$12.00", embed.description)
        self.assertIn("$35.00", embed.description)
        self.assertIn("Save $3!", embed.description)
        self.assertIn("Best Value!", embed.description)

    async def test_economy_daily_cooldown_tip(self):
        """Test the .daily cooldown message includes the premium price tip."""
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        self.bot.db.is_user_premium.return_value = False
        
        await self.economy_cog.daily.callback(self.economy_cog, mock_ctx)
        
        self.assertTrue(mock_ctx.send.called)
        msg = mock_ctx.send.call_args[0][0]
        self.assertIn("$5.00/mo", msg)
        self.assertIn("2x Daily Coins", msg)

    async def test_economy_rob_cooldown_tip(self):
        """Test the .rob cooldown message includes the premium price tip."""
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        self.bot.db.get_economy_data.return_value = {
            "coins": 1000, 
            "last_daily": 0, 
            "last_rob": time.time(), 
            "premium_until": 0
        }
        
        await self.economy_cog.rob.callback(self.economy_cog, mock_ctx, AsyncMock())
        
        self.assertTrue(mock_ctx.send.called)
        msg = mock_ctx.send.call_args[0][0]
        self.assertIn("$5.00/mo", msg)
        self.assertIn("50% reduced rob cooldowns", msg)

    async def test_economy_premium_item_error(self):
        """Test the .buy command error for premium items includes the price."""
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        self.bot.db.is_user_premium.return_value = False
        
        # 'mystic_petal' is premium-only in cogs/economy.py
        await self.economy_cog.buy.callback(self.economy_cog, mock_ctx, item_name="mystic petal")
        
        self.assertTrue(mock_ctx.send.called)
        msg = mock_ctx.send.call_args[0][0]
        self.assertIn("$5.00/mo", msg)

    async def test_music_247_premium_error(self):
        """Test the .24/7 command error includes the premium price."""
        mock_ctx = AsyncMock()
        mock_ctx.guild.id = 456
        self.bot.db.is_guild_premium.return_value = False
        
        await self.music_cog.toggle_247.callback(self.music_cog, mock_ctx)
        
        self.assertTrue(mock_ctx.send.called)
        msg = mock_ctx.send.call_args[0][0]
        self.assertIn("$5.00/mo", msg)

    async def test_music_filter_premium_error(self):
        """Test the .filter command error includes the premium price."""
        mock_ctx = AsyncMock()
        mock_ctx.guild.id = 456
        self.bot.db.is_guild_premium.return_value = False
        
        await self.music_cog.apply_filter.callback(self.music_cog, mock_ctx, filter_name="bassboost")
        
        self.assertTrue(mock_ctx.send.called)
        msg = mock_ctx.send.call_args[0][0]
        self.assertIn("$5.00/mo", msg)

    async def test_support_server_link(self):
        """Verify the support server link is updated in premium buy and help menu."""
        # Check .premium buy
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        await self.premium_cog.buy_premium.callback(self.premium_cog, mock_ctx)
        
        embed = mock_ctx.send.call_args[1].get('embed') or mock_ctx.send.call_args[0][0]
        self.assertIn("https://discord.gg/mXtvjGpQmM", embed.description)
        self.assertNotIn("discord.gg/flowerbot", embed.description)
        
        # Check Help Menu
        view = HelpView(self.bot, ".")
        help_embed = view.create_home_embed()
        self.assertIn("https://discord.gg/mXtvjGpQmM", help_embed.description)
        self.assertNotIn("discord.gg/flowerbot", help_embed.description)

if __name__ == '__main__':
    unittest.main()
