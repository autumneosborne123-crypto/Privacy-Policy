import discord
from discord.ext import commands
from discord import app_commands, ui
import json
import logging

class EmbedBuilderView(ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.embed = discord.Embed(title="New Embed", description="Use the buttons below to customize this embed.", color=0x2b2d31)
        self.target_channel = None

    @ui.button(label="Title & Description", style=discord.ButtonStyle.primary, row=0)
    async def set_main(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("This menu is not for you.", ephemeral=True)
        await interaction.response.send_modal(EmbedMainModal(self))

    @ui.button(label="Author", style=discord.ButtonStyle.secondary, row=0)
    async def set_author(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("This menu is not for you.", ephemeral=True)
        await interaction.response.send_modal(EmbedAuthorModal(self))

    @ui.button(label="Footer", style=discord.ButtonStyle.secondary, row=0)
    async def set_footer(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("This menu is not for you.", ephemeral=True)
        await interaction.response.send_modal(EmbedFooterModal(self))

    @ui.button(label="Images", style=discord.ButtonStyle.secondary, row=1)
    async def set_images(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("This menu is not for you.", ephemeral=True)
        await interaction.response.send_modal(EmbedImageModal(self))

    @ui.button(label="Color", style=discord.ButtonStyle.secondary, row=1)
    async def set_color(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("This menu is not for you.", ephemeral=True)
        await interaction.response.send_modal(EmbedColorModal(self))

    @ui.button(label="Select Channel", style=discord.ButtonStyle.success, row=2)
    async def set_channel(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("This menu is not for you.", ephemeral=True)
        
        view = ui.View()
        select = ui.ChannelSelect(placeholder="Select a channel to send this embed to...", channel_types=[discord.ChannelType.text])
        
        async def select_callback(interaction: discord.Interaction):
            self.target_channel = select.values[0]
            await interaction.response.edit_message(content=f"✅ Target channel set to {self.target_channel.mention}", view=self)
            
        select.callback = select_callback
        view.add_item(select)
        await interaction.response.send_message("Select a channel:", view=view, ephemeral=True)

    @ui.button(label="SEND", style=discord.ButtonStyle.danger, row=2)
    async def send_embed(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("This menu is not for you.", ephemeral=True)
        
        channel = self.target_channel or interaction.channel
        try:
            await channel.send(embed=self.embed)
            await interaction.response.edit_message(content=f"✅ Embed sent to {channel.mention}!", view=None)
            await self.bot.log_action(interaction.guild, "📝 Embed Sent (Pro Builder)", f"Channel: {channel.mention}", moderator=interaction.user)
            self.stop()
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to send embed: {e}", ephemeral=True)

    async def update_preview(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.embed, view=self)

class EmbedMainModal(ui.Modal, title="Embed Title & Description"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.e_title = ui.TextInput(label="Title", default=view.embed.title, required=False)
        self.e_desc = ui.TextInput(label="Description", style=discord.TextStyle.paragraph, default=view.embed.description, required=True)
        self.add_item(self.e_title)
        self.add_item(self.e_desc)

    async def on_submit(self, interaction: discord.Interaction):
        self.view.embed.title = self.e_title.value or None
        self.view.embed.description = self.e_desc.value
        await self.view.update_preview(interaction)

class EmbedAuthorModal(ui.Modal, title="Embed Author"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.name = ui.TextInput(label="Name", default=view.embed.author.name if view.embed.author else "", required=False)
        self.icon = ui.TextInput(label="Icon URL", default=view.embed.author.icon_url if view.embed.author else "", required=False)
        self.add_item(self.name)
        self.add_item(self.icon)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.name.value:
            self.view.embed.set_author(name=None)
        else:
            self.view.embed.set_author(name=self.name.value, icon_url=self.icon.value or None)
        await self.view.update_preview(interaction)

class EmbedFooterModal(ui.Modal, title="Embed Footer"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.text = ui.TextInput(label="Text", default=view.embed.footer.text if view.embed.footer else "", required=False)
        self.icon = ui.TextInput(label="Icon URL", default=view.embed.footer.icon_url if view.embed.footer else "", required=False)
        self.add_item(self.text)
        self.add_item(self.icon)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.text.value:
            self.view.embed.set_footer(text=None)
        else:
            self.view.embed.set_footer(text=self.text.value, icon_url=self.icon.value or None)
        await self.view.update_preview(interaction)

class EmbedImageModal(ui.Modal, title="Embed Images"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.thumbnail = ui.TextInput(label="Thumbnail URL", default=view.embed.thumbnail.url if view.embed.thumbnail else "", required=False)
        self.image = ui.TextInput(label="Image URL", default=view.embed.image.url if view.embed.image else "", required=False)
        self.add_item(self.thumbnail)
        self.add_item(self.image)

    async def on_submit(self, interaction: discord.Interaction):
        self.view.embed.set_thumbnail(url=self.thumbnail.value or None)
        self.view.embed.set_image(url=self.image.value or None)
        await self.view.update_preview(interaction)

class EmbedColorModal(ui.Modal, title="Embed Color"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.color = ui.TextInput(label="Hex Color", placeholder="#2b2d31", default=str(view.embed.color) if view.embed.color else "", required=True)
        self.add_item(self.color)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            color_val = int(self.color.value.lstrip('#'), 16)
            self.view.embed.color = color_val
            await self.view.update_preview(interaction)
        except:
            await interaction.response.send_message("❌ Invalid hex color.", ephemeral=True)

class Tools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not ctx.guild:
            return True
        
        embed_channel_id = await self.bot.db.get_guild_setting(ctx.guild.id, "embed_channel_id")
        if embed_channel_id and ctx.channel.id != int(embed_channel_id):
            if ctx.author.guild_permissions.administrator:
                return True
            
            embed_channel = self.bot.get_channel(int(embed_channel_id))
            channel_mention = embed_channel.mention if embed_channel else f"<#{embed_channel_id}>"
            await ctx.send(f"❌ This command can only be used in {channel_mention}.", ephemeral=True)
            return False
        return True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return True
        
        embed_channel_id = await self.bot.db.get_guild_setting(interaction.guild.id, "embed_channel_id")
        if embed_channel_id and interaction.channel.id != int(embed_channel_id):
            if interaction.user.guild_permissions.administrator:
                return True
            
            embed_channel = self.bot.get_channel(int(embed_channel_id))
            channel_mention = embed_channel.mention if embed_channel else f"<#{embed_channel_id}>"
            await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}.", ephemeral=True)
            return False
        return True

    @commands.hybrid_group(name="embed", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    @app_commands.default_permissions(manage_messages=True)
    async def embed(self, ctx):
        """Embed creation and management."""
        await ctx.send_help(ctx.command)

    @embed.command(name="create", description="Create a simple embed")
    @commands.has_permissions(manage_messages=True)
    async def embed_create(self, ctx, title: str, *, description: str):
        """Create a simple embed.
        Usage: .embed create "My Title" My description here...
        """
        embed = discord.Embed(title=title, description=description, color=0x2b2d31)
        await ctx.send(embed=embed)
        await self.bot.log_action(ctx.guild, "📝 Embed Created", f"Title: {title}\nChannel: {ctx.channel.mention}", moderator=ctx.author)

    @embed.command(name="json", description="Create an embed from JSON data")
    @commands.has_permissions(manage_messages=True)
    async def embed_json(self, ctx, *, data: str):
        """Create an embed from JSON data.
        Example: .embed json {"title": "Hello", "description": "World", "color": 16711680}
        """
        try:
            embed_data = json.loads(data)
            embed = discord.Embed.from_dict(embed_data)
            await ctx.send(embed=embed)
            await self.bot.log_action(ctx.guild, "📝 Embed Created (JSON)", f"Channel: {ctx.channel.mention}", moderator=ctx.author)
        except json.JSONDecodeError:
            await ctx.send("❌ Invalid JSON format.")
        except Exception as e:
            await ctx.send(f"❌ Error creating embed: {e}")

    @embed.command(name="edit", description="Edit an existing embed sent by the bot using JSON")
    @commands.has_permissions(manage_messages=True)
    async def embed_edit(self, ctx, message_id: str, *, data: str):
        """Edit an existing embed sent by the bot using JSON."""
        try:
            msg = await ctx.channel.fetch_message(message_id)
            if msg.author != self.bot.user:
                return await ctx.send("❌ I can only edit my own messages.")
            
            embed_data = json.loads(data)
            embed = discord.Embed.from_dict(embed_data)
            await msg.edit(embed=embed)
            await ctx.send("✅ Embed edited.")
            await self.bot.log_action(ctx.guild, "📝 Embed Edited", f"Message ID: {message_id}\nChannel: {ctx.channel.mention}", moderator=ctx.author)
        except json.JSONDecodeError:
            await ctx.send("❌ Invalid JSON format.")
        except Exception as e:
            await ctx.send(f"❌ Error editing embed: {e}")

    @embed.command(name="say", aliases=["message"], description="Send an embed to a specific channel using JSON")
    @commands.has_permissions(manage_messages=True)
    async def embed_say(self, ctx, channel: discord.TextChannel, *, data: str):
        """Send an embed to a specific channel using JSON."""
        try:
            embed_data = json.loads(data)
            embed = discord.Embed.from_dict(embed_data)
            await channel.send(embed=embed)
            await ctx.send(f"✅ Embed sent to {channel.mention}")
            await self.bot.log_action(ctx.guild, "📝 Embed Sent", f"Channel: {channel.mention}", moderator=ctx.author)
        except json.JSONDecodeError:
            await ctx.send("❌ Invalid JSON format.")
        except Exception as e:
            await ctx.send(f"❌ Error sending embed: {e}")

    @app_commands.command(name="builder", description="Open an interactive professional embed builder")
    @app_commands.default_permissions(manage_messages=True)
    async def embed_builder(self, interaction: discord.Interaction):
        """Open an interactive professional embed builder."""
        view = EmbedBuilderView(self.bot, interaction.user)
        await interaction.response.send_message("Building your professional embed...", embed=view.embed, view=view, ephemeral=True)

class EmbedBuilderModal(ui.Modal, title="Interactive Embed Builder"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    embed_title = ui.TextInput(label="Title", placeholder="Enter embed title...", required=False)
    description = ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Enter embed description...", required=True)
    color = ui.TextInput(label="Color (Hex)", placeholder="e.g. #2b2d31", required=False)
    thumbnail = ui.TextInput(label="Thumbnail URL", placeholder="https://...", required=False)
    image = ui.TextInput(label="Image URL", placeholder="https://...", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        color_val = 0x2b2d31
        if self.color.value:
            try:
                color_val = int(self.color.value.lstrip('#'), 16)
            except:
                pass
        
        embed = discord.Embed(title=self.embed_title.value or None, description=self.description.value, color=color_val)
        if self.thumbnail.value:
            embed.set_thumbnail(url=self.thumbnail.value)
        if self.image.value:
            embed.set_image(url=self.image.value)
        
        await interaction.response.send_message("Here is your embed!", embed=embed)
        await self.bot.log_action(interaction.guild, "📝 Embed Created (Builder)", f"Channel: {interaction.channel.mention}", moderator=interaction.user)

async def setup(bot):
    await bot.add_cog(Tools(bot))
