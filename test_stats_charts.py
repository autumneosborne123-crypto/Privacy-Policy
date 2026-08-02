import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import os
from cogs.leveling import Leveling
from cogs.security import Security
from utils.database import Database

class TestStatsCharts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_file = "test_stats_run.db"
        if os.path.exists(self.db_file):
            os.remove(self.db_file)
            
        self.db = Database(self.db_file)
        await self.db.init()
        
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.db = self.db
        self.bot.config = MagicMock()
        
        self.leveling_cog = Leveling(self.bot)
        self.security_cog = Security(self.bot)

    async def asyncTearDown(self):
        if os.path.exists(self.db_file):
            os.remove(self.db_file)

    async def test_stat_increments(self):
        guild_id = "123"
        user_id = "456"
        
        # Test message increments
        await self.db.increment_daily_stat(guild_id, "messages")
        await self.db.increment_user_daily_messages(user_id, guild_id)
        
        stats = await self.db.get_daily_stats(guild_id)
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0][1], 1) # messages
        
        user_stats = await self.db.get_user_daily_messages(user_id, guild_id)
        self.assertEqual(len(user_stats), 1)
        self.assertEqual(user_stats[0][1], 1)

    async def test_join_leave_increments(self):
        guild_id = "123"
        await self.db.increment_daily_stat(guild_id, "joins")
        await self.db.increment_daily_stat(guild_id, "leaves")
        
        stats = await self.db.get_daily_stats(guild_id)
        self.assertEqual(stats[0][2], 1) # joins
        self.assertEqual(stats[0][3], 1) # leaves

    def test_chart_url_generation(self):
        labels = ["2024-01-01", "2024-01-02"]
        data = [10, 20]
        url = self.leveling_cog.generate_chart_url("Test Title", labels, data)
        self.assertTrue(url.startswith("https://quickchart.io/chart?c="))
        self.assertIn("Test%20Title", url)

    async def test_level_distribution(self):
        await self.db.update_user_data("u1", 100, 1, 0, 10)
        await self.db.update_user_data("u2", 200, 2, 0, 20)
        await self.db.update_user_data("u3", 300, 1, 0, 30)
        
        dist = await self.db.get_level_distribution()
        # Should be [(1, 2), (2, 1)] -> Level 1 has 2 users, Level 2 has 1 user
        self.assertEqual(len(dist), 2)
        self.assertEqual(dist[0], (1, 2))
        self.assertEqual(dist[1], (2, 1))

    async def test_joins_command_logic(self):
        ctx = AsyncMock()
        ctx.guild.id = "123"
        await self.db.increment_daily_stat("123", "joins")
        
        await self.security_cog.joins.callback(self.security_cog, ctx)
        ctx.send.assert_called()
        embed = ctx.send.call_args[1]['embed']
        self.assertTrue(embed.image.url.startswith("https://quickchart.io/chart"))

if __name__ == '__main__':
    unittest.main()
