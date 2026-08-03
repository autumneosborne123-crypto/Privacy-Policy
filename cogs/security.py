import discord
import json
import urllib.parse
from discord.ext import commands
from datetime import timedelta
import re
import logging
import collections
import time

from utils.permissions import is_admin_or_moderator, is_admin, is_staff

class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.SCAM_PATTERNS = [
            r"get.*nitro", r"free.*nitro", r"steam.*gift", r"steam.*promo", r"trade.*offer",
            r"robux.*free", r"vbucks.*free", r"cashapp.*money", r"paypal.*money"
        ]
        self.SCAM_DOMAINS = [
            "discord-gift", "dlscord", "discord-nitro", "discordgift", 
            "steamcommunity.com.ru", "steamcommunnity", "steam-trade",
            "discorcl", "discordapp.click", "nitro-gift", "nitro-generator",
            "free-nitro", "gift-discord", "discord-promo", "steam-promo",
            "discort", "discord-nltro", "dlscord-gift", "discord.gg.gift",
            "discord-app.net", "discord-presents.com", "discord-rewards.com",
            "nitro-drop.com", "steam-nitro.ru", "discord-claim.com"
        ]
        self.SLURS = ["nigger", "pussy", "nigga", "freaky", "foid", "moid", "horny", "slut", "whore", "dick","rape", "penis"]
        self.slur_pattern = re.compile(rf"\b({'|'.join(self.SLURS)})\b", re.IGNORECASE)
        
        # Anti-Raid tracking
        self.join_log = collections.deque(maxlen=20)
        self.message_track = collections.defaultdict(list)
        self.raid_mode = False
        
        # Anti-Nuke tracking: user_id -> {action_type -> [timestamps]}
        self.nuke_track = collections.defaultdict(lambda: collections.defaultdict(list))

    def is_suspicious_bot(self, member: discord.Member) -> bool:
        account_age = discord.utils.utcnow() - member.created_at
        if account_age < timedelta(hours=1) and member.avatar is None:
            return True
        if re.search(r'^[a-f0-9]{32}$', member.name):
            return True
        return False

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return

        # Increment daily joins
        await self.bot.db.increment_daily_stat(member.guild.id, "joins")

        if member.id in self.bot.whitelisted_bots:
            return

        settings = await self.bot.db.get_all_guild_settings(member.guild.id)

        # Auto-Role
        auto_role_id = settings.get('auto_role_id')
        if auto_role_id:
            role = member.guild.get_role(int(auto_role_id))
            if role and role < member.guild.me.top_role:
                try: await member.add_roles(role, reason="Auto-role on join")
                except: pass

        # Join Rate Limiting (Anti-Raid)
        if settings.get('anti_raid_enabled') != 0:
            now = time.time()
            self.join_log.append(now)
            recent_joins = [t for t in self.join_log if now - t < 30]
            
            if len(recent_joins) >= 10:
                if not self.raid_mode:
                    self.raid_mode = True
                    logging.warning("🚨 RAID DETECTED! Enabling Raid Mode.")
                    try:
                        # Notify admins
                        channel = await self.bot.get_log_channel(member.guild)
                        if not channel:
                            channel = member.guild.system_channel or next((c for c in member.guild.text_channels if c.permissions_for(member.guild.me).send_messages), None)
                        
                        if channel:
                            await channel.send("🚨 **RAID DETECTED!** Anti-Raid Mode has been automatically enabled. New joins will be auto-kicked.")
                    except: pass

            if self.raid_mode:
                try:
                    await member.kick(reason="Anti-Raid: Raid mode enabled")
                    logging.info(f"Raid-Kicked: {member.name}")
                    return
                except: pass

        if self.is_suspicious_bot(member):
            try:
                reason = "Auto-ban: Suspicious account"
                await member.ban(reason=reason)
                await self.bot.log_action(member.guild, "🛡️ Auto-Ban: Suspicious Account", f"{member.mention} was automatically banned.\n**Reason:** {reason}\n**Account Age:** {discord.utils.utcnow() - member.created_at}", color=0xff0000, user=member)
                logging.info(f"Auto-banned: {member.name} ({reason})")
            except Exception as e:
                logging.error(f"Error banning {member.name}: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        if message.author.id in self.bot.whitelisted_bots: return

        settings = await self.bot.db.get_all_guild_settings(message.guild.id) if message.guild else {}
        content_lower = message.content.lower()
        
        # Anti-Scam
        if settings.get('anti_scam_enabled') != 0:
            is_scam = False
            if any(domain in content_lower for domain in self.SCAM_DOMAINS):
                is_scam = True
                
            if not is_scam:
                for pattern in self.SCAM_PATTERNS:
                    if re.search(pattern, content_lower):
                        if "nitro" in pattern:
                            if "@everyone" in message.content or "@here" in message.content or "http" in content_lower:
                                is_scam = True
                                break
                        else:
                            is_scam = True
                            break

            if is_scam:
                try:
                    await message.delete()
                    await message.author.ban(reason="Auto-ban: Scam account/content")
                    await self.bot.log_action(message.guild, "🛡️ Auto-Ban: Scam Content", f"{message.author.mention} was automatically banned for scam content.\n**Message:** {message.content[:500]}", color=0xff0000, user=message.author)
                    return
                except Exception as e:
                    logging.error(f"Error banning scammer {message.author.name}: {e}")

        # Slur Filter
        if settings.get('slur_filter_enabled') != 0:
            if self.slur_pattern.search(message.content):
                try:
                    await message.delete()
                    await self.bot.log_action(message.guild, "🛡️ Slur Filter", f"A message from {message.author.mention} was deleted for containing prohibited language.\n**Content:** {message.content[:500]}", color=0xffff00, user=message.author)
                    await message.channel.send(f"⚠️ {message.author.mention} - Please avoid using such language.", delete_after=10)
                except: pass
                return

        # Anti-Spam (Message Flood)
        if settings.get('anti_spam_enabled') != 0:
            now = time.time()
            uid = message.author.id
            self.message_track[uid].append(now)
            # Keep only last 5 seconds
            self.message_track[uid] = [t for t in self.message_track[uid] if now - t < 5]
            
            spam_threshold = settings.get('anti_spam_threshold', 5)
            if len(self.message_track[uid]) >= spam_threshold:
                try:
                    await message.author.timeout(timedelta(minutes=10), reason="Anti-Spam: Message flooding")
                    await self.bot.log_action(message.guild, "🛡️ Auto-Timeout: Spam", f"{message.author.mention} was automatically timed out for 10 minutes (Message Flood).", color=0xffa500, user=message.author)
                    await message.channel.send(f"🚫 {message.author.mention} has been timed out for 10 minutes for spamming.", delete_after=10)
                    # Purge recent messages from this user
                    def is_author(m): return m.author.id == uid
                    await message.channel.purge(limit=10, check=is_author)
                except: pass
                return

        # Mention Spam (always on as it's dangerous, but threshold configurable)
        mention_threshold = settings.get('mention_spam_threshold', 5)
        if len(message.mentions) > mention_threshold:
            try:
                await message.delete()
                await message.author.timeout(timedelta(minutes=30), reason="Anti-Spam: Mention spam")
                await self.bot.log_action(message.guild, "🛡️ Auto-Timeout: Mention Spam", f"{message.author.mention} was automatically timed out for 30 minutes (Mention Spam: {len(message.mentions)} mentions).", color=0xffa500, user=message.author)
                await message.channel.send(f"🚫 {message.author.mention} has been timed out for 30 minutes for mention spam.", delete_after=10)
            except: pass

    async def handle_nuke_attempt(self, guild, user, action_type):
        if user.bot:
            return

        settings = await self.bot.db.get_all_guild_settings(guild.id)
        if settings.get('anti_nuke_enabled') == 0:
            return

        now = time.time()
        self.nuke_track[user.id][action_type].append(now)
        # 60s window
        self.nuke_track[user.id][action_type] = [t for t in self.nuke_track[user.id][action_type] if now - t < 60]
        
        threshold = 3
        if action_type in ["ban", "kick"]: threshold = 5
        
        if len(self.nuke_track[user.id][action_type]) >= threshold:
            logging.warning(f"🚨 NUKE ATTEMPT DETECTED! User: {user.name} Action: {action_type}")
            try:
                # Remove all dangerous roles from the user
                member = guild.get_member(user.id)
                if member:
                    roles_to_remove = [role for role in member.roles if role.permissions.administrator or role.permissions.manage_guild or role.permissions.ban_members]
                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove, reason="Anti-Nuke: Mass action detected")
                
                # Notify
                await self.bot.log_action(guild, "🚨 NUKE ATTEMPT DETECTED", f"{user.mention} performed too many `{action_type}` actions. Their administrative roles have been removed.", color=0xff0000, moderator=None, user=user)
                
                channel = await self.bot.get_log_channel(guild)
                if not channel:
                    channel = guild.system_channel or next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
                
                if channel:
                    await channel.send(f"🚨 **NUKE ATTEMPT DETECTED!** {user.mention} performed too many `{action_type}` actions. Their administrative roles have been removed.")
            except Exception as e:
                logging.error(f"Error handling nuke attempt: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            if (discord.utils.utcnow() - entry.created_at).total_seconds() < 10:
                await self.handle_nuke_attempt(channel.guild, entry.user, "channel_delete")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            if (discord.utils.utcnow() - entry.created_at).total_seconds() < 10:
                await self.handle_nuke_attempt(role.guild, entry.user, "role_delete")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if (discord.utils.utcnow() - entry.created_at).total_seconds() < 10:
                await self.handle_nuke_attempt(guild, entry.user, "ban")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not member.bot:
            # Increment daily leaves
            await self.bot.db.increment_daily_stat(member.guild.id, "leaves")

        async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
            if (discord.utils.utcnow() - entry.created_at).total_seconds() < 10:
                await self.handle_nuke_attempt(member.guild, entry.user, "kick")

    @commands.command(name="joins", description="Show join/leave statistics chart", aliases=["stats_joins"])
    @is_staff()
    async def joins(self, ctx):
        stats = await self.bot.db.get_daily_stats(ctx.guild.id, days=7)
        if not stats:
            return await ctx.send("No statistical data collected yet.")
        
        # Gap-filling logic for 7 days
        from datetime import datetime, timedelta
        now = datetime.now()
        full_stats = []
        stats_dict = {row[0]: (row[2], row[3]) for row in stats} # date -> (joins, leaves)
        
        for i in range(6, -1, -1):
            d = (now - timedelta(days=i)).strftime('%Y-%m-%d')
            j, l = stats_dict.get(d, (0, 0))
            full_stats.append((d, j, l))
            
        labels = [row[0] for row in full_stats]
        joins_data = [row[1] for row in full_stats]
        leaves_data = [row[2] for row in full_stats]
        
        chart_config = {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": "Joins",
                        "data": joins_data,
                        "borderColor": "rgb(75, 192, 192)",
                        "fill": False
                    },
                    {
                        "label": "Leaves",
                        "data": leaves_data,
                        "borderColor": "rgb(255, 99, 132)",
                        "fill": False
                    }
                ]
            },
            "options": {
                "title": {"display": True, "text": "Join/Leave Activity (Last 7 Days)", "fontColor": "white"},
                "legend": {"labels": {"fontColor": "white"}},
                "scales": {
                    "yAxes": [{"ticks": {"fontColor": "white", "beginAtZero": True}}],
                    "xAxes": [{"ticks": {"fontColor": "white"}}]
                }
            }
        }
        encoded_config = urllib.parse.quote(json.dumps(chart_config))
        chart_url = f"https://quickchart.io/chart?c={encoded_config}&bkg=rgb(43,45,49)"
        
        embed = discord.Embed(title="📊 Server Join/Leave Statistics", color=0x2b2d31)
        embed.set_image(url=chart_url)
        await ctx.send(embed=embed)

    @commands.command(name="security_status", description="Show bot security monitoring status")
    @is_staff()
    async def security_status(self, ctx):
        embed = discord.Embed(title="🛡️ Security Status", color=0x2b2d31)
        embed.add_field(name="Auto-Ban Suspicious Accounts", value="✅ Enabled", inline=True)
        embed.add_field(name="Scam Detection", value=f"✅ {len(self.SCAM_DOMAINS)} domains monitored", inline=True)
        embed.add_field(name="Slur Filter", value=f"✅ {len(self.SLURS)} words filtered", inline=True)
        embed.add_field(name="Anti-Raid (Join Rate)", value="✅ 10 joins / 30s", inline=True)
        embed.add_field(name="Anti-Spam", value="✅ 5 msgs / 5s", inline=True)
        embed.add_field(name="Anti-Nuke", value="✅ Enabled", inline=True)
        embed.add_field(name="Raid Mode", value="🔴 Active" if self.raid_mode else "🟢 Inactive", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="raidmode", description="Toggle Raid Mode manually")
    @is_staff()
    async def raidmode(self, ctx, status: bool):
        self.raid_mode = status
        state = "enabled" if status else "disabled"
        await ctx.send(f"✅ Raid Mode has been **{state}**.")
        logging.info(f"Raid Mode manually {state} by {ctx.author}")

async def setup(bot):
    await bot.add_cog(Security(bot))
