import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Literal
from pinterest_dl import ApiScraper
import random
import asyncio
import logging

from utils.permissions import is_admin

class Media(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scraper = ApiScraper()
        self.min_res = (0, 0)
        self.nsfw_keywords = [
            "nsfw", "nude", "naked", "porn", "sex", "hentai", "rule34", "xxx", "r34", 
            "lewd", "ero", "fetish", "erotic", "adult", "explicit", "undress",
            "sexy", "bikini", "lingerie", "bra", "panties"
        ]
        self.banner_styles = ["realism", "aesthetic", "animal", "pattern", "cute", "cool", "hot"]
        self.queries = {
            "female-pfp": "real life female pfp aesthetic",
            "male-pfp": "real life male pfp boy aesthetic",
            "female-gif": "real life female aesthetic animated gif",
            "male-gif": "real life male aesthetic animated gif",
            "anime-pfp": "anime pfp aesthetic",
            "manga-pfp": "manga pfp icon aesthetic",
            "matching-pfp": "matching pfp couples aesthetic",
            "couple-pfp": "couple pfp aesthetic real life",
            "kpop-pfp": "kpop idol aesthetic pfp",
            "pets-pfp": "cute animal pfp aesthetic",
            "icon-pfp": "aesthetic discord icons",
            "edgy-pfp": "edgy aesthetic pfp",
            "retro-pfp": "retro aesthetic pfp",
            "cyberpunk-pfp": "cyberpunk aesthetic pfp",
            "banner": "aesthetic discord banner",
            "banner-gif": "aesthetic discord banner animated gif"
        }
        self.media_loop.start()
        self.cleanup_task.start()

    def cog_unload(self):
        self.media_loop.cancel()
        self.cleanup_task.cancel()

    @tasks.loop(hours=24)
    async def cleanup_task(self):
        await self.bot.db.cleanup_sent_media(days=3)

    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        try:
            await self.bot.wait_until_ready()
        except RuntimeError as error:
            if "not been properly initialised" not in str(error):
                raise

    @tasks.loop(minutes=2)
    async def media_loop(self):
        try:
            feeds = await self.bot.db.get_media_feeds()
            # Randomize order to avoid hitting same guilds at same time every loop
            random.shuffle(feeds)
            
            for feed_id, guild_id, channel_id, category in feeds:
                channel = self.bot.get_channel(int(channel_id))
                if not channel: continue
                
                # Check permissions before attempting to send media to avoid 403 Forbidden spam
                permissions = channel.permissions_for(channel.guild.me)
                if not (permissions.send_messages and permissions.embed_links):
                    continue

                query = self.queries.get(category.lower(), f"{category} aesthetic")
                
                # Special handling for banners to include variety of styles
                if "banner" in category.lower():
                    style = random.choice(self.banner_styles)
                    query = f"{style} discord banner"
                    if "gif" in category.lower():
                        query += " animated gif"

                gif_only = "gif" in category.lower()
                urls = await self.fetch_images(query, num=10, gif_only=gif_only)
                
                if urls:
                    url = await self.pick_suitable_image(urls)
                    if url:
                        embed = discord.Embed(color=0xffb6c1)
                        embed.set_image(url=url)
                        embed.set_footer(text=f"Category: {category} | 2-Minute Feed")
                        try:
                            await channel.send(embed=embed)
                        except discord.HTTPException as e:
                            if e.status == 429:
                                logging.warning(f"Rate limit hit in media loop (Channel: {channel_id}), sleeping 2 minutes...")
                                await asyncio.sleep(120)
                            else:
                                logging.error(f"Failed to send media feed to {channel_id}: {e}")
                        except Exception as e:
                            logging.error(f"Failed to send media feed to {channel_id}: {e}")
                
                # Minor delay between different feeds to avoid global rate limit while keeping up with 2min interval
                await asyncio.sleep(random.randint(2, 5)) 
        except Exception as e:
            logging.error(f"Error in media loop: {e}")

    @media_loop.before_loop
    async def before_media_loop(self):
        try:
            await self.bot.wait_until_ready()
        except RuntimeError as error:
            if "not been properly initialised" not in str(error):
                raise

    def is_sfw_url(self, url: str) -> bool:
        url_lower = url.lower()
        return not any(word in url_lower for word in self.nsfw_keywords)

    async def fetch_images(self, query, num=30, gif_only=False):
        # No longer appending 'sfw' as it breaks many queries on Pinterest
        # We rely on is_sfw_url to filter out suspicious URLs
        loop = asyncio.get_event_loop()
        try:
            # Running in executor because pinterest-dl is synchronous
            results = await loop.run_in_executor(None, lambda: self.scraper.search(query=query, num=num, min_resolution=self.min_res))
            urls = [item.src for item in results]
            # Filter URLs for safety
            filtered = [url for url in urls if self.is_sfw_url(url)]
            if gif_only:
                filtered = [url for url in filtered if ".gif" in url.lower()]
            return filtered
        except Exception as e:
            logging.error(f"Pinterest search error for query '{query}': {e}")
            return []

    async def pick_suitable_image(self, urls):
        if not urls: return None
        
        # Shuffle to pick a random one that isn't sent
        random.shuffle(urls)
        for url in urls:
            if await self.bot.db.claim_media_url(url):
                return url
        
        # If all are sent, just return the first one (fallback)
        return urls[0]

    async def send_random_image(self, ctx, query, title):
        await ctx.defer()
        
        actual_query = query
        gif_only = "gif" in title.lower() or "gif" in query.lower()
        urls = await self.fetch_images(actual_query, gif_only=gif_only)
        if not urls:
            return await ctx.send("❌ Could not find any images on Pinterest for this category.", ephemeral=True)
        
        url = await self.pick_suitable_image(urls)
        embed = discord.Embed(title=title, color=0xffb6c1)
        embed.set_image(url=url)
        embed.set_footer(text="Source: Pinterest | Flower Media")
        await ctx.send(embed=embed)


    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore our own messages
        if message.author.id == self.bot.user.id:
            return

        # Check if author is a whitelisted PFP bot
        # PFP Bot ID: 1373666241033535558
        if message.author.id in self.bot.whitelisted_bots:
            for embed in message.embeds:
                image_url = None
                if embed.image:
                    image_url = embed.image.url
                elif embed.thumbnail:
                    image_url = embed.thumbnail.url
                
                if not image_url:
                    continue

                # Determine category from embed content
                title = (embed.title or "").lower()
                desc = (embed.description or "").lower()
                footer = (embed.footer.text or "").lower()
                content = f"{title} {desc} {footer}"
                
                category = None
                content_words = content.split()
                
                if "anime" in content:
                    category = "anime_pfp"
                elif "manga" in content:
                    category = "manga_pfp"
                elif any(w in content for w in ["banner", "bg", "background"]):
                    if "gif" in content or ".gif" in image_url.lower():
                        category = "banner_gif"
                    else:
                        category = "banner"
                elif any(w in content for w in ["matching", "couple"]):
                    category = "matching_pfp"
                elif any(w in content for w in ["female", "girl", "woman", "lady"]):
                    if "gif" in content or ".gif" in image_url.lower():
                        category = "female_gif"
                    else:
                        category = "female_pfp"
                elif any(w in content for w in ["male", "boy", "man", "guy"]):
                    if "gif" in content or ".gif" in image_url.lower():
                        category = "male_gif"
                    else:
                        category = "male_pfp"
                
                if category:
                    media_config = self.bot.config.get("media_channels", {})
                    channel_id = media_config.get(category)
                    if channel_id:
                        target_channel = self.bot.get_channel(int(channel_id))
                        if target_channel and target_channel.id != message.channel.id:
                            # Create a clean mirror embed
                            mirror_embed = discord.Embed(color=0xffb6c1)
                            mirror_embed.set_image(url=image_url)
                            mirror_embed.set_footer(text=f"Mirror: {category.replace('_', ' ').title()} | Flower Media")
                            try:
                                await target_channel.send(embed=mirror_embed)
                                logging.info(f"Mirrored {category} from {message.author.id} to {target_channel.id}")
                            except Exception as e:
                                logging.error(f"Failed to send mirrored media to {target_channel.id}: {e}")

    @commands.hybrid_command(name="populate_media", description="Populate the current channel with images from a category")
    @is_admin()
    async def populate_media(self, ctx, category: str, count: int = 5):
        if count > 10: count = 10
        await ctx.defer()
        
        query = self.queries.get(category.lower(), f"{category} aesthetic")
        
        # Special handling for banners to include variety of styles
        if "banner" in category.lower():
            style = random.choice(self.banner_styles)
            query = f"{style} discord banner"
            if "gif" in category.lower():
                query += " animated gif"
        
        gif_only = "gif" in category.lower()
        urls = await self.fetch_images(query, num=50, gif_only=gif_only)
        
        if not urls:
            return await ctx.send(f"❌ Could not find images for `{category}`.", ephemeral=True)
        
        # Filter duplicates for population too
        selected = []
        for url in urls:
            if not await self.bot.db.is_media_sent(url):
                selected.append(url)
                if len(selected) >= count: break
        
        if not selected: # All were duplicates, just take what we have
            selected = random.sample(urls, min(count, len(urls)))
        
        for url in selected:
            await self.bot.db.mark_media_sent(url)
        
        await ctx.send(f"✅ Found {len(selected)} images for `{category}`. Posting now...")
        await self.bot.log_action(ctx.guild, "🖼️ Media Populated", f"**Category:** {category}\n**Count:** {len(selected)}\n**Channel:** {ctx.channel.mention}", color=0xffb6c1, moderator=ctx.author)
        
        for url in selected:
            embed = discord.Embed(color=0xffb6c1)
            embed.set_image(url=url)
            embed.set_footer(text=f"Category: {category} | Pinterest")
            await ctx.send(embed=embed)
            await asyncio.sleep(1) # Rate limit protection

    @commands.hybrid_command(name="auto_populate", description="Automatically populate all configured media channels")
    @is_admin()
    async def auto_populate(self, ctx, count: int = 5):
        """Send media to all predefined channels for this server."""
        if count > 10: count = 10
        await ctx.defer()
        
        media_config = self.bot.config.get("media_channels", {})
        if not media_config:
            return await ctx.send("❌ Media channels not configured.", ephemeral=True)
            
        mapping = {
            "female_pfp": "female-pfp",
            "male_pfp": "male-pfp",
            "female_gif": "female-gif",
            "male_gif": "male-gif",
            "anime_pfp": "anime-pfp",
            "manga_pfp": "manga-pfp",
            "matching_pfp": "matching-pfp",
            "couple_pfp": "couple-pfp",
            "kpop_pfp": "kpop-pfp",
            "pets_pfp": "pets-pfp",
            "icon_pfp": "icon-pfp",
            "edgy_pfp": "edgy-pfp",
            "retro_pfp": "retro-pfp",
            "cyberpunk_pfp": "cyberpunk-pfp",
            "banner": "banner",
            "banner_gif": "banner-gif"
        }
        
        status_msg = await ctx.send("🚀 Starting auto-population of media channels...")
        results = []
        
        for config_key, internal_category in mapping.items():
            channel_id = media_config.get(config_key)
            if not channel_id or channel_id == 0: continue
            
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(int(channel_id))
                except:
                    results.append(f"❌ Channel not found for `{config_key}`")
                    continue
            
            # Check permissions
            permissions = channel.permissions_for(channel.guild.me)
            if not (permissions.send_messages and permissions.embed_links):
                results.append(f"❌ Missing permissions in {channel.mention}")
                continue

            query = self.queries.get(internal_category)
            
            # Special handling for banners
            if "banner" in internal_category.lower():
                style = random.choice(self.banner_styles)
                query = f"{style} discord banner"
                if "gif" in internal_category.lower():
                    query += " animated gif"
                
            gif_only = "gif" in internal_category.lower()
            urls = await self.fetch_images(query, num=50, gif_only=gif_only)
            if not urls:
                results.append(f"⚠️ No images found for `{internal_category}`")
                continue
            
            selected = []
            for url in urls:
                if not await self.bot.db.is_media_sent(url):
                    selected.append(url)
                    if len(selected) >= count: break
            
            if not selected:
                selected = random.sample(urls, min(count, len(urls)))
            
            sent_count = 0
            for url in selected:
                await self.bot.db.mark_media_sent(url)
                embed = discord.Embed(color=0xffb6c1)
                embed.set_image(url=url)
                embed.set_footer(text=f"Category: {internal_category} | Pinterest")
                try:
                    await channel.send(embed=embed)
                    sent_count += 1
                    await asyncio.sleep(1)
                except Exception as e:
                    logging.error(f"Error sending to {channel.name}: {e}")
            
            results.append(f"✅ Sent {sent_count} images to {channel.mention}")
            
        await status_msg.edit(content="🏁 **Auto-population complete!**\n" + "\n".join(results))
        await self.bot.log_action(ctx.guild, "🖼️ Auto-Population", f"**{ctx.author}** triggered auto-population.\n" + "\n".join(results), color=0xffb6c1, moderator=ctx.author)

    @commands.hybrid_command(name="avatar", aliases=["pfp", "av"], description="Show a member's avatar")
    async def avatar(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=f"Avatar of {member.name}", color=member.color)
        embed.set_image(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_group(name="media", aliases=["media_add"], description="Manage automatic media feeds (every 2 minutes)")
    @is_admin()
    async def media_feed(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Usage: `.media <add|remove|list>`", ephemeral=True)

    @media_feed.command(name="add", description="Add an automatic media feed to a channel")
    async def media_feed_add(self, ctx, category: Literal["female-pfp", "male-pfp", "female-gif", "male-gif", "anime-pfp", "manga-pfp", "matching-pfp", "couple-pfp", "kpop-pfp", "pets-pfp", "icon-pfp", "edgy-pfp", "retro-pfp", "cyberpunk-pfp", "banner", "banner-gif"], channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        await self.bot.db.add_media_feed(ctx.guild.id, channel.id, category)
        await ctx.send(f"✅ Added **{category}** media feed to {channel.mention}. It will post every 2 minutes.")
        await self.bot.log_action(ctx.guild, "🖼️ Media Feed Added", f"**Category:** {category}\n**Channel:** {channel.mention}", color=0xffb6c1, moderator=ctx.author)

    @media_feed.command(name="remove", description="Remove a media feed by its ID")
    async def media_feed_remove(self, ctx, feed_id: int):
        await self.bot.db.remove_media_feed(feed_id)
        await ctx.send(f"✅ Removed media feed with ID `{feed_id}`.")
        await self.bot.log_action(ctx.guild, "🖼️ Media Feed Removed", f"**Feed ID:** {feed_id}", color=0xe74c3c, moderator=ctx.author)

    @media_feed.command(name="list", description="List all media feeds for this guild")
    async def media_feed_list(self, ctx):
        feeds = await self.bot.db.get_media_feeds(ctx.guild.id)
        if not feeds:
            return await ctx.send("❌ No media feeds configured for this guild.", ephemeral=True)
        
        embed = discord.Embed(title="🖼️ Media Feeds", color=0xffb6c1)
        description = ""
        for feed_id, channel_id, category in feeds:
            description += f"**ID:** `{feed_id}` | **Channel:** <#{channel_id}> | **Category:** `{category}`\n"
        
        embed.description = description
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Media(bot))
