import asyncio
import os
from urllib.parse import parse_qs, urlparse

import discord
from unittest.mock import AsyncMock, MagicMock

from cogs.config import ConfigCog
from cogs.moderation import Moderation
from main import FlowerBot, send_context_message
from utils.database import Database


class PrefixContext:
    def __init__(self, bot, guild_id=123):
        self.bot = bot
        self.guild = MagicMock(spec=discord.Guild)
        self.guild.id = guild_id
        self.message = MagicMock()
        self.message.guild = self.guild
        self.author = MagicMock(spec=discord.Member)
        self.author.guild_permissions.administrator = True
        self.send = AsyncMock()


async def test_prefix_configuration():
    db_path = "test_command_configuration.db"
    if os.path.exists(db_path):
        os.remove(db_path)


async def test_prefix_response_does_not_use_ephemeral():
    ctx = MagicMock()
    ctx.interaction = None
    ctx.send = AsyncMock()

    await send_context_message(ctx, "error", ephemeral=True)

    ctx.send.assert_awaited_once_with("error")


async def test_interaction_response_remains_ephemeral():
    ctx = MagicMock()
    ctx.interaction = MagicMock()
    ctx.send = AsyncMock()

    await send_context_message(ctx, "error", ephemeral=True)

    ctx.send.assert_awaited_once_with("error", ephemeral=True)

    db = Database(db_path)
    await db.init()
    try:
        bot = FlowerBot()
        bot.db = db
        bot._connection.user = MagicMock(id=999)
        ctx = PrefixContext(bot)
        config = ConfigCog(bot)

        invite_url = bot.get_admin_invite_url()
        query = parse_qs(urlparse(invite_url).query)
        assert query["client_id"] == ["999"]
        assert query["permissions"] == ["8"]
        assert query["scope"] == ["bot applications.commands"]

        assert "." in await bot.get_prefix(ctx.message)

        for expected_prefix in bot.SUPPORTED_PREFIXES:
            await config.prefix.callback(config, ctx, expected_prefix)
            assert await db.get_guild_setting(123, "command_prefix") == expected_prefix
            assert expected_prefix in await bot.get_prefix(ctx.message)

        ctx.send.reset_mock()
        await config.prefix.callback(config, ctx, "s")
        ctx.send.assert_awaited_once()
        assert await db.get_guild_setting(123, "command_prefix") == bot.SUPPORTED_PREFIXES[-1]
    finally:
        await db.close()
        os.remove(db_path)


def test_warning_commands_are_prefix_only():
    moderation = Moderation(FlowerBot())

    command_names = {command.name for command in moderation.get_commands()}
    assert "mod" not in command_names
    assert {"mute", "timeout", "ban", "kick", "warn"}.issubset(command_names)
    assert moderation.top_warnings.extras.get("prefix_only") is True
    assert moderation.top_delwarn.extras.get("prefix_only") is True


if __name__ == "__main__":
    asyncio.run(test_prefix_configuration())
    test_warning_commands_are_prefix_only()