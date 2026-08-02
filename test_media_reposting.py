
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from cogs.media import Media

class TestMediaReposting(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.bot.user.id = 12345
        self.bot.whitelisted_bots = [422087909634736160, 1373666241033535558] # PFP Bot ID
        self.bot.config = MagicMock()
        self.bot.config.get = MagicMock(side_effect=lambda key, default=None: {
            "media_channels": {
                "female_pfp": 101,
                "male_pfp": 102,
                "female_gif": 103,
                "male_gif": 104,
                "banner": 105,
                "banner_gif": 106,
                "anime_pfp": 107,
                "manga_pfp": 108
            }
        }.get(key, default))
        
        # Mock get_channel
        self.channels = {}
        media_channels = {
            "female_pfp": 101,
            "male_pfp": 102,
            "female_gif": 103,
            "male_gif": 104,
            "banner": 105,
            "banner_gif": 106,
            "anime_pfp": 107,
            "manga_pfp": 108
        }
        for name, cid in media_channels.items():
            mock_channel = AsyncMock(spec=discord.TextChannel)
            mock_channel.id = cid
            mock_channel.name = name
            mock_channel.send = AsyncMock()
            self.channels[cid] = mock_channel
            
        self.bot.get_channel = MagicMock(side_effect=lambda cid: self.channels.get(int(cid)))
        
        # Patch tasks in Media cog initialization
        with patch('cogs.media.Media.media_loop'), \
             patch('cogs.media.Media.cleanup_task'):
            self.cog = Media(self.bot)

    async def test_on_message_ignores_self(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = self.bot.user.id
        await self.cog.on_message(message)
        self.bot.get_channel.assert_not_called()

    async def test_on_message_ignores_non_whitelisted(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = 999
        await self.cog.on_message(message)
        self.bot.get_channel.assert_not_called()

    async def test_repost_female_pfp(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = 1373666241033535558
        message.channel.id = 999
        
        embed = MagicMock(spec=discord.Embed)
        embed.image.url = "http://example.com/girl.png"
        embed.thumbnail = None
        embed.title = "Aesthetic Female PFP"
        embed.description = ""
        embed.footer.text = ""
        message.embeds = [embed]
        
        await self.cog.on_message(message)
        
        target_channel = self.channels[101]
        target_channel.send.assert_called_once()
        args, kwargs = target_channel.send.call_args
        sent_embed = kwargs.get('embed') or args[0]
        self.assertEqual(sent_embed.image.url, "http://example.com/girl.png")
        self.assertIn("Female Pfp", sent_embed.footer.text)

    async def test_repost_male_gif(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = 1373666241033535558
        message.channel.id = 999
        
        embed = MagicMock(spec=discord.Embed)
        embed.image = None
        embed.thumbnail.url = "http://example.com/boy.gif"
        embed.title = "Cool Boy GIF"
        embed.description = ""
        embed.footer.text = ""
        message.embeds = [embed]
        
        await self.cog.on_message(message)
        
        target_channel = self.channels[104]
        target_channel.send.assert_called_once()
        args, kwargs = target_channel.send.call_args
        sent_embed = kwargs.get('embed') or args[0]
        self.assertEqual(sent_embed.image.url, "http://example.com/boy.gif")
        self.assertIn("Male Gif", sent_embed.footer.text)

    async def test_repost_banner(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = 1373666241033535558
        message.channel.id = 999
        
        embed = MagicMock(spec=discord.Embed)
        embed.image.url = "http://example.com/banner.jpg"
        embed.thumbnail = None
        embed.title = "Aesthetic Banner"
        embed.description = ""
        embed.footer.text = ""
        message.embeds = [embed]
        
        await self.cog.on_message(message)
        
        target_channel = self.channels[105]
        target_channel.send.assert_called_once()

    async def test_repost_anime_pfp(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = 1373666241033535558
        message.channel.id = 999
        
        embed = MagicMock(spec=discord.Embed)
        embed.image.url = "http://example.com/anime.png"
        embed.thumbnail = None
        embed.title = "Anime PFP Collection"
        embed.description = ""
        embed.footer.text = ""
        message.embeds = [embed]
        
        await self.cog.on_message(message)
        
        target_channel = self.channels[107]
        target_channel.send.assert_called_once()

    async def test_repost_manga_pfp(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = 1373666241033535558
        message.channel.id = 999
        
        embed = MagicMock(spec=discord.Embed)
        embed.image.url = "http://example.com/manga.png"
        embed.thumbnail = None
        embed.title = "Aesthetic Manga Icon"
        embed.description = ""
        embed.footer.text = ""
        message.embeds = [embed]
        
        await self.cog.on_message(message)
        
        target_channel = self.channels[108]
        target_channel.send.assert_called_once()

    async def test_repost_banner_gif(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = 1373666241033535558
        message.channel.id = 999
        
        embed = MagicMock(spec=discord.Embed)
        embed.image.url = "http://example.com/banner.gif"
        embed.thumbnail = None
        embed.title = "Aesthetic Animated Banner GIF"
        embed.description = ""
        embed.footer.text = ""
        message.embeds = [embed]
        
        await self.cog.on_message(message)
        
        target_channel = self.channels[106]
        target_channel.send.assert_called_once()

    async def test_repost_female_gif(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = 1373666241033535558
        message.channel.id = 999
        
        embed = MagicMock(spec=discord.Embed)
        embed.image.url = "http://example.com/female.gif"
        embed.thumbnail = None
        embed.title = "Aesthetic Girl GIF"
        embed.description = ""
        embed.footer.text = ""
        message.embeds = [embed]
        
        await self.cog.on_message(message)
        
        target_channel = self.channels[103]
        target_channel.send.assert_called_once()

    async def test_repost_male_pfp(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = 1373666241033535558
        message.channel.id = 999
        
        embed = MagicMock(spec=discord.Embed)
        embed.image.url = "http://example.com/male.png"
        embed.thumbnail = None
        embed.title = "Aesthetic Boy PFP"
        embed.description = ""
        embed.footer.text = ""
        message.embeds = [embed]
        
        await self.cog.on_message(message)
        
        target_channel = self.channels[102]
        target_channel.send.assert_called_once()

    async def test_keyword_priority_banner_over_female(self):
        # Even if "female" is in the title, if "banner" is there, it should go to banner
        message = MagicMock(spec=discord.Message)
        message.author.id = 1373666241033535558
        message.channel.id = 999
        
        embed = MagicMock(spec=discord.Embed)
        embed.image.url = "http://example.com/banner.png"
        embed.thumbnail = None
        embed.title = "Female Aesthetic Banner"
        embed.description = ""
        embed.footer.text = ""
        message.embeds = [embed]
        
        await self.cog.on_message(message)
        
        # Priority: anime > manga > banner > female > male
        target_channel = self.channels[105] # banner
        target_channel.send.assert_called_once()

    async def test_keyword_guy_mapping_to_male_pfp(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = 1373666241033535558
        message.channel.id = 999
        
        embed = MagicMock(spec=discord.Embed)
        embed.image.url = "http://example.com/guy.png"
        embed.thumbnail = None
        embed.title = "Cool Guy PFP"
        embed.description = ""
        embed.footer.text = ""
        message.embeds = [embed]
        
        await self.cog.on_message(message)
        
        target_channel = self.channels[102] # male_pfp
        target_channel.send.assert_called_once()

    async def test_female_banner_gif(self):
        message = MagicMock(spec=discord.Message)
        message.author.id = 1373666241033535558
        message.channel.id = 999
        
        embed = MagicMock(spec=discord.Embed)
        embed.image.url = "http://example.com/female_banner.gif"
        embed.thumbnail = None
        embed.title = "Female Animated Banner"
        embed.description = ""
        embed.footer.text = ""
        message.embeds = [embed]
        
        await self.cog.on_message(message)
        
        # Priority: anime > manga > banner > female > male
        # Should go to banner_gif
        target_channel = self.channels[106] # banner_gif
        target_channel.send.assert_called_once()

if __name__ == '__main__':
    unittest.main()
