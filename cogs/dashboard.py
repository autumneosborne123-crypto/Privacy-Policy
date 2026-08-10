import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from utils.permissions import is_admin
import asyncio

class DashboardBaseView(ui.View):
    def __init__(self, bot, guild, user, original_view=None, timeout=60):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild = guild
        self.user = user
        self.original_view = original_view

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This dashboard is not for you.", ephemeral=True)
            return False
        return True

class ModuleToggleView(DashboardBaseView):
    def __init__(self, bot, guild, user, original_view):
        super().__init__(bot, guild, user, original_view)
        self.add_buttons()

    def add_buttons(self):
        modules = [
            ("Leveling", "Leveling"), ("Music", "Music"), ("Security", "Security"),
            ("Fun", "Fun"), ("Moderation", "Moderation"), ("Games", "Games"),
            ("Economy", "Economy"), ("Adventure", "Adventure"), ("Logging", "Logging"),
            ("Roles", "Roles"), ("Tools", "Tools"), ("Media", "Media")
        ]
        for label, value in modules:
            self.add_item(ModuleButton(label, value))
        
        # Back button
        back_button = ui.Button(label="Back to Main", style=discord.ButtonStyle.secondary, row=4)
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def back_callback(self, interaction: discord.Interaction):
        await self.original_view.update_message(interaction)

class ModuleButton(ui.Button):
    def __init__(self, label, value):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.value = value

    async def callback(self, interaction: discord.Interaction):
        settings = await self.view.bot.db.get_all_guild_settings(interaction.guild.id)
        disabled_raw = settings.get('disabled_cogs') or ""
        disabled = [d.strip().lower() for d in disabled_raw.split(',') if d.strip()]
        
        module_lower = self.value.lower()
        enabled = module_lower in disabled
        
        if enabled:
            disabled.remove(module_lower)
        else:
            disabled.append(module_lower)
        
        new_disabled = ",".join(disabled)
        await self.view.bot.db.set_guild_setting(interaction.guild.id, "disabled_cogs", new_disabled if new_disabled else None)
        
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"✅ Module `{self.value}` has been **{status}**.", ephemeral=True)
        # We could update the view colors here too but keep it simple for now

class LoggingToggleView(DashboardBaseView):
    def __init__(self, bot, guild, user, original_view):
        super().__init__(bot, guild, user, original_view)
        self.add_buttons()

    def add_buttons(self):
        categories = [
            ("Delete", "log_message_delete"), ("Edit", "log_message_edit"),
            ("Join", "log_member_join"), ("Leave", "log_member_leave"),
            ("Ban", "log_member_ban"), ("Unban", "log_member_unban"),
            ("Voice", "log_voice_activity")
        ]
        for label, value in categories:
            self.add_item(LoggingButton(label, value))
        
        back_button = ui.Button(label="Back to Main", style=discord.ButtonStyle.secondary, row=4)
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def back_callback(self, interaction: discord.Interaction):
        await self.original_view.update_message(interaction)

class LoggingButton(ui.Button):
    def __init__(self, label, value):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.value = value

    async def callback(self, interaction: discord.Interaction):
        settings = await self.view.bot.db.get_all_guild_settings(interaction.guild.id)
        current = settings.get(self.value)
        new_status = 0 if current != 0 else 1
        
        await self.view.bot.db.set_guild_setting(interaction.guild.id, self.value, new_status)
        status_text = "enabled" if new_status == 1 else "disabled"
        await interaction.response.send_message(f"✅ Logging for `{self.label}` has been **{status_text}**.", ephemeral=True)

class SecurityToggleView(DashboardBaseView):
    def __init__(self, bot, guild, user, original_view):
        super().__init__(bot, guild, user, original_view)
        self.add_buttons()

    def add_buttons(self):
        tools = [
            ("Anti-Spam", "anti_spam_enabled"), ("Anti-Scam", "anti_scam_enabled"),
            ("Slur Filter", "slur_filter_enabled"), ("Anti-Raid", "anti_raid_enabled"),
            ("Anti-Nuke", "anti_nuke_enabled")
        ]
        for label, value in tools:
            self.add_item(SecurityButton(label, value))
        
        back_button = ui.Button(label="Back to Main", style=discord.ButtonStyle.secondary, row=4)
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def back_callback(self, interaction: discord.Interaction):
        await self.original_view.update_message(interaction)

class SecurityButton(ui.Button):
    def __init__(self, label, value):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.value = value

    async def callback(self, interaction: discord.Interaction):
        settings = await self.view.bot.db.get_all_guild_settings(interaction.guild.id)
        current = settings.get(self.value)
        new_status = 0 if current != 0 else 1
        
        await self.view.bot.db.set_guild_setting(interaction.guild.id, self.value, new_status)
        status_text = "enabled" if new_status == 1 else "disabled"
        await interaction.response.send_message(f"✅ Security tool `{self.label}` has been **{status_text}**.", ephemeral=True)

