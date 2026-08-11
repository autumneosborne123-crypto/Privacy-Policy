import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from utils.permissions import is_admin

class ConfigCog(commands.Cog, name="Config"):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="config", description="Bot configuration management", invoke_without_command=True)
    @is_admin()
    async def config_group(self, ctx):
        """Main command for configuration. Use .config <command>."""
        await ctx.defer()
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(title="⚙️ Configuration System", description="Use `.config <command>` to manage server settings.", color=0x2b2d31)
            cmds = ["settings", "welcome", "goodbye", "leveling", "music", "log", "quotes", "roles", "toggle", "mute_role"]
            embed.add_field(name="Available Categories", value=", ".join([f"`{c}`" for c in cmds]), inline=False)
            await ctx.send(embed=embed)

    @config_group.command(name="welcome", description="Configure welcome messages")
    @is_admin()
    @app_commands.describe(channel="The channel for welcome messages", message="The message template (use {member} and {guild})", reset="Reset welcome settings")
    async def welcome(self, ctx, channel: discord.TextChannel = None, message: str = None, reset: bool = False):
        if reset:
            await self.bot.db.set_guild_setting(ctx.guild.id, "welcome_channel_id", None)
            await self.bot.db.set_guild_setting(ctx.guild.id, "welcome_message", None)
            return await ctx.send("✅ Welcome settings have been reset.", ephemeral=True)

        if channel:
            await self.bot.db.set_guild_setting(ctx.guild.id, "welcome_channel_id", str(channel.id))
        if message:
            await self.bot.db.set_guild_setting(ctx.guild.id, "welcome_message", message)
        
        await ctx.send(f"✅ Welcome settings updated!", ephemeral=True)

    @config_group.command(name="goodbye", description="Configure goodbye messages")
    @is_admin()
    @app_commands.describe(channel="The channel for goodbye messages", message="The message template (use {member} and {guild})", reset="Reset goodbye settings")
    async def goodbye(self, ctx, channel: discord.TextChannel = None, message: str = None, reset: bool = False):
        if reset:
            await self.bot.db.set_guild_setting(ctx.guild.id, "goodbye_channel_id", None)
            await self.bot.db.set_guild_setting(ctx.guild.id, "goodbye_message", None)
            return await ctx.send("✅ Goodbye settings have been reset.", ephemeral=True)

        if channel:
            await self.bot.db.set_guild_setting(ctx.guild.id, "goodbye_channel_id", str(channel.id))
        if message:
            await self.bot.db.set_guild_setting(ctx.guild.id, "goodbye_message", message)
        
        await ctx.send(f"✅ Goodbye settings updated!", ephemeral=True)

    @config_group.command(name="quotes", description="Configure inspirational quote feed")
    @is_admin()
    async def quotes(self, ctx, channel: discord.TextChannel = None):
        if channel:
            await self.bot.db.set_quote_feed(ctx.guild.id, channel.id)
            await ctx.send(f"✅ Inspirational quotes will now be sent to {channel.mention} every 2.5 hours.", ephemeral=True)
        else:
            await self.bot.db.remove_quote_feed(ctx.guild.id)
            await ctx.send("❌ Inspirational quote feed has been disabled.", ephemeral=True)

    @config_group.command(name="leveling", description="Configure leveling system")
    @is_admin()
    async def leveling(self, ctx, notify_channel: discord.TextChannel = None, restrict_channel: discord.TextChannel = None, reset_notify: bool = False, reset_restrict: bool = False):
        if reset_notify:
            await self.bot.db.set_guild_setting(ctx.guild.id, "level_up_channel_id", None)
        elif notify_channel:
            await self.bot.db.set_guild_setting(ctx.guild.id, "level_up_channel_id", str(notify_channel.id))
            
        if reset_restrict:
            await self.bot.db.set_guild_setting(ctx.guild.id, "leveling_channel_id", None)
        elif restrict_channel:
            await self.bot.db.set_guild_setting(ctx.guild.id, "leveling_channel_id", str(restrict_channel.id))
        
        await ctx.send("✅ Leveling settings updated!", ephemeral=True)

    @config_group.command(name="settings", description="Show current bot settings")
    @is_admin()
    async def settings(self, ctx):
        await ctx.defer()
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

    @config_group.command(name="music", description="Configure music channel")
    @is_admin()
    async def music(self, ctx, channel: discord.TextChannel = None):
        await self.bot.db.set_guild_setting(ctx.guild.id, "music_channel_id", str(channel.id) if channel else None)
        status = f"restricted to {channel.mention}" if channel else "allowed in any channel"
        await ctx.send(f"✅ Music commands are now {status}!", ephemeral=True)

    @config_group.command(name="log", description="Configure bot audit logs")
    @is_admin()
    async def log(self, ctx, channel: discord.TextChannel = None, toggle_category: str = None, enabled: bool = True):
        if channel:
            permissions = channel.permissions_for(ctx.guild.me)
            if not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
                return await ctx.send("❌ I don't have enough permissions in that channel.", ephemeral=True)
            await self.bot.db.set_log_channel(ctx.guild.id, channel.id)
            await ctx.send(f"✅ Audit logs set to {channel.mention}.", ephemeral=True)
        
        if toggle_category:
            await self.bot.db.set_guild_setting(ctx.guild.id, toggle_category, 1 if enabled else 0)
            status = "enabled" if enabled else "disabled"
            await ctx.send(f"✅ Logging for `{toggle_category}` has been **{status}**.", ephemeral=True)

    @config_group.command(name="mute_role", description="Set the mute role")
    @is_admin()
    async def mute_role(self, ctx, role: discord.Role = None):
        await self.bot.db.set_mute_role(ctx.guild.id, role.id if role else None)
        status = f"set to {role.mention}" if role else "removed"
        await ctx.send(f"✅ Mute role {status}.", ephemeral=True)

    @config_group.command(name="embeds", description="Configure embed channel")
    @is_admin()
    async def embeds(self, ctx, channel: discord.TextChannel = None):
        await self.bot.db.set_guild_setting(ctx.guild.id, "embed_channel_id", str(channel.id) if channel else None)
        status = f"restricted to {channel.mention}" if channel else "allowed in any channel"
        await ctx.send(f"✅ Embed commands are now {status}!", ephemeral=True)

    @config_group.command(name="roles", description="Configure roles channel")
    @is_admin()
    async def roles(self, ctx, channel: discord.TextChannel = None):
        await self.bot.db.set_guild_setting(ctx.guild.id, "roles_channel_id", str(channel.id) if channel else None)
        status = f"restricted to {channel.mention}" if channel else "allowed in any channel"
        await ctx.send(f"✅ Role commands are now {status}!", ephemeral=True)

    @config_group.command(name="toggle", description="Enable or disable a module or log category")
    @is_admin()
    async def toggle(self, ctx, module: str = None, log_category: str = None, enabled: bool = True):
        await self._do_toggle(ctx, module, log_category, enabled)

    async def _do_toggle(self, ctx, module: str = None, log_category: str = None, enabled: bool = True):
        if module:
            settings = await self.bot.db.get_all_guild_settings(ctx.guild.id)
            disabled_raw = settings.get('disabled_cogs') or ""
            disabled = [d.strip().lower() for d in disabled_raw.split(',') if d.strip()]
            module_lower = module.lower()
            if enabled:
                if module_lower in disabled: disabled.remove(module_lower)
            else:
                if module_lower not in disabled: disabled.append(module_lower)
            await self.bot.db.set_guild_setting(ctx.guild.id, "disabled_cogs", ",".join(disabled) if disabled else None)
            await ctx.send(f"✅ Module `{module}` {'enabled' if enabled else 'disabled'}.", ephemeral=True)
        
        if log_category:
            await self.bot.db.set_guild_setting(ctx.guild.id, log_category, 1 if enabled else 0)
            await ctx.send(f"✅ Log category `{log_category}` {'enabled' if enabled else 'disabled'}.", ephemeral=True)

    @commands.hybrid_command(name="enable", description="Enable a bot module (e.g. moderation, adventure)")
    @is_admin()
    async def enable(self, ctx, module: str):
        """Super easy command to enable a module for this server."""
        await ctx.defer()
        await self._do_toggle(ctx, module=module, enabled=True)

    @commands.hybrid_command(name="disable", description="Disable a bot module (e.g. moderation, adventure)")
    @is_admin()
    async def disable(self, ctx, module: str):
        """Super easy command to disable a module for this server."""
        await ctx.defer()
        await self._do_toggle(ctx, module=module, enabled=False)

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
