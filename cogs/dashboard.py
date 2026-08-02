import discord
from discord.ext import commands
import aiohttp
from aiohttp import web
import aiohttp_jinja2
import jinja2
import os
import asyncio
import logging
from datetime import datetime, timedelta
import json
from urllib.parse import quote
import secrets

# OAuth2 Config
CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 'http://localhost:5000/callback')
BRANDING = "flowerbot.gg"
# Use DASHBOARD_URL from env, or derive from REDIRECT_URI
DASHBOARD_URL = os.getenv('DASHBOARD_URL')
if not DASHBOARD_URL:
    if '/callback' in REDIRECT_URI:
        DASHBOARD_URL = REDIRECT_URI.split('/callback')[0]
    else:
        DASHBOARD_URL = f"http://{BRANDING}:5000"

INVITE_URL = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&permissions=8&scope=bot%20applications.commands"

def is_configured():
    """Check if Discord OAuth credentials are properly set in .env"""
    placeholders = ["your_client_id_here", "your_client_secret_here", ""]
    if not CLIENT_ID or CLIENT_ID in placeholders: return False
    if not CLIENT_SECRET or CLIENT_SECRET in placeholders: return False
    return True

class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.app = web.Application()
        self.tokens = {} # In-memory session tokens: token -> {user_id, expires}
        
        # Setup Jinja2
        aiohttp_jinja2.setup(self.app, loader=jinja2.FileSystemLoader('templates'), context_processors=[aiohttp_jinja2.request_processor])
        
        # Routes
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/login', self.handle_login)
        self.app.router.add_get('/callback', self.handle_callback)
        self.app.router.add_get('/dashboard', self.handle_dashboard)
        self.app.router.add_get('/commands', self.handle_commands)
        self.app.router.add_get('/privacy', self.handle_privacy)
        self.app.router.add_get('/terms', self.handle_terms)
        self.app.router.add_get('/guild/{guild_id}', self.handle_guild_page)
        self.app.router.add_post('/guild/{guild_id}/update', self.handle_guild_update)
        self.app.router.add_post('/guild/{guild_id}/update_modules', self.handle_guild_update_modules)
        self.app.router.add_post('/guild/{guild_id}/update_welcome', self.handle_guild_update_welcome)
        self.app.router.add_post('/guild/{guild_id}/update_moderation', self.handle_guild_update_moderation)
        self.app.router.add_post('/guild/{guild_id}/update_security', self.handle_guild_update_security)
        self.app.router.add_post('/guild/{guild_id}/update_roles', self.handle_guild_update_roles)
        self.app.router.add_post('/guild/{guild_id}/update_logging', self.handle_guild_update_logging)
        self.app.router.add_post('/guild/{guild_id}/add_media', self.handle_guild_add_media)
        self.app.router.add_post('/guild/{guild_id}/remove_media/{feed_id}', self.handle_guild_remove_media)
        self.app.router.add_post('/guild/{guild_id}/send_embed', self.handle_send_embed)
        self.app.router.add_static('/static', path='static', name='static', show_index=True)

        self.runner = None
        self.site = None
        self.bot.loop.create_task(self.start_server())

    async def start_server(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', 5000)
        try:
            await self.site.start()
            logging.info(f"Dashboard started on port 5000 ({BRANDING})")
        except Exception as e:
            logging.error(f"Failed to start dashboard server: {e}")

    def cog_unload(self):
        if self.runner:
            self.bot.loop.create_task(self.runner.cleanup())

    def get_user_from_token(self, token):
        session = self.tokens.get(token)
        if session and session['expires'] > datetime.now():
            return session['user_id']
        return None

    def safe_int(self, val, default=0):
        try:
            if val is None or val == "": return default
            return int(val)
        except:
            return default

    async def handle_index(self, request):
        try:
            token = request.query.get('token')
            stats = {
                'guilds': len(self.bot.guilds),
                'users': sum(g.member_count for g in self.bot.guilds if g.member_count) or len(self.bot.users),
                'commands': len([c for c in self.bot.commands if not c.hidden])
            }
            return aiohttp_jinja2.render_template('index.html', request, {
                'bot': self.bot,
                'branding': BRANDING,
                'stats': stats,
                'token': token,
                'invite_url': INVITE_URL
            })
        except Exception as e:
            logging.error(f"Error in handle_index: {e}")
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_privacy(self, request):
        try:
            token = request.query.get('token')
            return aiohttp_jinja2.render_template('privacy.html', request, {
                'bot': self.bot,
                'branding': BRANDING,
                'token': token
            })
        except Exception as e:
            logging.error(f"Error in handle_privacy: {e}")
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_terms(self, request):
        try:
            token = request.query.get('token')
            return aiohttp_jinja2.render_template('terms.html', request, {
                'bot': self.bot,
                'branding': BRANDING,
                'token': token
            })
        except Exception as e:
            logging.error(f"Error in handle_terms: {e}")
            return web.Response(text=f"Internal Server Error: {e}", status=500)


    async def handle_login(self, request):
        if not is_configured():
            return aiohttp_jinja2.render_template('index.html', request, {
                'bot': self.bot,
                'branding': BRANDING,
                'error': "❌ Dashboard Error: DISCORD_CLIENT_ID or CLIENT_SECRET is not configured. Please update your .env file with your Discord Application credentials."
            })
        login_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={quote(REDIRECT_URI, safe='')}&response_type=code&scope=identify%20guilds"
        return web.Response(status=302, headers={'Location': login_url})

    async def handle_callback(self, request):
        code = request.query.get('code')
        if not code: return web.Response(text="No code provided", status=400)

        if not is_configured():
            return aiohttp_jinja2.render_template('index.html', request, {
                'bot': self.bot,
                'branding': BRANDING,
                'error': "❌ Dashboard Error: OAuth credentials (ID/Secret) are missing or invalid in .env."
            })
            
        data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post('https://discord.com/api/oauth2/token', data=data, headers=headers) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        return web.Response(text=f"Failed to get token: {err_text}", status=resp.status)
                    token_data = await resp.json()
            except Exception as e:
                return web.Response(text=f"Token exchange error: {e}", status=500)

            if 'access_token' not in token_data:
                return web.Response(text=f"Failed to get token: {token_data}", status=400)
            
            access_token = token_data['access_token']
            
            # Get User Info
            try:
                async with session.get('https://discord.com/api/users/@me', headers={'Authorization': f"Bearer {access_token}"}) as user_resp:
                    if user_resp.status != 200:
                        return web.Response(text="Failed to fetch user info", status=user_resp.status)
                    user_info = await user_resp.json()
            except Exception as e:
                return web.Response(text=f"User info fetch error: {e}", status=500)

            user_id = user_info.get('id')
            if not user_id:
                return web.Response(text="User ID missing in response", status=500)
            
            # Generate Session Token
            session_token = secrets.token_urlsafe(32)
            self.tokens[session_token] = {
                'user_id': user_id,
                'access_token': access_token,
                'expires': datetime.now() + timedelta(days=7)
            }
            
            return web.HTTPFound(f'/dashboard?token={session_token}')

    async def handle_dashboard(self, request):
        token = request.query.get('token')
        user_id = self.get_user_from_token(token)
        if not user_id: return web.HTTPFound('/login')

        access_token = self.tokens[token]['access_token']
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get('https://discord.com/api/users/@me/guilds', headers={'Authorization': f"Bearer {access_token}"}) as resp:
                    if resp.status != 200:
                        return web.Response(text="Failed to fetch guilds", status=resp.status)
                    guilds = await resp.json()
            except Exception as e:
                return web.Response(text=f"Guild fetch error: {e}", status=500)
                
        if not isinstance(guilds, list):
            return web.Response(text=f"Unexpected API response: {guilds}", status=500)

        # Filter guilds where user is admin
        manageable_guilds = []
        for g in guilds:
            permissions = int(g.get('permissions', 0))
            if (permissions & 0x8) == 0x8 or g.get('owner'): # Administrator
                # Check if bot is in guild
                discord_guild = self.bot.get_guild(int(g['id']))
                g['bot_in'] = discord_guild is not None
                manageable_guilds.append(g)

        return aiohttp_jinja2.render_template('dashboard.html', request, {
            'guilds': manageable_guilds,
            'token': token,
            'branding': BRANDING,
            'invite_url': INVITE_URL
        })

    async def handle_commands(self, request):
        try:
            token = request.query.get('token')
            
            cogs_data = {}
            for cog_name, cog in self.bot.cogs.items():
                if cog_name in ["Dashboard", "System", "Config"]: continue
                
                cmds = []
                for cmd in cog.get_commands():
                    if isinstance(cmd, commands.Group):
                        for sub in cmd.commands:
                            usage = ""
                            if hasattr(sub, 'clean_params') and sub.clean_params:
                                usage = " ".join([f"<{p}>" if param.default == param.empty else f"[{p}]" for p, param in sub.clean_params.items()])
                            cmds.append({
                                'name': f"{cmd.name} {sub.name}",
                                'description': sub.description,
                                'usage': usage
                            })
                    else:
                        usage = ""
                        if hasattr(cmd, 'clean_params') and cmd.clean_params:
                            usage = " ".join([f"<{p}>" if param.default == param.empty else f"[{p}]" for p, param in cmd.clean_params.items()])
                        cmds.append({
                            'name': cmd.name,
                            'description': cmd.description,
                            'usage': usage
                        })
                
                if cmds:
                    cogs_data[cog_name] = cmds

            return aiohttp_jinja2.render_template('commands.html', request, {
                'bot': self.bot,
                'cogs': cogs_data,
                'token': token,
                'branding': BRANDING
            })
        except Exception as e:
            logging.error(f"Error in handle_commands: {e}")
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def get_admin_member(self, guild_id, token):
        user_id = self.get_user_from_token(token)
        if not user_id: return None
        
        guild = self.bot.get_guild(int(guild_id))
        if not guild: return None
        
        member = guild.get_member(int(user_id))
        if not member:
            try: member = await guild.fetch_member(int(user_id))
            except: return None
            
        if not member.guild_permissions.administrator: return None
        return member

    async def handle_guild_page(self, request):
        try:
            guild_id = int(request.match_info['guild_id'])
            token = request.query.get('token')
            
            logging.info(f"Handling guild page for {guild_id}")
            
            member = await self.get_admin_member(guild_id, token)
            if not member: 
                logging.warning(f"Admin member not found for guild {guild_id}")
                return web.HTTPFound('/login')
            
            guild = member.guild
            settings = await self.bot.db.get_all_guild_settings(guild_id)
            media_feeds = await self.bot.db.get_media_feeds(guild_id)
            stats = await self.bot.db.get_daily_stats(guild_id, days=7)
            
            # Stringify dates for JSON serialization
            safe_stats = []
            for row in stats:
                safe_row = list(row)
                if hasattr(safe_row[0], 'isoformat'):
                    safe_row[0] = safe_row[0].isoformat()
                else:
                    safe_row[0] = str(safe_row[0])
                safe_stats.append(tuple(safe_row))
            
            # Safe cog gathering
            visible_cogs = []
            for cog_name, cog in self.bot.cogs.items():
                if cog_name not in ["Dashboard", "System", "Config"]:
                    visible_cogs.append(cog)
            
            # Calculate uptime
            uptime = "N/A"
            if hasattr(self.bot, 'start_time'):
                delta = discord.utils.utcnow() - self.bot.start_time
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime = f"{hours}h {minutes}m"

            return aiohttp_jinja2.render_template('guild.html', request, {
                'guild': guild,
                'settings': settings,
                'media_feeds': media_feeds,
                'stats': safe_stats,
                'token': token,
                'cogs': visible_cogs,
                'branding': BRANDING,
                'latency': round(self.bot.latency * 1000),
                'uptime': uptime
            })
        except Exception as e:
            logging.error(f"Error in handle_guild_page: {e}", exc_info=True)
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_guild_update(self, request):
        try:
            guild_id = request.match_info['guild_id']
            token = request.query.get('token')
            
            logging.info(f"Updating guild settings for {guild_id}")
            
            if not await self.get_admin_member(guild_id, token):
                return web.Response(text="Unauthorized", status=403)
                
            data = await request.post()
            
            if 'log_channel_id' in data:
                await self.bot.db.set_guild_setting(guild_id, 'log_channel_id', data['log_channel_id'] or None)
            if 'mute_role_id' in data:
                await self.bot.db.set_guild_setting(guild_id, 'mute_role_id', data['mute_role_id'] or None)
                
            return web.HTTPFound(f'/guild/{guild_id}?token={token}&success=true')
        except Exception as e:
            logging.error(f"Error in handle_guild_update: {e}", exc_info=True)
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_guild_update_modules(self, request):
        try:
            guild_id = request.match_info['guild_id']
            token = request.query.get('token')
            
            if not await self.get_admin_member(guild_id, token):
                return web.Response(text="Unauthorized", status=403)
                
            data = await request.post()
            
            disabled = []
            for cog_name in self.bot.cogs:
                if cog_name in ["Dashboard", "System", "Config"]: continue
                if data.get(f'cog_{cog_name}') != 'on':
                    cog = self.bot.get_cog(cog_name)
                    if cog:
                        disabled.append(cog.__module__)
            
            await self.bot.db.set_guild_setting(guild_id, 'disabled_cogs', ",".join(disabled))
            return web.HTTPFound(f'/guild/{guild_id}?token={token}&success=true')
        except Exception as e:
            logging.error(f"Error in handle_guild_update_modules: {e}", exc_info=True)
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_guild_update_welcome(self, request):
        try:
            guild_id = request.match_info['guild_id']
            token = request.query.get('token')
            
            if not await self.get_admin_member(guild_id, token):
                return web.Response(text="Unauthorized", status=403)
                
            data = await request.post()
            
            await self.bot.db.set_guild_setting(guild_id, 'welcome_channel_id', data.get('welcome_channel_id') or None)
            await self.bot.db.set_guild_setting(guild_id, 'welcome_message', data.get('welcome_message') or "")
            await self.bot.db.set_guild_setting(guild_id, 'goodbye_channel_id', data.get('goodbye_channel_id') or None)
            await self.bot.db.set_guild_setting(guild_id, 'goodbye_message', data.get('goodbye_message') or "")
            
            return web.HTTPFound(f'/guild/{guild_id}?token={token}&success=true')
        except Exception as e:
            logging.error(f"Error in handle_guild_update_welcome: {e}", exc_info=True)
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_guild_update_moderation(self, request):
        try:
            guild_id = request.match_info['guild_id']
            token = request.query.get('token')
            
            if not await self.get_admin_member(guild_id, token):
                return web.Response(text="Unauthorized", status=403)
                
            data = await request.post()
            
            await self.bot.db.set_guild_setting(guild_id, "anti_spam_enabled", 1 if data.get("anti_spam_enabled") == "on" else 0)
            await self.bot.db.set_guild_setting(guild_id, "anti_spam_threshold", self.safe_int(data.get("anti_spam_threshold"), 5))
            await self.bot.db.set_guild_setting(guild_id, "anti_scam_enabled", 1 if data.get("anti_scam_enabled") == "on" else 0)
            await self.bot.db.set_guild_setting(guild_id, "mention_spam_threshold", self.safe_int(data.get("mention_spam_threshold"), 5))
            await self.bot.db.set_guild_setting(guild_id, "slur_filter_enabled", 1 if data.get("slur_filter_enabled") == "on" else 0)
            
            return web.HTTPFound(f'/guild/{guild_id}?token={token}&success=true')
        except Exception as e:
            logging.error(f"Error in handle_guild_update_moderation: {e}", exc_info=True)
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_guild_update_security(self, request):
        try:
            guild_id = request.match_info['guild_id']
            token = request.query.get('token')
            
            if not await self.get_admin_member(guild_id, token):
                return web.Response(text="Unauthorized", status=403)
                
            data = await request.post()
            
            await self.bot.db.set_guild_setting(guild_id, "anti_raid_enabled", 1 if data.get("anti_raid_enabled") == "on" else 0)
            await self.bot.db.set_guild_setting(guild_id, "anti_nuke_enabled", 1 if data.get("anti_nuke_enabled") == "on" else 0)
            
            return web.HTTPFound(f'/guild/{guild_id}?token={token}&success=true')
        except Exception as e:
            logging.error(f"Error in handle_guild_update_security: {e}", exc_info=True)
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_guild_update_roles(self, request):
        try:
            guild_id = request.match_info['guild_id']
            token = request.query.get('token')
            
            if not await self.get_admin_member(guild_id, token):
                return web.Response(text="Unauthorized", status=403)
                
            data = await request.post()
            
            await self.bot.db.set_guild_setting(guild_id, "auto_role_id", data.get("auto_role_id") or None)
            return web.HTTPFound(f'/guild/{guild_id}?token={token}&success=true')
        except Exception as e:
            logging.error(f"Error in handle_guild_update_roles: {e}", exc_info=True)
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_guild_update_logging(self, request):
        try:
            guild_id = request.match_info['guild_id']
            token = request.query.get('token')
            
            if not await self.get_admin_member(guild_id, token):
                return web.Response(text="Unauthorized", status=403)
                
            data = await request.post()
            
            log_keys = ['log_message_delete', 'log_message_edit', 'log_member_join', 'log_member_leave', 'log_voice_activity']
            for key in log_keys:
                await self.bot.db.set_guild_setting(guild_id, key, 1 if data.get(key) == 'on' else 0)
                
            return web.HTTPFound(f'/guild/{guild_id}?token={token}&success=true')
        except Exception as e:
            logging.error(f"Error in handle_guild_update_logging: {e}", exc_info=True)
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_guild_add_media(self, request):
        try:
            guild_id = request.match_info['guild_id']
            token = request.query.get('token')
            
            if not await self.get_admin_member(guild_id, token):
                return web.Response(text="Unauthorized", status=403)
                
            data = await request.post()
            
            if 'channel_id' not in data or 'category' not in data:
                return web.Response(text="Missing channel_id or category", status=400)
                
            await self.bot.db.add_media_feed(guild_id, data['channel_id'], data['category'])
            return web.HTTPFound(f'/guild/{guild_id}?token={token}&success=true')
        except Exception as e:
            logging.error(f"Error in handle_guild_add_media: {e}", exc_info=True)
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_guild_remove_media(self, request):
        try:
            guild_id = request.match_info['guild_id']
            feed_id = self.safe_int(request.match_info.get('feed_id'))
            token = request.query.get('token')
            
            if not await self.get_admin_member(guild_id, token):
                return web.Response(text="Unauthorized", status=403)
            
            await self.bot.db.remove_media_feed(feed_id)
            return web.HTTPFound(f'/guild/{guild_id}?token={token}&success=true')
        except Exception as e:
            logging.error(f"Error in handle_guild_remove_media: {e}", exc_info=True)
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    async def handle_send_embed(self, request):
        try:
            guild_id = self.safe_int(request.match_info.get('guild_id'))
            token = request.query.get('token')
            
            member = await self.get_admin_member(guild_id, token)
            if not member:
                return web.Response(text="Unauthorized", status=403)
                
            data = await request.post()
            guild = member.guild
            if not guild: return web.Response(text="Bot not in guild", status=404)
            
            channel_id = data.get('channel_id')
            if not channel_id: return web.Response(text="Channel ID missing", status=400)
            
            channel = guild.get_channel(self.safe_int(channel_id))
            if not channel: return web.Response(text="Channel not found", status=404)
            
            color_hex = data.get('color', '#2b2d31').replace('#', '')
            try:
                color_val = int(color_hex, 16)
            except:
                color_val = 0x2b2d31
                
            embed = discord.Embed(
                title=data.get('title', 'No Title'),
                description=data.get('description', 'No Description'),
                color=color_val
            )
            if data.get('footer'):
                embed.set_footer(text=data['footer'])
                
            await channel.send(embed=embed)
            return web.HTTPFound(f'/guild/{guild_id}?token={token}&success=true')
        except Exception as e:
            logging.error(f"Error in handle_send_embed: {e}", exc_info=True)
            return web.Response(text=f"Internal Server Error: {e}", status=500)

    @commands.hybrid_command(name="dashboard", description="Get the link to the web dashboard")
    async def dashboard(self, ctx):
        await ctx.send(f"🌐 **Manage {BRANDING} on the web:** {DASHBOARD_URL}\nLocal link: http://localhost:5000/login", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Dashboard(bot))
