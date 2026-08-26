import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from cogs.system import System
from main import FlowerBot, HelpSelect


class TestCommandRegistration(unittest.IsolatedAsyncioTestCase):
    async def test_on_ready_does_not_copy_global_commands_into_guilds(self):
        tree = MagicMock()
        tree.sync = AsyncMock()
        bot = SimpleNamespace(
            start_time=None,
            _guild_commands_synced=False,
            guilds=[MagicMock(id=123)],
            tree=tree,
            change_presence=AsyncMock(),
            user=MagicMock(id=456),
            application_id=456,
            get_admin_invite_url=MagicMock(return_value=None),
        )

        with patch("main.discord.utils.utcnow", return_value=MagicMock()):
            await FlowerBot.on_ready(bot)

        tree.copy_global_to.assert_not_called()
        tree.sync.assert_not_awaited()

    def test_help_select_does_not_show_duplicate_commands(self):
        command_a = SimpleNamespace(name="status", qualified_name="status", hidden=False)
        command_b = SimpleNamespace(name="status", qualified_name="status", hidden=False)
        cog = SimpleNamespace(get_commands=lambda: [command_a, command_b])
        bot = SimpleNamespace(cogs={"System": cog})

        select = HelpSelect(bot, ".")

        self.assertEqual(len(select.options), 2)
        self.assertEqual(select.options[1].description, "1 commands")

    async def test_guild_sync_removes_copies_instead_of_creating_duplicates(self):
        tree = MagicMock()
        tree.sync = AsyncMock(return_value=[])
        guild = MagicMock(name="Guild")
        bot = SimpleNamespace(tree=tree, get_guild=MagicMock(return_value=guild))
        ctx = SimpleNamespace(
            guild=guild,
            send=AsyncMock(),
        )

        await System(bot).sync.callback(System(bot), ctx, "123")

        tree.clear_commands.assert_called_once_with(guild=guild)
        tree.copy_global_to.assert_not_called()


if __name__ == "__main__":
    unittest.main()