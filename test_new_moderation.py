import asyncio
import os
import discord
from utils.database import Database
from cogs.moderation import Moderation
from utils.permissions import is_staff
from datetime import datetime

class MockPermissions:
    def __init__(self, administrator=False):
        self.administrator = administrator

class MockRole:
    def __init__(self, name):
        self.name = name
        self.mention = f"@{name}"

class MockMember:
    def __init__(self, id, name, roles=None, administrator=False):
        self.id = id
        self.name = name
        self.mention = f"<@{id}>"
        self.roles = roles or []
        self.guild_permissions = MockPermissions(administrator=administrator)
        self.banned = False
        self.ban_reason = None
        self.display_avatar = type('Avatar', (), {'url': 'http://example.com/avatar.png'})

    async def ban(self, reason=None):
        self.banned = True
        self.ban_reason = reason

    def __str__(self):
        return self.name

class MockUser:
    def __init__(self, id, name):
        self.id = id
        self.name = name
    def __str__(self):
        return self.name

class MockAuditLogEntry:
    def __init__(self, user, target, action, reason=None):
        self.user = user
        self.target = target
        self.action = action
        self.reason = reason
        self.created_at = datetime.utcnow()

class MockGuild:
    def __init__(self, id, name="Test Guild"):
        self.id = id
        self.name = name
        self.me = MockMember(999, "Bot")
        self.unbanned_user = None
        self.unban_reason = None
        self.audit_log_entries = []

    async def unban(self, user, reason=None):
        self.unbanned_user = user
        self.unban_reason = reason

    async def audit_logs(self, limit=100, action=None):
        for entry in self.audit_log_entries:
            yield entry

class MockCtx:
    def __init__(self, bot, author, guild):
        self.bot = bot
        self.author = author
        self.guild = guild
        self.sent_messages = []
        self.deferred = False

    async def send(self, content=None, embed=None, ephemeral=False, delete_after=None):
        if content: self.sent_messages.append(content)
        if embed: self.sent_messages.append(embed)
        return True

    async def defer(self):
        self.deferred = True

class MockBot:
    def __init__(self, db):
        self.db = db
        self.latency = 0.05
    
    async def log_action(self, *args, **kwargs):
        pass

    def get_user(self, user_id):
        return MockUser(user_id, f"User{user_id}")

async def test_permissions():
    print("--- Testing is_staff Permissions ---")
    guild = MockGuild(123)
    
    # 1. Administrator permission
    admin_member = MockMember(1, "AdminUser", administrator=True)
    ctx = MockCtx(None, admin_member, guild)
    predicate = is_staff().predicate
    assert await predicate(ctx) == True
    print("Permission (Admin Perm): PASSED")

    # 2. Staff roles
    staff_roles = ["sr.mod", "admin", "head admin", "co-owner", "adminstator", "administrator"]
    for role_name in staff_roles:
        member = MockMember(2, f"Staff_{role_name}", roles=[MockRole(role_name)])
        ctx = MockCtx(None, member, guild)
        assert await predicate(ctx) == True
        print(f"Permission (Role {role_name}): PASSED")

    # 3. Non-staff role
    non_staff = MockMember(3, "RegularUser", roles=[MockRole("Member")])
    ctx = MockCtx(None, non_staff, guild)
    assert await predicate(ctx) == False
    print("Permission (Non-staff): PASSED")

async def test_moderation_commands():
    db_path = "test_new_mod.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = Database(db_path)
    try:
        await db.init()
        bot = MockBot(db)
        cog = Moderation(bot)
        
        guild = MockGuild(123)
        author = MockMember(1, "Mod", roles=[MockRole("admin")])
        target = MockMember(2, "Spammer")
        ctx = MockCtx(bot, author, guild)

        print("\n--- Testing Warn Commands ---")
        # warn
        await cog.warn.callback(cog, ctx, target, reason="Test warn")
        warns = await db.get_warns(target.id, guild.id)
        assert len(warns) == 1
        assert warns[0][0] == str(author.id)
        assert warns[0][1] == "Test warn"
        assert any("has been warned" in str(m) for m in ctx.sent_messages)
        print("Command warn: PASSED")

        # warns
        ctx.sent_messages = []
        await cog.warns.callback(cog, ctx, target)
        assert any(isinstance(m, discord.Embed) and "Warnings for Spammer" in m.title for m in ctx.sent_messages)
        print("Command warns: PASSED")

        # delwarn
        warn_id = warns[0][3]
        ctx.sent_messages = []
        await cog.removewarn.callback(cog, ctx, warn_id)
        warns_after = await db.get_warns(target.id, guild.id)
        assert len(warns_after) == 0
        assert any("removed" in str(m) for m in ctx.sent_messages)
        print("Command delwarn: PASSED")

        print("\n--- Testing Ban/Unban Commands ---")
        # ban
        ctx.sent_messages = []
        await cog.ban.callback(cog, ctx, target, reason="Bad user")
        assert target.banned == True
        assert target.ban_reason == "Bad user"
        assert any("banned" in str(m) for m in ctx.sent_messages)
        print("Command ban: PASSED")

        # unban
        user_to_unban = MockUser(2, "Spammer")
        ctx.sent_messages = []
        await cog.unban.callback(cog, ctx, user_to_unban, reason="Apology accepted")
        assert guild.unbanned_user == user_to_unban
        assert guild.unban_reason == "Apology accepted"
        assert any("unbanned" in str(m) for m in ctx.sent_messages)
        print("Command unban: PASSED")

        print("\n--- Testing Logs Command ---")
        entry = MockAuditLogEntry(author, target, discord.AuditLogAction.ban, "Test reason")
        guild.audit_log_entries.append(entry)
        ctx.sent_messages = []
        await cog.logs.callback(cog, ctx, limit=5)
        assert any(isinstance(m, discord.Embed) and "Moderation Logs" in m.title for m in ctx.sent_messages)
        print("Command logs: PASSED")
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

async def run_tests():
    try:
        await test_permissions()
        await test_moderation_commands()
        print("\nAll new moderation tests passed successfully!")
    except Exception as e:
        print(f"\nTests FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_tests())
