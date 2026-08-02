import asyncio
import os
from utils.database import Database
from main import FlowerBot

class MockChannel:
    def __init__(self, id):
        self.id = id
        self.sent_messages = []

    async def send(self, content=None, embed=None):
        self.sent_messages.append({"content": content, "embed": embed})
        return True

class MockGuild:
    def __init__(self, id):
        self.id = id
        self.name = "Test Guild"
        self.text_channels = []

class MockUser:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.display_avatar = type('obj', (object,), {'url': 'http://example.com/avatar.png'})
    
    def __str__(self):
        return f"{self.name}#{self.id}"

async def test_audit_log():
    db_file = "test_audit.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    
    db = Database(db_file)
    await db.init()
    
    bot = FlowerBot()
    bot.db = db
    
    guild = MockGuild(123456789)
    log_channel = MockChannel(987654321)
    
    # 1. Set log channel
    await db.set_log_channel(guild.id, log_channel.id)
    stored_channel_id = await db.get_log_channel(guild.id)
    assert stored_channel_id == log_channel.id
    print("Log channel setting: PASSED")
    
    # 2. Mock bot.get_channel
    bot.get_channel = lambda id: log_channel if id == log_channel.id else None
    
    # 3. Test log_action
    moderator = MockUser(1, "Mod")
    user = MockUser(2, "Player")
    
    await bot.log_action(guild, "Test Title", "Test Description", color=0x00ff00, moderator=moderator, user=user)
    
    assert len(log_channel.sent_messages) == 1
    sent_log = log_channel.sent_messages[0]["embed"]
    assert sent_log.title == "Test Title"
    assert sent_log.description == "Test Description"
    assert sent_log.color.value == 0x00ff00
    assert any(f.name == "Moderator" and str(moderator.id) in f.value for f in sent_log.fields)
    assert any(f.name == "User" and str(user.id) in f.value for f in sent_log.fields)
    print("Log action execution: PASSED")
    
    # 4. Test logging with missing channel
    await db.set_log_channel(guild.id, 0) # Disable
    await bot.log_action(guild, "Should not log", "...")
    assert len(log_channel.sent_messages) == 1 # Still 1
    print("Log action disabled: PASSED")

    print("\n--- Additional Trading Tests with Logging Simulation ---")
    # Simulation of Economy.pay with logging
    user_a = MockUser(10, "Alice")
    user_b = MockUser(11, "Bob")
    await db.set_log_channel(guild.id, log_channel.id)
    
    # Mock update_balance
    async def mock_update_balance(uid, amt):
        await db.update_balance(uid, amt)
    bot.update_balance = mock_update_balance
    
    await db.update_balance(user_a.id, 1000)
    
    # Simulate pay command
    amount = 200
    await bot.update_balance(user_a.id, -amount)
    await bot.update_balance(user_b.id, amount)
    await bot.log_action(guild, "BFC Transfer", f"**{user_a}** paid **{amount}** BFC to **{user_b}**.", color=0x3498db, moderator=user_a, user=user_b)
    
    assert len(log_channel.sent_messages) == 2
    transfer_log = log_channel.sent_messages[1]["embed"]
    assert transfer_log.title == "BFC Transfer"
    assert "200" in transfer_log.description
    print("Trading log simulation: PASSED")

    print("\nAll audit log tests passed!")
    
    if os.path.exists(db_file):
        os.remove(db_file)

if __name__ == "__main__":
    asyncio.run(test_audit_log())
