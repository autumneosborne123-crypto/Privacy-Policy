import discord
from discord.ext import commands

def safe_int(val):
    try:
        if not val: return None
        return int(val)
    except (ValueError, TypeError):
        return None

def is_admin():
    async def predicate(ctx):
        if ctx.guild is None:
            return False
        # Check for Administrator permission
        if ctx.author.guild_permissions.administrator:
            return True
        
        # Check for configured Admin Role ID
        admin_role_id = await ctx.bot.db.get_guild_setting(ctx.guild.id, "admin_role_id")
        rid = safe_int(admin_role_id)
        if rid:
            role = ctx.guild.get_role(rid)
            if role and role in ctx.author.roles:
                return True
        
        # Check for Admin role names (case-insensitive)
        target_roles = ["admin", "admins", "administrator", "administrators", "head admin", "co-owner", "owner", "founder"]
        for role in ctx.author.roles:
            if role.name.lower() in target_roles:
                return True
        
        return False
    return commands.check(predicate)

def is_admin_or_moderator():
    async def predicate(ctx):
        if ctx.guild is None:
            return False
        # Check for Administrator permission
        if ctx.author.guild_permissions.administrator:
            return True
        
        # Check for configured Role IDs
        admin_role_id = await ctx.bot.db.get_guild_setting(ctx.guild.id, "admin_role_id")
        staff_role_id = await ctx.bot.db.get_guild_setting(ctx.guild.id, "staff_role_id")
        
        for raw_rid in [admin_role_id, staff_role_id]:
            rid = safe_int(raw_rid)
            if rid:
                role = ctx.guild.get_role(rid)
                if role and role in ctx.author.roles:
                    return True
        
        # Check for role names (case-insensitive)
        target_roles = [
            "admin", "admins", "administrator", "administrators", "head admin", "co-owner", "owner", "founder",
            "mod", "moderator", "moderators", "sr.mod", "sernior mod", "senior mod", "moderation", "security"
        ]
        for role in ctx.author.roles:
            if role.name.lower() in target_roles:
                return True
        
        return False
    return commands.check(predicate)

def is_staff():
    async def predicate(ctx):
        if ctx.guild is None:
            return False
        # Check for Administrator permission
        if ctx.author.guild_permissions.administrator:
            return True
        
        # Check for configured Role IDs
        admin_role_id = await ctx.bot.db.get_guild_setting(ctx.guild.id, "admin_role_id")
        staff_role_id = await ctx.bot.db.get_guild_setting(ctx.guild.id, "staff_role_id")
        
        for raw_rid in [admin_role_id, staff_role_id]:
            rid = safe_int(raw_rid)
            if rid:
                role = ctx.guild.get_role(rid)
                if role and role in ctx.author.roles:
                    return True
        
        # Check for role names (case-insensitive, including user-specified ones)
        target_roles = [
            "mod", "sr.mod", "sernior mod", "senior mod", "moderation", 
            "admin", "head admin", "co-owner", "owner", "founder",
            "administrator", "moderator", "staff", "security"
        ]
        for role in ctx.author.roles:
            if role.name.lower() in target_roles:
                return True
        
        return False
    return commands.check(predicate)

def is_senior_staff():
    async def predicate(ctx):
        if ctx.guild is None:
            return False
        # Check for Administrator permission
        if ctx.author.guild_permissions.administrator:
            return True
        
        # Check for configured Admin Role ID
        admin_role_id = await ctx.bot.db.get_guild_setting(ctx.guild.id, "admin_role_id")
        rid = safe_int(admin_role_id)
        if rid:
            role = ctx.guild.get_role(rid)
            if role and role in ctx.author.roles:
                return True
        
        # Check for role names (case-insensitive)
        target_roles = ["sernior mod", "senior mod", "admin", "head admin", "co-owner", "owner", "founder"]
        for role in ctx.author.roles:
            if role.name.lower() in target_roles:
                return True
        
        return False
    return commands.check(predicate)
