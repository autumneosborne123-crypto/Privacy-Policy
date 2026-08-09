import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from utils.permissions import is_admin

class ConfigCog(commands.Cog, name="Config"):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="set_welcome")
    @is_admin()
    async def set_welcome(self, ctx, channel: discord.TextChannel):
        await self.bot.db.set_guild_setting(ctx.guild.id, "welcome_channel_id", str(channel.id))
        await ctx.send(f"Welcome channel set to {channel.mention}!", ephemeral=True)

    @commands.hybrid_command(name="set_welcome_message")
    @is_admin()
    async def set_welcome_message(self, ctx, *, message: str):
        await self.bot.db.set_guild_setting(ctx.guild.id, "welcome_message", message)
        await ctx.send("Welcome message updated!", ephemeral=True)

    @commands.hybrid_command(name="set_goodbye")
    @is_admin()
    async def set_goodbye(self, ctx, channel: discord.TextChannel):
        await self.bot.db.set_guild_setting(ctx.guild.id, "goodbye_channel_id", str(channel.id))
        await ctx.send(f"Goodbye channel set to {channel.mention}!", ephemeral=True)

    @commands.hybrid_command(name="set_goodbye_message")
    @is_admin()
    async def set_goodbye_message(self, ctx, *, message: str):
        await self.bot.db.set_guild_setting(ctx.guild.id, "goodbye_message", message)
        await ctx.send("Goodbye message updated!", ephemeral=True)

    @commands.hybrid_command(name="set_inspirational_quotes")
    @is_admin()
    async def set_inspirational_quotes(self, ctx, channel: discord.TextChannel):
        await self.bot.db.set_quote_feed(ctx.guild.id, channel.id)
        await ctx.send(f"Inspirational quotes channel set to {channel.mention}!", ephemeral=True)

    @commands.hybrid_command(name="quote_feed", description="Set or remove the inspirational quote feed for this server")
    @is_admin()
    async def quote_feed(self, ctx, channel: discord.TextChannel = None):
        """Set or remove the inspirational quote feed for this server.
        Only Admins and members with the 'Administrator' role can use this.
        """
        if channel:
            await self.bot.db.set_quote_feed(ctx.guild.id, channel.id)
            await ctx.send(f"✅ Inspirational quotes will now be sent to {channel.mention} every 2.5 hours.", ephemeral=True)
        else:
            await self.bot.db.remove_quote_feed(ctx.guild.id)
            await ctx.send("❌ Inspirational quote feed has been disabled for this server.", ephemeral=True)

    @commands.hybrid_command(name="set_level_channel")
    @is_admin()
    async def set_level_channel(self, ctx, channel: discord.TextChannel):
        await self.bot.db.set_guild_setting(ctx.guild.id, "level_up_channel_id", str(channel.id))
        await ctx.send(f"Level-up notifications set to {channel.mention}!", ephemeral=True)

    @commands.hybrid_command(name="set_leveling_channel", description="Set the channel where leveling commands can be used")
    @is_admin()
    async def set_leveling_channel(self, ctx, channel: discord.TextChannel = None):
        if channel:
            await self.bot.db.set_guild_setting(ctx.guild.id, "leveling_channel_id", str(channel.id))
            await ctx.send(f"Leveling commands are now restricted to {channel.mention}!", ephemeral=True)
        else:
            await self.bot.db.set_guild_setting(ctx.guild.id, "leveling_channel_id", None)
            await ctx.send("Leveling commands can now be used in any channel.", ephemeral=True)

    @commands.hybrid_command(name="settings", description="Show current bot settings for this server")
    @is_admin()
    async def settings(self, ctx):
        embed = discord.Embed(title="⚙️ Server Settings", color=0x2b2d31)
        
        settings = await self.bot.db.get_all_guild_settings(ctx.guild.id)
        
        # Welcome
        w_chan_id = settings.get("welcome_channel_id")
        w_chan = self.bot.get_channel(int(w_chan_id)) if w_chan_id else None
        embed.add_field(name="👋 Welcome", value=f"**Channel:** {w_chan.mention if w_chan else 'None'}\n**Message:** {settings.get('welcome_message') or 'None'}", inline=False)
        
        # Goodbye
        g_chan_id = settings.get("goodbye_channel_id")
        g_chan = self.bot.get_channel(int(g_chan_id)) if g_chan_id else None
        embed.add_field(name="🚪 Goodbye", value=f"**Channel:** {g_chan.mention if g_chan else 'None'}\n**Message:** {settings.get('goodbye_message') or 'None'}", inline=False)
        
        # Leveling
        l_chan_id = settings.get("level_up_channel_id")
        l_chan = self.bot.get_channel(int(l_chan_id)) if l_chan_id else None
        lc_chan_id = settings.get("leveling_channel_id")
        lc_chan = self.bot.get_channel(int(lc_chan_id)) if lc_chan_id else None
        embed.add_field(name="📈 Leveling", value=f"**Notification Channel:** {l_chan.mention if l_chan else 'Original'}\n**Command Restriction:** {lc_chan.mention if lc_chan else 'Any'}", inline=False)
        
        # Music
        m_chan_id = settings.get("music_channel_id")
        m_chan = self.bot.get_channel(int(m_chan_id)) if m_chan_id else None
        
        # Quotes
        q_feeds = await self.bot.db.get_quote_feeds()
        guild_feed = next((f[1] for f in q_feeds if f[0] == str(ctx.guild.id)), None)
        q_chan = self.bot.get_channel(int(guild_feed)) if guild_feed else None
        
        # Logs
        log_chan_id = settings.get("log_channel_id")
        log_chan = None
        if log_chan_id:
            log_chan = self.bot.get_channel(int(log_chan_id))
            if not log_chan:
                try: log_chan = await self.bot.fetch_channel(int(log_chan_id))
                except: pass
        
        log_status = ""
        if log_chan:
            log_status = log_chan.mention
            # Permission check
            perms = log_chan.permissions_for(ctx.guild.me)
            if not (perms.view_channel and perms.send_messages and perms.embed_links):
                log_status += " ⚠️ **(Missing Permissions)**"
        else:
            log_status = "None"
            # Try to see if fallback by name would work
            channels = getattr(ctx.guild, "text_channels", [])
            if isinstance(channels, list):
                for name in ["flower-log", "flower-logs", "flower logs"]:
                    fb = discord.utils.get(channels, name=name)
                    if fb and hasattr(fb, "mention"):
                        log_status += f"\n*(Found {fb.mention} by name)*"
                        break
        
        log_settings = []
        if settings.get('log_message_delete') != 0: log_settings.append("Del")
        if settings.get('log_message_edit') != 0: log_settings.append("Edit")
        if settings.get('log_member_join') != 0: log_settings.append("Join")
        if settings.get('log_member_leave') != 0: log_settings.append("Leave")
        if settings.get('log_member_ban') != 0: log_settings.append("Ban")
        if settings.get('log_member_unban') != 0: log_settings.append("Unban")
        if settings.get('log_voice_activity') != 0: log_settings.append("Voice")
        
        log_info = f"**Channel:** {log_status}"
        if log_settings: log_info += f"\n**Active:** {', '.join(log_settings)}"
        else: log_info += "\n**Active:** None"
        
        # Mute Role
        m_role_id = settings.get("mute_role_id")
        mute_role = ctx.guild.get_role(int(m_role_id)) if m_role_id else None

        # Embed & Roles Channels
        e_chan_id = settings.get("embed_channel_id")
        e_chan = self.bot.get_channel(int(e_chan_id)) if e_chan_id else None
        r_chan_id = settings.get("roles_channel_id")
        r_chan = self.bot.get_channel(int(r_chan_id)) if r_chan_id else None

        # Security & Moderation
        anti_spam = "✅" if settings.get('anti_spam_enabled') != 0 else "❌"
        anti_scam = "✅" if settings.get('anti_scam_enabled') != 0 else "❌"
        slur_filt = "✅" if settings.get('slur_filter_enabled') != 0 else "❌"
        anti_raid = "✅" if settings.get('anti_raid_enabled') != 0 else "❌"
        anti_nuke = "✅" if settings.get('anti_nuke_enabled') != 0 else "❌"
        auto_role_id = settings.get('auto_role_id')
        auto_role = ctx.guild.get_role(int(auto_role_id)) if auto_role_id else None

        embed.add_field(name="🌟 Quotes", value=f"**Channel:** {q_chan.mention if q_chan else 'None'}", inline=True)
        embed.add_field(name="🎵 Music", value=f"**Channel:** {m_chan.mention if m_chan else 'None'}", inline=True)
        embed.add_field(name="📜 Audit Logs", value=log_info, inline=True)
        embed.add_field(name="🔇 Mute Role", value=f"**Role:** {mute_role.mention if mute_role else 'None'}", inline=True)
        embed.add_field(name="🛠️ Embeds", value=f"**Channel:** {e_chan.mention if e_chan else 'Any'}", inline=True)
        embed.add_field(name="🎭 Roles", value=f"**Channel:** {r_chan.mention if r_chan else 'Any'}", inline=True)
        embed.add_field(name="🛡️ Security", value=f"**Anti-Spam:** {anti_spam} | **Anti-Scam:** {anti_scam}\n**Slur Filter:** {slur_filt} | **Anti-Raid:** {anti_raid}\n**Anti-Nuke:** {anti_nuke}", inline=False)
        embed.add_field(name="🎭 Auto-Role", value=f"**Role:** {auto_role.mention if auto_role else 'None'}", inline=True)
        
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="set_music_channel", description="Set the channel for music commands")
    @is_admin()
    async def set_music_channel(self, ctx, channel: discord.TextChannel):
        await self.bot.db.set_guild_setting(ctx.guild.id, "music_channel_id", str(channel.id))
        await ctx.send(f"Music commands are now restricted to {channel.mention}!", ephemeral=True)

    @commands.hybrid_command(name="set_log_channel", description="Set the channel for bot audit logs")
    @is_admin()
    async def set_log_channel(self, ctx, channel: discord.TextChannel = None):
        if channel:
            # Check permissions before setting
            permissions = channel.permissions_for(ctx.guild.me)
            if not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
                missing = []
                if not permissions.view_channel: missing.append("View Channel")
                if not permissions.send_messages: missing.append("Send Messages")
                if not permissions.embed_links: missing.append("Embed Links")
                return await ctx.send(f"❌ I don't have enough permissions in {channel.mention} to send logs. Missing: {', '.join(missing)}", ephemeral=True)

            await self.bot.db.set_log_channel(ctx.guild.id, channel.id)
            await ctx.send(f"✅ Bot audit logs will now be sent to {channel.mention}.", ephemeral=True)
        else:
            await self.bot.db.set_log_channel(ctx.guild.id, None)
            await ctx.send("❌ Bot audit logs have been disabled for this server.", ephemeral=True)

    @commands.command(name="set_mute_role", description="Set the role used for muting members")
    @is_admin()
    async def set_mute_role(self, ctx, role: discord.Role = None):
        if role:
            await self.bot.db.set_mute_role(ctx.guild.id, role.id)
            await ctx.send(f"✅ Mute role set to {role.mention}.")
        else:
            await self.bot.db.set_mute_role(ctx.guild.id, None)
            await ctx.send("❌ Mute role has been removed. Muting will now only use timeouts.")

    @commands.hybrid_command(name="set_embed_channel", description="Set the channel for embed commands")
    @is_admin()
    async def set_embed_channel(self, ctx, channel: discord.TextChannel = None):
        if channel:
            await self.bot.db.set_guild_setting(ctx.guild.id, "embed_channel_id", str(channel.id))
            await ctx.send(f"✅ Embed commands are now restricted to {channel.mention}!", ephemeral=True)
        else:
            await self.bot.db.set_guild_setting(ctx.guild.id, "embed_channel_id", None)
            await ctx.send("✅ Embed commands can now be used in any channel.", ephemeral=True)

    @commands.hybrid_command(name="set_roles_channel", description="Set the channel for role commands")
    @is_admin()
    async def set_roles_channel(self, ctx, channel: discord.TextChannel = None):
        if channel:
            await self.bot.db.set_guild_setting(ctx.guild.id, "roles_channel_id", str(channel.id))
            await ctx.send(f"✅ Role commands are now restricted to {channel.mention}!", ephemeral=True)
        else:
            await self.bot.db.set_guild_setting(ctx.guild.id, "roles_channel_id", None)
            await ctx.send("✅ Role commands can now be used in any channel.", ephemeral=True)

    @commands.hybrid_command(name="toggle_log", description="Enable or disable a logging category")
    @is_admin()
    @app_commands.choices(category=[
        app_commands.Choice(name="Message Delete", value="log_message_delete"),
        app_commands.Choice(name="Message Edit", value="log_message_edit"),
        app_commands.Choice(name="Member Join", value="log_member_join"),
        app_commands.Choice(name="Member Leave", value="log_member_leave"),
        app_commands.Choice(name="Member Ban", value="log_member_ban"),
        app_commands.Choice(name="Member Unban", value="log_member_unban"),
        app_commands.Choice(name="Voice Activity", value="log_voice_activity")
    ])
    async def toggle_log(self, ctx, category: str, enabled: bool):
        await self.bot.db.set_guild_setting(ctx.guild.id, category, 1 if enabled else 0)
        status = "enabled" if enabled else "disabled"
        await ctx.send(f"✅ Logging for `{category.replace('log_', '').replace('_', ' ').title()}` has been **{status}**.", ephemeral=True)

    @commands.hybrid_command(name="toggle_module", description="Enable or disable a bot module (Cog)")
    @is_admin()
    @app_commands.choices(module=[
        app_commands.Choice(name="Leveling", value="Leveling"),
        app_commands.Choice(name="Music", value="Music"),
        app_commands.Choice(name="Security", value="Security"),
        app_commands.Choice(name="Fun", value="Fun"),
        app_commands.Choice(name="Moderation", value="Moderation"),
        app_commands.Choice(name="Games", value="Games"),
        app_commands.Choice(name="Economy", value="Economy"),
        app_commands.Choice(name="Adventure", value="Adventure"),
        app_commands.Choice(name="Logging", value="Logging"),
        app_commands.Choice(name="Roles", value="Roles"),
        app_commands.Choice(name="Tools", value="Tools"),
        app_commands.Choice(name="Media", value="Media")
    ])
    async def toggle_module(self, ctx, module: str, enabled: bool):
        settings = await self.bot.db.get_all_guild_settings(ctx.guild.id)
        disabled_raw = settings.get('disabled_cogs') or ""
        disabled = [d.strip().lower() for d in disabled_raw.split(',') if d.strip()]
        
        module_lower = module.lower()
        if enabled:
            if module_lower in disabled:
                disabled.remove(module_lower)
        else:
            if module_lower not in disabled:
                disabled.append(module_lower)
        
        new_disabled = ",".join(disabled)
        await self.bot.db.set_guild_setting(ctx.guild.id, "disabled_cogs", new_disabled if new_disabled else None)
        
        status = "enabled" if enabled else "disabled"
        await ctx.send(f"✅ Module `{module}` has been **{status}** for this server.", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # We don't want to conflict with Security cog's auto-ban
        # But we need to check if the member is still there
        await asyncio.sleep(1) # Wait a bit for potential auto-ban
        if member.guild.get_member(member.id) is None: return

        cid = await self.bot.db.get_guild_setting(member.guild.id, "welcome_channel_id")
        msg_template = await self.bot.db.get_guild_setting(member.guild.id, "welcome_message")
        if cid and msg_template:
            channel = self.bot.get_channel(int(cid))
            if channel:
                msg = msg_template.replace("{member}", member.mention).replace("{guild}", member.guild.name)
                try: await channel.send(msg)
                except: pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        cid = await self.bot.db.get_guild_setting(member.guild.id, "goodbye_channel_id")
        msg_template = await self.bot.db.get_guild_setting(member.guild.id, "goodbye_message")
        if cid and msg_template:
            channel = self.bot.get_channel(int(cid))
            if channel:
                msg = msg_template.replace("{member}", member.mention).replace("{guild}", member.guild.name)
                try: await channel.send(msg)
                except: pass

async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
