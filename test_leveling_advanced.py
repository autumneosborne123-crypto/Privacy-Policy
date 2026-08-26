import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import os
import sqlite3
import time
from cogs.leveling import Leveling
from utils.database import Database

class TestLevelingAdvanced(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_file = "test_leveling_adv.db"
        if os.path.exists(self.db_file):
            os.remove(self.db_file)
            
        self.db = Database(self.db_file)
        await self.db.init()
        
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.db = self.db
        self.bot.config = MagicMock()
        self.bot.user = MagicMock(spec=discord.ClientUser)
        self.bot.user.display_avatar.url = "http://example.com/avatar.png"
        
        self.cog = Leveling(self.bot)

    async def asyncTearDown(self):
        await self.db.close()
        self.cog.cog_unload()
        if os.path.exists(self.db_file):
            os.remove(self.db_file)

    async def test_award_xp_with_boost(self):
        member = MagicMock(spec=discord.Member)
        member.id = 123456
        member.bot = False
        member.roles = []
        member.guild = MagicMock()
        
        # Add boost for a role
        role_id = 789
        await self.db.add_xp_boost(role_id, 2.0)
        
        # Member has the role
        role = MagicMock(spec=discord.Role)
        role.id = role_id
        member.roles = [role]
        
        # Award 25 XP
        await self.cog.award_xp(member, 25)
        
        data = await self.db.get_user_data(member.id)
        # Should be 50 XP due to 2x boost
        self.assertEqual(data["xp"], 50)

    async def test_write_waits_for_transient_sqlite_lock(self):
        lock_conn = sqlite3.connect(self.db_file, timeout=30)
        lock_conn.execute("BEGIN IMMEDIATE")

        write_task = asyncio.create_task(
            self.db.update_user_data(987654, 25, 1, time.time(), 1, 0)
        )
        await asyncio.sleep(0.2)
        self.assertFalse(write_task.done())

        lock_conn.commit()
        lock_conn.close()
        await write_task

        data = await self.db.get_user_data(987654)
        self.assertEqual(data["xp"], 25)

    async def test_voice_xp_task_logic(self):
        # Mock guilds and voice channels
        guild = MagicMock(spec=discord.Guild)
        vc = MagicMock(spec=discord.VoiceChannel)
        member1 = MagicMock(spec=discord.Member)
        member1.id = 111
        member1.bot = False
        member1.voice.self_deaf = False
        member1.voice.deaf = False
        member1.roles = []
        member1.guild = guild
        
        member2 = MagicMock(spec=discord.Member)
        member2.id = 222
        member2.bot = False
        member2.voice.self_deaf = False
        member2.voice.deaf = False
        member2.roles = []
        member2.guild = guild
        
        vc.members = [member1, member2]
        guild.voice_channels = [vc]
        self.bot.guilds = [guild]
        
        # Run one iteration of the task manually
        with patch('random.randint', return_value=15):
            await self.cog.voice_xp_task()
        
        data1 = await self.db.get_user_data(111)
        data2 = await self.db.get_user_data(222)
        
        self.assertEqual(data1["xp"], 15)
        self.assertEqual(data1["voice_minutes"], 1)
        self.assertEqual(data2["xp"], 15)
        self.assertEqual(data2["voice_minutes"], 1)

    async def test_leaderboard_sorting(self):
        await self.db.update_user_data("u1", 100, 1, 0, 10, 50) # 50 voice mins
        await self.db.update_user_data("u2", 200, 2, 0, 20, 10) # 10 voice mins
        
        # Sort by XP (default)
        top_xp = await self.db.get_top_users(10, sort_by="xp")
        self.assertEqual(top_xp[0][0], "u2") # Level 2 first
        
        # Sort by Voice
        top_voice = await self.db.get_top_users(10, sort_by="voice")
        self.assertEqual(top_voice[0][0], "u1") # 50 mins first

    async def test_rank_command_next_reward(self):
        ctx = AsyncMock()
        ctx.author.id = 123
        ctx.author.display_name = "TestUser"
        ctx.author.display_avatar.url = "http://example.com/avatar.png"
        ctx.guild.get_role = MagicMock(side_effect=lambda rid: MagicMock(mention=f"<@&{rid}>"))
        
        await self.db.add_role_reward(5, 555)
        await self.db.update_user_data(123, 0, 1, 0, 0, 0)
        
        await self.cog.rank.callback(self.cog, ctx)
        
        ctx.send.assert_called()
        embed = ctx.send.call_args[1]['embed']
        # Check if Next Reward field exists and has the correct level
        next_reward_field = next(f for f in embed.fields if f.name == "🎖️ Next Reward")
        self.assertIn("Level **5**", next_reward_field.value)

if __name__ == '__main__':
    unittest.main()
