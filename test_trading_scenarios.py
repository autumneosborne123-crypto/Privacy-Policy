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

async def test_trading_scenarios():
    db_file = "test_trading_scen.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    
    db = Database(db_file)
    await db.init()
    
    bot = MockBot(db)
    ach_cog = Achievements(bot)
    bot.add_cog_listeners(ach_cog)
    
    user_a = "user_a"
    user_b = "user_b"
    
    print("--- Scenario 1: Bulk Multi-Item Transfer ---")
    items_to_give = [
        ("wood", 10, "Common"),
        ("stone", 5, "Rare"),
        ("iron", 2, "Epic")
    ]
    for item, qty, rank in items_to_give:
        await db.add_item(user_a, item, qty, rank=rank)
    
    # Simulate gifting all
    for item, qty, rank in items_to_give:
        success = await db.remove_item(user_a, item, qty, rank=rank)
        assert success is True
        await db.add_item(user_b, item, qty, rank=rank)
    
    inv_b = await db.get_inventory(user_b)
    # inv_b is list of (item_id, quantity, rank)
    assert len(inv_b) == 3
    assert ("wood", 10, "Common") in inv_b
    assert ("stone", 5, "Rare") in inv_b
    assert ("iron", 2, "Epic") in inv_b
    print("Bulk Multi-Item Transfer: PASSED")

    print("\n--- Scenario 2: Partial Transfer & Exhaustion ---")
    await db.add_item(user_a, "gold", 10, rank="Legendary")
    # Give 3
    success = await db.remove_item(user_a, "gold", 3, rank="Legendary")
    assert success is True
    await db.add_item(user_b, "gold", 3, rank="Legendary")
    
    inv_a = await db.get_inventory(user_a)
    assert ("gold", 7, "Legendary") in inv_a
    
    # Give remaining 7
    success = await db.remove_item(user_a, "gold", 7, rank="Legendary")
    assert success is True
    await db.add_item(user_b, "gold", 7, rank="Legendary")
    
    inv_a = await db.get_inventory(user_a)
    # Check that gold is gone from A
    assert not any(i[0] == "gold" for i in inv_a)
    inv_b = await db.get_inventory(user_b)
    assert ("gold", 10, "Legendary") in inv_b
    print("Partial Transfer & Exhaustion: PASSED")

    print("\n--- Scenario 3: Simultaneous Transfers (Race Condition Check) ---")
    # Reset balances
    await db.update_balance(user_a, -await db.get_balance(user_a))
    await db.update_balance(user_b, -await db.get_balance(user_b))
    await db.update_balance(user_a, 1000)
    
    # A gives 100 to B 5 times simultaneously
    async def give_coins():
        # Note: In real bot, update_balance is called twice (one - and one +)
        # We simulate the pay command logic
        await db.update_balance(user_a, -100)
        await db.update_balance(user_b, 100)
    
    await asyncio.gather(*(give_coins() for _ in range(5)))
    
    bal_a = await db.get_balance(user_a)
    bal_b = await db.get_balance(user_b)
    assert bal_a == 500
    assert bal_b == 500
    print("Simultaneous Transfers: PASSED")

    print("\n--- Scenario 4: Trading Invalid Animal ID ---")
    # Try to update an animal that doesn't exist
    await db.update_animal(999, {"user_id": user_b})
    animals_b = await db.get_user_animals(user_b)
    assert len(animals_b) == 0
    print("Trading Invalid Animal: PASSED")

    print("\n--- Scenario 5: Self-Trading (Gifting to self) ---")
    await db.add_item(user_a, "mirror", 1, rank="Common")
    # remove and add back
    success = await db.remove_item(user_a, "mirror", 1, rank="Common")
    assert success is True
    await db.add_item(user_a, "mirror", 1, rank="Common")
    inv_a = await db.get_inventory(user_a)
    assert ("mirror", 1, "Common") in inv_a
    print("Self-Trading: PASSED")

    print("\n--- Scenario 7: Gifting Animal You Don't Own ---")
    await db.add_animal(user_a, "leafy_rabbit", "Bugs", {"hp": 50, "attack": 10, "defense": 5, "speed": 10}, rarity="Common")
    animals_a = await db.get_user_animals(user_a)
    animal_id = animals_a[0][0]
    
    # Try to gift someone else's animal (simulated by updating animal not in inventory)
    # The command logic usually checks ownership first.
    # Here we check if update_animal with a specific filter works if we were to add it, 
    # but currently update_animal just takes ID.
    # The cog logic: animal = next((a for a in animals if a[0] == animal_id), None)
    # So if animal_id is not in user_a's animals, it fails.
    
    animals_b = await db.get_user_animals(user_b)
    # user_b has no animals. user_a has animal_id.
    # simulate user_b trying to gift animal_id
    animals_of_b = await db.get_user_animals(user_b)
    animal_to_gift = next((a for a in animals_of_b if a[0] == animal_id), None)
    assert animal_to_gift is None
    print("Gifting Unowned Animal (Logic Check): PASSED")

    print("\n--- Scenario 8: Gifting Non-Existent Rank ---")
    await db.add_item(user_a, "stone", 5, rank="Rare")
    success = await db.remove_item(user_a, "stone", 1, rank="Legendary")
    assert success is False
    print("Gifting Non-Existent Rank: PASSED")

    print("\n--- Scenario 9: Highwayman Achievement ---")
    bot.dispatch("rob_success", user_a)
    await asyncio.sleep(0.5)
    ach_a = await db.get_achievements(user_a)
    assert any(a[0] == "highwayman" for a in ach_a)
    print("Highwayman Achievement: PASSED")

    print("\nAll trading scenarios passed!")
    
    if os.path.exists(db_file):
        os.remove(db_file)

if __name__ == "__main__":
    asyncio.run(test_trading_scenarios())
