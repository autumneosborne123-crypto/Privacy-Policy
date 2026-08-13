import asyncio
import unittest
import os
from utils.database import Database
from cogs.adventure import Adventure
from unittest.mock import AsyncMock, MagicMock
import discord
import urllib.request

class TestAdventureVisualsFix(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_visuals_fix.db"
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

    async def test_image_urls_validity(self):
        """Check if all images in animals_data are reachable and not removed."""
        for species, data in self.adventure_cog.animals_data.items():
            url = data['image']
            print(f"Checking {species}: {url}")
            try:
                req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    self.assertEqual(response.status, 200, f"URL for {species} returned status {response.status}")
                    self.assertNotIn("removed.png", response.geturl(), f"URL for {species} redirected to removed.png")
            except Exception as e:
                self.fail(f"Failed to reach URL for {species}: {e}")

    async def test_animal_info_embed(self):
        """Verify animal_info embed uses the new image URL."""
        ctx = AsyncMock()
        ctx.author.id = 123456789
        ctx.author.display_avatar.url = "https://example.com/avatar.png"
        
        # Add an animal
        stats = {"hp": 100, "attack": 15, "defense": 10, "speed": 12}
        await self.db.add_animal(ctx.author.id, "fire_fox", "Foxy", stats, rarity="Uncommon")
        
        # Call animal_info
        await self.adventure_cog.animal_info.callback(self.adventure_cog, ctx, "Foxy")
        
        # Verify response
        ctx.send.assert_called_once()
        args, kwargs = ctx.send.call_args
        embed = kwargs["embed"]
        
        self.assertEqual(embed.title, "🐾 Foxy")
        self.assertEqual(embed.image.url, "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/653.png")

if __name__ == "__main__":
    unittest.main()
