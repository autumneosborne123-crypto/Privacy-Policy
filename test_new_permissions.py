import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
import discord
from utils.permissions import is_staff, is_senior_staff, is_admin, is_admin_or_moderator

class MockRole:
    def __init__(self, name):
        self.name = name

class MockMember:
    def __init__(self, roles, administrator=False):
        self.roles = [MockRole(r) for r in roles]
        self.guild_permissions = MagicMock()
        self.guild_permissions.administrator = administrator

class MockContext:
    def __init__(self, member, guild=True):
        self.author = member
        self.guild = MagicMock() if guild else None

class TestPermissions(unittest.IsolatedAsyncioTestCase):
    async def test_is_admin(self):
        # Admin roles
        admin_roles = ["admin", "head admin", "co-owner", "owner", "founder"]
        for role in admin_roles:
            member = MockMember([role])
            ctx = MockContext(member)
            check = is_admin().predicate
            self.assertTrue(await check(ctx), f"Role '{role}' should be recognized as admin")

        # Non-admin roles
        member = MockMember(["mod", "staff"])
        ctx = MockContext(member)
        check = is_admin().predicate
        self.assertFalse(await check(ctx))

    async def test_is_admin_or_moderator(self):
        # Admin and Mod roles
        roles = ["admin", "owner", "mod", "sr.mod", "sernior mod", "moderation"]
        for role in roles:
            member = MockMember([role])
            ctx = MockContext(member)
            check = is_admin_or_moderator().predicate
            self.assertTrue(await check(ctx), f"Role '{role}' should be recognized as admin/mod")

    async def test_is_staff(self):
        # Staff roles
        staff_roles = ["mod", "sr.mod", "sernior mod", "senior mod", "moderation", "admin", "head admin", "co-owner", "owner", "founder", "staff"]
        for role in staff_roles:
            member = MockMember([role])
            ctx = MockContext(member)
            check = is_staff().predicate
            self.assertTrue(await check(ctx), f"Role '{role}' should be recognized as staff")

        # Non-staff roles
        member = MockMember(["member", "user"])
        ctx = MockContext(member)
        check = is_staff().predicate
        self.assertFalse(await check(ctx))

        # Administrator
        member = MockMember([], administrator=True)
        ctx = MockContext(member)
        check = is_staff().predicate
        self.assertTrue(await check(ctx))

    async def test_is_senior_staff(self):
        # Senior staff roles
        senior_roles = ["sernior mod", "senior mod", "admin", "head admin", "co-owner", "owner", "founder"]
        for role in senior_roles:
            member = MockMember([role])
            ctx = MockContext(member)
            check = is_senior_staff().predicate
            self.assertTrue(await check(ctx), f"Role '{role}' should be recognized as senior staff")

        # Junior staff roles (should fail)
        junior_roles = ["mod", "sr.mod", "moderation", "staff"]
        for role in junior_roles:
            member = MockMember([role])
            ctx = MockContext(member)
            check = is_senior_staff().predicate
            self.assertFalse(await check(ctx), f"Role '{role}' should NOT be recognized as senior staff")

        # Administrator
        member = MockMember([], administrator=True)
        ctx = MockContext(member)
        check = is_senior_staff().predicate
        self.assertTrue(await check(ctx))

if __name__ == "__main__":
    unittest.main()
