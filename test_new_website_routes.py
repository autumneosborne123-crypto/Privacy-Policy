import asyncio
from aiohttp import web
from unittest.mock import MagicMock
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from cogs.dashboard import Dashboard

async def test_new_routes():
    bot = MagicMock()
    bot.db = MagicMock()
    bot.guilds = [MagicMock(member_count=10), MagicMock(member_count=20)]
    bot.users = [MagicMock(), MagicMock()]
    bot.commands = [MagicMock(hidden=False), MagicMock(hidden=False)]
    bot.loop = asyncio.get_event_loop()
    
    # Mock DISCORD_CLIENT_ID
    os.environ["DISCORD_CLIENT_ID"] = "123"
    os.environ["DISCORD_CLIENT_SECRET"] = "secret"
    
    cog = Dashboard(bot)
    
    # Check if new routes are registered
    routes = [r.resource.canonical for r in cog.app.router.routes() if r.resource]
    print("Registered routes:", routes)
    
    # Simulate a request to /
    from aiohttp.test_utils import make_mocked_request
    
    success = True
    for path in ['/', '/privacy', '/terms', '/commands']:
        request = make_mocked_request('GET', path, app=cog.app)
        try:
            if path == '/':
                response = await cog.handle_index(request)
            elif path == '/privacy':
                response = await cog.handle_privacy(request)
            elif path == '/terms':
                response = await cog.handle_terms(request)
            elif path == '/commands':
                response = await cog.handle_commands(request)
            print(f"Path {path} response status: {response.status}")
            if response.status != 200:
                success = False
        except Exception as e:
            print(f"Path {path} failed: {e}")
            success = False
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_new_routes())
