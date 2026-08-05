import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import random
import time
import logging
import asyncio
import urllib.parse
from utils.permissions import is_admin

class LeaderboardView(discord.ui.View):
    def __init__(self, bot, db, cog, top_users, user_id, page=1, sort_by="xp", guild=None):
        super().__init__(timeout=60)
        self.bot = bot
        self.db = db
        self.cog = cog
        self.top_users = top_users
        self.user_id = user_id
        self.page = page
        self.sort_by = sort_by
        self.guild = guild

    async def create_leaderboard_embed(self, page):
        if page == 0:
            return await self.create_overview_embed()
        
        logging.info(f"Creating leaderboard embed for page {page} sorted by {self.sort_by}")
        limit = 10
        offset = (page - 1) * limit
        users = self.top_users[offset:offset+limit]
        
        title = "🏆 Server Leaderboard"
        if self.sort_by == "messages": title = "💬 Message Leaderboard"
        elif self.sort_by == "voice": title = "🎙️ Voice Leaderboard"
        
        embed = discord.Embed(title=title, color=0x2b2d31)
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        for i, (uid, xp, level, msg_count, voice_min) in enumerate(users, offset + 1):
            user = None
            try:
                user_id_int = int(uid)
                if self.guild:
                    user = self.guild.get_member(user_id_int)
                
                if not user:
                    user = self.bot.get_user(user_id_int)
                    
                if not user:
                    try: 
                        logging.debug(f"Fetching user {uid} for leaderboard")
                        user = await self.bot.fetch_user(user_id_int)
                    except Exception as e:
                        logging.warning(f"Failed to fetch user {uid}: {e}")
                        pass
            except ValueError:
                logging.warning(f"Invalid user ID in database: {uid}")
            
            name = user.display_name if user else f"User {uid}"
            
            xp_needed = self.cog.get_xp_to_level(level)
            progress = self.cog.create_progress_bar(xp, xp_needed, length=5)
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**#{i}**"
            
            if self.sort_by == "messages":
                value = f"**{msg_count}** msgs | Level **{level}**"
            elif self.sort_by == "voice":
                value = f"**{voice_min}** mins | Level **{level}**"
            else:
                value = f"Level **{level}** | **{msg_count}** msgs | **{xp}** XP\n`{progress}`"
            
            embed.add_field(name=f"{medal} {name}", value=value, inline=False)
        
        # User's current rank
        rank_pos = await self.db.get_rank(self.user_id, sort_by=self.sort_by)
        user_data = await self.db.get_user_data(self.user_id)
        total_users = await self.db.get_total_users()
        embed.set_footer(text=f"Page {page} | Your Rank: #{rank_pos if rank_pos else 'N/A'} | Total Users: {total_users}")
        return embed

    async def create_overview_embed(self):
        embed = discord.Embed(title=f"🏆 Top Stats for {self.guild.name if self.guild else 'Server'}", color=0x2b2d31)
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Top 5 Messages
        top_msgs = await self.db.get_top_users(5, sort_by="messages")
        msg_list = ""
        for i, (uid, xp, level, msg_count, voice_min) in enumerate(top_msgs, 1):
            user = self.guild.get_member(int(uid)) if self.guild else None
            name = user.display_name if user else f"User {uid}"
            msg_list += f"{i}. **{name}** — {msg_count}\n"
        embed.add_field(name="💬 Top Members (Messages)", value=msg_list or "No data", inline=False)

        # Top 5 Voice
        top_voice = await self.db.get_top_users(5, sort_by="voice")
        voice_list = ""
        for i, (uid, xp, level, msg_count, voice_min) in enumerate(top_voice, 1):
            user = self.guild.get_member(int(uid)) if self.guild else None
            name = user.display_name if user else f"User {uid}"
            h = voice_min // 60
            m = voice_min % 60
            time_str = f"{h}h {m}m" if h > 0 else f"{m}m"
            voice_list += f"{i}. **{name}** — {time_str}\n"
        embed.add_field(name="🎙️ Top Members (Voice)", value=voice_list or "No data", inline=False)

        # User's current rank
        rank_pos = await self.db.get_rank(self.user_id, sort_by=self.sort_by)
        total_users = await self.db.get_total_users()
        embed.set_footer(text=f"Overview | Your Rank: #{rank_pos if rank_pos else 'N/A'} | Total Users: {total_users}")
        return embed

    @discord.ui.button(label="🏠 Overview", style=discord.ButtonStyle.blurple)
    async def overview_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        embed = await self.create_leaderboard_embed(self.page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.grey)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 1:
            self.page -= 1
            embed = await self.create_leaderboard_embed(self.page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("You're on the first page!", ephemeral=True)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.grey)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page * 10 < len(self.top_users) or self.page == 0:
            self.page += 1
            embed = await self.create_leaderboard_embed(self.page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("No more pages!", ephemeral=True)

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.voice_xp_task.start()

    def cog_unload(self):
        self.voice_xp_task.cancel()

    def get_xp_to_level(self, level):
        return 5 * (level**2) + 50*level + 100

    def create_progress_bar(self, current, total, length=10):
        if total <= 0: return "░" * length + " 0%"
        filled = int(length * current / total)
        if filled > length: filled = length
        bar = "█" * filled + "░" * (length - filled)
        percent = int(current / total * 100)
        return f"{bar} {percent}%"

    def generate_chart_url(self, title, labels, data, label="Value", color="rgb(75, 192, 192)"):
        chart_config = {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": label,
                    "data": data,
                    "fill": True,
                    "backgroundColor": color.replace("rgb", "rgba").replace(")", ", 0.2)"),
                    "borderColor": color,
                    "pointRadius": 4,
                    "lineTension": 0.4
                }]
            },
            "options": {
                "title": {"display": True, "text": title, "fontColor": "white", "fontSize": 20},
                "legend": {"labels": {"fontColor": "white"}},
                "scales": {
                    "yAxes": [{"ticks": {"fontColor": "white", "beginAtZero": True}}],
                    "xAxes": [{"ticks": {"fontColor": "white"}}]
                }
            }
        }
        encoded_config = urllib.parse.quote(json.dumps(chart_config))
        return f"https://quickchart.io/chart?c={encoded_config}&bkg=rgb(43, 45, 49)"

    async def award_xp(self, user: discord.Member, xp_amount: int, is_message=True, channel=None):
        if user.bot: return
        
        user_id = str(user.id)
        data = await self.db.get_user_data(user_id)
        
        # Apply XP Boosts
        boosts = await self.db.get_xp_boosts()
        multiplier = 1.0
        for b_role_id, mult in boosts.items():
            # Check if user has role_id
            has_role = any(r.id == b_role_id for r in user.roles)
            if has_role:
                if mult > multiplier: multiplier = mult
        
        xp_gain = int(xp_amount * multiplier)
        
        new_xp = data["xp"] + xp_gain
        current_level = data["level"]
        new_msg_count = data["message_count"] + (1 if is_message else 0)
        new_voice_min = data["voice_minutes"] + (0 if is_message else 1)
        
        leveled_up = False
        while new_xp >= self.get_xp_to_level(current_level):
            new_xp -= self.get_xp_to_level(current_level)
            current_level += 1
            leveled_up = True

        await self.db.update_user_data(user_id, new_xp, current_level, time.time() if is_message else data["last_xp_time"], new_msg_count, new_voice_min)

        if leveled_up:
            # Role Rewards
            rewards = await self.db.get_role_rewards()
            role_msg = ""
            if current_level in rewards:
                role_id = rewards[current_level]
                role = user.guild.get_role(role_id)
                if role:
                    try:
                        await user.add_roles(role)
                        role_msg = f"\n🎖️ You've been awarded the **{role.name}** role!"
                    except Exception as e:
                        logging.error(f"Error adding role reward: {e}")

            # Level Up Notification
            level_channel_id = await self.db.get_guild_setting(user.guild.id, "level_up_channel_id", int)
            target_channel = None
            if level_channel_id:
                target_channel = self.bot.get_channel(level_channel_id)
                if not target_channel:
                    try:
                        target_channel = await self.bot.fetch_channel(level_channel_id)
                    except:
                        pass
            
            if not target_channel:
                target_channel = channel
            
            if not target_channel:
                # Try to find a channel in the guild where we have permission
                for channel in user.guild.text_channels:
                    if "level" in channel.name.lower():
                        target_channel = channel
                        break
            
            if not target_channel and hasattr(user, 'guild'):
                # Default to current channel for messages, or first available for voice
                # But here we don't have ctx/message. We can't easily know where to send if it's voice.
                pass

            if target_channel:
                try:
                    embed = discord.Embed(title="🎉 Level Up!", 
                                        description=f"Congratulations {user.mention}, you reached **Level {current_level}**!{role_msg}",
                                        color=0x2ecc71)
                    embed.set_thumbnail(url=user.display_avatar.url)
                    await target_channel.send(embed=embed)
                except: pass

    @tasks.loop(minutes=1)
    async def voice_xp_task(self):
        logging.debug("Running voice XP task")
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                if len(vc.members) < 2: continue # Prevent solo idling
                for member in vc.members:
                    if member.bot: continue
                    if member.voice.self_deaf or member.voice.deaf: continue # Don't award XP to deafened users
                    
                    # Award 10-20 XP per minute
                    await self.award_xp(member, random.randint(10, 20), is_message=False)
                    await self.db.increment_user_daily_voice(member.id, guild.id)

    @voice_xp_task.before_loop
    async def before_voice_xp_task(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # Increment daily stats
        await self.db.increment_daily_stat(message.guild.id, "messages")
        await self.db.increment_user_daily_messages(message.author.id, message.guild.id)

        ignored_channels = await self.db.get_ignored_channels()
        if message.channel.id in ignored_channels:
            return

        user_id = str(message.author.id)
        data = await self.db.get_user_data(user_id)
        current_time = time.time()
        
        if current_time - data["last_xp_time"] >= 60:
            await self.award_xp(message.author, random.randint(15, 25), is_message=True, channel=message.channel)
        else:
            # Just increment msg count if on cooldown for XP
            await self.db.update_user_data(user_id, data["xp"], data["level"], data["last_xp_time"], data["message_count"] + 1, data["voice_minutes"])

    def is_leveling_channel():
        async def predicate(ctx):
            if not ctx.guild: return True
            db_channel_id = await ctx.bot.db.get_guild_setting(ctx.guild.id, "leveling_channel_id", int)
            if not db_channel_id or ctx.channel.id == db_channel_id:
                return True
            
            chan = ctx.bot.get_channel(db_channel_id)
            await ctx.send(f"❌ Leveling commands are restricted to {chan.mention if chan else f'<#{db_channel_id}>'}.", ephemeral=True)
            return False
        return commands.check(predicate)

    @commands.command(name="u", description="Show the server message leaderboard", aliases=["leaderboard", "top", "lb", "s?u"])
    @is_leveling_channel()
    async def leaderboard(self, ctx: commands.Context, sort: str = "messages", type: str = None):
        logging.info(f"Leaderboard command invoked by {ctx.author} with sort={sort}, type={type}")
        # Use a task to handle defer-like behavior in prefix commands if needed, 
        # but here we can just process. Prefix commands don't have a 3s limit like interactions.

        if type:
            type = type.lower()
            if type in ["messages", "joins", "leaves"]:
                stats = await self.db.get_daily_stats(ctx.guild.id, days=7)
                if not stats:
                    return await ctx.send("No statistical data collected yet.")
                
                # Gap-filling logic for 7 days
                from datetime import datetime, timedelta
                now = datetime.now()
                full_stats = []
                idx = 1 if type == "messages" else 2 if type == "joins" else 3
                stats_dict = {row[0]: row[idx] for row in stats}
                
                for i in range(6, -1, -1):
                    d = (now - timedelta(days=i)).strftime('%Y-%m-%d')
                    full_stats.append((d, stats_dict.get(d, 0)))
                
                labels = [row[0] for row in full_stats]
                data = [row[1] for row in full_stats]
                
                title = f"{type.capitalize()} Activity (Last 7 Days)"
                chart_url = self.generate_chart_url(title, labels, data, type.capitalize())
                embed = discord.Embed(title=f"📊 Server {type.capitalize()} Statistics", color=0x2b2d31)
                embed.set_image(url=chart_url)
                return await ctx.send(embed=embed)
            
            elif type == "levels":
                dist = await self.db.get_level_distribution()
                if not dist:
                    return await ctx.send("No level data collected yet.")
                
                labels = [f"Lvl {row[0]}" for row in dist]
                data = [row[1] for row in dist]
                
                # Bar chart for distribution
                chart_config = {
                    "type": "bar",
                    "data": {
                        "labels": labels,
                        "datasets": [{
                            "label": "Members",
                            "data": data,
                            "backgroundColor": "rgba(255, 206, 86, 0.6)",
                            "borderColor": "rgb(255, 206, 86)",
                            "borderWidth": 1
                        }]
                    },
                    "options": {
                        "title": {"display": True, "text": "Level Distribution", "fontColor": "white"},
                        "legend": {"display": False},
                        "scales": {
                            "yAxes": [{"ticks": {"fontColor": "white", "beginAtZero": True}}],
                            "xAxes": [{"ticks": {"fontColor": "white"}}]
                        }
                    }
                }
                encoded_config = urllib.parse.quote(json.dumps(chart_config))
                chart_url = f"https://quickchart.io/chart?c={encoded_config}&bkg=rgb(43, 45, 49)"
                
                embed = discord.Embed(title="📊 Server Level Distribution", color=0x2b2d31)
                embed.set_image(url=chart_url)
                return await ctx.send(embed=embed)

        # List Leaderboard
        try:
            top_users = await self.db.get_top_users(100, sort_by=sort.lower())
            if not top_users:
                return await ctx.send("No data collected yet!")
    
            view = LeaderboardView(self.bot, self.db, self, top_users, ctx.author.id, sort_by=sort.lower(), guild=ctx.guild)
            embed = await view.create_leaderboard_embed(0) # Start with overview
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            logging.error(f"Error in leaderboard command: {e}")
            await ctx.send(f"❌ An error occurred: {e}")

    @commands.hybrid_command(name="rank", description="Check your or another member's rank", aliases=["me", "stats"])
    @is_leveling_channel()
    @app_commands.describe(member="The member to check (defaults to you)", chart="Show 7-day message chart")
    async def rank(self, ctx: commands.Context, member: discord.Member = None, chart: bool = False):
        member = member or ctx.author
        user_id = str(member.id)

        if chart:
            stats = await self.db.get_user_daily_messages(user_id, ctx.guild.id, days=7)
            if not stats:
                return await ctx.send(f"No message data found for {member.display_name} in the last 7 days.")
            
            # Gap-filling
            from datetime import datetime, timedelta
            now = datetime.now()
            full_stats = []
            stats_dict = {row[0]: row[1] for row in stats}
            
            for i in range(6, -1, -1):
                d = (now - timedelta(days=i)).strftime('%Y-%m-%d')
                full_stats.append((d, stats_dict.get(d, 0)))
            
            labels = [row[0] for row in full_stats]
            data = [row[1] for row in full_stats]
            
            chart_url = self.generate_chart_url(f"{member.display_name}'s Message Stats", labels, data, "Messages", "rgb(255, 99, 132)")
            embed = discord.Embed(title=f"📈 {member.display_name}'s Statistics", color=0x2b2d31)
            embed.set_image(url=chart_url)
            return await ctx.send(embed=embed)

        data = await self.db.get_user_data(user_id)
        today = await self.db.get_user_today_stats(user_id, ctx.guild.id)
        week = await self.db.get_user_lookback_stats(user_id, ctx.guild.id, days=7)
        
        xp = data["xp"]
        level = data["level"]
        msg_count = data["message_count"]
        voice_min = data["voice_minutes"]
        xp_needed = self.get_xp_to_level(level)
        rank_pos = await self.db.get_rank(user_id)
                
        embed = discord.Embed(title=f"📊 Activity Overview — {member.display_name}", color=0x2b2d31)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Messages field
        msg_today = today["messages"]
        msg_week = week["messages"]
        embed.add_field(name="💬 Messages", value=f"Total: **{msg_count}**\nToday: **{msg_today}**\n7d: **{msg_week}**", inline=True)
        
        # Voice field
        voice_today = today["voice_minutes"]
        voice_week = week["voice_minutes"]
        
        def format_time(mins):
            h, m = divmod(mins, 60)
            return f"{h}h {m}m" if h > 0 else f"{m}m"

        embed.add_field(name="🎙️ Voice", value=f"Total: **{format_time(voice_min)}**\nToday: **{format_time(voice_today)}**\n7d: **{format_time(voice_week)}**", inline=True)
        
        # Leveling field
        embed.add_field(name="✨ Leveling", value=f"Level: **{level}**\nRank: **#{rank_pos if rank_pos else 'N/A'}**", inline=True)
        
        # XP & Progress
        progress = self.create_progress_bar(xp, xp_needed)
        embed.add_field(name="📈 XP & Progress", value=f"**{xp}** / **{xp_needed}** XP\n`{progress}`", inline=False)
        
        # Calculate Next Role Reward
        rewards = await self.db.get_role_rewards()
        next_role_str = "None"
        for l in sorted(rewards.keys()):
            if l > level:
                role = ctx.guild.get_role(rewards[l])
                next_role_str = f"Level **{l}** ({role.mention if role else 'Unknown'})"
                break
        embed.add_field(name="🎖️ Next Reward", value=next_role_str, inline=False)
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="add_xp", description="Add XP to a member (Admin only)", aliases=["add_ex"])
    @is_admin()
    async def add_xp(self, ctx: commands.Context, member: discord.Member, amount: int):
        user_id = str(member.id)
        data = await self.db.get_user_data(user_id)
        new_xp = data["xp"] + amount
        current_level = data["level"]
        
        leveled_up = False
        while new_xp >= self.get_xp_to_level(current_level):
            new_xp -= self.get_xp_to_level(current_level)
            current_level += 1
            leveled_up = True
            
            rewards = await self.db.get_role_rewards()
            if current_level in rewards:
                role = ctx.guild.get_role(rewards[current_level])
                if role:
                    try: await member.add_roles(role)
                    except: pass
            
        await self.db.update_user_data(user_id, new_xp, current_level, data["last_xp_time"], data["message_count"], data["voice_minutes"])
        msg = f"Added **{amount}** XP to {member.mention}."
        if leveled_up: msg += f" They leveled up to **Level {current_level}**!"
        await ctx.send(msg)
        await self.bot.log_action(ctx.guild, "📈 XP Added", f"**{ctx.author}** added **{amount}** XP to {member.mention}.\n**New Level:** {current_level}", color=0x3498db, moderator=ctx.author, user=member)

    @commands.hybrid_command(name="set_level", description="Set a member's level (Admin only)")
    @is_admin()
    async def set_level(self, ctx: commands.Context, member: discord.Member, level: int):
        if level < 0: return await ctx.send("Level cannot be negative!", ephemeral=True)
        data = await self.db.get_user_data(member.id)
        await self.db.update_user_data(member.id, 0, level, data["last_xp_time"], data["message_count"], data["voice_minutes"])
        await ctx.send(f"Set {member.mention}'s level to **{level}** (XP reset to 0).")
        await self.bot.log_action(ctx.guild, "📈 Level Set", f"**{ctx.author}** set {member.mention}'s level to **{level}**.", color=0x3498db, moderator=ctx.author, user=member)

    @commands.hybrid_command(name="reset_level", description="Reset a member's level and XP (Admin only)")
    @is_admin()
    async def reset_level(self, ctx: commands.Context, member: discord.Member):
        await self.db.update_user_data(member.id, 0, 0, 0, 0, 0)
        await ctx.send(f"Reset {member.mention}'s level and XP to 0.")
        await self.bot.log_action(ctx.guild, "📈 Level Reset", f"**{ctx.author}** reset {member.mention}'s leveling data.", color=0xe74c3c, moderator=ctx.author, user=member)

    @commands.hybrid_command(name="add_role_reward", description="Add a role reward for a level")
    @is_admin()
    async def add_role_reward(self, ctx: commands.Context, level: int, role: discord.Role):
        await self.db.add_role_reward(level, role.id)
        await ctx.send(f"✅ Added reward for Level {level}: {role.name}")
        await self.bot.log_action(ctx.guild, "📈 Role Reward Added", f"**Level:** {level}\n**Role:** {role.mention}", color=0x3498db, moderator=ctx.author)

    @commands.hybrid_command(name="remove_role_reward", description="Remove a role reward for a level")
    @is_admin()
    async def remove_role_reward(self, ctx: commands.Context, level: int):
        await self.db.remove_role_reward(level)
        await ctx.send(f"✅ Removed reward for Level {level}")
        await self.bot.log_action(ctx.guild, "📈 Role Reward Removed", f"**Level:** {level}", color=0xe74c3c, moderator=ctx.author)

    @commands.hybrid_command(name="level_rewards", description="Show all level rewards", aliases=["member_ranks", "role_rewards"])
    @is_admin()
    async def level_rewards(self, ctx: commands.Context):
        rewards = await self.db.get_role_rewards()
        if not rewards: return await ctx.send("No rewards set.")
        embed = discord.Embed(title="🎖️ Level Role Rewards", color=0x2b2d31)
        desc = ""
        for level, role_id in rewards.items():
            role = ctx.guild.get_role(role_id)
            desc += f"Level **{level}**: {role.mention if role else role_id}\n"
        embed.description = desc
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="add_xp_boost", description="Add an XP multiplier for a role")
    @is_admin()
    async def add_xp_boost(self, ctx: commands.Context, role: discord.Role, multiplier: float):
        await self.db.add_xp_boost(role.id, multiplier)
        await ctx.send(f"✅ Added **{multiplier}x** XP boost for {role.mention}")
        await self.bot.log_action(ctx.guild, "⚡ XP Boost Added", f"**Multiplier:** {multiplier}x\n**Role:** {role.mention}", color=0x3498db, moderator=ctx.author)

    @commands.hybrid_command(name="remove_xp_boost", description="Remove an XP multiplier for a role")
    @is_admin()
    async def remove_xp_boost(self, ctx: commands.Context, role: discord.Role):
        await self.db.remove_xp_boost(role.id)
        await ctx.send(f"✅ Removed XP boost for {role.mention}")
        await self.bot.log_action(ctx.guild, "⚡ XP Boost Removed", f"**Role:** {role.mention}", color=0xe74c3c, moderator=ctx.author)

    @commands.hybrid_command(name="xp_boosts", description="Show all active XP boosts")
    async def xp_boosts(self, ctx: commands.Context):
        boosts = await self.db.get_xp_boosts()
        if not boosts: return await ctx.send("No active XP boosts.")
        embed = discord.Embed(title="⚡ Active XP Boosts", color=0x2b2d31)
        desc = ""
        for role_id, multiplier in boosts.items():
            role = ctx.guild.get_role(role_id)
            desc += f"{role.mention if role else role_id}: **{multiplier}x**\n"
        embed.description = desc
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="ignore_channel", description="Ignore a channel for XP", aliases=["ignore_channels"])
    @is_admin()
    async def ignore_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.db.add_ignored_channel(channel.id)
        await ctx.send(f"🚫 Ignored {channel.mention} for XP.")

    @commands.hybrid_command(name="unignore_channel", description="Allow XP in a channel", aliases=["unignore"])
    @is_admin()
    async def unignore_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.db.remove_ignored_channel(channel.id)
        await ctx.send(f"✅ Unignored {channel.mention} for XP.")

    @commands.hybrid_command(name="ignored_channels", description="List ignored channels")
    @is_admin()
    async def ignored_channels(self, ctx: commands.Context):
        channels = await self.db.get_ignored_channels()
        if not channels: return await ctx.send("No channels ignored.")
        mentions = [f"<#{cid}>" for cid in channels]
        await ctx.send(f"🚫 **Ignored Channels:**\n" + "\n".join(mentions))

    @commands.hybrid_command(name="levelupchannel", description="Set the channel for level-up notifications")
    @is_admin()
    @app_commands.describe(channel="The channel to send level-up messages to (leave empty to reset)")
    async def levelupchannel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        if channel:
            await self.db.set_guild_setting(ctx.guild.id, "level_up_channel_id", str(channel.id))
            await ctx.send(f"✅ Level-up notifications will now be sent to {channel.mention}.", ephemeral=True)
            await self.bot.log_action(ctx.guild, "📈 Level-Up Channel Set", f"**Channel:** {channel.mention}", color=0x3498db, moderator=ctx.author)
        else:
            await self.db.set_guild_setting(ctx.guild.id, "level_up_channel_id", None)
            await ctx.send("✅ Level-up notifications will now be sent in the channel where the user leveled up.", ephemeral=True)
            await self.bot.log_action(ctx.guild, "📈 Level-Up Channel Reset", "Notifications will now be sent in the original channel.", color=0xe74c3c, moderator=ctx.author)

async def setup(bot):
    await bot.add_cog(Leveling(bot))
