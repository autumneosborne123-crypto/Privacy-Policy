import aiosqlite
import os
import json
import logging
import time

class Database:
    def __init__(self, db_path):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS levels
                             (user_id TEXT PRIMARY KEY, xp INTEGER, level INTEGER, last_xp_time REAL, message_count INTEGER DEFAULT 0, voice_minutes INTEGER DEFAULT 0)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS role_rewards
                             (level INTEGER PRIMARY KEY, role_id TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS ignored_channels
                             (channel_id TEXT PRIMARY KEY)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS xp_boosts
                             (role_id TEXT PRIMARY KEY, multiplier REAL)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS warns
                             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, guild_id TEXT, moderator_id TEXT, reason TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS media_feeds
                             (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, channel_id TEXT, category TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS sent_media
                             (url TEXT PRIMARY KEY, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS quote_feeds
                             (guild_id TEXT PRIMARY KEY, channel_id TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS daily_stats
                             (guild_id TEXT, date DATE, messages INTEGER DEFAULT 0, joins INTEGER DEFAULT 0, leaves INTEGER DEFAULT 0, PRIMARY KEY (guild_id, date))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS user_daily_activity
                             (user_id TEXT, guild_id TEXT, date DATE, messages INTEGER DEFAULT 0, voice_minutes INTEGER DEFAULT 0, PRIMARY KEY (user_id, guild_id, date))''')
            
            # New tables for Economy and Adventure
            await db.execute('''CREATE TABLE IF NOT EXISTS economy
                             (user_id TEXT PRIMARY KEY, flower_coins INTEGER DEFAULT 500, last_daily REAL DEFAULT 0, last_rob REAL DEFAULT 0, premium_until REAL DEFAULT 0)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS user_inventory
                             (user_id TEXT, item_id TEXT, quantity INTEGER DEFAULT 1, rank TEXT DEFAULT 'Common', PRIMARY KEY (user_id, item_id, rank))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS user_animals
                             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, animal_type TEXT, nickname TEXT, level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, hp INTEGER, max_hp INTEGER, attack INTEGER, defense INTEGER, speed INTEGER, rarity TEXT DEFAULT 'Common')''')
            await db.execute('''CREATE TABLE IF NOT EXISTS user_achievements
                             (user_id TEXT, achievement_id TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (user_id, achievement_id))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS user_quests
                             (user_id TEXT, quest_id TEXT, progress INTEGER DEFAULT 0, goal INTEGER, reward_coins INTEGER, reward_item TEXT, completed BOOLEAN DEFAULT 0, PRIMARY KEY (user_id, quest_id))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS playlists
                             (user_id TEXT, playlist_name TEXT, songs TEXT, PRIMARY KEY (user_id, playlist_name))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS guild_settings
                             (guild_id TEXT PRIMARY KEY, 
                              log_channel_id TEXT, 
                              mute_role_id TEXT,
                              welcome_channel_id TEXT,
                              welcome_message TEXT,
                              goodbye_channel_id TEXT,
                              goodbye_message TEXT,
                              level_up_channel_id TEXT,
                              music_channel_id TEXT,
                              disabled_cogs TEXT,
                              premium_until REAL DEFAULT 0)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS reaction_roles
                             (guild_id TEXT, message_id TEXT, emoji TEXT, role_id TEXT, PRIMARY KEY (guild_id, message_id, emoji))''')
            
            # Migration for user_daily_messages to activity if needed
            has_old_table = False
            async with db.execute("PRAGMA table_info(user_daily_messages)") as cursor:
                if await cursor.fetchone():
                    has_old_table = True
            
            if has_old_table:
                # Move data and drop old table
                await db.execute("INSERT OR IGNORE INTO user_daily_activity (user_id, guild_id, date, messages) SELECT user_id, guild_id, date, messages FROM user_daily_messages")
                await db.execute("DROP TABLE user_daily_messages")
                logging.info("Migrated user_daily_messages to user_daily_activity.")

            # Schema Migration: Add message_count and voice_minutes if they don't exist
            columns = []
            async with db.execute("PRAGMA table_info(levels)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
            
            if 'message_count' not in columns:
                await db.execute("ALTER TABLE levels ADD COLUMN message_count INTEGER DEFAULT 0")
                logging.info("Added missing message_count column to levels table.")
            if 'voice_minutes' not in columns:
                await db.execute("ALTER TABLE levels ADD COLUMN voice_minutes INTEGER DEFAULT 0")
                logging.info("Added missing voice_minutes column to levels table.")
            
            # Schema Migration for inventory and animals
            async with db.execute("PRAGMA table_info(user_inventory)") as cursor:
                inv_columns = [row[1] for row in await cursor.fetchall()]
            if 'rank' not in inv_columns:
                # We need to recreate the table because we are changing the primary key
                await db.execute("CREATE TABLE IF NOT EXISTS user_inventory_new (user_id TEXT, item_id TEXT, quantity INTEGER DEFAULT 1, rank TEXT DEFAULT 'Common', PRIMARY KEY (user_id, item_id, rank))")
                await db.execute("INSERT INTO user_inventory_new (user_id, item_id, quantity) SELECT user_id, item_id, quantity FROM user_inventory")
                await db.execute("DROP TABLE user_inventory")
                await db.execute("ALTER TABLE user_inventory_new RENAME TO user_inventory")
                logging.info("Migrated user_inventory to include rank in PK.")

            async with db.execute("PRAGMA table_info(guild_settings)") as cursor:
                gs_columns = [row[1] for row in await cursor.fetchall()]
            
            new_cols = {
                'mute_role_id': 'TEXT',
                'welcome_channel_id': 'TEXT',
                'welcome_message': 'TEXT',
                'goodbye_channel_id': 'TEXT',
                'goodbye_message': 'TEXT',
                'level_up_channel_id': 'TEXT',
                'music_channel_id': 'TEXT',
                'disabled_cogs': 'TEXT',
                'auto_role_id': 'TEXT',
                'anti_spam_enabled': 'BOOLEAN DEFAULT 1',
                'anti_scam_enabled': 'BOOLEAN DEFAULT 1',
                'slur_filter_enabled': 'BOOLEAN DEFAULT 1',
                'anti_raid_enabled': 'BOOLEAN DEFAULT 1',
                'anti_nuke_enabled': 'BOOLEAN DEFAULT 1',
                'anti_spam_threshold': 'INTEGER DEFAULT 5',
                'mention_spam_threshold': 'INTEGER DEFAULT 5',
                'embed_channel_id': 'TEXT',
                'roles_channel_id': 'TEXT',
                'log_message_delete': 'BOOLEAN DEFAULT 1',
                'log_message_edit': 'BOOLEAN DEFAULT 1',
                'log_member_join': 'BOOLEAN DEFAULT 1',
                'log_member_leave': 'BOOLEAN DEFAULT 1',
                'log_voice_activity': 'BOOLEAN DEFAULT 1',
                'premium_247': 'BOOLEAN DEFAULT 0'
            }
            for col, col_type in new_cols.items():
                if col not in gs_columns:
                    await db.execute(f"ALTER TABLE guild_settings ADD COLUMN {col} {col_type}")
                    logging.info(f"Added {col} column to guild_settings.")
            
            # Schema Migration for premium columns
            async with db.execute("PRAGMA table_info(economy)") as cursor:
                eco_columns = [row[1] for row in await cursor.fetchall()]
            if 'premium_until' not in eco_columns:
                await db.execute("ALTER TABLE economy ADD COLUMN premium_until REAL DEFAULT 0")
                logging.info("Added premium_until column to economy table.")

            async with db.execute("PRAGMA table_info(guild_settings)") as cursor:
                gs_columns_check = [row[1] for row in await cursor.fetchall()]
            if 'premium_until' not in gs_columns_check:
                await db.execute("ALTER TABLE guild_settings ADD COLUMN premium_until REAL DEFAULT 0")
                logging.info("Added premium_until column to guild_settings table.")

            await db.commit()
        await self.migrate_from_json()

    async def migrate_from_json(self):
        levels_file = "levels.json"
        if os.path.exists(levels_file):
            try:
                with open(levels_file, "r") as f:
                    old_data = json.load(f)
                
                async with aiosqlite.connect(self.db_path) as db:
                    for user_id, count in old_data.items():
                        xp = count * 20
                        level = 0
                        temp_xp = xp
                        while temp_xp >= (5 * (level**2) + 50*level + 100):
                            temp_xp -= (5 * (level**2) + 50*level + 100)
                            level += 1
                        
                        await db.execute("INSERT OR IGNORE INTO levels (user_id, xp, level, last_xp_time, message_count) VALUES (?, ?, ?, ?, ?)",
                                  (user_id, xp, level, 0, count))
                    await db.commit()
                os.rename(levels_file, levels_file + ".old")
                logging.info("Migrated levels.json to SQLite.")
            except Exception as e:
                logging.error(f"Migration failed: {e}")

    async def get_user_data(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT xp, level, last_xp_time, message_count, voice_minutes FROM levels WHERE user_id = ?", (str(user_id),)) as cursor:
                data = await cursor.fetchone()
                if data:
                    return {"xp": data[0], "level": data[1], "last_xp_time": data[2], "message_count": data[3], "voice_minutes": data[4]}
                return {"xp": 0, "level": 0, "last_xp_time": 0, "message_count": 0, "voice_minutes": 0}

    async def update_user_data(self, user_id, xp, level, last_xp_time, message_count, voice_minutes=0):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO levels (user_id, xp, level, last_xp_time, message_count, voice_minutes) VALUES (?, ?, ?, ?, ?, ?)",
                          (str(user_id), xp, level, last_xp_time, message_count, voice_minutes))
            await db.commit()

    async def get_top_users(self, limit=10, sort_by="xp"):
        async with aiosqlite.connect(self.db_path) as db:
            order_by = "level DESC, xp DESC"
            if sort_by == "messages": order_by = "message_count DESC"
            elif sort_by == "voice": order_by = "voice_minutes DESC"
            
            async with db.execute(f"SELECT user_id, xp, level, message_count, voice_minutes FROM levels ORDER BY {order_by} LIMIT ?", (limit,)) as cursor:
                return await cursor.fetchall()

    async def get_total_users(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM levels") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def get_level_distribution(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT level, COUNT(*) FROM levels GROUP BY level ORDER BY level ASC") as cursor:
                return await cursor.fetchall()

    async def get_rank(self, user_id, sort_by="xp"):
        async with aiosqlite.connect(self.db_path) as db:
            order_by = "level DESC, xp DESC"
            if sort_by == "messages": order_by = "message_count DESC"
            elif sort_by == "voice": order_by = "voice_minutes DESC"
            
            # Use a subquery to find the rank without fetching all rows
            # This is more efficient than fetching all users and iterating in Python
            query = f"""
                SELECT rank FROM (
                    SELECT user_id, 
                    RANK() OVER (ORDER BY {order_by}) as rank 
                    FROM levels
                ) WHERE user_id = ?
            """
            try:
                async with db.execute(query, (str(user_id),)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
            except aiosqlite.OperationalError:
                # Fallback for very old SQLite versions without window functions
                logging.warning("SQLite version might be too old for RANK() window function. Using fallback.")
                async with db.execute(f"SELECT user_id FROM levels ORDER BY {order_by}") as cursor:
                    all_users = await cursor.fetchall()
                    for i, (uid,) in enumerate(all_users, 1):
                        if uid == str(user_id):
                            return i
                    return 0

    async def get_role_rewards(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT level, role_id FROM role_rewards ORDER BY level ASC") as cursor:
                rewards = await cursor.fetchall()
                return {level: int(role_id) for level, role_id in rewards}

    async def add_role_reward(self, level, role_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO role_rewards (level, role_id) VALUES (?, ?)", (level, str(role_id)))
            await db.commit()

    async def remove_role_reward(self, level):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM role_rewards WHERE level = ?", (level,))
            await db.commit()

    async def add_xp_boost(self, role_id, multiplier):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO xp_boosts (role_id, multiplier) VALUES (?, ?)", (str(role_id), multiplier))
            await db.commit()

    async def remove_xp_boost(self, role_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM xp_boosts WHERE role_id = ?", (str(role_id),))
            await db.commit()

    async def get_xp_boosts(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT role_id, multiplier FROM xp_boosts") as cursor:
                rows = await cursor.fetchall()
                return {int(row[0]): row[1] for row in rows}

    async def get_ignored_channels(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT channel_id FROM ignored_channels") as cursor:
                channels = await cursor.fetchall()
                return [int(row[0]) for row in channels]

    async def add_ignored_channel(self, channel_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO ignored_channels (channel_id) VALUES (?)", (str(channel_id),))
            await db.commit()

    async def remove_ignored_channel(self, channel_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM ignored_channels WHERE channel_id = ?", (str(channel_id),))
            await db.commit()

    async def add_warn(self, user_id, guild_id, moderator_id, reason):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO warns (user_id, guild_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
                          (str(user_id), str(guild_id), str(moderator_id), reason))
            await db.commit()

    async def get_warns(self, user_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT moderator_id, reason, timestamp, id FROM warns WHERE user_id = ? AND guild_id = ? ORDER BY timestamp DESC",
                               (str(user_id), str(guild_id))) as cursor:
                return await cursor.fetchall()

    async def get_warn(self, warn_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id, moderator_id, reason, timestamp FROM warns WHERE id = ? AND guild_id = ?",
                               (warn_id, str(guild_id))) as cursor:
                return await cursor.fetchone()

    async def remove_warn(self, warn_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM warns WHERE id = ? AND guild_id = ?", (warn_id, str(guild_id)))
            await db.commit()

    async def clear_warns(self, user_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM warns WHERE user_id = ? AND guild_id = ?", (str(user_id), str(guild_id)))
            await db.commit()

    async def add_media_feed(self, guild_id, channel_id, category):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO media_feeds (guild_id, channel_id, category) VALUES (?, ?, ?)",
                          (str(guild_id), str(channel_id), category))
            await db.commit()

    async def remove_media_feed(self, feed_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM media_feeds WHERE id = ?", (feed_id,))
            await db.commit()

    async def get_media_feeds(self, guild_id=None):
        async with aiosqlite.connect(self.db_path) as db:
            if guild_id:
                async with db.execute("SELECT id, channel_id, category FROM media_feeds WHERE guild_id = ?", (str(guild_id),)) as cursor:
                    return await cursor.fetchall()
            else:
                async with db.execute("SELECT id, guild_id, channel_id, category FROM media_feeds") as cursor:
                    return await cursor.fetchall()

    async def is_media_sent(self, url):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM sent_media WHERE url = ?", (url,)) as cursor:
                return await cursor.fetchone() is not None

    async def mark_media_sent(self, url):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO sent_media (url) VALUES (?)", (url,))
            await db.commit()

    async def cleanup_sent_media(self, days=7):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM sent_media WHERE timestamp < datetime('now', '-' || ? || ' days')", (days,))
            await db.commit()

    async def set_quote_feed(self, guild_id, channel_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO quote_feeds (guild_id, channel_id) VALUES (?, ?)",
                          (str(guild_id), str(channel_id)))
            await db.commit()

    async def get_quote_feeds(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT guild_id, channel_id FROM quote_feeds") as cursor:
                return await cursor.fetchall()

    async def remove_quote_feed(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM quote_feeds WHERE guild_id = ?", (str(guild_id),))
            await db.commit()

    async def set_log_channel(self, guild_id, channel_id):
        await self.set_guild_setting(guild_id, "log_channel_id", str(channel_id) if channel_id else None)

    async def get_log_channel(self, guild_id):
        return await self.get_guild_setting(guild_id, "log_channel_id", int)

    async def set_mute_role(self, guild_id, role_id):
        await self.set_guild_setting(guild_id, "mute_role_id", str(role_id) if role_id else None)

    async def get_mute_role(self, guild_id):
        return await self.get_guild_setting(guild_id, "mute_role_id", int)

    async def set_guild_setting(self, guild_id, key, value):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"INSERT INTO guild_settings (guild_id, {key}) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET {key} = excluded.{key}", (str(guild_id), value))
            await db.commit()

    async def get_guild_setting(self, guild_id, key, type_cast=None):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(f"SELECT {key} FROM guild_settings WHERE guild_id = ?", (str(guild_id),)) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return type_cast(row[0]) if type_cast else row[0]
                return None

    async def get_all_guild_settings(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (str(guild_id),)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {}

    async def is_guild_premium(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT premium_until FROM guild_settings WHERE guild_id = ?", (str(guild_id),)) as cursor:
                row = await cursor.fetchone()
                if row and row[0] > time.time():
                    return True
                return False

    async def set_guild_premium(self, guild_id, days):
        until = time.time() + (days * 86400)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO guild_settings (guild_id, premium_until) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET premium_until = ?",
                          (str(guild_id), until, until))
            await db.commit()

    # Reaction Roles
    async def add_reaction_role(self, guild_id, message_id, emoji, role_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO reaction_roles (guild_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?)",
                             (str(guild_id), str(message_id), str(emoji), str(role_id)))
            await db.commit()

    async def remove_reaction_role(self, guild_id, message_id, emoji=None):
        async with aiosqlite.connect(self.db_path) as db:
            if emoji:
                await db.execute("DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
                                 (str(guild_id), str(message_id), str(emoji)))
            else:
                await db.execute("DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ?",
                                 (str(guild_id), str(message_id)))
            await db.commit()

    async def get_reaction_role(self, guild_id, message_id, emoji):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT role_id FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
                                 (str(guild_id), str(message_id), str(emoji))) as cursor:
                row = await cursor.fetchone()
                return int(row[0]) if row else None

    async def get_all_reaction_roles(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT message_id, emoji, role_id FROM reaction_roles WHERE guild_id = ?", (str(guild_id),)) as cursor:
                return await cursor.fetchall()

    async def increment_daily_stat(self, guild_id, stat_type):
        async with aiosqlite.connect(self.db_path) as db:
            date = "date('now')"
            await db.execute(f"INSERT INTO daily_stats (guild_id, date, {stat_type}) VALUES (?, date('now'), 1) ON CONFLICT(guild_id, date) DO UPDATE SET {stat_type} = {stat_type} + 1",
                          (str(guild_id),))
            await db.commit()

    async def increment_user_daily_messages(self, user_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO user_daily_activity (user_id, guild_id, date, messages) VALUES (?, ?, date('now'), 1) ON CONFLICT(user_id, guild_id, date) DO UPDATE SET messages = messages + 1",
                          (str(user_id), str(guild_id)))
            await db.commit()

    async def increment_user_daily_voice(self, user_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO user_daily_activity (user_id, guild_id, date, voice_minutes) VALUES (?, ?, date('now'), 1) ON CONFLICT(user_id, guild_id, date) DO UPDATE SET voice_minutes = voice_minutes + 1",
                          (str(user_id), str(guild_id)))
            await db.commit()

    async def get_user_today_stats(self, user_id, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT messages, voice_minutes FROM user_daily_activity WHERE user_id = ? AND guild_id = ? AND date = date('now')",
                               (str(user_id), str(guild_id))) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"messages": row[0], "voice_minutes": row[1]}
                return {"messages": 0, "voice_minutes": 0}

    async def get_user_lookback_stats(self, user_id, guild_id, days=7):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT SUM(messages), SUM(voice_minutes) FROM user_daily_activity WHERE user_id = ? AND guild_id = ? AND date > date('now', '-' || ? || ' days')",
                               (str(user_id), str(guild_id), days)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"messages": row[0] or 0, "voice_minutes": row[1] or 0}
                return {"messages": 0, "voice_minutes": 0}

    async def get_daily_stats(self, guild_id, days=7):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT date, COALESCE(messages, 0), COALESCE(joins, 0), COALESCE(leaves, 0) FROM daily_stats WHERE guild_id = ? ORDER BY date DESC LIMIT ?",
                               (str(guild_id), days)) as cursor:
                return await cursor.fetchall()

    async def get_user_daily_messages(self, user_id, guild_id, days=7):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT date, messages FROM user_daily_activity WHERE user_id = ? AND guild_id = ? ORDER BY date DESC LIMIT ?",
                               (str(user_id), str(guild_id), days)) as cursor:
                return await cursor.fetchall()

    # --- Economy Methods ---
    async def get_balance(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT flower_coins FROM economy WHERE user_id = ?", (str(user_id),)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 500

    async def update_balance(self, user_id, amount):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO economy (user_id, flower_coins) VALUES (?, 500 + ?) ON CONFLICT(user_id) DO UPDATE SET flower_coins = flower_coins + ?",
                          (str(user_id), amount, amount))
            await db.commit()

    async def get_economy_data(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT flower_coins, last_daily, last_rob, premium_until FROM economy WHERE user_id = ?", (str(user_id),)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"coins": row[0], "last_daily": row[1], "last_rob": row[2], "premium_until": row[3]}
                return {"coins": 500, "last_daily": 0, "last_rob": 0, "premium_until": 0}

    async def is_user_premium(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT premium_until FROM economy WHERE user_id = ?", (str(user_id),)) as cursor:
                row = await cursor.fetchone()
                if row and row[0] > time.time():
                    return True
                return False

    async def set_user_premium(self, user_id, days):
        until = time.time() + (days * 86400)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO economy (user_id, premium_until) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET premium_until = ?",
                          (str(user_id), until, until))
            await db.commit()

    async def update_economy_cooldown(self, user_id, cooldown_type, timestamp):
        column = "last_daily" if cooldown_type == "daily" else "last_rob"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"INSERT INTO economy (user_id, {column}) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET {column} = ?",
                          (str(user_id), timestamp, timestamp))
            await db.commit()

    # --- Inventory Methods ---
    async def get_inventory(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT item_id, quantity, rank FROM user_inventory WHERE user_id = ?", (str(user_id),)) as cursor:
                return await cursor.fetchall()

    async def add_item(self, user_id, item_id, quantity=1, rank='Common'):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO user_inventory (user_id, item_id, quantity, rank) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, item_id, rank) DO UPDATE SET quantity = quantity + ?",
                          (str(user_id), item_id, quantity, rank, quantity))
            await db.commit()

    async def remove_item(self, user_id, item_id, quantity=1, rank='Common'):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT quantity FROM user_inventory WHERE user_id = ? AND item_id = ? AND rank = ?", (str(user_id), item_id, rank)) as cursor:
                row = await cursor.fetchone()
                if not row or row[0] < quantity: return False
                
                if row[0] == quantity:
                    await db.execute("DELETE FROM user_inventory WHERE user_id = ? AND item_id = ? AND rank = ?", (str(user_id), item_id, rank))
                else:
                    await db.execute("UPDATE user_inventory SET quantity = quantity - ? WHERE user_id = ? AND item_id = ? AND rank = ?", (quantity, str(user_id), item_id, rank))
            await db.commit()
            return True

    # --- Animal Methods ---
    async def get_user_animals(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT id, animal_type, nickname, level, xp, hp, max_hp, attack, defense, speed, rarity FROM user_animals WHERE user_id = ?", (str(user_id),)) as cursor:
                return await cursor.fetchall()

    async def add_animal(self, user_id, animal_type, nickname, stats, rarity='Common'):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO user_animals (user_id, animal_type, nickname, hp, max_hp, attack, defense, speed, rarity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (str(user_id), animal_type, nickname, stats['hp'], stats['hp'], stats['attack'], stats['defense'], stats['speed'], rarity))
            await db.commit()

    async def update_animal(self, animal_id, updates):
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values())
        values.append(animal_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE user_animals SET {set_clause} WHERE id = ?", values)
            await db.commit()

    # --- Achievement Methods ---
    async def get_achievements(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT achievement_id, timestamp FROM user_achievements WHERE user_id = ?", (str(user_id),)) as cursor:
                return await cursor.fetchall()

    async def add_achievement(self, user_id, achievement_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO user_achievements (user_id, achievement_id) VALUES (?, ?)", (str(user_id), achievement_id))
            await db.commit()

    # --- Quest Methods ---
    async def get_quests(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT quest_id, progress, goal, reward_coins, reward_item, completed FROM user_quests WHERE user_id = ?", (str(user_id),)) as cursor:
                return await cursor.fetchall()

    async def add_quest(self, user_id, quest_id, goal, reward_coins=0, reward_item=None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO user_quests (user_id, quest_id, goal, reward_coins, reward_item) VALUES (?, ?, ?, ?, ?)",
                          (str(user_id), quest_id, goal, reward_coins, reward_item))
            await db.commit()

    async def update_quest_progress(self, user_id, quest_id, amount=1):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT progress, goal, completed, reward_coins, reward_item FROM user_quests WHERE user_id = ? AND quest_id = ?", (str(user_id), quest_id)) as cursor:
                row = await cursor.fetchone()
                if not row or row[2]: return False # Already completed or not found
                
                new_progress = row[0] + amount
                completed = 1 if new_progress >= row[1] else 0
                
                await db.execute("UPDATE user_quests SET progress = ?, completed = ? WHERE user_id = ? AND quest_id = ?", (new_progress, completed, str(user_id), quest_id))
                
                if completed:
                    if row[3] > 0:
                        await db.execute("INSERT INTO economy (user_id, flower_coins) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET flower_coins = flower_coins + ?",
                                      (str(user_id), row[3], row[3]))
                    if row[4]:
                        # Determine rank for reward item
                        item_rank = 'Rare' if row[4] in ['ultra_bait', 'super_petal', 'honey_cake'] else 'Legendary' if row[4] in ['golden_flower', 'excalibur'] else 'Common'
                        await db.execute("INSERT INTO user_inventory (user_id, item_id, quantity, rank) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, item_id, rank) DO UPDATE SET quantity = quantity + ?",
                                      (str(user_id), row[4], 1, item_rank, 1))
                    await db.commit()
                    return "COMPLETED"
                
            await db.commit()
            return True


    # --- Playlist Methods ---
    async def get_playlists(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT playlist_name FROM playlists WHERE user_id = ?", (str(user_id),)) as cursor:
                return [row[0] for row in await cursor.fetchall()]

    async def get_playlist(self, user_id, name):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT songs FROM playlists WHERE user_id = ? AND playlist_name = ?", (str(user_id), name)) as cursor:
                row = await cursor.fetchone()
                return json.loads(row[0]) if row else None

    async def save_playlist(self, user_id, name, songs):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO playlists (user_id, playlist_name, songs) VALUES (?, ?, ?)",
                          (str(user_id), name, json.dumps(songs)))
            await db.commit()

    async def delete_playlist(self, user_id, name):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM playlists WHERE user_id = ? AND playlist_name = ?", (str(user_id), name))
            await db.commit()
