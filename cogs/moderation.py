import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
import typing
import re
from utils.permissions import is_admin, is_staff

def parse_duration(duration: typing.Union[str, int]) -> int:
    """Parses a duration string like '1d', '3h', '10m' into minutes."""
    if duration is None:
        return None
    
    if isinstance(duration, int):
        return duration
    
    duration = str(duration).lower().strip()
    if not duration:
        return None
    
    if duration.isdigit():
        return int(duration)
    
    match = re.match(r'^(\d+)([dhwm]?)$', duration)
    if not match:
        raise ValueError(f"Invalid duration format: {duration}")
    
    value, unit = match.groups()
    value = int(value)
    
    if unit == 'd':
        return value * 1440
    elif unit == 'h':
        return value * 60
    elif unit == 'w':
        return value * 10080
    else: # 'm' or empty
        return value

def format_duration(minutes: int) -> str:
    """Formats minutes into a human-readable string."""
    if minutes is None:
        return "Indefinite"
    if minutes >= 10080 and minutes % 10080 == 0:
        weeks = minutes // 10080
        return f"{weeks} week{'s' if weeks > 1 else ''}"
    if minutes >= 1440 and minutes % 1440 == 0:
        days = minutes // 1440
        return f"{days} day{'s' if days > 1 else ''}"
    if minutes >= 60 and minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour{'s' if hours > 1 else ''}"
    return f"{minutes} minute{'s' if minutes != 1 else ''}"

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _send_dm(self, user, embed):
        try:
            await user.send(embed=embed)
        except:
            pass

    async def _do_timeout(self, ctx, member: discord.Member, duration: str, reason: str):
        try:
            minutes = parse_duration(duration)
        except ValueError as e:
            return await ctx.send(f"❌ {e}")

        if minutes > 40320: # 28 days
            return await ctx.send("❌ Timeout duration cannot exceed 28 days (40,320 minutes).")
        
        duration_text = format_duration(minutes)
        try:
            await member.timeout(timedelta(minutes=minutes), reason=reason)
            await ctx.send(f"✅ Successfully timed out {member.mention} for {duration_text}. Reason: {reason}")
            await self.bot.log_action(ctx.guild, "Member Timeout", f"{member.mention} was timed out for {duration_text}.\n**Reason:** {reason}", color=0xffa500, moderator=ctx.author, user=member)
            
            # DM Notification
            embed = discord.Embed(title=f"⏳ You have been timed out in {ctx.guild.name}", color=0xffa500, timestamp=discord.utils.utcnow())
            embed.add_field(name="Duration", value=duration_text)
            embed.add_field(name="Reason", value=reason)
            await self._send_dm(member, embed)
        except Exception as e:
            await ctx.send(f"❌ Failed to timeout member: {e}")

    async def _do_mute(self, ctx, member: discord.Member, duration: str = None, reason: str = "No reason provided"):
        minutes = None
        if duration:
            try:
                minutes = parse_duration(duration)
            except ValueError as e:
                return await ctx.send(f"❌ {e}")

        if minutes and minutes > 40320:
            return await ctx.send("❌ Mute duration (timeout) cannot exceed 28 days (40,320 minutes).")
        
        mute_role_id = await self.bot.db.get_mute_role(ctx.guild.id)
        mute_role = ctx.guild.get_role(mute_role_id) if mute_role_id else None
        
        actions = []
        duration_text = format_duration(minutes) if minutes else None
        
        # 1. Apply Timeout if minutes provided
        if minutes:
            try:
                await member.timeout(timedelta(minutes=minutes), reason=reason)
                actions.append(f"timed out for {duration_text}")
            except Exception as e:
                return await ctx.send(f"❌ Failed to timeout member: {e}")
        
        # 2. Apply Mute Role if configured
        if mute_role:
            try:
                await member.add_roles(mute_role, reason=reason)
                actions.append(f"assigned {mute_role.mention} role")
            except Exception as e:
                # If we already did timeout, we might still want to report this failure
                if not actions:
                    return await ctx.send(f"❌ Failed to add mute role: {e}")
                actions.append(f"(failed to add mute role: {e})")
        
        if not actions:
            # Fallback to indefinite timeout (not possible in Discord, max 28 days)
            # If no minutes and no mute role, we should probably warn the user
            return await ctx.send("❌ No duration provided and no mute role configured. Please provide a duration or set a mute role using `.set_mute_role`.")

        action_str = " and ".join(actions)
        await ctx.send(f"✅ Successfully muted {member.mention} ({action_str}). Reason: {reason}")
        await self.bot.log_action(ctx.guild, "Member Mute", f"{member.mention} was muted.\n**Actions:** {action_str}\n**Reason:** {reason}", color=0xffa500, moderator=ctx.author, user=member)
        
        # DM Notification
        embed = discord.Embed(title=f"🔇 You have been muted in {ctx.guild.name}", color=0xffa500, timestamp=discord.utils.utcnow())
        if duration_text:
            embed.add_field(name="Duration", value=duration_text)
        embed.add_field(name="Reason", value=reason)
        await self._send_dm(member, embed)

    @commands.hybrid_command(name="timeout", description="Timeout a member")
    @is_staff()
    @app_commands.choices(duration=[
        app_commands.Choice(name="1 Day", value="1d"),
        app_commands.Choice(name="3 Days", value="3d"),
        app_commands.Choice(name="7 Days", value="7d")
    ])
    async def timeout(self, ctx, member: discord.Member, duration: str, reason: str = "No reason provided"):
        await self._do_timeout(ctx, member, duration, reason)

    @commands.hybrid_command(name="mute", description="Mute a member (uses role and/or timeout)", aliases=["m"])
    @is_staff()
    @app_commands.choices(duration=[
        app_commands.Choice(name="1 Day", value="1d"),
        app_commands.Choice(name="3 Days", value="3d"),
        app_commands.Choice(name="7 Days", value="7d")
    ])
    async def mute(self, ctx, member: discord.Member, duration: str = None, reason: str = "No reason provided"):
        await self._do_mute(ctx, member, duration, reason)

    @commands.hybrid_command(name="unmute", description="Unmute a member (removes role and timeout)", aliases=["um"])
    @is_staff()
    async def unmute(self, ctx, member: discord.Member, reason: str = "Unmuted by moderator"):
        try:
            mute_role_id = await self.bot.db.get_mute_role(ctx.guild.id)
            mute_role = ctx.guild.get_role(mute_role_id) if mute_role_id else None
            
            actions = []
            
            # Remove Timeout
            if member.timed_out_until:
                await member.timeout(None, reason=reason)
                actions.append("timeout removed")
            
            # Remove Mute Role
            if mute_role and mute_role in member.roles:
                await member.remove_roles(mute_role, reason=reason)
                actions.append("mute role removed")
            
            if not actions and not member.timed_out_until and (not mute_role or mute_role not in member.roles):
                # Even if not "technically" muted by us, we try to clear everything
                await member.timeout(None, reason=reason)
                if mute_role: await member.remove_roles(mute_role, reason=reason)
                actions.append("cleared all restrictions")

            action_str = ", ".join(actions)
            await ctx.send(f"✅ Successfully unmuted {member.mention} ({action_str}).")
            await self.bot.log_action(ctx.guild, "Member Unmute", f"{member.mention} was unmuted.\n**Actions:** {action_str}\n**Reason:** {reason}", color=0x00ff00, moderator=ctx.author, user=member)
            
            # DM Notification
            embed = discord.Embed(title=f"🔊 You have been unmuted in {ctx.guild.name}", color=0x00ff00, timestamp=discord.utils.utcnow())
            embed.add_field(name="Reason", value=reason)
            await self._send_dm(member, embed)
        except Exception as e:
            await ctx.send(f"❌ Failed to unmute member: {e}")

    @commands.hybrid_command(name="ban", description="Ban a member")
    @is_staff()
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, reason: str = "No reason provided"):
        if ctx.guild.me.top_role <= member.top_role:
            return await ctx.send("❌ I cannot ban this member because their role is higher than or equal to mine.")
        if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("❌ You cannot ban this member because their role is higher than or equal to yours.")

        try:
            # DM Notification BEFORE ban
            embed = discord.Embed(title=f"🔨 You have been banned from {ctx.guild.name}", color=0xff0000, timestamp=discord.utils.utcnow())
            embed.add_field(name="Reason", value=reason)
            await self._send_dm(member, embed)
            
            await member.ban(reason=reason, delete_message_seconds=604800)
            await ctx.send(f"✅ Successfully banned {member.name}. Reason: {reason}")
            await self.bot.log_action(ctx.guild, "Member Ban", f"{member.name} was banned and messages from the last 7 days were deleted.\n**Reason:** {reason}", color=0xff0000, moderator=ctx.author, user=member)
        except Exception as e:
            await ctx.send(f"❌ Failed to ban member: {e}")

    @commands.hybrid_command(name="kick", description="Kick a member")
    @is_staff()
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, reason: str = "No reason provided"):
        if ctx.guild.me.top_role <= member.top_role:
            return await ctx.send("❌ I cannot kick this member because their role is higher than or equal to mine.")
        if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("❌ You cannot kick this member because their role is higher than or equal to yours.")

        try:
            # DM Notification BEFORE kick
            embed = discord.Embed(title=f"👢 You have been kicked from {ctx.guild.name}", color=0xffa500, timestamp=discord.utils.utcnow())
            embed.add_field(name="Reason", value=reason)
            await self._send_dm(member, embed)
            
            await member.kick(reason=reason)
            await ctx.send(f"✅ Successfully kicked {member.name}. Reason: {reason}")
            await self.bot.log_action(ctx.guild, "Member Kick", f"{member.name} was kicked.\n**Reason:** {reason}", color=0xffa500, moderator=ctx.author, user=member)
        except Exception as e:
            await ctx.send(f"❌ Failed to kick member: {e}")

    @commands.hybrid_command(name="unban", description="Unban a user")
    @is_staff()
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User, reason: str = "No reason provided"):
        try:
            await ctx.guild.unban(user, reason=reason)
            await ctx.send(f"✅ Successfully unbanned {user.name}. Reason: {reason}")
            await self.bot.log_action(ctx.guild, "Member Unban", f"{user.name} was unbanned.\n**Reason:** {reason}", color=0x00ff00, moderator=ctx.author, user=user)
            
            # DM Notification + Invite Link
            try:
                invite = await ctx.channel.create_invite(max_age=86400, max_uses=1, reason="User unbanned")
                embed = discord.Embed(title=f"✨ You have been unbanned from {ctx.guild.name}", color=0x00ff00, timestamp=discord.utils.utcnow())
                embed.add_field(name="Reason", value=reason)
                embed.add_field(name="Invite Link", value=invite.url)
                embed.description = f"You can rejoin the server using this link: {invite.url}"
                await self._send_dm(user, embed)
            except:
                pass # Might not have permission to create invite
        except Exception as e:
            await ctx.send(f"❌ Failed to unban member: {e}")

    @commands.hybrid_command(name="warn", description="Warn a member")
    @is_staff()
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        try:
            await self.bot.db.add_warn(member.id, ctx.guild.id, ctx.author.id, reason)
            warns = await self.bot.db.get_warns(member.id, ctx.guild.id)
            await ctx.send(f"⚠️ {member.mention} has been warned. Reason: {reason} (Total warns: {len(warns)})")
            await self.bot.log_action(ctx.guild, "Member Warning", f"{member.mention} was warned.\n**Reason:** {reason}\n**Total Warns:** {len(warns)}", color=0xffff00, moderator=ctx.author, user=member)
            
            # DM Notification
            embed = discord.Embed(title=f"⚠️ You have been warned in {ctx.guild.name}", color=0xffff00, timestamp=discord.utils.utcnow())
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Total Warnings", value=str(len(warns)))
            await self._send_dm(member, embed)
        except Exception as e:
            await ctx.send(f"❌ Failed to warn member: {e}")

    @commands.hybrid_command(name="warns", description="Check a member's warnings", aliases=["warnings"])
    @is_staff()
    async def warns(self, ctx, member: discord.Member):
        try:
            warn_list = await self.bot.db.get_warns(member.id, ctx.guild.id)
            if not warn_list:
                return await ctx.send(f"{member.name} has no warnings.")

            embed = discord.Embed(title=f"Warnings for {member.name}", color=0xffa500)
            for moderator_id, reason, timestamp, warn_id in warn_list:
                moderator = self.bot.get_user(int(moderator_id))
                mod_name = moderator.name if moderator else "Unknown Moderator"
                embed.add_field(
                    name=f"ID: {warn_id} | {timestamp}",
                    value=f"**Moderator:** {mod_name}\n**Reason:** {reason}",
                    inline=False
                )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Failed to fetch warnings: {e}")

    @commands.hybrid_command(name="removewarn", description="Remove a specific warning", aliases=["delwarn"])
    @is_staff()
    async def removewarn(self, ctx, warn_id: int):
        try:
            warn = await self.bot.db.get_warn(warn_id, ctx.guild.id)
            user_id = warn[0] if warn else None
            
            await self.bot.db.remove_warn(warn_id, ctx.guild.id)
            await ctx.send(f"✅ Warning ID `{warn_id}` removed.")
            await self.bot.log_action(ctx.guild, "Warning Removed", f"Warning ID `{warn_id}` was removed.", color=0x00ffff, moderator=ctx.author)
            
            if user_id:
                user = self.bot.get_user(int(user_id))
                if user:
                    embed = discord.Embed(title=f"✅ A warning was removed from you in {ctx.guild.name}", color=0x00ffff, timestamp=discord.utils.utcnow())
                    embed.add_field(name="Warning ID", value=str(warn_id))
                    await self._send_dm(user, embed)
        except Exception as e:
            await ctx.send(f"❌ Failed to remove warning: {e}")

    @commands.hybrid_command(name="clearwarns", description="Clear all warnings for a member", aliases=["delwarns"])
    @is_staff()
    async def clearwarns(self, ctx, member: discord.Member):
        try:
            await self.bot.db.clear_warns(member.id, ctx.guild.id)
            await ctx.send(f"✅ All warnings for {member.mention} have been cleared.")
            await self.bot.log_action(ctx.guild, "Warnings Cleared", f"All warnings for {member.mention} were cleared.", color=0x00ffff, moderator=ctx.author, user=member)
            
            # DM Notification
            embed = discord.Embed(title=f"✅ All your warnings have been cleared in {ctx.guild.name}", color=0x00ffff, timestamp=discord.utils.utcnow())
            await self._send_dm(member, embed)
        except Exception as e:
            await ctx.send(f"❌ Failed to clear warnings: {e}")

    @commands.hybrid_command(name="clear", description="Clear messages")
    @is_staff()
    async def clear(self, ctx, amount: int = 5):
        await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"Cleared {amount} messages.", delete_after=5)
        await self.bot.log_action(ctx.guild, "Messages Cleared", f"{amount} messages were cleared in {ctx.channel.mention}.", color=0x00ffff, moderator=ctx.author)

    @commands.hybrid_command(name="ping")
    async def ping(self, ctx):
        await ctx.send(f"Pong! {round(self.bot.latency * 1000)}ms")

    @commands.hybrid_command(name="muted", description="List all muted/timed-out members")
    @is_staff()
    async def muted(self, ctx):
        mute_role_id = await self.bot.db.get_mute_role(ctx.guild.id)
        mute_role = ctx.guild.get_role(mute_role_id) if mute_role_id else None
        
        muted_members = []
        for member in ctx.guild.members:
            reasons = []
            if member.timed_out_until and member.timed_out_until > discord.utils.utcnow():
                reasons.append(f"Timeout until {discord.utils.format_dt(member.timed_out_until, 'R')}")
            if mute_role and mute_role in member.roles:
                reasons.append("Mute Role")
            
            if reasons:
                muted_members.append(f"{member.mention} ({member.id}) - {', '.join(reasons)}")
        
        if not muted_members:
            return await ctx.send("No members are currently muted or timed out.")
        
        embed = discord.Embed(title="🔇 Muted Members", description="\n".join(muted_members), color=0xffa500)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="logs", description="View recent moderation logs")
    @is_staff()
    async def logs(self, ctx, user: discord.User = None, limit: int = 10):
        try:
            logs = []
            async for entry in ctx.guild.audit_logs(limit=100, action=None):
                if user and entry.target and entry.target.id != user.id:
                    continue
                
                # Filter for moderation actions
                if entry.action in [discord.AuditLogAction.ban, discord.AuditLogAction.unban, 
                                   discord.AuditLogAction.kick, discord.AuditLogAction.member_update,
                                   discord.AuditLogAction.member_role_update, discord.AuditLogAction.member_prune,
                                   discord.AuditLogAction.member_disconnect, discord.AuditLogAction.member_move,
                                   discord.AuditLogAction.message_delete, discord.AuditLogAction.message_bulk_delete]:
                    
                    time = discord.utils.format_dt(entry.created_at, 'R')
                    logs.append(f"**{entry.user}**: {entry.action.name.replace('_', ' ').title()} on **{entry.target}** {time}\nReason: {entry.reason or 'No reason'}")
                    if len(logs) >= limit:
                        break

            if not logs:
                return await ctx.send("No recent moderation logs found.")

            embed = discord.Embed(title="📜 Moderation Logs", description="\n\n".join(logs), color=0x2b2d31)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Failed to fetch logs: {e}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
