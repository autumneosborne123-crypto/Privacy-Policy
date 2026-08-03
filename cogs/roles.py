import discord
from discord.ext import commands
from discord import app_commands, ui
import logging

class RRSetupView(ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.channel = None
        self.message_id = None
        self.pairs = []

    @ui.button(label="Select Channel", style=discord.ButtonStyle.primary, row=0)
    async def set_channel(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Not for you.", ephemeral=True)
        
        view = ui.View()
        select = ui.ChannelSelect(placeholder="Select a channel...", channel_types=[discord.ChannelType.text])
        
        async def callback(interaction: discord.Interaction):
            self.channel = select.values[0]
            await interaction.response.edit_message(content=f"✅ Channel set to {self.channel.mention}", view=self)
            
        select.callback = callback
        view.add_item(select)
        await interaction.response.send_message("Select channel:", view=view, ephemeral=True)

    @ui.button(label="Message ID", style=discord.ButtonStyle.secondary, row=0)
    async def set_msg(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Not for you.", ephemeral=True)
        await interaction.response.send_modal(RRMessageModal(self))

    @ui.button(label="Add Emoji-Role Pair", style=discord.ButtonStyle.secondary, row=1)
    async def add_pair(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Not for you.", ephemeral=True)
        await interaction.response.send_modal(RRPairModal(self))

    @ui.button(label="FINISH", style=discord.ButtonStyle.success, row=2)
    async def finish(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Not for you.", ephemeral=True)
        
        if not self.message_id or not self.pairs:
            return await interaction.response.send_message("❌ You must set a message ID and add at least one emoji-role pair.", ephemeral=True)
        
        target_channel = self.channel or interaction.channel
        try:
            msg = await target_channel.fetch_message(int(self.message_id))
            for emoji, role in self.pairs:
                await msg.add_reaction(emoji)
                await self.bot.db.add_reaction_role(interaction.guild.id, self.message_id, emoji, role.id)
            
            await interaction.response.edit_message(content=f"✅ Successfully set up {len(self.pairs)} reaction roles on message `{self.message_id}` in {target_channel.mention}!", view=None)
            await self.bot.log_action(interaction.guild, "🎭 Reaction Roles Setup (Make)", f"Message: {self.message_id}\nPairs: {len(self.pairs)}", moderator=interaction.user)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    async def update_status(self, interaction: discord.Interaction):
        status = f"**Reaction Role Setup**\nChannel: {self.channel.mention if self.channel else 'Current'}\nMessage ID: `{self.message_id or 'Not set'}`\n\n**Pairs:**\n"
        for emoji, role in self.pairs:
            status += f"- {emoji} -> {role.mention}\n"
        await interaction.response.edit_message(content=status, view=self)

class RRMessageModal(ui.Modal, title="Reaction Role Message"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.msg_id = ui.TextInput(label="Message ID", placeholder="Paste the message ID here...", required=True)
        self.add_item(self.msg_id)

    async def on_submit(self, interaction: discord.Interaction):
        self.view.message_id = self.msg_id.value
        await self.view.update_status(interaction)

class RRPairModal(ui.Modal, title="Add Emoji-Role Pair"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.emoji = ui.TextInput(label="Emoji", placeholder="Enter emoji...", required=True)
        self.role_id = ui.TextInput(label="Role ID or Name", placeholder="Enter role ID or exact name...", required=True)
        self.add_item(self.emoji)
        self.add_item(self.role_id)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        role = None
        if self.role_id.value.isdigit():
            role = guild.get_role(int(self.role_id.value))
        else:
            role = discord.utils.get(guild.roles, name=self.role_id.value)
        
        if not role:
            return await interaction.response.send_message(f"❌ Role `{self.role_id.value}` not found.", ephemeral=True)
        
        if role >= guild.me.top_role:
            return await interaction.response.send_message("❌ I cannot manage this role (too high).", ephemeral=True)
            
        self.view.pairs.append((self.emoji.value, role))
        await self.view.update_status(interaction)

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not ctx.guild:
            return True
        
        roles_channel_id = await self.bot.db.get_guild_setting(ctx.guild.id, "roles_channel_id")
        if roles_channel_id and ctx.channel.id != int(roles_channel_id):
            # Allow admins to bypass
            if ctx.author.guild_permissions.administrator:
                return True
            
            roles_channel = self.bot.get_channel(int(roles_channel_id))
            channel_mention = roles_channel.mention if roles_channel else f"<#{roles_channel_id}>"
            await ctx.send(f"❌ This command can only be used in {channel_mention}.")
            return False
        return True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return True
        
        roles_channel_id = await self.bot.db.get_guild_setting(interaction.guild.id, "roles_channel_id")
        if roles_channel_id and interaction.channel.id != int(roles_channel_id):
            if interaction.user.guild_permissions.administrator:
                return True
            
            roles_channel = self.bot.get_channel(int(roles_channel_id))
            channel_mention = roles_channel.mention if roles_channel else f"<#{roles_channel_id}>"
            await interaction.response.send_message(f"❌ This command can only be used in {channel_mention}.", ephemeral=True)
            return False
        return True

    @commands.command(name="roles", description="List all roles in the server")
    async def roles_list(self, ctx):
        """List all roles in the server."""
        roles = sorted(ctx.guild.roles, key=lambda x: x.position, reverse=True)
        role_mentions = [f"{role.mention} ({role.id})" for role in roles if not role.is_default()]
        
        embed = discord.Embed(title=f"Roles in {ctx.guild.name}", color=0x2b2d31)
        
        if not role_mentions:
            return await ctx.send("No roles found (other than @everyone).")

        # Split into chunks if too many roles
        chunks = [role_mentions[i:i + 15] for i in range(0, len(role_mentions), 15)]
        
        for i, chunk in enumerate(chunks):
            embed.add_field(name=f"Roles (Part {i+1})", value="\n".join(chunk), inline=False)
            
        await ctx.send(embed=embed)

    @commands.group(name="role", description="Role management commands")
    @commands.has_permissions(manage_roles=True)
    async def role_group(self, ctx):
        """Role management commands."""
        await ctx.send_help(ctx.command)

    @role_group.command(name="add", description="Add a role to a member")
    @commands.has_permissions(manage_roles=True)
    async def role_add(self, ctx, member: discord.Member, role: discord.Role):
        """Add a role to a member."""
        if role >= ctx.guild.me.top_role:
            return await ctx.send("❌ I cannot add this role because it is higher than or equal to my highest role.")
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send("❌ You cannot add a role higher than or equal to your own top role.")
        
        await member.add_roles(role)
        await ctx.send(f"✅ Added {role.name} to {member.mention}")
        await self.bot.log_action(ctx.guild, "🎭 Role Added", f"Role: {role.mention}\nMember: {member.mention}", moderator=ctx.author)

    @role_group.command(name="remove", description="Remove a role from a member")
    @commands.has_permissions(manage_roles=True)
    async def role_remove(self, ctx, member: discord.Member, role: discord.Role):
        """Remove a role from a member."""
        if role >= ctx.guild.me.top_role:
            return await ctx.send("❌ I cannot remove this role because it is higher than or equal to my highest role.")
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send("❌ You cannot remove a role higher than or equal to your own top role.")
        
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed {role.name} from {member.mention}")
        await self.bot.log_action(ctx.guild, "🎭 Role Removed", f"Role: {role.mention}\nMember: {member.mention}", moderator=ctx.author)

    @role_group.command(name="info", description="Get information about a role")
    async def role_info(self, ctx, role: discord.Role):
        """Get information about a role."""
        embed = discord.Embed(title=f"Role Info: {role.name}", color=role.color)
        embed.add_field(name="ID", value=role.id, inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Mentionable", value=role.mentionable, inline=True)
        embed.add_field(name="Hoisted", value=role.hoist, inline=True)
        embed.add_field(name="Position", value=role.position, inline=True)
        embed.add_field(name="Members", value=len(role.members), inline=True)
        embed.add_field(name="Created At", value=discord.utils.format_dt(role.created_at), inline=False)
        
        perms = [p[0].replace("_", " ").title() for p in role.permissions if p[1]]
        if perms:
            embed.add_field(name="Permissions", value=", ".join(perms[:20]) + ("..." if len(perms) > 20 else ""), inline=False)
        
        await ctx.send(embed=embed)

    @commands.group(name="reactionrole", aliases=["rr"], invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    async def reactionrole(self, ctx):
        """Reaction Role management commands."""
        await ctx.send_help(ctx.command)

    @reactionrole.command(name="make", description="Interactive professional reaction role setup")
    @commands.has_permissions(manage_roles=True)
    async def rr_make(self, ctx):
        """Interactive professional reaction role setup."""
        view = RRSetupView(self.bot, ctx.author)
        await ctx.send("Starting interactive reaction role setup...", view=view)

    @reactionrole.command(name="remove", description="Remove a reaction role from a message")
    @commands.has_permissions(manage_roles=True)
    async def rr_remove(self, ctx, message_id: str, emoji: str):
        """Remove a reaction role from a message."""
        await self.bot.db.remove_reaction_role(ctx.guild.id, message_id, emoji)
        await ctx.send(f"✅ Reaction role removed for {emoji} on message {message_id}")
        await self.bot.log_action(ctx.guild, "🎭 Reaction Role Removed", f"Emoji: {emoji}\nMessage ID: {message_id}", moderator=ctx.author)

    @reactionrole.command(name="list", description="List all reaction roles in this server")
    @commands.has_permissions(manage_roles=True)
    async def rr_list(self, ctx):
        """List all reaction roles in this server."""
        roles = await self.bot.db.get_all_reaction_roles(ctx.guild.id)
        if not roles:
            return await ctx.send("No reaction roles configured for this server.")
        
        embed = discord.Embed(title="🎭 Reaction Roles", color=0x2b2d31)
        description = ""
        for msg_id, emoji, role_id in roles:
            role = ctx.guild.get_role(int(role_id))
            role_mention = role.mention if role else f"Unknown Role ({role_id})"
            description += f"**Msg:** `{msg_id}` | {emoji} -> {role_mention}\n"
        
        embed.description = description
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        
        # Get role ID from DB. We store emoji as string.
        # payload.emoji is a PartialEmoji. str(payload.emoji) returns the string representation.
        emoji_str = str(payload.emoji)
        role_id = await self.bot.db.get_reaction_role(payload.guild_id, payload.message_id, emoji_str)
        
        if role_id:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild: return
            
            role = guild.get_role(role_id)
            member = guild.get_member(payload.user_id)
            if role and member:
                try:
                    await member.add_roles(role, reason="Reaction Role")
                except Exception as e:
                    logging.error(f"Failed to add reaction role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        
        emoji_str = str(payload.emoji)
        role_id = await self.bot.db.get_reaction_role(payload.guild_id, payload.message_id, emoji_str)
        
        if role_id:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild: return
            
            role = guild.get_role(role_id)
            member = guild.get_member(payload.user_id)
            if role and member:
                try:
                    await member.remove_roles(role, reason="Reaction Role")
                except Exception as e:
                    logging.error(f"Failed to remove reaction role: {e}")

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        # Cleanup reaction roles if the message is deleted
        await self.bot.db.remove_reaction_role(payload.guild_id, str(payload.message_id), None)
        # Note: we might need a better DB method to remove ALL reaction roles for a message.
        # Currently remove_reaction_role requires emoji too if not modified.

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
        for msg_id in payload.message_ids:
            await self.bot.db.remove_reaction_role(payload.guild_id, str(msg_id), None)

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
