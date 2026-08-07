import discord
from discord.ext import commands

def is_admin():
    async def predicate(ctx):
        if ctx.guild is None:
            return False
        # Check for Administrator permission
        if ctx.author.guild_permissions.administrator:
            return True
        
        # Check for Admin role names (case-insensitive)
        target_roles = ["admin", "admins", "administrator", "administrators"]
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
        
        # Check for role names (case-insensitive)
        target_roles = ["admin", "admins", "administrator", "administrators", "mod", "moderator", "moderators"]
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
        
        # Check for role names (case-insensitive, including user-specified ones)
        target_roles = ["sr.mod", "admin", "head admin", "co-owner", "administrator", "moderator", "mod", "staff"]
        for role in ctx.author.roles:
            if role.name.lower() in target_roles:
                return True
        
        return False
    return commands.check(predicate)
