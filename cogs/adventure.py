import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

class Adventure(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.animals_data = {
            "leafy_rabbit": {"name": "Leafy Rabbit", "type": "Grass", "hp": 50, "attack": 10, "defense": 5, "speed": 15, "rarity": "Common"},
            "fire_fox": {"name": "Fire Fox", "type": "Fire", "hp": 45, "attack": 15, "defense": 5, "speed": 12, "rarity": "Common"},
            "water_turtle": {"name": "Water Turtle", "type": "Water", "hp": 60, "attack": 8, "defense": 12, "speed": 5, "rarity": "Common"},
            "electric_mouse": {"name": "Electric Mouse", "type": "Electric", "hp": 40, "attack": 12, "defense": 5, "speed": 20, "rarity": "Uncommon"},
            "ice_wolf": {"name": "Ice Wolf", "type": "Ice", "hp": 55, "attack": 14, "defense": 8, "speed": 14, "rarity": "Uncommon"},
            "magma_slug": {"name": "Magma Slug", "type": "Magma", "hp": 70, "attack": 18, "defense": 10, "speed": 4, "rarity": "Uncommon"},
            "stone_golem": {"name": "Stone Golem", "type": "Rock", "hp": 80, "attack": 10, "defense": 15, "speed": 2, "rarity": "Rare"},
            "thunder_bird": {"name": "Thunder Bird", "type": "Electric", "hp": 65, "attack": 22, "defense": 8, "speed": 25, "rarity": "Rare"},
            "crystal_deer": {"name": "Crystal Deer", "type": "Crystal", "hp": 90, "attack": 15, "defense": 20, "speed": 15, "rarity": "Rare"},
            "shadow_dragon": {"name": "Shadow Dragon", "type": "Shadow", "hp": 100, "attack": 25, "defense": 20, "speed": 18, "rarity": "Legendary"},
            "celestial_phoenix": {"name": "Celestial Phoenix", "type": "Celestial", "hp": 120, "attack": 30, "defense": 25, "speed": 30, "rarity": "Legendary"}
        }

    async def animal_autocomplete(self, interaction: discord.Interaction, current: str):
        animals = await self.db.get_user_animals(interaction.user.id)
        choices = []
        for a in animals:
            # id, animal_type, nickname, level, ...
            a_id, a_type, nick, lvl = a[0], a[1], a[2], a[3]
            name = self.animals_data.get(a_type, {"name": a_type})["name"]
            label = f"{nick} ({name}) Lvl {lvl}"
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=nick))
        return choices[:25]

    @commands.hybrid_command(name="catch", description="Try to catch a wild animal")
    async def catch(self, ctx):
        await ctx.defer()
        # Check if user has bait
        inventory = await self.db.get_inventory(ctx.author.id)
        # Prioritize best bait
        bait_type = None
        for b in ['ultra_bait', 'super_bait', 'bait']:
            if any(item[0] == b for item in inventory):
                bait_type = b
                break
        
        if not bait_type:
            return await ctx.send("❌ You need **Bait** to catch animals! Buy some in the `.shop`.", ephemeral=True)
        
        bait_rank = 'Rare' if bait_type == 'ultra_bait' else 'Uncommon' if bait_type == 'super_bait' else 'Common'
        await self.db.remove_item(ctx.author.id, bait_type, 1, rank=bait_rank)
        
        # Pick a random animal based on rarity
        is_premium = await self.db.is_user_premium(ctx.author.id)
        
        rarity_chances = {"Common": 0.6, "Uncommon": 0.25, "Rare": 0.1, "Legendary": 0.05}
        if bait_type == 'ultra_bait':
            rarity_chances = {"Common": 0.2, "Uncommon": 0.3, "Rare": 0.35, "Legendary": 0.15}
        elif bait_type == 'super_bait':
            rarity_chances = {"Common": 0.4, "Uncommon": 0.35, "Rare": 0.2, "Legendary": 0.05}
        
        if is_premium:
            # Boost higher rarities for premium
            if bait_type == 'ultra_bait':
                rarity_chances = {"Common": 0.1, "Uncommon": 0.2, "Rare": 0.45, "Legendary": 0.25}
            elif bait_type == 'super_bait':
                rarity_chances = {"Common": 0.3, "Uncommon": 0.4, "Rare": 0.2, "Legendary": 0.1}
            else:
                rarity_chances = {"Common": 0.4, "Uncommon": 0.35, "Rare": 0.15, "Legendary": 0.1}
        
        roll = random.random()
        cumulative = 0
        selected_rarity = "Common"
        for rarity, chance in rarity_chances.items():
            cumulative += chance
            if roll <= cumulative:
                selected_rarity = rarity
                break
        
        possible_animals = [k for k, v in self.animals_data.items() if v['rarity'] == selected_rarity]
        animal_id = random.choice(possible_animals)
        animal = self.animals_data[animal_id]
        
        # Catch chance
        catch_roll = random.random()
        catch_chance = 0.7 if bait_type == 'bait' else 0.8 if bait_type == 'super_bait' else 0.95
        if catch_roll <= catch_chance:
            stats = {
                "hp": animal['hp'],
                "attack": animal['attack'] + random.randint(-2, 2),
                "defense": animal['defense'] + random.randint(-2, 2),
                "speed": animal['speed'] + random.randint(-2, 2)
            }
            await self.db.add_animal(ctx.author.id, animal_id, animal['name'], stats, rarity=selected_rarity)
            await ctx.send(f"🎉 Success! You caught a **{animal['name']}** ([{selected_rarity}])!")
            
            if selected_rarity == "Legendary":
                await self.bot.log_action(ctx.guild, "Legendary Catch", f"**{ctx.author}** caught a **Legendary {animal['name']}**!", color=0xf1c40f, user=ctx.author)

            # Dispatch event for achievement
            self.bot.dispatch("animal_catch", ctx.author.id)
            
            # Progress quest if exists
            res = await self.db.update_quest_progress(ctx.author.id, "catch_animals")
            if res == "COMPLETED":
                self.bot.dispatch("quest_completion", ctx.author.id)
        else:
            await ctx.send(f"💨 The wild **{animal['name']}** escaped!")

    @commands.hybrid_command(name="animals", description="List your caught animals")
    async def animals(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        animals = await self.db.get_user_animals(member.id)
        
        if not animals:
            return await ctx.send(f"🐾 {member.display_name} hasn't caught any animals yet.")
        
        embed = discord.Embed(title=f"🐾 {member.display_name}'s Animals", color=0x2ecc71)
        for a in animals:
            # id, animal_type, nickname, level, xp, hp, max_hp, attack, defense, speed, rarity
            a_id, a_type, nick, lvl, xp, hp, mhp, atk, df, spd, rarity = a
            name = self.animals_data[a_type]['name']
            embed.add_field(name=f"{nick} ({name})", value=f"Rank: **{rarity}** | Lvl: {lvl} | HP: {hp}/{mhp} | Atk: {atk} | Def: {df}", inline=True)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="battle", description="Battle against another user or a wild animal")
    async def battle(self, ctx, member: discord.Member = None):
        user_animals = await self.db.get_user_animals(ctx.author.id)
        if not user_animals:
            return await ctx.send("❌ You don't have any animals to battle with!", ephemeral=True)
        
        # Pick first healthy animal
        attacker = next((a for a in user_animals if a[5] > 0), None)
        if not attacker:
            return await ctx.send("❌ All your animals are fainted! Use medicine or rest.", ephemeral=True)
        
        if member:
            if member == ctx.author: return await ctx.send("❌ You can't battle yourself.")
            target_animals = await self.db.get_user_animals(member.id)
            if not target_animals: return await ctx.send(f"❌ {member.display_name} has no animals!")
            defender = next((a for a in target_animals if a[5] > 0), None)
            if not defender: return await ctx.send(f"❌ All of {member.display_name}'s animals are fainted!")
            
            await ctx.send(f"⚔️ {ctx.author.mention} challenged {member.mention} to an animal battle! Type `accept` to battle.")
            def check(m): return m.author == member and m.channel == ctx.channel and m.content.lower() == 'accept'
            try: await self.bot.wait_for('message', check=check, timeout=30.0)
            except asyncio.TimeoutError: return await ctx.send("⏰ Battle request timed out.")
            
            await self.run_battle(ctx, attacker, defender, member)
        else:
            # Wild battle
            wild_id = random.choice(list(self.animals_data.keys()))
            wild_data = self.animals_data[wild_id]
            # Wild defender stats
            defender = (0, wild_id, wild_data['name'], 1, 0, wild_data['hp'], wild_data['hp'], wild_data['attack'], wild_data['defense'], wild_data['speed'], wild_data['rarity'])
            await self.run_battle(ctx, attacker, defender, None)

    async def run_battle(self, ctx, attacker, defender, target_member):
        # attacker/defender: (id, type, nick, lvl, xp, hp, mhp, atk, df, spd, rarity)
        a_nick = attacker[2]
        d_nick = defender[2]
        a_hp = attacker[5]
        d_hp = defender[5]
        
        embed = discord.Embed(title="⚔️ Animal Battle", color=0xe74c3c)
        embed.add_field(name=f"🔺 {a_nick}", value=f"HP: {a_hp}/{attacker[6]}", inline=True)
        embed.add_field(name=f"🔻 {d_nick}", value=f"HP: {d_hp}/{defender[6]}", inline=True)
        msg = await ctx.send(embed=embed)
        
        # Turn-based battle loop
        turn = 0
        while a_hp > 0 and d_hp > 0 and turn < 20:
            await asyncio.sleep(1.5)
            turn += 1
            if turn % 2 != 0: # Attacker turn
                dmg = max(5, attacker[7] - (defender[8] // 2) + random.randint(-2, 5))
                d_hp -= dmg
                log = f"**{a_nick}** attacked **{d_nick}** for **{dmg}** damage!"
            else: # Defender turn
                dmg = max(5, defender[7] - (attacker[8] // 2) + random.randint(-2, 5))
                a_hp -= dmg
                log = f"**{d_nick}** attacked **{a_nick}** for **{dmg}** damage!"
            
            embed.description = log
            embed.set_field_at(0, name=f"🔺 {a_nick}", value=f"HP: {max(0, a_hp)}/{attacker[6]}", inline=True)
            embed.set_field_at(1, name=f"🔻 {d_nick}", value=f"HP: {max(0, d_hp)}/{defender[6]}", inline=True)
            await msg.edit(embed=embed)
        
        winner = None
        if a_hp <= 0:
            winner = target_member or "Wild Animal"
            await ctx.send(f"💀 **{a_nick}** fainted! **{d_nick}** wins!")
            await self.db.update_animal(attacker[0], {"hp": 0})
        else:
            winner = ctx.author
            await ctx.send(f"🏆 **{d_nick}** fainted! **{a_nick}** wins!")
            if defender[0] != 0: # If not wild
                await self.db.update_animal(defender[0], {"hp": 0})
            
            # Dispatch event for achievement
            self.bot.dispatch("battle_win", ctx.author.id)
            
            # Rewards for winner
            reward = random.randint(50, 150)
            await self.bot.update_balance(ctx.author.id, reward)
            await ctx.send(f"<:rose_coin:1533598631612125397> {ctx.author.mention} earned **{reward}** RC!")
            
            # Progress quest if exists
            res = await self.db.update_quest_progress(ctx.author.id, "win_battles")
            if res == "COMPLETED":
                self.bot.dispatch("quest_completion", ctx.author.id)
            
            # Level up logic for attacker
            new_xp = attacker[4] + 20
            new_lvl = attacker[3]
            leveled_up = False
            while new_xp >= 100:
                new_xp -= 100
                new_lvl += 1
                leveled_up = True
            
            if leveled_up:
                await ctx.send(f"✨ **{a_nick}** leveled up to **{new_lvl}**!")
                # Progress quest if exists
                res = await self.db.update_quest_progress(ctx.author.id, "train_animals")
                if res == "COMPLETED":
                    self.bot.dispatch("quest_completion", ctx.author.id)
            
            await self.db.update_animal(attacker[0], {"hp": max(0, a_hp), "xp": new_xp, "level": new_lvl})

    @commands.hybrid_command(name="heal", description="Heal your animal using medicine")
    @app_commands.autocomplete(animal=animal_autocomplete)
    async def heal(self, ctx, animal: str):
        await ctx.defer()
        animal = str(animal)
        
        user_animals = await self.db.get_user_animals(ctx.author.id)
        target_animal = next((a for a in user_animals if a[2].lower() == animal.lower()), None)
        if not target_animal and animal.isdigit():
            target_animal = next((a for a in user_animals if str(a[0]) == animal), None)
            
        if not target_animal: return await ctx.send(f"❌ You don't have an animal named '**{animal}**'.")
        
        animal_id = target_animal[0]
        inventory = await self.db.get_inventory(ctx.author.id)
        if not any(item[0] == 'medicine' for item in inventory):
            return await ctx.send("❌ You don't have any medicine! Buy some in the `.shop`.", ephemeral=True)
        
        if target_animal[5] >= target_animal[6]: return await ctx.send("❌ This animal is already at full HP.")
        
        await self.db.remove_item(ctx.author.id, 'medicine', 1)
        new_hp = min(target_animal[6], target_animal[5] + 50)
        await self.db.update_animal(animal_id, {"hp": new_hp})
        await ctx.send(f"💊 You used medicine on **{target_animal[2]}**. HP is now {new_hp}/{target_animal[6]}.")

    @commands.hybrid_command(name="train", description="Train your animal to gain XP")
    @commands.cooldown(1, 30, commands.BucketType.user)
    @app_commands.autocomplete(animal=animal_autocomplete)
    async def train(self, ctx, animal: str):
        await ctx.defer()
        animal = str(animal)
        
        user_animals = await self.db.get_user_animals(ctx.author.id)
        target_animal = next((a for a in user_animals if a[2].lower() == animal.lower()), None)
        if not target_animal and animal.isdigit():
            target_animal = next((a for a in user_animals if str(a[0]) == animal), None)
            
        if not target_animal: return await ctx.send(f"❌ You don't have an animal named '**{animal}**'.")
        
        animal_id = target_animal[0]
        if target_animal[5] <= 0: return await ctx.send("❌ This animal is fainted! Heal it first.")
        
        # Training takes a bit of HP
        hp_cost = random.randint(5, 15)
        new_hp = max(0, target_animal[5] - hp_cost)
        
        xp_gain = random.randint(20, 50)
        new_xp = target_animal[4] + xp_gain
        new_lvl = target_animal[3]
        leveled_up = False
        while new_xp >= 100:
            new_xp -= 100
            new_lvl += 1
            leveled_up = True
            
        await self.db.update_animal(animal_id, {"hp": new_hp, "xp": new_xp, "level": new_lvl})
        
        msg = f"💪 **{target_animal[2]}** trained hard and gained **{xp_gain}** XP! (Remaining HP: {new_hp}/{target_animal[6]})"
        if leveled_up:
            msg += f"\n✨ **Leveled up to {new_lvl}!**"
            # Progress quest
            res = await self.db.update_quest_progress(ctx.author.id, "train_animals")
            if res == "COMPLETED":
                self.bot.dispatch("quest_completion", ctx.author.id)
                
        await ctx.send(msg)

    @commands.hybrid_command(name="explore", description="Explore the wild for random events and rewards")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def explore(self, ctx):
        await ctx.defer()
        events = [
            {"text": "You found a hidden patch of Rose Flowers!", "reward_coins": random.randint(100, 300)},
            {"text": "You discovered a lost item in the bushes!", "reward_item": random.choice(["petal", "bait", "medicine"])},
            {"text": "A wild animal approached you but ran away, leaving some fur behind.", "reward_item": "petal"},
            {"text": "You tripped and lost some coins...", "reward_coins": -random.randint(20, 50)},
            {"text": "The sun is shining beautifully. You feel refreshed!", "reward_hp": 20},
            {"text": "You found a Rare Flower Petal!", "reward_item": "super_petal"},
            {"text": "You stumbled upon an ancient shrine!", "reward_item": "protein_shake"},
            {"text": "You found a buried treasure chest!", "reward_coins": 1000}
        ]
        
        event = random.choice(events)
        result_text = event['text']
        
        if 'reward_coins' in event:
            await self.bot.update_balance(ctx.author.id, event['reward_coins'])
            result_text += f"\n💰 Result: **{event['reward_coins']}** RC"
        
        if 'reward_item' in event:
            # Determine rank for explore items
            rank = 'Rare' if event['reward_item'] in ['super_petal', 'protein_shake'] else 'Common'
            await self.db.add_item(ctx.author.id, event['reward_item'], 1, rank=rank)
            result_text += f"\n📦 Result: **1x {event['reward_item'].replace('_', ' ').title()}**"
            
        if 'reward_hp' in event:
            animals = await self.db.get_user_animals(ctx.author.id)
            if animals:
                animal = random.choice(animals)
                new_hp = min(animal[6], animal[5] + event['reward_hp'])
                await self.db.update_animal(animal[0], {"hp": new_hp})
                result_text += f"\n💖 Result: **{animal[2]}** recovered some HP!"
        
        await ctx.send(f"🌸 **{ctx.author.display_name}'s Adventure**\n{result_text}")
        
        # Progress quest
        res = await self.db.update_quest_progress(ctx.author.id, "explore_events")
        if res == "COMPLETED":
            self.bot.dispatch("quest_completion", ctx.author.id)

    @commands.hybrid_command(name="revive", description="Revive a fainted animal using a Revive item")
    @app_commands.autocomplete(animal=animal_autocomplete)
    async def revive(self, ctx, animal: str):
        await ctx.defer()
        animal = str(animal)
        
        user_animals = await self.db.get_user_animals(ctx.author.id)
        target_animal = next((a for a in user_animals if a[2].lower() == animal.lower()), None)
        if not target_animal and animal.isdigit():
            target_animal = next((a for a in user_animals if str(a[0]) == animal), None)
            
        if not target_animal: return await ctx.send(f"❌ You don't have an animal named '**{animal}**'.")
        
        animal_id = target_animal[0]
        inventory = await self.db.get_inventory(ctx.author.id)
        if not any(item[0] == 'revive' for item in inventory):
            return await ctx.send("❌ You don't have any Revive! Buy some in the `.shop`.", ephemeral=True)
        
        if target_animal[5] > 0: return await ctx.send("❌ This animal is not fainted.")
        
        await self.db.remove_item(ctx.author.id, 'revive', 1, rank='Rare')
        await self.db.update_animal(animal_id, {"hp": target_animal[6]})
        await ctx.send(f"👼 You used Revive on **{target_animal[2]}**! It's back to full HP.")

    @commands.hybrid_command(name="boost", description="Permanently boost an animal's stats using Protein Shake or Iron Shield")
    @app_commands.autocomplete(animal=animal_autocomplete)
    async def boost(self, ctx, animal: str, item_name: str):
        await ctx.defer()
        animal = str(animal)
        
        user_animals = await self.db.get_user_animals(ctx.author.id)
        target_animal = next((a for a in user_animals if a[2].lower() == animal.lower()), None)
        if not target_animal and animal.isdigit():
            target_animal = next((a for a in user_animals if str(a[0]) == animal), None)
            
        if not target_animal: return await ctx.send(f"❌ You don't have an animal named '**{animal}**'.")
        
        animal_id = target_animal[0]
        item_name = item_name.lower().replace(" ", "_")
        if item_name not in ["protein_shake", "iron_shield"]:
            return await ctx.send("❌ Invalid boost item. Use `protein_shake` or `iron_shield`.", ephemeral=True)
            
        inventory = await self.db.get_inventory(ctx.author.id)
        if not any(item[0] == item_name for item in inventory):
            return await ctx.send(f"❌ You don't have a **{item_name.replace('_', ' ').title()}**!", ephemeral=True)
        
        await self.db.remove_item(ctx.author.id, item_name, 1, rank='Rare')
        
        if item_name == "protein_shake":
            new_val = target_animal[7] + 3
            await self.db.update_animal(animal_id, {"attack": new_val})
            await ctx.send(f"💪 **{target_animal[2]}** drank a Protein Shake! Attack increased to **{new_val}**!")
        else:
            new_val = target_animal[8] + 3
            await self.db.update_animal(animal_id, {"defense": new_val})
            await ctx.send(f"🛡️ **{target_animal[2]}** used an Iron Shield! Defense increased to **{new_val}**!")

    @commands.hybrid_command(name="quest", description="View your current quests")
    async def quest(self, ctx):
        await ctx.defer()
        quests = await self.db.get_quests(ctx.author.id)
        active_quests = [q for q in quests if not q[5]]
        
        if not active_quests:
            # Assign a random quest if none exist or all are completed
            q_types = [
                ("catch_animals", 3, 500, "bait", "Catch 3 Animals"),
                ("win_battles", 5, 1000, "ultra_bait", "Win 5 Battles"),
                ("train_animals", 2, 800, "medicine", "Level Up 2 Animals"),
                ("explore_events", 3, 600, "super_petal", "Explore the Wild 3 times"),
                ("raid_participate", 1, 1500, "ultra_bait", "Participate in 1 Raid")
            ]
            q = random.choice(q_types)
            await self.db.add_quest(ctx.author.id, q[0], q[1], q[2], q[3])
            quests = await self.db.get_quests(ctx.author.id)
        
        embed = discord.Embed(title="📜 Quest Board", color=0xf1c40f)
        embed.add_field(name="Status", value=f"Viewing quests for {ctx.author.display_name}", inline=False)
        for q in quests:
            # quest_id, progress, goal, reward_coins, reward_item, completed
            qid, prog, goal, rc, ri, comp = q
            status = "✅ Completed" if comp else f"Progress: {prog}/{goal}"
            embed.add_field(name=qid.replace("_", " ").title(), value=f"{status}\nReward: {rc} RC <:rose_coin:1533598631612125397>, {ri}", inline=False)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="raid", description="Start a cooperative raid against a boss animal")
    async def raid(self, ctx):
        boss_id = "elder_dragon"
        boss_data = {"name": "Elder Dragon Boss", "hp": 1000, "attack": 40, "defense": 30}
        
        embed = discord.Embed(title="🌋 RAID ALERT: Elder Dragon Appeared!", description="Multiple players can join forces to defeat this beast!", color=0x992d22)
        embed.add_field(name="Boss HP", value=f"❤️ {boss_data['hp']}")
        embed.set_footer(text="React with ⚔️ to join the raid! Starting in 30 seconds.")
        
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("⚔️")
        
        await asyncio.sleep(30)
        
        msg = await ctx.channel.fetch_message(msg.id)
        reaction = discord.utils.get(msg.reactions, emoji="⚔️")
        if not reaction:
            return await ctx.send("😔 No reactions found. The dragon flew away.")
            
        users = [user async for user in reaction.users() if not user.bot]
        
        if not users:
            return await ctx.send("😔 No one joined the raid. The dragon flew away.")
        
        await ctx.send(f"🚀 The raid starts with **{len(users)}** heroes!")
        
        boss_hp = boss_data['hp']
        participants_data = []
        for u in users:
            animals = await self.db.get_user_animals(u.id)
            attacker = next((a for a in animals if a[5] > 0), None)
            if attacker:
                participants_data.append({"user": u, "animal": list(attacker)})
        
        if not participants_data:
            return await ctx.send("❌ None of the participants have healthy animals!")
        
        # Dispatch event for achievement and progress quest
        for p in participants_data:
            u = p['user']
            self.bot.dispatch("raid_participate", u.id)
            res = await self.db.update_quest_progress(u.id, "raid_participate")
            if res == "COMPLETED":
                self.bot.dispatch("quest_completion", u.id)
        
        battle_log = []
        turn = 0
        original_participants_list = [p['user'] for p in participants_data]
        
        while boss_hp > 0 and participants_data and turn < 15:
            turn += 1
            total_damage = 0
            for p in participants_data:
                dmg = max(10, p['animal'][7] - (boss_data['defense'] // 3) + random.randint(0, 10))
                total_damage += dmg
            
            boss_hp -= total_damage
            battle_log.append(f"Turn {turn}: Heroes dealt **{total_damage}** damage!")
            
            if boss_hp <= 0:
                break
            
            # Boss attacks one random participant
            target = random.choice(participants_data)
            boss_dmg = max(15, boss_data['attack'] - (target['animal'][8] // 2))
            new_hp = max(0, target['animal'][5] - boss_dmg)
            target['animal'][5] = new_hp
            await self.db.update_animal(target['animal'][0], {"hp": new_hp})
            
            if new_hp == 0:
                battle_log.append(f"💀 **{target['animal'][2]}** ({target['user'].display_name}) has fainted!")
                # Remove fainted animal from current raid participants
                participants_data = [p for p in participants_data if p['animal'][0] != target['animal'][0]]
            
            await ctx.send(f"📝 **Turn {turn}**: Boss HP: {max(0, boss_hp)}")
            await asyncio.sleep(2)
        
        if boss_hp <= 0:
            reward = 2000 // len(original_participants_list)
            await ctx.send(f"🎉 **VICTORY!** The Elder Dragon has been defeated! Each participant earned **{reward}** RC <:rose_coin:1533598631612125397>!")
            for u in original_participants_list:
                await self.bot.update_balance(u.id, reward)
        else:
            await ctx.send("💀 **DEFEAT!** The boss was too strong. The raid failed.")

    @commands.hybrid_command(name="gift_animal", description="Gift an animal to another user")
    @app_commands.autocomplete(animal=animal_autocomplete)
    async def gift_animal(self, ctx, member: discord.Member, animal: str):
        if member == ctx.author: return await ctx.send("❌ You cannot gift an animal to yourself.", ephemeral=True)
        animal = str(animal)
        
        user_animals = await self.db.get_user_animals(ctx.author.id)
        target_animal = next((a for a in user_animals if a[2].lower() == animal.lower()), None)
        if not target_animal and animal.isdigit():
            target_animal = next((a for a in user_animals if str(a[0]) == animal), None)
            
        if not target_animal:
            return await ctx.send(f"❌ You don't have an animal named '**{animal}**' in your collection.", ephemeral=True)
        
        animal_id = target_animal[0]
        await self.db.update_animal(animal_id, {"user_id": str(member.id)})
        await ctx.send(f"🎁 You gifted **{target_animal[2]}** to {member.mention}!")
        await self.bot.log_action(ctx.guild, "Animal Gifted", f"**{ctx.author}** gifted **{target_animal[2]}** (ID: {animal_id}) to **{member}**.", color=0x9b59b6, moderator=ctx.author, user=member)
        
        # Achievement for trading
        self.bot.dispatch("trade_complete", ctx.author.id)

    @commands.hybrid_command(name="trade_animal", description="Trade an animal with another user")
    @app_commands.autocomplete(animal=animal_autocomplete)
    async def trade_animal(self, ctx, member: discord.Member, animal: str):
        if member == ctx.author: return await ctx.send("❌ You cannot trade with yourself.", ephemeral=True)
        animal = str(animal)
        
        user_animals = await self.db.get_user_animals(ctx.author.id)
        target_animal = next((a for a in user_animals if a[2].lower() == animal.lower()), None)
        if not target_animal and animal.isdigit():
            target_animal = next((a for a in user_animals if str(a[0]) == animal), None)
            
        if not target_animal:
            return await ctx.send(f"❌ You don't have an animal named '**{animal}**'.", ephemeral=True)
        
        await ctx.send(f"🤝 {member.mention}, {ctx.author.mention} wants to trade their **{target_animal[2]}** to you! Type `accept` to confirm.")
        
        def check(m):
            return m.author == member and m.channel == ctx.channel and m.content.lower() == 'accept'
        
        try:
            await self.bot.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await ctx.send("⏰ Trade request timed out.")
            
        # Re-check ownership
        user_animals = await self.db.get_user_animals(ctx.author.id)
        still_owns = any(a[0] == target_animal[0] for a in user_animals)
        if not still_owns:
            return await ctx.send("❌ The animal is no longer in the owner's collection.")

        await self.db.update_animal(target_animal[0], {"user_id": str(member.id)})
        await ctx.send(f"🤝 Trade complete! {member.mention} now owns **{target_animal[2]}**!")
        self.bot.dispatch("trade_complete", ctx.author.id)

    @commands.hybrid_command(name="nickname", description="Give a nickname to your animal")
    @app_commands.autocomplete(animal=animal_autocomplete)
    async def nickname(self, ctx, animal: str, *, new_name: str):
        if len(new_name) > 32:
            return await ctx.send("❌ Nickname too long.", ephemeral=True)
        animal = str(animal)
        
        user_animals = await self.db.get_user_animals(ctx.author.id)
        target_animal = next((a for a in user_animals if a[2].lower() == animal.lower()), None)
        if not target_animal and animal.isdigit():
            target_animal = next((a for a in user_animals if str(a[0]) == animal), None)
            
        if not target_animal:
            return await ctx.send(f"❌ Animal not found.")
            
        await self.db.update_animal(target_animal[0], {"nickname": new_name})
        await ctx.send(f"✅ Your animal is now named **{new_name}**!")

async def setup(bot):
    await bot.add_cog(Adventure(bot))
