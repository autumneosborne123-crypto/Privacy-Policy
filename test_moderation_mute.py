import asyncio
import os
from utils.database import Database
from cogs.moderation import Moderation
from datetime import timedelta

class MockMember:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.mention = f"<@{id}>"
        self.timeout_until = None
        self.timed_out_until = None
        self.reason = None
        self.roles = []

    async def timeout(self, until, reason=None):
        self.timeout_until = until
        self.timed_out_until = until
        self.reason = reason
        return True

    async def add_roles(self, role, reason=None):
        if role not in self.roles:
            self.roles.append(role)
        self.reason = reason
        return True

    async def remove_roles(self, role, reason=None):
        if role in self.roles:
            self.roles.remove(role)
        self.reason = reason
        return True

class MockRole:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.mention = f"<@&{id}>"

class MockBot:
    def __init__(self, db):
        self.db = db
    
    async def log_action(self, *args, **kwargs):
        pass

class MockCtx:
    def __init__(self, bot, author, guild):
        self.bot = bot
        self.author = author
        self.guild = guild
        self.sent_messages = []
        self.interaction = None

    async def send(self, content, ephemeral=False, delete_after=None):
        self.sent_messages.append(content)
        return True

async def test_moderation_mute():
    db = Database("test_mod.db")
    await db.init()
    bot = MockBot(db)
    cog = Moderation(bot)
    
    class MockGuild:
        def __init__(self, id, name):
            self.id = id
            self.name = name
            self.roles = []
        def get_role(self, role_id):
            for r in self.roles:
                if r.id == role_id: return r
            return None

    guild = MockGuild(123, 'Test')
    author = MockMember(1, "Mod")
    target = MockMember(2, "Player")
    ctx = MockCtx(bot, author, guild)
    
    print("--- Test: Mute (Timeout Only) ---")
    await cog.mute.callback(cog, ctx, target, "10", reason="Spamming")
    assert target.timeout_until is not None
    assert target.reason == "Spamming"
    assert any("timed out for 10 minutes" in m for m in ctx.sent_messages)
    print("Mute Timeout: PASSED")
    
    print("\n--- Test: Mute (Role Only) ---")
    mute_role = MockRole(999, "Muted")
    guild.roles.append(mute_role)
    await db.set_mute_role(guild.id, mute_role.id)
    
    ctx.sent_messages = []
    target.roles = []
    target.timeout_until = None
    target.timed_out_until = None
    
    await cog.mute.callback(cog, ctx, target, None, reason="Bad behavior")
    assert mute_role in target.roles
    assert target.timeout_until is None
    assert any("assigned <@&999> role" in m for m in ctx.sent_messages)
    print("Mute Role: PASSED")
    
    print("\n--- Test: Mute (Both) ---")
    ctx.sent_messages = []
    target.roles = []
    target.timeout_until = None
    target.timed_out_until = None
    await cog.mute.callback(cog, ctx, target, "5", reason="Double punishment")
    assert mute_role in target.roles
    assert target.timeout_until is not None
    assert any("timed out for 5 minutes" in m for m in ctx.sent_messages)
    assert any("assigned <@&999> role" in m for m in ctx.sent_messages)
    print("Mute Both: PASSED")
    
    print("\n--- Test: Unmute (Both) ---")
    ctx.sent_messages = []
    await cog.unmute.callback(cog, ctx, target, reason="Good behavior")
    assert target.timeout_until is None
    assert mute_role not in target.roles
    assert any("timeout removed" in m for m in ctx.sent_messages)
    assert any("mute role removed" in m for m in ctx.sent_messages)
    print("Unmute Command: PASSED")
    
    print("\n--- Test: Mute (1d duration) ---")
    ctx.sent_messages = []
    target.roles = []
    target.timeout_until = None
    target.timed_out_until = None
    await cog.mute.callback(cog, ctx, target, "1d", reason="Long mute")
    assert target.timeout_until is not None
    assert target.timeout_until == timedelta(minutes=1440)
    assert any("timed out for 1 day" in m for m in ctx.sent_messages)
    print("Mute 1d: PASSED")
    
    print("\nAll moderation tests passed!")
    if os.path.exists("test_mod.db"):
        os.remove("test_mod.db")

if __name__ == "__main__":
    asyncio.run(test_moderation_mute())
