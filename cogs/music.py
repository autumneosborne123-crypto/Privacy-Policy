import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import random
import shutil
import time
import logging
import json
import lyricsgenius
import syncedlyrics
import re
import os

# Music Configuration
yt_dlp.utils.bug_reports_message = lambda *args, **kwargs: ''
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'extractor_args': {
        'youtube': {
            'player_client': ['ios', 'android', 'mweb'],
        }
    }
}
FFMPEG_OPTIONS = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 10M -analyzeduration 0'
}

FILTERS = {
    'bassboost': 'bass=g=20,dynaudnorm=f=200',
    'nightcore': 'asetrate=48000*1.25,aresample=48000,atempo=1.25',
    'vaporwave': 'asetrate=48000*0.8,aresample=48000,atempo=0.8',
    '8d': 'apulsator=hz=0.125',
}

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, data=None, loop=None, stream=False, audio_filter=None):
        loop = loop or asyncio.get_event_loop()
        
        if data is None:
            # Determine if it's a direct URL or search query
            if not url.startswith(('http://', 'https://')):
                url = f"ytsearch:{url}"
                
            def extract():
                with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                    info = ydl.extract_info(url, download=not stream)
                    if 'entries' in info:
                        info = info['entries'][0]
                    return info
                    
            data = await loop.run_in_executor(None, extract)
        
        # Check for 'fake' data (Sign in pages, etc)
        title = data.get('title', 'Unknown')
        if "Sign in" in title or "confirm you're not a bot" in title.lower():
            raise Exception("YouTube blocked extraction (Sign in required)")

        filename = data['url'] if stream else yt_dlp.prepare_filename(data)
        
        options = FFMPEG_OPTIONS['options']
        if audio_filter and audio_filter in FILTERS:
            options += f' -af "{FILTERS[audio_filter]}"'
            
        return cls(discord.FFmpegPCMAudio(filename, before_options=FFMPEG_OPTIONS['before_options'], options=options), data=data)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.current_tracks = {}
        self.loops = {}
        self.volumes = {}
        self.start_times = {}
        self.pause_times = {}
        self.total_paused_durations = {}
        self.autoplays = {}
        self.lyrics_tasks = {}
        self.active_filters = {}
        self.genius = lyricsgenius.Genius(os.getenv('GENIUS_TOKEN', "Your_Genius_API_Token_Here"))
        self.genius.verbose = False
        self.genius.remove_section_headers = True

    def is_dj():
        async def predicate(ctx):
            if ctx.author.guild_permissions.administrator:
                return True
            dj_role = discord.utils.get(ctx.guild.roles, name="DJ")
            if dj_role and dj_role in ctx.author.roles:
                return True
            
            # Allow if there's no DJ role in the server (fallback)
            if dj_role is None:
                return True
                
            await ctx.send("❌ This command is restricted to DJs.", ephemeral=True)
            return False
        return commands.check(predicate)

    def is_music_channel():
        async def predicate(ctx):
            # Check database first
            db_channel_id = await ctx.bot.db.get_guild_setting(ctx.guild.id, "music_channel_id", int)
            if db_channel_id and ctx.channel.id == db_channel_id:
                return True
            
            # Fallback to names if no setting
            if ctx.channel.name == 'music': return True
            if ctx.author.voice and ctx.author.voice.channel and 'music' in ctx.author.voice.channel.name.lower(): return True
            
            msg = "❌ Use this in the designated music channel"
            if db_channel_id:
                chan = ctx.bot.get_channel(db_channel_id)
                if chan: msg += f" ({chan.mention})"
            else:
                msg += " (#music)"
            
            await ctx.send(msg, ephemeral=True)
            return False
        return commands.check(predicate)

    def get_queue(self, guild_id):
        if guild_id not in self.queues: self.queues[guild_id] = []
        return self.queues[guild_id]

    async def get_autoplay_song(self, last_track):
        try:
            search_query = f"ytsearch5:related to {last_track['title']} {last_track.get('uploader', '')}"
            def extract():
                with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                    return ydl.extract_info(search_query, download=False)
            data = await self.bot.loop.run_in_executor(None, extract)
            if 'entries' in data and data['entries']:
                # Pick a random one from top 5 to avoid infinite loops of same song
                return random.choice(data['entries'])
        except Exception as e:
            logging.error(f"Autoplay search error: {e}")
        return None

    async def play_next(self, ctx):
        if not ctx.voice_client:
            return

        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        
        if self.loops.get(guild_id) and self.current_tracks.get(guild_id):
            data = self.current_tracks.get(guild_id)
        elif queue:
            data = queue.pop(0)
            self.current_tracks[guild_id] = data
        elif self.autoplays.get(guild_id) and self.current_tracks.get(guild_id):
            last_track = self.current_tracks.get(guild_id)
            data = await self.get_autoplay_song(last_track)
            if data:
                self.current_tracks[guild_id] = data
                await ctx.send(f"📻 **Autoplay:** Now playing **{data['title']}**")
            else:
                self.current_tracks[guild_id] = None
                return
        else:
            self.current_tracks[guild_id] = None
            return

        try:
            audio_filter = self.active_filters.get(guild_id)
            # Use data directly if it has the stream URL, otherwise re-extract (rare now)
            if 'url' in data:
                player = await YTDLSource.from_url(None, data=data, stream=True, audio_filter=audio_filter)
            else:
                player = await YTDLSource.from_url(data['webpage_url'], stream=True, audio_filter=audio_filter)
                
            player.volume = self.volumes.get(guild_id, 0.5)
            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))
            self.start_times[guild_id] = time.time()
            self.total_paused_durations[guild_id] = 0
            await ctx.send(f"🎶 **Now playing:** {data['title']}")
        except Exception as e:
            logging.error(f"Music error in {ctx.guild.name}: {e}")
            await ctx.send(f"❌ Error playing song: {e}")
            await self.play_next(ctx)

    async def music_play_logic(self, ctx, query: str):
        if not shutil.which("ffmpeg"):
            return await ctx.send("❌ FFmpeg is not installed on this server.", ephemeral=True)
        if not ctx.author.voice:
            return await ctx.send("❌ You must be in a voice channel!")
        
        await ctx.defer()
        
        if not ctx.voice_client:
            try:
                await ctx.author.voice.channel.connect(timeout=20, reconnect=True)
            except asyncio.TimeoutError:
                return await ctx.send("❌ Failed to connect to voice channel (Timeout).")
            except Exception as e:
                return await ctx.send(f"❌ Failed to connect to voice: {e}")

        async with ctx.typing():
            try:
                # Use ytsearch prefix if not a URL
                search_query = query if query.startswith(('http://', 'https://')) else f"ytsearch:{query}"
                
                def extract():
                    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                        return ydl.extract_info(search_query, download=False)
                
                data = await self.bot.loop.run_in_executor(None, extract)
                if 'entries' in data and data['entries']: 
                    data = data['entries'][0]
                elif 'entries' in data:
                    return await ctx.send("❌ No results found.")
                    
                self.get_queue(ctx.guild.id).append(data)
                
                if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                    await self.play_next(ctx)
                else:
                    await ctx.send(f"✅ Added **{data['title']}** to the queue.")
            except Exception as e:
                logging.error(f"Extraction error for {query}: {e}")
                await ctx.send(f"❌ An error occurred while searching: {e}")

    @commands.hybrid_group(name="music", description="Music player commands")
    @is_music_channel()
    async def music(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `/music play`, `/music skip`, etc.")

    @music.command(name="play", description="Play or queue a song")
    async def play(self, ctx, *, query: str):
        await self.music_play_logic(ctx, query)

    @music.command(name="skip", description="Skip the current song")
    @is_dj()
    async def skip(self, ctx):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("❌ Nothing is playing.")
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skipped!")

    @music.command(name="stop", description="Stop and disconnect")
    @is_dj()
    async def stop(self, ctx):
        if not ctx.voice_client: return await ctx.send("❌ Not in a voice channel.")
        self.queues[ctx.guild.id] = []
        self.current_tracks[ctx.guild.id] = None
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ Stopped and disconnected.")

    @music.command(name="pause", description="Pause music")
    @is_dj()
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            self.pause_times[ctx.guild.id] = time.time()
            await ctx.send("⏸️ Paused.")

    @music.command(name="resume", description="Resume music")
    @is_dj()
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            if ctx.guild.id in self.pause_times:
                paused_for = time.time() - self.pause_times.pop(ctx.guild.id)
                self.total_paused_durations[ctx.guild.id] = self.total_paused_durations.get(ctx.guild.id, 0) + paused_for
            await ctx.send("▶️ Resumed.")

    @music.command(name="shuffle", description="Shuffle the queue")
    @is_dj()
    async def shuffle(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if not queue: return await ctx.send("❌ Empty queue.")
        random.shuffle(queue)
        await ctx.send("🔀 Shuffled!")

    @music.command(name="clear", description="Clear the queue")
    @is_dj()
    async def clear(self, ctx):
        self.queues[ctx.guild.id] = []
        await ctx.send("🗑️ Queue cleared!")

    @music.command(name="queue", description="Show the queue")
    async def queue(self, ctx):
        q = self.get_queue(ctx.guild.id)
        if not q: return await ctx.send("❌ Queue is empty.")
        embed = discord.Embed(title="🎵 Music Queue", color=0x2b2d31)
        embed.description = "\n".join([f"{i+1}. {d['title']}" for i, d in enumerate(q[:10])])
        await ctx.send(embed=embed)

    @music.command(name="nowplaying", description="Show current song")
    async def nowplaying(self, ctx):
        data = self.current_tracks.get(ctx.guild.id)
        if not data or not ctx.voice_client or (not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused()):
            return await ctx.send("❌ Nothing playing.")
        
        embed = discord.Embed(title="🎵 Now Playing", description=f"**[{data['title']}]({data['webpage_url']})**", color=0x2b2d31)
        if 'thumbnail' in data: embed.set_thumbnail(url=data['thumbnail'])
        
        # Add metadata
        duration = data.get('duration')
        if duration:
            elapsed = self.get_elapsed(ctx.guild.id, ctx.voice_client)
            progress = self.create_music_progress_bar(elapsed, duration)
            
            mins_e, secs_e = divmod(int(elapsed), 60)
            mins_d, secs_d = divmod(int(duration), 60)
            
            embed.add_field(name="Progress", value=f"`{progress}`\n{mins_e:02d}:{secs_e:02d} / {mins_d:02d}:{secs_d:02d}", inline=False)
        
        embed.add_field(name="Uploader", value=data.get('uploader', 'Unknown'), inline=True)
        embed.add_field(name="Loop", value="✅ Enabled" if self.loops.get(ctx.guild.id) else "❌ Disabled", inline=True)
        embed.add_field(name="Volume", value=f"{int(self.volumes.get(ctx.guild.id, 0.5) * 100)}%", inline=True)
        
        await ctx.send(embed=embed)

    def create_music_progress_bar(self, current, total, length=20):
        filled = int(length * current / total)
        if filled > length: filled = length
        return "▬" * filled + "🔘" + "▬" * (length - filled)

    def get_elapsed(self, guild_id, voice_client):
        if not voice_client or (not voice_client.is_playing() and not voice_client.is_paused()):
            return 0
        
        start_time = self.start_times.get(guild_id, time.time())
        total_paused = self.total_paused_durations.get(guild_id, 0)
        
        if voice_client.is_paused() and guild_id in self.pause_times:
            elapsed = self.pause_times[guild_id] - start_time - total_paused
        else:
            elapsed = time.time() - start_time - total_paused
            
        return max(0, elapsed)

    def parse_lrc(self, lrc_content):
        lines = []
        pattern = re.compile(r'\[(\d+):(\d+(?:[.:]\d+)?)\](.*)')
        for line in lrc_content.split('\n'):
            match = pattern.search(line)
            if match:
                minutes = int(match.group(1))
                seconds_str = match.group(2).replace(':', '.')
                seconds = float(seconds_str)
                text = match.group(3).strip()
                if text or lines:
                    lines.append((minutes * 60 + seconds, text))
        return sorted(lines, key=lambda x: x[0])

    async def _fetch_synced_lyrics(self, song_name):
        search_query = re.sub(r'\(.*?\)|\[.*?\]', '', song_name)
        search_query = re.sub(r'Official Video|Music Video|Lyric Video|Lyrics', '', search_query, flags=re.I).strip()
        try:
            lrc_content = await self.bot.loop.run_in_executor(None, lambda: syncedlyrics.search(search_query))
            if lrc_content:
                return self.parse_lrc(lrc_content)
        except Exception as e:
            logging.error(f"Error fetching synced lyrics for {song_name}: {e}")
        return None

    async def show_synced_lyrics(self, ctx, parsed_lyrics, follow=True):
        guild_id = ctx.guild.id
        initial_track = self.current_tracks.get(guild_id)
        message = None
        last_index = -2 # Force update on first run
        
        try:
            while True:
                if not ctx.voice_client or not ctx.voice_client.is_connected():
                    break
                
                current_track = self.current_tracks.get(guild_id)
                
                # Check for track change
                if not current_track or (initial_track and current_track != initial_track):
                    if follow and current_track:
                        initial_track = current_track
                        await ctx.channel.send(f"⏭️ **Lyrics following track change:** {current_track['title']}", delete_after=5)
                        parsed_lyrics = await self._fetch_synced_lyrics(current_track['title'])
                        if not parsed_lyrics:
                            embed = discord.Embed(title=f"🎤 Karaoke: {current_track['title']}", description="❌ No synced lyrics found for this track.", color=0x2b2d31)
                            if message: await message.edit(embed=embed)
                            else: message = await ctx.send(embed=embed)
                            
                            # Wait for next track since we have no lyrics for this one
                            while self.current_tracks.get(guild_id) == initial_track:
                                if not ctx.voice_client or not ctx.voice_client.is_connected(): break
                                await asyncio.sleep(2)
                            continue
                        last_index = -2
                    else:
                        break
                
                if not parsed_lyrics:
                    await asyncio.sleep(2)
                    continue

                elapsed = self.get_elapsed(guild_id, ctx.voice_client)
                
                current_index = -1
                for i, (ts, text) in enumerate(parsed_lyrics):
                    if ts <= elapsed:
                        current_index = i
                    else:
                        break
                
                if current_index != last_index:
                    last_index = current_index
                    
                    lines_to_show = []
                    start = max(0, current_index - 2)
                    end = min(len(parsed_lyrics), current_index + 3)
                    
                    for i in range(start, end):
                        ts, text = parsed_lyrics[i]
                        if i == current_index:
                            lines_to_show.append(f"▶️ **{text}**")
                        else:
                            lines_to_show.append(f"░ {text}")
                    
                    if not lines_to_show and current_index == -1:
                        lines_to_show = ["⌛ *Song starting...*"]

                    embed = discord.Embed(
                        title=f"🎤 Karaoke: {current_track['title']}", 
                        description="\n".join(lines_to_show), 
                        color=0x2b2d31
                    )
                    if 'thumbnail' in current_track:
                        embed.set_thumbnail(url=current_track['thumbnail'])
                        
                    duration = current_track.get('duration', 1)
                    progress = self.create_music_progress_bar(elapsed, duration)
                    embed.set_footer(text=f"{progress}")

                    if not message:
                        message = await ctx.send(embed=embed)
                    else:
                        try:
                            await message.edit(embed=embed)
                        except discord.NotFound:
                            # Re-send if message was deleted
                            message = await ctx.send(embed=embed)
                        except discord.HTTPException:
                            pass # Rate limited or other issue
                
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Error in show_synced_lyrics: {e}")
        finally:
            if guild_id in self.lyrics_tasks:
                del self.lyrics_tasks[guild_id]

    @music.command(name="remove", description="Remove a song from the queue")
    @is_dj()
    async def remove(self, ctx, index: int):
        queue = self.get_queue(ctx.guild.id)
        if not queue: return await ctx.send("❌ Empty queue.")
        if 1 <= index <= len(queue):
            removed = queue.pop(index - 1)
            await ctx.send(f"🗑️ Removed **{removed['title']}** from the queue.")
        else:
            await ctx.send(f"❌ Invalid index (1-{len(queue)}).")

    @music.command(name="volume", description="Set volume (0-100)")
    @is_dj()
    async def volume(self, ctx, level: int):
        if 0 <= level <= 100:
            self.volumes[ctx.guild.id] = level / 100
            if ctx.voice_client and ctx.voice_client.source:
                ctx.voice_client.source.volume = level / 100
            await ctx.send(f"🔊 Volume set to **{level}%**")
        else:
            await ctx.send("❌ Level must be 0-100.", ephemeral=True)

    @music.command(name="247", description="Toggle 24/7 mode (Premium Server feature)")
    @is_dj()
    async def toggle_247(self, ctx):
        is_premium = await self.bot.db.is_guild_premium(ctx.guild.id)
        if not is_premium:
            dashboard_url = "http://flowerbot.gg:5000"
            try:
                from cogs.dashboard import DASHBOARD_URL
                dashboard_url = DASHBOARD_URL
            except: pass
            return await ctx.send(f"❌ **24/7 Mode** is a **Server Premium** feature! Visit {dashboard_url} to upgrade.", ephemeral=True)
        
        current = await self.bot.db.get_guild_setting(ctx.guild.id, "premium_247")
        new_val = 0 if current else 1
        await self.bot.db.set_guild_setting(ctx.guild.id, "premium_247", new_val)
        
        status = "enabled" if new_val else "disabled"
        await ctx.send(f"🕒 **24/7 Mode** has been **{status}**.")

    @music.command(name="filter", description="Apply an audio filter (Premium Server feature)")
    @is_dj()
    async def apply_filter(self, ctx, filter_name: str = None):
        is_premium = await self.bot.db.is_guild_premium(ctx.guild.id)
        if not is_premium:
            dashboard_url = "http://flowerbot.gg:5000"
            try:
                from cogs.dashboard import DASHBOARD_URL
                dashboard_url = DASHBOARD_URL
            except: pass
            return await ctx.send(f"❌ **Audio Filters** are a **Server Premium** feature! Visit {dashboard_url} to upgrade.", ephemeral=True)

        if not filter_name:
            available = ", ".join([f"`{f}`" for f in FILTERS.keys()])
            return await ctx.send(f"✨ Available filters: {available}\nUse `/music filter clear` to remove filters.")

        filter_name = filter_name.lower()
        if filter_name == "clear":
            self.active_filters[ctx.guild.id] = None
            await ctx.send("✨ Audio filters cleared. (Applies to next song)")
        elif filter_name in FILTERS:
            self.active_filters[ctx.guild.id] = filter_name
            await ctx.send(f"✨ Applied **{filter_name}** filter! (Applies to next song)")
        else:
            await ctx.send(f"❌ Invalid filter. Available: {', '.join(FILTERS.keys())}")

    @music.command(name="loop", description="Toggle loop")
    @is_dj()
    async def loop(self, ctx):
        guild_id = ctx.guild.id
        self.loops[guild_id] = not self.loops.get(guild_id, False)
        await ctx.send(f"🔄 Loop **{'enabled' if self.loops[guild_id] else 'disabled'}**")

    @music.command(name="playnext", description="Queue song to play next")
    @is_dj()
    async def playnext(self, ctx, *, query: str):
        if not shutil.which("ffmpeg"): return await ctx.send("❌ No FFmpeg.", ephemeral=True)
        if not ctx.author.voice: return await ctx.send("❌ Join a voice channel!")
        
        await ctx.defer()
        
        if not ctx.voice_client:
            try: await ctx.author.voice.channel.connect(timeout=20, reconnect=True)
            except: return await ctx.send("❌ Failed to connect to voice.")

        async with ctx.typing():
            try:
                search_query = query if query.startswith(('http://', 'https://')) else f"ytsearch:{query}"
                def extract():
                    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                        return ydl.extract_info(search_query, download=False)
                
                data = await self.bot.loop.run_in_executor(None, extract)
                if 'entries' in data and data['entries']: 
                    data = data['entries'][0]
                elif 'entries' in data:
                    return await ctx.send("❌ No results found.")
                    
                self.get_queue(ctx.guild.id).insert(0, data)
                if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                    await self.play_next(ctx)
                else:
                    await ctx.send(f"⏭️ Playing **{data['title']}** next.")
            except Exception as e:
                logging.error(f"Playnext error: {e}")
                await ctx.send(f"❌ Error: {e}")

    @music.command(name="search", description="Search for a song and pick from results")
    async def search(self, ctx, *, query: str):
        if not shutil.which("ffmpeg"): return await ctx.send("❌ No FFmpeg.", ephemeral=True)
        if not ctx.author.voice: return await ctx.send("❌ Join a voice channel!")
        
        await ctx.defer()
        
        async with ctx.typing():
            try:
                search_query = query if query.startswith(('http://', 'https://')) else f"ytsearch5:{query}"
                def extract():
                    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                        return ydl.extract_info(search_query, download=False)
                
                data = await self.bot.loop.run_in_executor(None, extract)
                
                if not data or 'entries' not in data or not data['entries']:
                    return await ctx.send("❌ No results found.")
                
                entries = data['entries']
                options = [
                    discord.SelectOption(label=e['title'][:100], value=str(i), description=f"By {e.get('uploader', 'Unknown')}")
                    for i, e in enumerate(entries)
                ]
                
                select = discord.ui.Select(placeholder="Choose a song...", options=options)
                
                async def select_callback(interaction):
                    if interaction.user != ctx.author:
                        return await interaction.response.send_message("❌ This is not your search!", ephemeral=True)
                    
                    selection = entries[int(select.values[0])]
                    await interaction.response.defer()
                    await interaction.edit_original_response(content=f"✅ Selected **{selection['title']}**", view=None)
                    
                    if not ctx.voice_client:
                        await ctx.author.voice.channel.connect()
                    
                    self.get_queue(ctx.guild.id).append(selection)
                    if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                        await self.play_next(ctx)
                    else:
                        await ctx.channel.send(f"✅ Added **{selection['title']}** to the queue.")

                select.callback = select_callback
                view = discord.ui.View()
                view.add_item(select)
                
                await ctx.send("🔎 **Search Results:**", view=view)
            except Exception as e:
                await ctx.send(f"❌ Search error: {e}")

    @music.command(name="autoplay", description="Toggle autoplay after queue ends")
    @is_dj()
    async def autoplay(self, ctx):
        guild_id = ctx.guild.id
        self.autoplays[guild_id] = not self.autoplays.get(guild_id, False)
        await ctx.send(f"📻 Autoplay is now **{'enabled' if self.autoplays[guild_id] else 'disabled'}**")

    @music.command(name="lyrics", description="Show lyrics for the current song (karaoke style)")
    async def lyrics(self, ctx, *, song_name: str = None):
        await ctx.defer()
        
        guild_id = ctx.guild.id
        if guild_id in self.lyrics_tasks:
            self.lyrics_tasks[guild_id].cancel()
            del self.lyrics_tasks[guild_id]

        if not song_name:
            data = self.current_tracks.get(guild_id)
            if not data or not ctx.voice_client:
                return await ctx.send("❌ Nothing playing and no song name provided.")
            song_name = data['title']
            follow = True
        else:
            follow = False
        
        try:
            # Try synced lyrics first
            parsed_lyrics = await self._fetch_synced_lyrics(song_name)
            
            if parsed_lyrics:
                task = self.bot.loop.create_task(self.show_synced_lyrics(ctx, parsed_lyrics, follow=follow))
                self.lyrics_tasks[guild_id] = task
                return

            # Fallback to standard Genius lyrics
            search_query = re.sub(r'\(.*?\)|\[.*?\]', '', song_name)
            search_query = re.sub(r'Official Video|Music Video|Lyric Video|Lyrics', '', search_query, flags=re.I).strip()
            song = await self.bot.loop.run_in_executor(None, lambda: self.genius.search_song(search_query))
            if not song:
                return await ctx.send(f"❌ Could not find lyrics for **{song_name}**.")
            
            lyrics = song.lyrics
            lyrics = re.sub(r'^\d+Embed$', '', lyrics, flags=re.MULTILINE)
            lyrics = re.sub(r'.*?Lyrics', '', lyrics, count=1)
            
            if len(lyrics) > 4000:
                lyrics = lyrics[:3997] + "..."
            
            embed = discord.Embed(title=f"📜 Lyrics: {song.title}", description=lyrics, color=0x2b2d31)
            embed.set_author(name=song.artist)
            if song.song_art_image_url:
                embed.set_thumbnail(url=song.song_art_image_url)
            
            await ctx.send(embed=embed)
        except Exception as e:
            logging.error(f"Lyrics error: {e}")
            await ctx.send("❌ An error occurred while fetching lyrics.")

    @music.group(name="playlist", description="Manage your playlists")
    async def playlist(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `/music playlist save`, `/music playlist load`, `/music playlist list`, or `/music playlist delete`.")

    @playlist.command(name="save", description="Save the current queue as a playlist")
    async def playlist_save(self, ctx, *, name: str):
        queue = self.get_queue(ctx.guild.id)
        current = self.current_tracks.get(ctx.guild.id)
        
        all_songs = []
        if current: all_songs.append(current)
        all_songs.extend(queue)
        
        if not all_songs:
            return await ctx.send("❌ The queue is empty.")
        
        # We only save titles and URLs to keep it small
        saved_songs = [{"title": s['title'], "webpage_url": s['webpage_url']} for s in all_songs]
        
        await self.bot.db.save_playlist(ctx.author.id, name, saved_songs)
        await ctx.send(f"✅ Playlist **{name}** saved with {len(saved_songs)} songs.")

    @playlist.command(name="load", description="Load a saved playlist")
    async def playlist_load(self, ctx, *, name: str):
        songs = await self.bot.db.get_playlist(ctx.author.id, name)
        if not songs:
            return await ctx.send(f"❌ Playlist **{name}** not found.")
        
        if not ctx.author.voice:
            return await ctx.send("❌ You must be in a voice channel!")
        
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        
        queue = self.get_queue(ctx.guild.id)
        queue.extend(songs)
        
        await ctx.send(f"📥 Loaded {len(songs)} songs from playlist **{name}**.")
        
        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await self.play_next(ctx)

    @playlist.command(name="list", description="List your saved playlists")
    async def playlist_list(self, ctx):
        playlists = await self.bot.db.get_playlists(ctx.author.id)
        if not playlists:
            return await ctx.send("❌ You have no saved playlists.")
        
        embed = discord.Embed(title="📜 Your Playlists", description="\n".join([f"• {p}" for p in playlists]), color=0x2b2d31)
        await ctx.send(embed=embed)

    @playlist.command(name="delete", description="Delete a saved playlist")
    async def playlist_delete(self, ctx, *, name: str):
        playlists = await self.bot.db.get_playlists(ctx.author.id)
        if name not in playlists:
            return await ctx.send(f"❌ Playlist **{name}** not found.")
        
        await self.bot.db.delete_playlist(ctx.author.id, name)
        await ctx.send(f"🗑️ Playlist **{name}** deleted.")


async def setup(bot):
    await bot.add_cog(Music(bot))
