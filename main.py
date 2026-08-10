import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import asyncio
from utils.database import Database
from utils.config import Config
from static_ffmpeg import add_paths

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CONFIG_FILE = "config.json"
DB_FILE = os.getenv('DATABASE_FILE', 'levels.db')

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
    handlers=[logging.FileHandler('discord.log', encoding='utf-8', mode='a'), logging.StreamHandler()]
)

class DiscordLogHandler(logging.Handler):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    def emit(self, record):
        if not self.bot.is_ready():
            return

        # Skip spammy or rate-limit logs to avoid recursion
        msg = record.getMessage()
        skip_terms = [
            "Scraped", "search queries", "Successfully scraped", "rate limited", 
            "429 Too Many Requests", "You are being blocked", "rate-limits",
            "Unknown interaction", "NotFound: 404 Not Found",
            "Failed to send log to channel"
        ]
        if any(term in msg for term in skip_terms):
            return
        
        # Only WARNING and above for technical logs in Discord to avoid spam
        if record.levelno < logging.WARNING:
            return

        log_entry = self.format(record)
        asyncio.run_coroutine_threadsafe(self.send_to_discord(log_entry, record.levelno), self.bot.loop)

    async def send_to_discord(self, message, level):
        color = 0x2b2d31
        if level >= logging.CRITICAL:
            color = 0xff0000
        elif level >= logging.ERROR:
            color = 0xff4b4b
        elif level >= logging.WARNING:
            color = 0xffa500
            
        log_channels = []
        
        # 1. Collect per-guild log channels
        for guild in self.bot.guilds:
            channel = await self.bot.get_log_channel(guild)
            if channel and channel not in log_channels:
                log_channels.append(channel)
        
        # 2. Add master log channel from config
        master_log_id = self.bot.config.get("master_log_channel_id")
        if master_log_id:
            master_channel = self.bot.get_channel(int(master_log_id))
            if not master_channel:
                try:
                    master_channel = await self.bot.fetch_channel(int(master_log_id))
                except:
                    pass
            if master_channel and master_channel not in log_channels:
                # Permission check for master channel
                try:
                    permissions = master_channel.permissions_for(master_channel.guild.me)
                    if permissions.view_channel and permissions.send_messages and permissions.embed_links:
                        log_channels.append(master_channel)
                except:
                    pass

        if not log_channels:
            return

        embed = discord.Embed(title="🤖 Bot Technical Log", description=f"```\n{message[:1900]}\n```", color=color, timestamp=discord.utils.utcnow())

        for channel in log_channels:
            # Permission check for technical logs
            permissions = channel.permissions_for(channel.guild.me)
            if not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
                continue
                    
            try:
                await channel.send(embed=embed)
            except:
                pass

