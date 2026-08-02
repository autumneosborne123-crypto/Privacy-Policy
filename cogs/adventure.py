import discord
from discord.ext import commands
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
            "stone_golem": {"name": "Stone Golem", "type": "Rock", "hp": 80, "attack": 10, "defense": 15, "speed": 2, "rarity": "Rare"},
            "shadow_dragon": {"name": "Shadow Dragon", "type": "Shadow", "hp": 100, "attack": 25, "defense": 20, "speed": 18, "rarity": "Legendary"}
        }

    @commands.hybrid_command(name="catch", description="Try to catch a wild animal")
    async def catch(self, ctx):
        # Check if user has bait
        inventory = await self.db.get_inventory(ctx.author.id)
        has_bait = any(item[0] == 'bait' or item[0] == 'ultra_bait' for item in inventory)
        
        if not has_bait:
            return await ctx.send("❌ You need **Bait** to catch animals! Buy some in the `.shop`.", ephemeral=True)
        
        # Determine bait used (prefer ultra_bait if both exist?)
        bait_type = 'ultra_bait' if any(item[0] == 'ultra_bait' for item in inventory) else 'bait'
        bait_rank = 'Rare' if bait_type == 'ultra_bait' else 'Common'
        await self.db.remove_item(ctx.author.id, bait_type, 1, rank=bait_rank)
        
        # Pick a random animal based on rarity
        is_premium = await self.db.is_user_premium(ctx.author.id)
        
        rarity_chances = {"Common": 0.6, "Uncommon": 0.25, "Rare": 0.1, "Legendary": 0.05}
        if bait_type == 'ultra_bait':
            rarity_chances = {"Common": 0.3, "Uncommon": 0.3, "Rare": 0.25, "Legendary": 0.15}
        
        if is_premium:
            # Boost higher rarities for premium
            if bait_type == 'ultra_bait':
                rarity_chances = {"Common": 0.15, "Uncommon": 0.25, "Rare": 0.35, "Legendary": 0.25}
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
        catch_chance = 0.7 if bait_type == 'bait' else 0.9
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
            embed.add_field(name=f"[{a_id}] {nick} ({name})", value=f"Rank: **{rarity}** | Lvl: {lvl} | HP: {hp}/{mhp} | Atk: {atk} | Def: {df}", inline=True)
        
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
            await ctx.send(f"🔵🌹 {ctx.author.mention} earned **{reward}** BFC!")
            
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
            
            await self.db.update_animal(attacker[0], {"hp": max(0, a_hp), "xp": new_xp, "level": new_lvl})

    @commands.hybrid_command(name="heal", description="Heal your animal using medicine")
    async def heal(self, ctx, animal_id: int):
        inventory = await self.db.get_inventory(ctx.author.id)
        if not any(item[0] == 'medicine' for item in inventory):
            return await ctx.send("❌ You don't have any medicine! Buy some in the `.shop`.", ephemeral=True)
        
        animals = await self.db.get_user_animals(ctx.author.id)
        animal = next((a for a in animals if a[0] == animal_id), None)
        if not animal: return await ctx.send("❌ Animal not found.")
        
        if animal[5] >= animal[6]: return await ctx.send("❌ This animal is already at full health.")
        
        await self.db.remove_item(ctx.author.id, 'medicine', 1)
        new_hp = min(animal[6], animal[5] + 50)
        await self.db.update_animal(animal_id, {"hp": new_hp})
        await ctx.send(f"💊 You used medicine on **{animal[2]}**. HP is now {new_hp}/{animal[6]}.")

    @commands.hybrid_command(name="quest", description="View your current quests")
    async def quest(self, ctx):
        quests = await self.db.get_quests(ctx.author.id)
        active_quests = [q for q in quests if not q[5]]
        
        if not active_quests:
            # Assign a random quest if none exist or all are completed
            q_types = [
                ("catch_animals", 3, 500, "bait", "Catch 3 Animals"),
                ("win_battles", 5, 1000, "ultra_bait", "Win 5 Battles")
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
            embed.add_field(name=qid.replace("_", " ").title(), value=f"{status}\nReward: {rc} BFC 🔵🌹, {ri}", inline=False)
        
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
        
        battle_log = []
        turn = 0
        original_participants = [p['user'] for p in participants_data]
        
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
            reward = 2000 // len(original_participants)
            await ctx.send(f"🎉 **VICTORY!** The Elder Dragon has been defeated! Each participant earned **{reward}** BFC 🔵🌹!")
            for u in original_participants:
                await self.bot.update_balance(u.id, reward)
        else:
            await ctx.send("💀 **DEFEAT!** The boss was too strong. The raid failed.")

    @commands.hybrid_command(name="gift_animal", description="Gift an animal to another user")
    async def gift_animal(self, ctx, member: discord.Member, animal_id: int):
        if member == ctx.author: return await ctx.send("❌ You cannot gift an animal to yourself.", ephemeral=True)
        
        animals = await self.db.get_user_animals(ctx.author.id)
        animal = next((a for a in animals if a[0] == animal_id), None)
        if not animal:
            return await ctx.send("❌ Animal not found in your collection.", ephemeral=True)
        
        await self.db.update_animal(animal_id, {"user_id": str(member.id)})
        await ctx.send(f"🎁 You gifted **{animal[2]}** to {member.mention}!")
        await self.bot.log_action(ctx.guild, "Animal Gifted", f"**{ctx.author}** gifted **{animal[2]}** (ID: {animal_id}) to **{member}**.", color=0x9b59b6, moderator=ctx.author, user=member)
        
        # Achievement for trading
        self.bot.dispatch("trade_complete", ctx.author.id)

async def setup(bot):
    await bot.add_cog(Adventure(bot))
