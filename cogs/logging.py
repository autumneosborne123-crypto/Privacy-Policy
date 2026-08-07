import discord
from discord.ext import commands
import logging
from datetime import datetime

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or message.author.bot: return
        
        enabled = await self.bot.db.get_guild_setting(message.guild.id, "log_message_delete")
        if enabled == 0: return

        description = f"**Message sent by {message.author.mention} deleted in {message.channel.mention}**\n{message.content}"
        await self.bot.log_action(message.guild, "Message Deleted", description, color=0xff4b4b, user=message.author)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.guild or before.author.bot: return
        if before.content == after.content: return
        
        enabled = await self.bot.db.get_guild_setting(before.guild.id, "log_message_edit")
        if enabled == 0: return

        description = f"**Message edited in {before.channel.mention}** [Jump to Message]({after.jump_url})\n\n**Before:**\n{before.content}\n\n**After:**\n{after.content}"
        await self.bot.log_action(before.guild, "Message Edited", description, color=0x3498db, user=before.author)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        enabled = await self.bot.db.get_guild_setting(member.guild.id, "log_member_join")
        if enabled == 0: return
        
        description = f"{member.mention} joined the server.\n**Account Created:** {discord.utils.format_dt(member.created_at, 'R')}"
        await self.bot.log_action(member.guild, "Member Joined", description, color=0x2ecc71, user=member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        enabled = await self.bot.db.get_guild_setting(member.guild.id, "log_member_leave")
        if enabled == 0: return
        
        # Check if they were kicked recently to avoid duplicate logs
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 5:
                    return # Handled by audit log listener
        except:
            pass

        description = f"{member.mention} left the server."
        await self.bot.log_action(member.guild, "Member Left", description, color=0xe74c3c, user=member)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Role updates
        if before.roles != after.roles:
            added = [role.mention for role in after.roles if role not in before.roles]
            removed = [role.mention for role in before.roles if role not in after.roles]
            
            description = ""
            if added: description += f"**Roles Added:** {', '.join(added)}\n"
            if removed: description += f"**Roles Removed:** {', '.join(removed)}"
            
            if description:
                await self.bot.log_action(before.guild, "Member Roles Updated", description, color=0x9b59b6, user=before)

        # Nickname updates
        if before.nick != after.nick:
            description = f"**Nickname Changed**\n**Before:** {before.nick}\n**After:** {after.nick}"
            await self.bot.log_action(before.guild, "Nickname Updated", description, color=0x3498db, user=before)


    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        guild = entry.guild
        action = entry.action
        moderator = entry.user
        target = entry.target
        
        # Mapping action types to human-readable text and colors
        action_map = {
            discord.AuditLogAction.ban: ("Member Banned", 0xff0000),
            discord.AuditLogAction.unban: ("Member Unbanned", 0x00ff00),
            discord.AuditLogAction.kick: ("Member Kicked", 0xe67e22),
            discord.AuditLogAction.member_update: ("Member Updated", 0x3498db),
            discord.AuditLogAction.guild_update: ("Server Updated", 0x3498db),
            discord.AuditLogAction.channel_create: ("Channel Created", 0x2ecc71),
            discord.AuditLogAction.channel_delete: ("Channel Deleted", 0xe74c3c),
            discord.AuditLogAction.channel_update: ("Channel Updated", 0x3498db),
            discord.AuditLogAction.role_create: ("Role Created", 0x2ecc71),
            discord.AuditLogAction.role_delete: ("Role Deleted", 0xe74c3c),
            discord.AuditLogAction.role_update: ("Role Updated", 0x3498db),
            discord.AuditLogAction.invite_create: ("Invite Created", 0x2ecc71),
            discord.AuditLogAction.invite_delete: ("Invite Deleted", 0xe74c3c),
            discord.AuditLogAction.webhook_create: ("Webhook Created", 0x2ecc71),
            discord.AuditLogAction.webhook_delete: ("Webhook Deleted", 0xe74c3c),
            discord.AuditLogAction.webhook_update: ("Webhook Updated", 0x3498db),
            discord.AuditLogAction.emoji_create: ("Emoji Created", 0x2ecc71),
            discord.AuditLogAction.emoji_delete: ("Emoji Deleted", 0xe74c3c),
            discord.AuditLogAction.emoji_update: ("Emoji Updated", 0x3498db),
            discord.AuditLogAction.sticker_create: ("Sticker Created", 0x2ecc71),
            discord.AuditLogAction.sticker_delete: ("Sticker Deleted", 0xe74c3c),
            discord.AuditLogAction.sticker_update: ("Sticker Updated", 0x3498db),
            discord.AuditLogAction.thread_create: ("Thread Created", 0x2ecc71),
            discord.AuditLogAction.thread_delete: ("Thread Deleted", 0xe74c3c),
            discord.AuditLogAction.thread_update: ("Thread Updated", 0x3498db),
            discord.AuditLogAction.bot_add: ("Bot Added", 0x2ecc71),
        }

        if action not in action_map:
            return

        title, color = action_map[action]
        
        # Check if enabled for this guild (excluding master channel which gets everything)
        # For per-guild logs, we check specific settings
        setting_key = None
        if action == discord.AuditLogAction.ban: setting_key = "log_member_ban"
        elif action == discord.AuditLogAction.unban: setting_key = "log_member_unban"
        elif action == discord.AuditLogAction.kick: setting_key = "log_member_leave"
        
        # If no specific setting, we still log to master but might skip guild channel
        # But wait, log_action handles both. So we just need to decide if we call it.
        # The user wants ALL logs in the master channel.
        
        description = ""
        user_obj = None
        
        if action in [discord.AuditLogAction.ban, discord.AuditLogAction.unban, discord.AuditLogAction.kick]:
            description = f"**User:** {target.mention if hasattr(target, 'mention') else target} ({getattr(target, 'id', 'N/A')})\n"
            description += f"**Reason:** {entry.reason or 'No reason provided'}"
            user_obj = target
        elif action == discord.AuditLogAction.member_update:
            # Only log important member updates like timeouts
            if hasattr(entry.before, 'timed_out_until') and hasattr(entry.after, 'timed_out_until'):
                if entry.before.timed_out_until != entry.after.timed_out_until:
                    title = "Member Timeout Updated"
                    description = f"**User:** {target.mention} ({target.id})\n"
                    if entry.after.timed_out_until:
                        description += f"**Timed out until:** {discord.utils.format_dt(entry.after.timed_out_until)}\n"
                    else:
                        description += "**Timeout removed.**\n"
                    description += f"**Reason:** {entry.reason or 'No reason provided'}"
                    user_obj = target
                else:
                    return # Ignore other member updates for now to avoid spam
            else:
                return
        else:
            if hasattr(target, 'mention'):
                description = f"**Target:** {target.mention} ({target.id})\n"
            else:
                description = f"**Target:** {target} ({getattr(target, 'id', 'N/A')})\n"

        # Add changes for updates
        if entry.after:
            changes = []
            try:
                for attr, value in entry.after:
                    before_val = getattr(entry.before, attr, "None")
                    changes.append(f"• **{attr.replace('_', ' ').title()}**: `{before_val}` → `{value}`")
            except:
                pass
                
            if changes:
                # Avoid adding changes to Ban/Kick/Unban as they have specific descriptions
                if action not in [discord.AuditLogAction.ban, discord.AuditLogAction.unban, discord.AuditLogAction.kick]:
                    if description: description += "\n"
                    description += "**Changes:**\n" + "\n".join(changes[:10])

        await self.bot.log_action(guild, title, description, color=color, moderator=moderator, user=user_obj)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel != after.channel:
            enabled = await self.bot.db.get_guild_setting(member.guild.id, "log_voice_activity")
            if enabled == 0: return
            
            if before.channel is None:
                description = f"{member.mention} joined voice channel **{after.channel.name}**"
                color = 0x2ecc71
            elif after.channel is None:
                description = f"{member.mention} left voice channel **{before.channel.name}**"
                color = 0xe74c3c
            else:
                description = f"{member.mention} moved from **{before.channel.name}** to **{after.channel.name}**"
                color = 0x3498db
            
            await self.bot.log_action(member.guild, "Voice Activity", description, color=color, user=member)
            

async def setup(bot):
    await bot.add_cog(Logging(bot))
