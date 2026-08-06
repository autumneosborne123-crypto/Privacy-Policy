import asyncio
import unittest
import os
from utils.database import Database
from cogs.adventure import Adventure
from unittest.mock import AsyncMock, MagicMock
import discord

class TestCatchVisuals(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_catch_visuals.db"
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
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_catch_image_presence(self):
        ctx = AsyncMock()
        ctx.author.id = 123456789
        ctx.author.display_name = "TestUser"
        ctx.author.display_avatar.url = "https://example.com/avatar.png"
        ctx.guild.id = 987654321
        
        # Add bait
        await self.db.add_item(ctx.author.id, "ultra_bait", 5)
        
        # Run catch multiple times to cover both success and escape
        found_success = False
        found_escape = False
        
        for _ in range(20):
            ctx.send.reset_mock()
            await self.adventure_cog.catch.callback(self.adventure_cog, ctx)
            
            if not ctx.send.called:
                continue

            args, kwargs = ctx.send.call_args
            self.assertIn("embed", kwargs)
            embed = kwargs["embed"]
            
            # Verify image is present
            self.assertIsNotNone(embed.image.url, f"Image URL is missing in embed for {embed.title}")
            self.assertTrue(
                embed.image.url.startswith("https://raw.githubusercontent.com/PokeAPI/"), 
                f"Unexpected image URL: {embed.image.url}"
            )
            
            # Verify thumbnail is present (user avatar)
            self.assertEqual(embed.thumbnail.url, "https://example.com/avatar.png")
            
            if "Success" in embed.title:
                found_success = True
            if "Escaped" in embed.title:
                found_escape = True
        
        self.assertTrue(found_success or found_escape, "Should have triggered at least one catch attempt result")
        print("Verified images and thumbnails are present in catch embeds (PokeAPI).")

if __name__ == "__main__":
    unittest.main()
