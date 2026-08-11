import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import discord
import os
from utils.database import Database
from datetime import timedelta
import time
import json

# Set dummy environment variable for bot token
os.environ['DISCORD_TOKEN'] = 'dummy_token'

from cogs.moderation import Moderation
from cogs.fun import Fun
from cogs.leveling import Leveling, LeaderboardView
from cogs.config import ConfigCog
from cogs.security import Security

class TestBotFeatures(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = AsyncMock(spec=discord.ext.commands.Bot)
        self.bot.db = AsyncMock()
        self.bot.db.get_ignored_channels.return_value = []
        self.bot.db.get_guild_setting.return_value = None
        self.bot.db.get_all_guild_settings.return_value = {}
        self.bot.db.get_role_rewards.return_value = {}
        self.bot.db.get_xp_boosts.return_value = {}
        self.bot.db.get_user_data.return_value = {"xp": 0, "level": 0, "last_xp_time": 0, "message_count": 0, "voice_minutes": 0}
        self.bot.db.get_user_today_stats.return_value = {"messages": 0, "voice_minutes": 0}
        self.bot.db.get_user_lookback_stats.return_value = {"messages": 0, "voice_minutes": 0}
        self.bot.db.get_top_users.return_value = []
        self.bot.db.get_rank.return_value = 1
        self.bot.db.get_total_users.return_value = 1
        self.bot.config = MagicMock()
        self.bot.config.set = AsyncMock()
        self.bot.user = MagicMock()
        self.bot.user.name = "FlowerBot"
        self.bot.latency = 0.05
        self.bot.whitelisted_bots = []
        self.bot.log_action = AsyncMock()
        self.bot.update_balance = AsyncMock()
        
        self.mod_cog = Moderation(self.bot)
        with patch('discord.ext.tasks.Loop.start'):
            self.fun_cog = Fun(self.bot)
        self.level_cog = Leveling(self.bot)
        self.config_cog = ConfigCog(self.bot)
        self.security_cog = Security(self.bot)

    async def asyncTearDown(self):
        pass

    # --- Moderation Tests ---
    async def test_timeout_success(self):
        mock_ctx = AsyncMock()
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.name = "NaughtyUser"
        mock_member.mention = "@NaughtyUser"
        await self.mod_cog.timeout.callback(self.mod_cog, mock_ctx, mock_member, "30m", reason="Spamming")
        mock_member.timeout.assert_called_once_with(timedelta(minutes=30), reason="Spamming")
        mock_ctx.send.assert_called_once()
        self.assertIn("Successfully timed out @NaughtyUser for 30 minutes", mock_ctx.send.call_args[0][0])

    async def test_timeout_default_days(self):
        mock_ctx = AsyncMock()
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.name = "NaughtyUser"
        mock_member.mention = "@NaughtyUser"
        await self.mod_cog.timeout.callback(self.mod_cog, mock_ctx, mock_member, "1", reason="Spamming")
        mock_member.timeout.assert_called_once_with(timedelta(minutes=1440), reason="Spamming")
        mock_ctx.send.assert_called_once()
        self.assertIn("Successfully timed out @NaughtyUser for 1 day", mock_ctx.send.call_args[0][0])

    async def test_timeout_zero_minutes(self):
        mock_ctx = AsyncMock()
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.name = "NaughtyUser"
        await self.mod_cog.timeout.callback(self.mod_cog, mock_ctx, mock_member, 0, reason="Test")
        mock_member.timeout.assert_called_once_with(timedelta(minutes=0), reason="Test")
        mock_ctx.send.assert_called_once()

    async def test_clear_success(self):
        mock_ctx = AsyncMock()
        mock_ctx.channel = AsyncMock()
        await self.mod_cog.clear.callback(self.mod_cog, mock_ctx, amount=10)
        mock_ctx.channel.purge.assert_called_once_with(limit=11)
        mock_ctx.send.assert_called_once()
        self.assertIn("Cleared 10 messages", mock_ctx.send.call_args[0][0])

    async def test_slur_filter_word_boundaries(self):
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.author.mention = "@User"
        mock_message.channel = AsyncMock()
        
        # Should NOT delete 'Dickson'
        mock_message.content = "My name is Dickson"
        await self.security_cog.on_message(mock_message)
        mock_message.delete.assert_not_called()
        
        # Should delete 'dick'
        mock_message.content = "Don't be a dick"
        await self.security_cog.on_message(mock_message)
        mock_message.delete.assert_called_once()

    async def test_slur_filter_triggered(self):
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.author.mention = "@BadActor"
        mock_message.content = "nigger" # Using exact word from list
        mock_message.channel = AsyncMock()
        
        await self.security_cog.on_message(mock_message)
        mock_message.delete.assert_called_once()
        mock_message.channel.send.assert_called()
        self.assertIn("@BadActor - Please avoid using such language.", mock_message.channel.send.call_args[0][0])

    # --- Fun Commands Tests ---
    async def test_roll_command(self):
        mock_ctx = AsyncMock()
        await self.fun_cog.roll.callback(self.fun_cog, mock_ctx, sides=6)
        mock_ctx.send.assert_called_once()
        self.assertIn("You rolled a", mock_ctx.send.call_args[0][0])

    async def test_rps_command(self):
        mock_ctx = AsyncMock()
        await self.fun_cog.rps.callback(self.fun_cog, mock_ctx, choice="rock")
        mock_ctx.send.assert_called_once()
        self.assertIn("You chose **rock**", mock_ctx.send.call_args[0][0])

    async def test_coinflip_command(self):
        mock_ctx = AsyncMock()
        await self.fun_cog.coinflip.callback(self.fun_cog, mock_ctx)
        mock_ctx.send.assert_called_once()
        self.assertIn("It's **", mock_ctx.send.call_args[0][0])

    async def test_eightball_command(self):
        mock_ctx = AsyncMock()
        await self.fun_cog.eightball.callback(self.fun_cog, mock_ctx, question="Will it rain?")
        mock_ctx.send.assert_called_once()
        self.assertIn("🎱 **Q:** Will it rain?", mock_ctx.send.call_args[0][0])

    async def test_guess_command(self):
        mock_ctx = AsyncMock()
        await self.fun_cog.guess.callback(self.fun_cog, mock_ctx, number=5)
        mock_ctx.send.assert_called_once()
        self.assertIn("It was", mock_ctx.send.call_args[0][0])

    async def test_encourage_command(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.mention = "@User"
        await self.fun_cog.encourage.callback(self.fun_cog, mock_ctx)
        mock_ctx.send.assert_called_once()
        self.assertIn("@User", mock_ctx.send.call_args[0][0])

    async def test_auto_encouragement(self):
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.author.mention = "@SadUser"
        mock_message.content = "I am so sad today"
        mock_message.channel = AsyncMock()
        
        await self.fun_cog.on_message(mock_message)
        mock_message.channel.send.assert_called_with("I'm sorry you're feeling that way, @SadUser. ✨❤️")

    async def test_on_member_join_bot_no_ban(self):
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.bot = True
        mock_member.name = "BotUser"
        mock_member.created_at = discord.utils.utcnow() - timedelta(minutes=5)
        mock_member.avatar = None
        await self.security_cog.on_member_join(mock_member)
        mock_member.ban.assert_not_called()

    async def test_leaderboard_command(self):
        mock_ctx = AsyncMock()
        mock_ctx.guild = MagicMock()
        mock_ctx.guild.name = "Test Server"
        mock_ctx.guild.get_member.return_value = None
        # Mock database call - now returns 5 values (uid, xp, level, msgs, voice)
        self.bot.db.get_top_users.return_value = [('123', 100, 1, 5, 0)]
        self.bot.get_user.return_value = MagicMock(name="TestUser")
        
        await self.level_cog.leaderboard.callback(self.level_cog, mock_ctx)
        
        mock_ctx.send.assert_called_once()
        args, kwargs = mock_ctx.send.call_args
        embed = kwargs['embed']
        self.assertIn("Top Stats for Test Server", embed.title)
        self.assertIn("Top Members (Messages)", embed.fields[0].name)

    async def test_rank_command(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        mock_ctx.author.display_name = "TestUser"
        mock_ctx.author.display_avatar.url = "http://example.com/avatar.png"
        mock_ctx.guild.id = 1
        
        self.bot.db.get_user_data.return_value = {"xp": 50, "level": 1, "last_xp_time": 0, "message_count": 5, "voice_minutes": 0}
        self.bot.db.get_rank.return_value = 1
        self.bot.db.get_user_today_stats.return_value = {"messages": 1, "voice_minutes": 0}
        self.bot.db.get_user_lookback_stats.return_value = {"messages": 2, "voice_minutes": 0}
        
        await self.level_cog.rank.callback(self.level_cog, mock_ctx, member=None)
            
        mock_ctx.send.assert_called_once()
        args, kwargs = mock_ctx.send.call_args
        embed = kwargs['embed']
        self.assertIn("Activity Overview — TestUser", embed.title)
        # Fields: Messages, Voice, Leveling, XP & Progress, Next Reward
        self.assertIn("Total: **5**", embed.fields[0].value) # Messages
        self.assertIn("Today: **1**", embed.fields[0].value) # Messages Today
        self.assertIn("Level: **1**", embed.fields[2].value) # Leveling
        self.assertIn("Rank: **#1**", embed.fields[2].value) # Rank

    async def test_message_tracking_xp_gain(self):
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.author.id = 123
        mock_message.content = "hello world"
        mock_message.channel = AsyncMock()
        mock_message.guild = MagicMock()
        mock_message.guild.text_channels = []
        
        # Test XP gain with no cooldown (last_xp_time = 0)
        self.bot.db.get_ignored_channels.return_value = []
        self.bot.db.get_user_data.return_value = {"xp": 0, "level": 0, "last_xp_time": 0, "message_count": 0, "voice_minutes": 0}
        
        await self.level_cog.on_message(mock_message)
        
        self.bot.db.update_user_data.assert_called_once()
        args = self.bot.db.update_user_data.call_args[0]
        self.assertEqual(args[0], '123') # user_id
        self.assertGreater(args[1], 0)   # new_xp > 0
        self.assertGreater(args[3], 0)   # last_xp_time > 0

    async def test_message_tracking_cooldown(self):
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.author.id = 123
        mock_message.content = "hello again"
        mock_message.guild = MagicMock()
        mock_message.guild.text_channels = []
        
        # Test cooldown (last_xp_time is very recent)
        current_time = time.time()
        self.bot.db.get_ignored_channels.return_value = []
        self.bot.db.get_user_data.return_value = {"xp": 10, "level": 1, "last_xp_time": current_time, "message_count": 1, "voice_minutes": 0}
        
        await self.level_cog.on_message(mock_message)
        
        # Should still update message count but not XP
        self.bot.db.update_user_data.assert_called_once_with('123', 10, 1, current_time, 2, 0)

    async def test_add_xp_command(self):
        mock_ctx = AsyncMock()
        mock_member = MagicMock(spec=discord.Member)
        mock_member.id = 456
        mock_member.mention = "@User"
        
        self.bot.db.get_user_data.return_value = {"xp": 0, "level": 0, "last_xp_time": 0, "message_count": 0, "voice_minutes": 0}
        self.bot.db.get_role_rewards.return_value = {}
        self.bot.db.get_xp_boosts.return_value = {}
        
        await self.level_cog.add_xp.callback(self.level_cog, mock_ctx, mock_member, 500)
        
        self.bot.db.update_user_data.assert_called_once()
        self.assertGreater(self.bot.db.update_user_data.call_args[0][2], 0) # Level should have increased
        mock_ctx.send.assert_called_once()

    async def test_set_level_command(self):
        mock_ctx = AsyncMock()
        mock_member = MagicMock(spec=discord.Member)
        mock_member.id = 456
        mock_member.mention = "@User"
        
        self.bot.db.get_user_data.return_value = {"xp": 100, "level": 5, "last_xp_time": 0, "message_count": 10, "voice_minutes": 0}
        
        await self.level_cog.set_level.callback(self.level_cog, mock_ctx, mock_member, 10)
        
        self.bot.db.update_user_data.assert_called_once_with(456, 0, 10, 0, 10, 0)
        mock_ctx.send.assert_called_once()

    async def test_set_level_channel_command(self):
        mock_ctx = AsyncMock()
        mock_ctx.guild.id = 123
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = 789
        mock_channel.mention = "#levels"
        
        await self.config_cog.leveling.callback(self.config_cog, mock_ctx, notify_channel=mock_channel)
        
        self.bot.db.set_guild_setting.assert_called_once_with(123, "level_up_channel_id", "789")
        mock_ctx.send.assert_called_once()

    async def test_on_message_level_up_with_custom_channel(self):
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.author.id = 123
        mock_message.author.mention = "@User"
        mock_message.author.roles = []
        mock_message.content = "ping"
        mock_message.channel = AsyncMock()
        mock_message.guild = MagicMock()
        mock_message.guild.id = 123
        mock_message.guild.text_channels = []
        mock_message.author.guild = mock_message.guild
        
        mock_level_channel = AsyncMock(spec=discord.TextChannel)
        self.bot.db.get_guild_setting.return_value = 789
        self.bot.get_channel.return_value = mock_level_channel
        
        # Level up scenario: 90 XP, needs 100 to level up. Gaining 20 XP.
        self.bot.db.get_ignored_channels.return_value = []
        self.bot.db.get_user_data.return_value = {"xp": 90, "level": 0, "last_xp_time": 0, "message_count": 5, "voice_minutes": 0}
        self.bot.db.get_role_rewards.return_value = {}
        self.bot.db.get_xp_boosts.return_value = {}
        
        # Patch random to ensure level up
        with patch('random.randint', return_value=20):
            await self.level_cog.on_message(mock_message)
        
        mock_level_channel.send.assert_called_once()
        embed = mock_level_channel.send.call_args[1].get('embed')
        self.assertIsNotNone(embed)
        self.assertIn("Level 1", embed.description)
        self.assertIn(mock_message.author.mention, embed.description)
        # Should NOT send to original channel
        mock_message.channel.send.assert_not_called()

    async def test_on_message_ignored_channel(self):
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.author.id = 123
        mock_message.channel.id = 999
        mock_message.content = "ping"
        mock_message.guild = MagicMock()
        mock_message.guild.text_channels = []
        
        self.bot.db.get_ignored_channels.return_value = [999]
        
        await self.level_cog.on_message(mock_message)
        
        self.bot.db.get_user_data.assert_not_called()

    async def test_on_message_role_reward(self):
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.author = AsyncMock(spec=discord.Member)
        mock_message.author.bot = False
        mock_message.author.id = 123
        mock_message.author.mention = "@User"
        mock_message.guild = MagicMock()
        mock_message.author.guild = mock_message.guild
        mock_message.channel = AsyncMock()
        mock_message.channel.name = "general"
        mock_message.guild.text_channels = [mock_message.channel]
        
        mock_role = MagicMock(spec=discord.Role)
        mock_role.name = "Level 1 Role"
        mock_message.guild.get_role.return_value = mock_role
        
        # Level up to Level 1, reward at Level 1
        self.bot.db.get_ignored_channels.return_value = []
        self.bot.db.get_user_data.return_value = {"xp": 90, "level": 0, "last_xp_time": 0, "message_count": 5, "voice_minutes": 0}
        self.bot.db.get_role_rewards.return_value = {1: 555}
        self.bot.db.get_xp_boosts.return_value = {}
        
        with patch('random.randint', return_value=20):
            await self.level_cog.on_message(mock_message)
        
        mock_message.author.add_roles.assert_called_once_with(mock_role)
        mock_message.channel.send.assert_called()
        embed = mock_message.channel.send.call_args[1].get('embed')
        self.assertIsNotNone(embed)
        self.assertIn("Level 1 Role", embed.description)

    async def test_add_role_reward_command(self):
        mock_ctx = AsyncMock()
        mock_role = MagicMock(spec=discord.Role)
        mock_role.id = 555
        mock_role.name = "RewardRole"
        
        await self.level_cog.add_role_reward.callback(self.level_cog, mock_ctx, 5, mock_role)
        
        self.bot.db.add_role_reward.assert_called_once_with(5, 555)
        mock_ctx.send.assert_called_once()

    async def test_add_xp_command_with_role_reward(self):
        mock_ctx = AsyncMock()
        mock_ctx.guild = MagicMock()
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.id = 456
        mock_member.mention = "@User"
        
        mock_role = MagicMock(spec=discord.Role)
        mock_ctx.guild.get_role.return_value = mock_role
        
        # Level up from 0 to 1, reward at Level 1
        self.bot.db.get_user_data.return_value = {"xp": 0, "level": 0, "last_xp_time": 0, "message_count": 0, "voice_minutes": 0}
        self.bot.db.get_role_rewards.return_value = {1: 555}
        self.bot.db.get_xp_boosts.return_value = {}
        
        await self.level_cog.add_xp.callback(self.level_cog, mock_ctx, mock_member, 500)
        
        mock_member.add_roles.assert_called()
        mock_ctx.send.assert_called_once()

    async def test_ignore_channel_command(self):
        mock_ctx = AsyncMock()
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = 999
        mock_channel.mention = "#ignored"
        
        await self.level_cog.ignore_channel.callback(self.level_cog, mock_ctx, mock_channel)
        
        self.bot.db.add_ignored_channel.assert_called_once_with(999)
        mock_ctx.send.assert_called_once()

    async def test_reset_level_command(self):
        mock_ctx = AsyncMock()
        mock_member = MagicMock(spec=discord.Member)
        mock_member.id = 456
        mock_member.mention = "@User"
        
        await self.level_cog.reset_level.callback(self.level_cog, mock_ctx, mock_member)
        
        self.bot.db.update_user_data.assert_called_once_with(456, 0, 0, 0, 0, 0)
        mock_ctx.send.assert_called_once()

    async def test_leaderboard_pagination(self):
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 123
        
        # Mock 25 users to have 3 pages (10 per page)
        # users: (uid, xp, level, msg_count, voice_min)
        top_users = [(f'{i}', i*100, i, i*10, 0) for i in range(25, 0, -1)]
        self.bot.db.get_top_users.return_value = top_users
        self.bot.db.get_rank.return_value = 1
        self.bot.db.get_total_users.return_value = 25
        
        def mock_get_user(uid):
            m = MagicMock(spec=discord.User)
            m.display_name = f"User {uid}"
            return m
        self.bot.get_user.side_effect = mock_get_user
        
        view = LeaderboardView(self.bot, self.bot.db, self.level_cog, top_users, 123)
        
        # Test Page 1 (Users 25-16)
        embed = await view.create_leaderboard_embed(1)
        self.assertIn("Page 1", embed.footer.text)
        self.assertEqual(len(embed.fields), 10)
        self.assertIn("User 25", embed.fields[0].name)
        self.assertIn("User 16", embed.fields[9].name)
        
        # Test Page 2 (Users 15-6)
        embed = await view.create_leaderboard_embed(2)
        self.assertIn("Page 2", embed.footer.text)
        self.assertEqual(len(embed.fields), 10)
        self.assertIn("User 15", embed.fields[0].name)
        
        # Test Page 3 (Users 5-1)
        embed = await view.create_leaderboard_embed(3)
        self.assertIn("Page 3", embed.footer.text)
        self.assertEqual(len(embed.fields), 5)
        self.assertIn("User 5", embed.fields[0].name)

    async def test_leaderboard_view_buttons(self):
        # uid, xp, level, msgs, voice
        top_users = [(f'{i}', i*100, i, i*10, 0) for i in range(25, 0, -1)]
        self.bot.db.get_total_users.return_value = 25
        self.bot.db.get_rank.return_value = 1
        
        def mock_get_user(uid):
            m = MagicMock(spec=discord.User)
            m.display_name = f"User {uid}"
            return m
        self.bot.get_user.side_effect = mock_get_user
        
        view = LeaderboardView(self.bot, self.bot.db, self.level_cog, top_users, 123)
        
        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.response = AsyncMock()
        mock_button = MagicMock(spec=discord.ui.Button)
        
        # Test Next button: Page 1 -> 2
        await LeaderboardView.next(view, mock_interaction, mock_button)
        self.assertEqual(view.page, 2)
        mock_interaction.response.edit_message.assert_called_once()
        
        # Test Next button: Page 2 -> 3
        mock_interaction.response.edit_message.reset_mock()
        await LeaderboardView.next(view, mock_interaction, mock_button)
        self.assertEqual(view.page, 3)
        mock_interaction.response.edit_message.assert_called_once()
        
        # Test Next button: Page 3 -> 3 (Failure/No more pages)
        mock_interaction.response.send_message.reset_mock()
        await LeaderboardView.next(view, mock_interaction, mock_button)
        self.assertEqual(view.page, 3)
        mock_interaction.response.send_message.assert_called_with("No more pages!", ephemeral=True)
        
        # Test Previous button: Page 3 -> 2
        mock_interaction.response.edit_message.reset_mock()
        await LeaderboardView.previous(view, mock_interaction, mock_button)
        self.assertEqual(view.page, 2)
        mock_interaction.response.edit_message.assert_called_once()
        
        # Test Previous button: Page 2 -> 1
        mock_interaction.response.edit_message.reset_mock()
        await LeaderboardView.previous(view, mock_interaction, mock_button)
        self.assertEqual(view.page, 1)
        mock_interaction.response.edit_message.assert_called_once()
        
        # Test Previous button: Page 1 -> 1 (Failure/First page)
        mock_interaction.response.send_message.reset_mock()
        await LeaderboardView.previous(view, mock_interaction, mock_button)
        self.assertEqual(view.page, 1)
        mock_interaction.response.send_message.assert_called_with("You're on the first page!", ephemeral=True)

if __name__ == '__main__':
    unittest.main()
