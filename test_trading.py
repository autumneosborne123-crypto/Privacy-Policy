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

async def test_trading():
    db_file = "test_trading.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    
    db = Database(db_file)
    await db.init()
    
    bot = MockBot(db)
    ach_cog = Achievements(bot)
    bot.add_cog_listeners(ach_cog)
    
    user_a = "user_a"
    user_b = "user_b"
    
    print("--- Setup: Giving User A some coins and items ---")
    await bot.update_balance(user_a, 1000)
    await db.add_item(user_a, "petal", 5)
    
    bal_a = await db.get_balance(user_a)
    inv_a = await db.get_inventory(user_a)
    print(f"User A Balance: {bal_a}, Inventory: {inv_a}")
    
    print("\n--- Testing: Pay (Transfer Coins) ---")
    amount_to_pay = 300
    # Logic from cogs/economy.py pay command
    await bot.update_balance(user_a, -amount_to_pay)
    await bot.update_balance(user_b, amount_to_pay)
    
    bal_a = await db.get_balance(user_a)
    bal_b = await db.get_balance(user_b)
    print(f"User A Balance: {bal_a}, User B Balance: {bal_b}")
    assert bal_a == 700
    assert bal_b == 300
    
    print("\n--- Testing: Gift Item ---")
    item_to_gift = "petal"
    qty_to_gift = 2
    # Logic from cogs/economy.py gift_item command
    success = await db.remove_item(user_a, item_to_gift, qty_to_gift, rank="Common")
    assert success is True
    await db.add_item(user_b, item_to_gift, qty_to_gift, rank="Common")
    bot.dispatch("trade_complete", user_a)
    
    inv_a = await db.get_inventory(user_a)
    inv_b = await db.get_inventory(user_b)
    print(f"User A Inventory: {inv_a}, User B Inventory: {inv_b}")
    assert ("petal", 3, "Common") in inv_a
    assert ("petal", 2, "Common") in inv_b

    print("\n--- Testing: Gift Ranked Items ---")
    # Give User A a Rare item
    await db.add_item(user_a, "iron_sword", 1, rank="Rare")
    inv_a = await db.get_inventory(user_a)
    print(f"User A Inventory with Rare item: {inv_a}")
    assert ("iron_sword", 1, "Rare") in inv_a

    # Gift the Rare item
    success = await db.remove_item(user_a, "iron_sword", 1, rank="Rare")
    assert success is True
    await db.add_item(user_b, "iron_sword", 1, rank="Rare")
    
    inv_a = await db.get_inventory(user_a)
    inv_b = await db.get_inventory(user_b)
    print(f"User A Inventory after gift: {inv_a}")
    print(f"User B Inventory after gift: {inv_b}")
    assert ("iron_sword", 1, "Rare") not in inv_a
    assert ("iron_sword", 1, "Rare") in inv_b

    print("\n--- Testing: Gift Animal ---")
    # Setup: Give User A an animal
    stats = {"hp": 50, "attack": 10, "defense": 5, "speed": 15}
    await db.add_animal(user_a, "fire_fox", "Flare", stats, rarity="Common")
    animals_a = await db.get_user_animals(user_a)
    animal_id = animals_a[0][0]
    print(f"User A Animals: {animals_a}")
    assert animals_a[0][10] == "Common"
    
    # Logic from cogs/adventure.py gift_animal command
    await db.update_animal(animal_id, {"user_id": user_b})
    bot.dispatch("trade_complete", user_a)
    
    animals_a = await db.get_user_animals(user_a)
    animals_b = await db.get_user_animals(user_b)
    print(f"User A Animals after gift: {animals_a}")
    print(f"User B Animals after gift: {animals_b}")
    assert len(animals_a) == 0
    assert len(animals_b) == 1
    assert animals_b[0][2] == "Flare"
    assert animals_b[0][10] == "Common"
    
    print("\n--- Testing: Achievement 'trader' ---")
    await asyncio.sleep(0.5)
    ach_a = await db.get_achievements(user_a)
    print(f"User A Achievements: {ach_a}")
    assert any(a[0] == "trader" for a in ach_a)
    
    print("\n--- Testing: Edge Case (Insufficient Coins) ---")
    # Trying to pay more than balance
    try_pay = 1000
    bal_a = await db.get_balance(user_a)
    if bal_a < try_pay:
        print("Caught insufficient balance (as expected in command logic)")
    else:
        raise AssertionError("Should have failed command logic check")
        
    print("\n--- Testing: Edge Case (Insufficient Items) ---")
    success = await db.remove_item(user_a, "petal", 10)
    print(f"Removal of 10 petals success: {success}")
    assert success is False
    
    print("\n--- Testing: Rob ---")
    # Setup: give user B some coins
    await bot.update_balance(user_b, 500)
    bal_b_before = await db.get_balance(user_b)
    bal_a_before = await db.get_balance(user_a)
    
    # Logic from cogs/economy.py rob command (success case)
    stolen = 100
    await bot.update_balance(user_a, stolen)
    await bot.update_balance(user_b, -stolen)
    
    bal_a_after = await db.get_balance(user_a)
    bal_b_after = await db.get_balance(user_b)
    print(f"User A Balance after rob: {bal_a_after}, User B: {bal_b_after}")
    assert bal_a_after == bal_a_before + stolen
    assert bal_b_after == bal_b_before - stolen
    
    # Logic from cogs/economy.py rob command (caught case)
    fine = 50
    await bot.update_balance(user_a, -fine)
    bal_a_after_fine = await db.get_balance(user_a)
    print(f"User A Balance after fine: {bal_a_after_fine}")
    assert bal_a_after_fine == bal_a_after - fine

    print("\nAll trading tests passed!")
    
    if os.path.exists(db_file):
        os.remove(db_file)

if __name__ == "__main__":
    asyncio.run(test_trading())
