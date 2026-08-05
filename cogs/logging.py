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
    async def on_guild_role_create(self, role):
        await self.bot.log_action(role.guild, "Role Created", f"Role: {role.mention} ({role.name})", color=0x2ecc71)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self.bot.log_action(role.guild, "Role Deleted", f"Role: {role.name}", color=0xe74c3c)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self.bot.log_action(channel.guild, "Channel Created", f"Channel: {channel.mention} ({channel.name})", color=0x2ecc71)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self.bot.log_action(channel.guild, "Channel Deleted", f"Channel: {channel.name}", color=0xe74c3c)

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
            
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        enabled = await self.bot.db.get_guild_setting(guild.id, "log_member_ban")
        if enabled == 0: return
        
        # Try to find the ban reason from audit logs
        reason = "No reason provided"
        moderator = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    reason = entry.reason or "No reason provided"
                    moderator = entry.user
                    break
        except:
            pass
            
        description = f"**{user.name}** was banned from the server."
        if reason:
            description += f"\n**Reason:** {reason}"
            
        await self.bot.log_action(guild, "Member Banned", description, color=0xff0000, user=user, moderator=moderator)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        enabled = await self.bot.db.get_guild_setting(guild.id, "log_member_unban")
        if enabled == 0: return
        
        reason = "No reason provided"
        moderator = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.unban):
                if entry.target.id == user.id:
                    reason = entry.reason or "No reason provided"
                    moderator = entry.user
                    break
        except:
            pass

        description = f"**{user.name}** was unbanned from the server."
        if reason:
            description += f"\n**Reason:** {reason}"

        await self.bot.log_action(guild, "Member Unbanned", description, color=0x00ff00, user=user, moderator=moderator)

async def setup(bot):
    await bot.add_cog(Logging(bot))