class HelpSelect(discord.ui.Select):
    def __init__(self, bot, prefix):
        self.bot = bot
        self.prefix = prefix
        options = [
            discord.SelectOption(label="Home", emoji="🏠", description="Back to the main menu")
        ]
        
        # Sort cogs by name
        sorted_cogs = sorted(bot.cogs.items())
        for cog_name, cog in sorted_cogs:
            if cog_name in ["System", "Config"]:
                emoji = "🛠️"
            elif cog_name == "Leveling": emoji = "📈"
            elif cog_name == "Music": emoji = "🎵"
            elif cog_name == "Security": emoji = "🛡️"
            elif cog_name == "Fun": emoji = "✨"
            elif cog_name == "Moderation": emoji = "⚖️"
            elif cog_name == "Games": emoji = "🎮"
            elif cog_name == "Media": emoji = "🖼️"
            elif cog_name == "Economy": emoji = "💰"
            elif cog_name == "Adventure": emoji = "🌸"
            elif cog_name == "Achievements": emoji = "🏆"
            elif cog_name == "Logging": emoji = "📜"
            elif cog_name == "Roles": emoji = "🎭"
            elif cog_name == "Tools": emoji = "🛠️"
            elif cog_name == "Stories": emoji = "📖"
            else: emoji = "📁"
            
            # Count non-hidden commands
            visible_cmds = [c for c in cog.get_commands() if not c.hidden]
            if visible_cmds:
                options.append(discord.SelectOption(label=cog_name, emoji=emoji, description=f"{len(visible_cmds)} commands"))
        
        super().__init__(placeholder="Select a category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "Home":
            embed = self.view.create_home_embed()
            return await interaction.response.edit_message(embed=embed, view=self.view)
            
        cog = self.bot.get_cog(self.values[0])
        embed = discord.Embed(title=f"{self.values[0]} Commands", color=0x2b2d31)
        
        # Use KDoc/description if available for the cog
        embed.description = cog.description or f"Here are the commands for the **{self.values[0]}** category:"
        
        cmds = []
        for cmd in sorted(cog.get_commands(), key=lambda x: x.name):
            if not cmd.hidden:
                if isinstance(cmd, commands.Group):
                    sub_cmds = ", ".join([f"`{c.name}`" for c in cmd.commands])
                    cmds.append(f"**{self.prefix}{cmd.name}** - {cmd.short_doc or 'No description'}\n└ *Subcommands: {sub_cmds}*")
                else:
                    cmds.append(f"**{self.prefix}{cmd.name}** - {cmd.short_doc or 'No description'}")
        
        if not cmds:
            embed.description = "No visible commands in this category."
        else:
            embed.add_field(name="List", value="\n".join(cmds[:15]), inline=False)
            if len(cmds) > 15:
                embed.add_field(name="Continued", value="\n".join(cmds[15:30]), inline=False)
        
        embed.set_footer(text=f"Use {self.prefix}help <command> for detailed info!")
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(discord.ui.View):
    def __init__(self, bot, prefix):
        super().__init__(timeout=60)
        self.bot = bot
        self.prefix = prefix
        self.add_item(HelpSelect(bot, prefix))
        
    def create_home_embed(self):
        embed = discord.Embed(title="🌸 flowerbot.gg Help Menu", color=0x2b2d31)
        embed.description = (
            "Welcome to the **flowerbot.gg** help menu! Use the selection menu below to browse commands by category.\n\n"
            "**Links:** [Privacy](https://github.com/autumneosborne123-crypto/Privacy-Policy/blob/main/PRIVACY_POLICY.md) | [Terms](https://github.com/autumneosborne123-crypto/Privacy-Policy/blob/main/TERMS_OF_SERVICE.md) | [Support](https://discord.gg/mXtvjGpQmM)\n\n"
            "💡 *Tip: Use `.help <command>` for specific command details.*"
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url if self.bot.user.display_avatar else None)
        
        # Show some stats
        total_commands = len([c for c in self.bot.commands if not c.hidden])
        embed.add_field(name="Stats", value=f"**Total Commands:** {total_commands}\n**Categories:** {len(self.bot.cogs)}", inline=True)
        embed.add_field(name="Prefix", value=f"Current prefix: `{self.prefix}`", inline=True)
        
        return embed

class FlowerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        super().__init__(command_prefix=['.', 's?'], intents=intents, help_command=None)
        
        self.db = Database(DB_FILE)
        self.config = Config(CONFIG_FILE)
        self.whitelisted_bots = [422087909634736160, 1373666241033535558] # Top.gg bot & PFP Bot
        self.add_check(self.global_cog_check)

    async def global_cog_check(self, ctx):
        if not ctx.guild: return True
        if not ctx.cog: return True
        
        # System and Config cogs should always be accessible
        if ctx.cog.qualified_name in ["System", "Config"]: return True
        
        settings = await self.db.get_all_guild_settings(ctx.guild.id)
        disabled_raw = settings.get('disabled_cogs')
        if not disabled_raw: return True
        
        disabled = [d.strip().lower() for d in disabled_raw.split(',')]
        cog_name = ctx.cog.qualified_name.lower()
        cog_module = ctx.cog.__module__.lower()
        
        # Check by qualified name or module name (e.g., 'Adventure' or 'cogs.adventure')
        if cog_name in disabled or cog_module in disabled or cog_module.split('.')[-1] in disabled:
            try: await ctx.send(f"❌ The `{ctx.cog.qualified_name}` module is disabled in this server.", ephemeral=True)
            except: pass
            return False
        return True

    async def setup_hook(self):
        await self.db.init()
        
        # Load Cogs
        cogs = ['cogs.leveling', 'cogs.music', 'cogs.security', 'cogs.fun', 'cogs.moderation', 'cogs.config', 'cogs.system', 'cogs.games', 'cogs.media', 'cogs.economy', 'cogs.adventure', 'cogs.achievements', 'cogs.logging', 'cogs.roles', 'cogs.tools', 'cogs.premium', 'cogs.afk', 'cogs.dashboard']
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logging.info(f"Loaded extension: {cog}")
            except Exception as e:
                logging.error(f"Failed to load extension {cog}: {e}")

        await self.tree.sync()
        logging.info(f"Synced slash commands for {self.user}")

    async def update_balance(self, user_id, amount):
        await self.db.update_balance(user_id, amount)
        new_balance = await self.db.get_balance(user_id)
        self.dispatch("balance_change", user_id, new_balance)
        return new_balance

    async def get_log_channel(self, guild):
        if not guild: return None
        log_channel_id = await self.db.get_log_channel(guild.id)
        channel = None
        if log_channel_id:
            channel = self.get_channel(int(log_channel_id))
            if not channel:
                try:
                    channel = await self.fetch_channel(int(log_channel_id))
                except:
                    pass
        
        # Verify permissions if we found a channel
        if channel:
            try:
                permissions = channel.permissions_for(guild.me)
                if permissions.view_channel and permissions.send_messages and permissions.embed_links:
                    return channel
            except:
                pass
        
        # Fallback to "flower-log" or "flower-logs" or "flower logs" channel by name
        for name in ["flower-log", "flower-logs", "flower logs"]:
            channel = discord.utils.get(guild.text_channels, name=name)
            if channel:
                try:
                    permissions = channel.permissions_for(guild.me)
                    if permissions.view_channel and permissions.send_messages and permissions.embed_links:
                        return channel
                except:
                    pass
        return None

    async def log_action(self, guild, title, description, color=0x2b2d31, moderator=None, user=None, guild_only=False, master_only=False):
        log_channels = []
        
        # 1. Get guild-specific log channel
        if not master_only:
            guild_channel = await self.get_log_channel(guild)
            if guild_channel:
                log_channels.append(guild_channel)
            
        # 2. Get master log channel from config
        if not guild_only:
            master_log_id = self.config.get("master_log_channel_id")
            if master_log_id:
                master_channel = self.get_channel(int(master_log_id))
                if not master_channel:
                    try:
                        master_channel = await self.fetch_channel(int(master_log_id))
                    except:
                        pass
                if master_channel and master_channel not in log_channels:
                    # Permission check for master channel
                    try:
                        permissions = master_channel.permissions_for(master_channel.guild.me)
                        if permissions.view_channel and permissions.send_messages and permissions.embed_links:
                            log_channels.append(master_channel)
                    except:
                        pass

        if not log_channels: return

        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        if moderator:
            embed.add_field(name="Moderator", value=f"{moderator} ({moderator.id})", inline=True)
        if user:
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
            if hasattr(user, "display_avatar"):
                embed.set_thumbnail(url=user.display_avatar.url)
        
        for channel in log_channels:
            # Check for view, send and embed permissions to avoid 403 errors
            permissions = channel.permissions_for(channel.guild.me)
            if not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
                continue
                
            try:
                await channel.send(embed=embed)
            except Exception as e:
                logging.error(f"Failed to send log to channel {channel.id}: {e}")

    async def on_ready(self):
        if not hasattr(self, 'start_time'):
            self.start_time = discord.utils.utcnow()
        await self.change_presence(activity=discord.Game(name=".help | Moderating & Playing"))
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')

    async def on_guild_join(self, guild):
        logging.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        
        # Initialize default settings
        # Security defaults (1 = enabled) are already handled by None != 0 logic in cogs,
        # but we can explicitly set them if we want to be sure.
        await self.db.set_guild_setting(guild.id, "anti_spam_enabled", 1)
        await self.db.set_guild_setting(guild.id, "anti_scam_enabled", 1)
        await self.db.set_guild_setting(guild.id, "anti_raid_enabled", 1)
        await self.db.set_guild_setting(guild.id, "anti_nuke_enabled", 1)
        
        # Send welcome message to system channel or owner
        embed = discord.Embed(title="🌸 Thank you for inviting flowerbot.gg!", color=0x2b2d31)
        embed.description = (
            f"Hello! I'm **flowerbot.gg**, a multi-purpose bot designed to help you moderate, "
            f"protect, and entertain your community in **{guild.name}**.\n\n"
            "🚀 **Quick Start:**\n"
            "1. Use `.dashboard` to open the interactive management menu.\n"
            "2. Use `.settings` to view your current configuration.\n"
            "3. Use `.help` to see all available commands.\n"
            "4. Use `.diagnose` to check if I have all required permissions.\n\n"
            "🛡️ **Security:** All protection tools (Anti-Spam, Anti-Raid, etc.) are **Enabled** by default."
        )
        embed.add_field(name="Support", value="[Join Support Server](https://discord.gg/mXtvjGpQmM)")
        embed.set_thumbnail(url=self.user.display_avatar.url)
        
        target = guild.system_channel
        if not target or not target.permissions_for(guild.me).send_messages:
            # Fallback to the first channel we can talk in
            target = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
            
        if target:
            try: await target.send(embed=embed)
            except: pass
            
        # Also notify owner if possible
        try:
            await guild.owner.send(embed=embed)
        except:
            pass

    @commands.hybrid_command(name="help", description="Show the help menu")
    async def help(self, ctx: commands.Context, command_name: str = None):
        prefix = ctx.prefix if ctx.prefix else "."
        if command_name:
            cmd = self.get_command(command_name.lower())
            if not cmd:
                return await ctx.send(f"❌ Command `{command_name}` not found.", ephemeral=True)
            
            embed = discord.Embed(title=f"📖 Help: {prefix}{cmd.name}", color=0x2b2d31)
            embed.description = cmd.description or "No description available."
            
            usage = f"{prefix}{cmd.name}"
            if hasattr(cmd, 'clean_params') and cmd.clean_params:
                for param_name, param in cmd.clean_params.items():
                    if param.default == param.empty: usage += f" <{param_name}>"
                    else: usage += f" [{param_name}]"
            
            embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join([f"`{prefix}{a}`" for a in cmd.aliases]), inline=False)
            
            return await ctx.send(embed=embed, ephemeral=True)

        view = HelpView(self, prefix)
        embed = view.create_home_embed()
        await ctx.send(embed=embed, view=view, ephemeral=True)

    async def on_command_error(self, ctx, error):
        embed = discord.Embed(color=0xff4b4b) # Red for errors
        
        if isinstance(error, commands.MissingPermissions):
            embed.title = "❌ Missing Permissions"
            embed.description = f"You need the following permissions to use this command: {', '.join(error.missing_permissions)}"
            await ctx.send(embed=embed, ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed.title = "❌ Missing Argument"
            embed.description = f"You are missing a required argument: `{error.param.name}`\n\n**Usage:** `.help {ctx.command.name}`"
            await ctx.send(embed=embed, ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            embed.title = "⏳ Cooldown"
            embed.description = f"This command is on cooldown. Please try again in **{error.retry_after:.1f}s**."
            await ctx.send(embed=embed, ephemeral=True)
        elif isinstance(error, commands.CheckFailure):
            embed.title = "❌ Access Denied"
            embed.description = "You do not have permission to use this command or it is disabled in this server."
            await ctx.send(embed=embed, ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            embed.title = "❌ Bot Missing Permissions"
            embed.description = f"I need the following permissions to perform this action: {', '.join(error.missing_permissions)}"
            await ctx.send(embed=embed, ephemeral=True)
        elif isinstance(error, commands.BadArgument):
            embed.title = "❌ Invalid Argument"
            embed.description = f"Please check your input and try again. Error: `{error}`"
            await ctx.send(embed=embed, ephemeral=True)
        elif isinstance(error, commands.CommandNotFound):
            pass
        else:
            logging.error(f"Unhandled error: {error}")
            embed.title = "❌ Unhandled Error"
            embed.description = f"An unexpected error occurred: `{error}`"
            try: await ctx.send(embed=embed, ephemeral=True)
            except: pass

def run_bot():
    bot = FlowerBot()
    
    # Add Discord Logging Handler
    discord_handler = DiscordLogHandler(bot)
    discord_handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s: %(message)s'))
    logging.getLogger().addHandler(discord_handler)
    
    add_paths()
    bot.run(TOKEN)

if __name__ == "__main__":
    run_bot()
