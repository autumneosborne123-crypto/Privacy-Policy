import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands
from main import FlowerBot
from utils.database import Database
from cogs.moderation import Moderation

class TestMultiServerCheck(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = FlowerBot()
        self.bot.db = AsyncMock(spec=Database)
        
        # Guild 1: Moderation Enabled
        self.guild1 = MagicMock(spec=discord.Guild)
        self.guild1.id = 111
        self.guild1.name = "Guild 1"
        
        # Guild 2: Moderation Disabled
        self.guild2 = MagicMock(spec=discord.Guild)
        self.guild2.id = 222
        self.guild2.name = "Guild 2"
        
        self.mod_cog = Moderation(self.bot)
        await self.bot.add_cog(self.mod_cog)
        
        # Mock settings for check
        async def mock_get_settings(guild_id):
            if guild_id == 222:
                return {'disabled_cogs': 'moderation'}
            return {}
        
        self.bot.db.get_all_guild_settings.side_effect = mock_get_settings

    async def test_prefix_command_isolation(self):
        print("Testing prefix command isolation...")
        
        # Mock Context for Guild 1
        ctx1 = MagicMock(spec=commands.Context)
        ctx1.guild = self.guild1
        ctx1.cog = self.mod_cog
        ctx1.command = MagicMock()
        
        # Should return True (Enabled)
        res1 = await self.bot.global_cog_check(ctx1)
        self.assertTrue(res1, "Moderation should be enabled in Guild 1")
        
        # Mock Context for Guild 2
        ctx2 = MagicMock(spec=commands.Context)
        ctx2.guild = self.guild2
        ctx2.cog = self.mod_cog
        ctx2.command = MagicMock()
        ctx2.send = AsyncMock()
        
        # Should return False (Disabled)
        res2 = await self.bot.global_cog_check(ctx2)
        self.assertFalse(res2, "Moderation should be disabled in Guild 2")
        ctx2.send.assert_called()
        print("Prefix command isolation: PASSED")

    async def test_slash_command_protection(self):
        print("Testing slash command protection...")
        # Mock Interaction for Guild 2
        inter = MagicMock(spec=discord.Interaction)
        inter.guild = self.guild2
        inter.command = MagicMock()
        inter.command.binding = self.mod_cog
        inter.response = MagicMock()
        inter.response.is_done = MagicMock(return_value=False)
        inter.response.send_message = AsyncMock()
        
        # Should return False (Disabled)
        res = await self.bot.global_interaction_check(inter)
        self.assertFalse(res, "Slash command should be disabled in Guild 2")
        inter.response.send_message.assert_called_with("❌ The `Moderation` module is disabled in this server.", ephemeral=True)
        
        # Guild 1 should still work
        inter1 = MagicMock(spec=discord.Interaction)
        inter1.guild = self.guild1
        inter1.command = MagicMock()
        inter1.command.binding = self.mod_cog
        res1 = await self.bot.global_interaction_check(inter1)
        self.assertTrue(res1, "Slash command should be enabled in Guild 1")
        print("Slash command protection: PASSED")

    async def test_welcome_view_toggle(self):
        print("Testing WelcomeView toggle...")
        from main import WelcomeView
        view = WelcomeView(self.bot)
        
        inter = MagicMock(spec=discord.Interaction)
        inter.guild = self.guild2
        inter.user.guild_permissions.administrator = True
        inter.response = MagicMock()
        inter.response.send_message = AsyncMock()
        
        # Guild 2 has moderation disabled initially in our mock side_effect
        # Try calling with only interaction as discord.py wraps the decorator method
        try:
            await view.toggle_mod.callback(inter)
        except TypeError:
            # Fallback if it's not wrapped in this environment for some reason
            await view.toggle_mod.callback(inter, view.toggle_mod)
        
        # The mock side_effect returns {'disabled_cogs': 'moderation'} for 222
        self.bot.db.set_guild_setting.assert_any_call(222, "disabled_cogs", None)
        inter.response.send_message.assert_called_with("✅ Moderation module has been **Enabled** for this server.", ephemeral=True)
        print("WelcomeView toggle: PASSED")

if __name__ == "__main__":
    unittest.main()