class DashboardView(ui.View):
    def __init__(self, bot, guild, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.user = user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This dashboard is not for you.", ephemeral=True)
            return False
        return True

    @ui.button(label="Modules", emoji="📁", style=discord.ButtonStyle.primary, row=0)
    async def modules_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = ModuleToggleView(self.bot, self.guild, self.user, self)
        embed = discord.Embed(title="📁 Module Management", description="Toggle bot modules on or off for this server.", color=0x2b2d31)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Logging", emoji="📜", style=discord.ButtonStyle.primary, row=0)
    async def logging_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = LoggingToggleView(self.bot, self.guild, self.user, self)
        embed = discord.Embed(title="📜 Logging Management", description="Toggle specific logging categories.", color=0x2b2d31)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Security", emoji="🛡️", style=discord.ButtonStyle.primary, row=0)
    async def security_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = SecurityToggleView(self.bot, self.guild, self.user, self)
        embed = discord.Embed(title="🛡️ Security Management", description="Toggle anti-raid, anti-spam, and other security tools.", color=0x2b2d31)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Permissions", emoji="⚖️", style=discord.ButtonStyle.secondary, row=1)
    async def perms_btn(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(title="⚖️ Permissions Setup", description="Use the select menus below to set your staff and admin roles.", color=0x2b2d31)
        
        view = DashboardBaseView(self.bot, self.guild, self.user, original_view=self, timeout=180)
        staff_select = ui.RoleSelect(placeholder="Select Staff Role...", min_values=1, max_values=1)
        admin_select = ui.RoleSelect(placeholder="Select Admin Role...", min_values=1, max_values=1)
        
        async def staff_callback(interaction: discord.Interaction):
            role = staff_select.values[0]
            await self.bot.db.set_guild_setting(self.guild.id, "staff_role_id", str(role.id))
            await interaction.response.send_message(f"✅ Staff role set to {role.mention}", ephemeral=True)

        async def admin_callback(interaction: discord.Interaction):
            role = admin_select.values[0]
            await self.bot.db.set_guild_setting(self.guild.id, "admin_role_id", str(role.id))
            await interaction.response.send_message(f"✅ Admin role set to {role.mention}", ephemeral=True)
            
        staff_select.callback = staff_callback
        admin_select.callback = admin_callback
        
        back_button = ui.Button(label="Back to Main", style=discord.ButtonStyle.secondary)
        back_button.callback = self.back_to_main_callback
        
        view.add_item(staff_select)
        view.add_item(admin_select)
        view.add_item(back_button)
        
        await interaction.response.edit_message(embed=embed, view=view)

    async def back_to_main_callback(self, interaction: discord.Interaction):
        await self.update_message(interaction)

    @ui.button(label="Embed Builder", emoji="📝", style=discord.ButtonStyle.success, row=1)
    async def embed_btn(self, interaction: discord.Interaction, button: ui.Button):
        # We can't easily nest views like this without complexity, so we just launch it
        # Actually, we can import it
        from cogs.tools import EmbedBuilderView
        view = EmbedBuilderView(self.bot, interaction.user)
        await interaction.response.send_message("Launching Embed Builder...", embed=view.embed, view=view, ephemeral=True)

    @ui.button(label="Refresh Overview", emoji="🔄", style=discord.ButtonStyle.secondary, row=2)
    async def refresh_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        embed = await self.create_overview_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def create_overview_embed(self):
        settings = await self.bot.db.get_all_guild_settings(self.guild.id)
        
        embed = discord.Embed(title=f"🌸 {self.guild.name} Dashboard", color=0x2b2d31)
        embed.description = "Quick overview of your server's current bot configuration."
        
        # Modules Status
        disabled_raw = settings.get('disabled_cogs') or ""
        disabled = [d.strip().lower() for d in disabled_raw.split(',') if d.strip()]
        mod_status = "✅ Active" if "moderation" not in disabled else "❌ Disabled"
        log_status = "✅ Active" if "logging" not in disabled else "❌ Disabled"
        sec_status = "✅ Active" if "security" not in disabled else "❌ Disabled"
        
        embed.add_field(name="Modules", value=f"**Moderation:** {mod_status}\n**Logging:** {log_status}\n**Security:** {sec_status}", inline=True)
        
        # Security Status
        anti_spam = "✅" if settings.get('anti_spam_enabled') != 0 else "❌"
        anti_raid = "✅" if settings.get('anti_raid_enabled') != 0 else "❌"
        embed.add_field(name="Security Tools", value=f"**Anti-Spam:** {anti_spam}\n**Anti-Raid:** {anti_raid}", inline=True)
        
        # Roles
        staff_role_id = settings.get('staff_role_id')
        admin_role_id = settings.get('admin_role_id')
        
        staff_role = None
        if staff_role_id and str(staff_role_id).isdigit():
            staff_role = self.guild.get_role(int(staff_role_id))
            
        admin_role = None
        if admin_role_id and str(admin_role_id).isdigit():
            admin_role = self.guild.get_role(int(admin_role_id))
        
        embed.add_field(name="Roles", value=f"**Staff:** {staff_role.mention if staff_role else 'None'}\n**Admin:** {admin_role.mention if admin_role else 'None'}", inline=False)
        
        embed.set_footer(text="Use buttons below to navigate and configure.")
        return embed

class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="dashboard", aliases=["dash", "db"], description="Open the server management dashboard")
    @is_admin()
    async def dashboard(self, ctx):
        """Open a simple, clean interactive dashboard to manage server settings."""
        view = DashboardView(self.bot, ctx.guild, ctx.author)
        embed = await view.create_overview_embed()
        await ctx.send(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Dashboard(bot))
