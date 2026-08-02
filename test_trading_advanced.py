import asyncio
import os
from utils.database import Database
from cogs.achievements import Achievements

class MockBot:
    def __init__(self, db):
        self.db = db
        self.listeners = {}

    def dispatch(self, event_name, *args):
        func_name = f"on_{event_name}"
        if func_name in self.listeners:
            for listener in self.listeners[func_name]:
                asyncio.create_task(listener(*args))

    def add_cog_listeners(self, cog):
        for name in dir(cog):
            if name.startswith("on_"):
                if name not in self.listeners:
                    self.listeners[name] = []
                self.listeners[name].append(getattr(cog, name))
    
    async def update_balance(self, user_id, amount):
        await self.db.update_balance(user_id, amount)
        new_balance = await self.db.get_balance(user_id)
        self.dispatch("balance_change", user_id, new_balance)
        return new_balance

async def test_trading_advanced():
    db_file = "test_trading_adv.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    
    db = Database(db_file)
    await db.init()
    
    bot = MockBot(db)
    ach_cog = Achievements(bot)
    bot.add_cog_listeners(ach_cog)
    
    user_a = "user_a"
    user_b = "user_b"
    user_c = "user_c"
    
    print("--- Test 1: Multi-User Gift Chain ---")
    await db.add_item(user_a, "apple", 1, rank="Common")
    # A -> B
    success = await db.remove_item(user_a, "apple", 1, rank="Common")
    assert success is True
    await db.add_item(user_b, "apple", 1, rank="Common")
    # B -> C
    success = await db.remove_item(user_b, "apple", 1, rank="Common")
    assert success is True
    await db.add_item(user_c, "apple", 1, rank="Common")
    
    inv_a = await db.get_inventory(user_a)
    inv_b = await db.get_inventory(user_b)
    inv_c = await db.get_inventory(user_c)
    assert len(inv_a) == 0
    assert len(inv_b) == 0
    assert ("apple", 1, "Common") in inv_c
    print("Multi-User Gift Chain: PASSED")

    print("\n--- Test 2: Rank Stacking ---")
    await db.add_item(user_a, "wooden_sword", 1, rank="Common")
    await db.add_item(user_b, "wooden_sword", 1, rank="Common")
    # A gifts to B
    success = await db.remove_item(user_a, "wooden_sword", 1, rank="Common")
    assert success is True
    await db.add_item(user_b, "wooden_sword", 1, rank="Common")
    
    inv_b = await db.get_inventory(user_b)
    print(f"User B Inventory after stacking: {inv_b}")
    assert ("wooden_sword", 2, "Common") in inv_b
    print("Rank Stacking: PASSED")

    print("\n--- Test 3: Rank Distinction ---")
    await db.add_item(user_a, "wooden_sword", 1, rank="Rare")
    # B already has 2 Common. Now A gifts 1 Rare.
    success = await db.remove_item(user_a, "wooden_sword", 1, rank="Rare")
    assert success is True
    await db.add_item(user_b, "wooden_sword", 1, rank="Rare")
    
    inv_b = await db.get_inventory(user_b)
    print(f"User B Inventory after distinction: {inv_b}")
    assert ("wooden_sword", 2, "Common") in inv_b
    assert ("wooden_sword", 1, "Rare") in inv_b
    print("Rank Distinction: PASSED")

    print("\n--- Test 4: Animal Rarity Persistence ---")
    stats = {"hp": 100, "attack": 25, "defense": 20, "speed": 30}
    await db.add_animal(user_a, "thunder_hawk", "Zeus", stats, rarity="Legendary")
    animals_a = await db.get_user_animals(user_a)
    animal_id = animals_a[0][0]
    assert animals_a[0][10] == "Legendary"
    
    # Gift Zeus to User C
    await db.update_animal(animal_id, {"user_id": user_c})
    
    animals_c = await db.get_user_animals(user_c)
    print(f"User C Animals: {animals_c}")
    assert animals_c[0][2] == "Zeus"
    assert animals_c[0][10] == "Legendary"
    print("Animal Rarity Persistence: PASSED")

    print("\n--- Test 5: Negative Case (Rank Specificity) ---")
    # User A has no items now. Let's give them a Common iron sword.
    await db.add_item(user_a, "iron_sword", 1, rank="Common")
    # Try to gift Rare iron sword
    success = await db.remove_item(user_a, "iron_sword", 1, rank="Rare")
    assert success is False
    print("Rank Specificity Removal: PASSED")

    print("\n--- Test 6: Achievement for Multiple Trades across Users ---")
    bot.dispatch("trade_complete", user_a)
    bot.dispatch("trade_complete", user_a)
    bot.dispatch("trade_complete", user_a)
    
    await asyncio.sleep(0.5)
    ach_a = await db.get_achievements(user_a)
    print(f"User A Achievements: {ach_a}")
    assert any(a[0] == "trader" for a in ach_a)
    print("Achievement Trigger: PASSED")

    print("\nAll advanced trading tests passed!")
    
    if os.path.exists(db_file):
        os.remove(db_file)

if __name__ == "__main__":
    asyncio.run(test_trading_advanced())
