import os
import json
import random
import asyncio
from datetime import datetime, timedelta
from threading import Thread

import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# ==========================================
# 1. FLASK KEEP-ALIVE SERVER (FOR RAILWAY)
# ==========================================
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Vouch Bot is active!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 2. CONFIG & 50 MIDDLEMAN RANKS
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN")

CONFIG = {
    "COOLDOWN_HOURS": 24
}

# 50 Middleman Ranks based on total vouches
MM_RANKS = [
    (1, "Bronze Middleman I"),
    (5, "Bronze Middleman II"),
    (10, "Bronze Middleman III"),
    (15, "Silver Middleman I"),
    (20, "Silver Middleman II"),
    (25, "Silver Middleman III"),
    (30, "Gold Middleman I"),
    (35, "Gold Middleman II"),
    (40, "Gold Middleman III"),
    (50, "Platinum Middleman I"),
    (60, "Platinum Middleman II"),
    (70, "Platinum Middleman III"),
    (80, "Diamond Middleman I"),
    (90, "Diamond Middleman II"),
    (100, "Diamond Middleman III"),
    (120, "Master Middleman I"),
    (140, "Master Middleman II"),
    (160, "Master Middleman III"),
    (180, "Grandmaster Middleman I"),
    (200, "Grandmaster Middleman II"),
    (220, "Grandmaster Middleman III"),
    (250, "Elite Middleman I"),
    (280, "Elite Middleman II"),
    (300, "Elite Middleman III"),
    (330, "Champion Middleman I"),
    (360, "Champion Middleman II"),
    (400, "Champion Middleman III"),
    (450, "Legendary Middleman I"),
    (500, "Legendary Middleman II"),
    (550, "Legendary Middleman III"),
    (600, "Mythic Middleman I"),
    (650, "Mythic Middleman II"),
    (700, "Mythic Middleman III"),
    (750, "Immortal Middleman I"),
    (800, "Immortal Middleman II"),
    (850, "Immortal Middleman III"),
    (900, "Divine Middleman I"),
    (950, "Divine Middleman II"),
    (1000, "Divine Middleman III"),
    (1100, "Apex Trader MM"),
    (1200, "Supreme Trade Guardian"),
    (1300, "Vanguard Middleman"),
    (1400, "Titan Middleman"),
    (1500, "Overlord Middleman"),
    (1700, "Shadow Sovereign MM"),
    (2000, "Eternal Trade Master"),
    (2500, "Celestial Middleman"),
    (3000, "Infinite Trade Lord"),
    (4000, "God-Tier Middleman"),
    (5000, "Celestial Sovereign MM")
]

SERVER_COMMENTS = [
    'Best middleman server out there!',
    'Super fast service, clean deal.',
    '100% safe server, highly recommended!',
    'Vouched for the server, super legit team.',
    'Fast MM deal, smooth transaction.',
    'Great support and instant middleman service.',
    'Safe and trustworthy server for trading.'
]

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

os.makedirs("./data", exist_ok=True)

# Helper Functions
def get_mm_rank(vouch_count):
    current_rank = "Unranked Middleman"
    for threshold, rank_name in MM_RANKS:
        if vouch_count >= threshold:
            current_rank = rank_name
        else:
            break
    return current_rank

def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_files(guild_id):
    return {
        "user_vouches": f"./data/{guild_id}_user_vouches.json",
        "server_vouches": f"./data/{guild_id}_server_vouches.json",
        "config": f"./data/{guild_id}_config.json",
        "server_config": f"./data/{guild_id}_servervouch_config.json",
        "manual_counts": f"./data/{guild_id}_manual_counts.json",
        "webhooks": f"./data/{guild_id}_webhooks.json"
    }

def get_vouch_count(guild_id, user_id):
    files = get_files(guild_id)
    vouches = load_json(files["user_vouches"], [])
    base_count = sum(1 for v in vouches if v.get("to_id") == str(user_id))
    manual = load_json(files["manual_counts"], {})
    return max(0, base_count + manual.get(str(user_id), 0))

def get_server_vouch_count(guild_id):
    files = get_files(guild_id)
    return len(load_json(files["server_vouches"], []))

async def in_cooldown(guild_id, from_id, to_id):
    files = get_files(guild_id)
    vouches = load_json(files["user_vouches"], [])
    cutoff = datetime.utcnow() - timedelta(hours=CONFIG["COOLDOWN_HOURS"])
    for v in vouches:
        if v.get("from_id") == str(from_id) and v.get("to_id") == str(to_id):
            v_time = datetime.fromisoformat(v["time"])
            if v_time > cutoff:
                return True
    return False

# Webhook Handler
async def send_webhook_vouch(guild, channel, embed):
    files = get_files(guild.id)
    webhooks = load_json(files["webhooks"], {})
    
    webhook = None
    if str(channel.id) in webhooks:
        try:
            webhook = await bot.fetch_webhook(webhooks[str(channel.id)]["id"])
        except Exception:
            webhook = None

    if not webhook:
        webhook = await channel.create_webhook(name=f"{guild.name} Vouch Bot")
        webhooks[str(channel.id)] = {"id": webhook.id, "token": webhook.token}
        save_json(files["webhooks"], webhooks)

    await webhook.send(embed=embed, username=f"{guild.name} Vouch System")

# Vouch Messaging Actions
async def send_user_vouch(guild, channel, from_user, to_user, rating, proof=None, is_auto=False):
    files = get_files(guild.id)
    new_vouch_count = get_vouch_count(guild.id, to_user.id) + 1
    user_rank = get_mm_rank(new_vouch_count)
    
    color = discord.Color.green() if rating >= 4 else (discord.Color.gold() if rating >= 3 else discord.Color.red())

    embed = discord.Embed(
        title="✅ VERIFIED USER VOUCH",
        description=f"### **{from_user.display_name}** vouched for **{to_user.display_name}**",
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.set_author(name=f"{guild.name} Vouch System", icon_url=guild.icon.url if guild.icon else None)
    embed.add_field(name="⭐ Rating", value=f"{'⭐' * rating} **{rating}/5**", inline=True)
    embed.add_field(name="📊 Total User Vouches", value=f"**{new_vouch_count}**", inline=True)
    embed.add_field(name="🎖️ Middleman Rank", value=f"🏆 **{user_rank}**", inline=False)
    embed.set_thumbnail(url=to_user.display_avatar.url)
    
    if proof:
        if any(proof.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
            embed.set_image(url=proof)
        else:
            embed.add_field(name="🔗 Proof", value=f"[Click Here]({proof})", inline=False)

    await send_webhook_vouch(guild, channel, embed)

    vouches = load_json(files["user_vouches"], [])
    vouches.append({
        "from_id": str(from_user.id),
        "to_id": str(to_user.id),
        "from_name": from_user.display_name,
        "to_name": to_user.display_name,
        "rating": rating,
        "proof": proof,
        "rank": user_rank,
        "time": datetime.utcnow().isoformat(),
        "auto": 1 if is_auto else 0
    })
    save_json(files["user_vouches"], vouches)

async def send_server_vouch(guild, channel, from_user, rating, comment):
    files = get_files(guild.id)
    total = get_server_vouch_count(guild.id)

    embed = discord.Embed(
        title="🛡️ VERIFIED SERVER VOUCH",
        description=f"### **{from_user.display_name}** vouched for **{guild.name}**",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    embed.set_author(name=f"{guild.name} Middleman Service", icon_url=guild.icon.url if guild.icon else None)
    embed.add_field(name="⭐ Rating", value=f"{'⭐' * rating} **{rating}/5**", inline=True)
    embed.add_field(name="📊 Total Server Vouches", value=f"**{total + 1}**", inline=True)
    embed.add_field(name="💬 Review", value=f"> {comment}", inline=False)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

    await send_webhook_vouch(guild, channel, embed)

    s_vouches = load_json(files["server_vouches"], [])
    s_vouches.append({
        "from_id": str(from_user.id),
        "from_name": from_user.display_name,
        "rating": rating,
        "comment": comment,
        "time": datetime.utcnow().isoformat()
    })
    save_json(files["server_vouches"], s_vouches)

# ==========================================
# 3. BACKGROUND AUTOMATION TASKS
# ==========================================
auto_vouch_tasks = {}
server_vouch_tasks = {}

async def auto_vouch_loop(guild_id):
    files = get_files(guild_id)
    while True:
        try:
            config = load_json(files["config"], {"enabled": False})
            if not config.get("enabled"):
                break

            guild = bot.get_guild(int(guild_id))
            if guild:
                channel = guild.get_channel(int(config["channel_id"]))
                voucher_role = guild.get_role(int(config["voucher_role_id"]))
                target_role = guild.get_role(int(config["target_role_id"]))

                if channel and voucher_role and target_role:
                    vouchers = [m for m in voucher_role.members if not m.bot]
                    targets = [m for m in target_role.members if not m.bot]

                    if vouchers and targets:
                        from_user = random.choice(vouchers)
                        to_user = random.choice(targets)

                        # Prevent self-vouching if user holds both roles
                        if from_user.id == to_user.id and len(vouchers) > 1:
                            vouchers_filtered = [m for m in vouchers if m.id != to_user.id]
                            from_user = random.choice(vouchers_filtered)

                        if from_user.id != to_user.id:
                            rating = random.randint(4, 5)
                            await send_user_vouch(guild, channel, from_user, to_user, rating, is_auto=True)

            min_d = config.get("min_delay", 90)
            max_d = config.get("max_delay", 150)
            await asyncio.sleep(random.randint(min_d, max_d))

        except Exception as e:
            print(f"Auto Vouch Error [{guild_id}]: {e}")
            await asyncio.sleep(60)

async def server_vouch_loop(guild_id):
    files = get_files(guild_id)
    while True:
        try:
            config = load_json(files["server_config"], {"enabled": False})
            if not config.get("enabled"):
                break

            guild = bot.get_guild(int(guild_id))
            if guild:
                channel = guild.get_channel(int(config["channel_id"]))
                role = guild.get_role(int(config["role_id"]))

                if role and channel:
                    eligible_members = [m for m in role.members if not m.bot]
                    if eligible_members:
                        from_user = random.choice(eligible_members)
                        comment = random.choice(SERVER_COMMENTS)
                        await send_server_vouch(guild, channel, from_user, 5, comment)

            min_d = config.get("min_delay", 90)
            max_d = config.get("max_delay", 150)
            await asyncio.sleep(random.randint(min_d, max_d))

        except Exception as e:
            print(f"Server Vouch Error [{guild_id}]: {e}")
            await asyncio.sleep(60)

# ==========================================
# 4. DISCORD SLASH COMMANDS
# ==========================================
@bot.event
async def on_ready():
    print(f"✅ Bot online as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} Slash Commands.")
    except Exception as e:
        print(f"❌ Sync Error: {e}")

    for guild in bot.guilds:
        files = get_files(guild.id)
        
        cfg = load_json(files["config"], {"enabled": False})
        if cfg.get("enabled") and str(guild.id) not in auto_vouch_tasks:
            auto_vouch_tasks[str(guild.id)] = bot.loop.create_task(auto_vouch_loop(str(guild.id)))

        s_cfg = load_json(files["server_config"], {"enabled": False})
        if s_cfg.get("enabled") and str(guild.id) not in server_vouch_tasks:
            server_vouch_tasks[str(guild.id)] = bot.loop.create_task(server_vouch_loop(str(guild.id)))

@bot.tree.command(name="vouch", description="Leave a vouch for a middleman/trader")
@app_commands.describe(user="User to vouch", rating="Rating (1-5)", channel="Target Channel", proof="Link/Image")
@app_commands.choices(rating=[
    app_commands.Choice(name="1 ⭐", value=1),
    app_commands.Choice(name="2 ⭐⭐", value=2),
    app_commands.Choice(name="3 ⭐⭐⭐", value=3),
    app_commands.Choice(name="4 ⭐⭐⭐⭐", value=4),
    app_commands.Choice(name="5 ⭐⭐⭐⭐⭐", value=5),
])
async def vouch(interaction: discord.Interaction, user: discord.Member, rating: app_commands.Choice[int], channel: discord.TextChannel, proof: str = None):
    await interaction.response.defer(ephemeral=True)
    
    if await in_cooldown(interaction.guild.id, interaction.user.id, user.id):
        return await interaction.followup.send("❌ You are on a 24-hour cooldown for vouching this user.")

    await send_user_vouch(interaction.guild, channel, interaction.user, user, rating.value, proof)
    await interaction.followup.send(f"✅ Vouch posted in {channel.mention}")

@bot.tree.command(name="autovouch", description="Start automated user vouches using voucher and target roles")
@app_commands.describe(
    voucher_role="Role for members who GIVE the vouch",
    target_role="Role for members who RECEIVE the vouch (e.g. Middleman)",
    channel="Channel to post embeds",
    min_delay="Minimum time delay in seconds (Default: 90)",
    max_delay="Maximum time delay in seconds (Default: 150)"
)
async def autovouch(
    interaction: discord.Interaction, 
    voucher_role: discord.Role, 
    target_role: discord.Role, 
    channel: discord.TextChannel,
    min_delay: int = 90,
    max_delay: int = 150
):
    await interaction.response.defer(ephemeral=True)

    if min_delay <= 0 or max_delay <= 0 or min_delay > max_delay:
        return await interaction.followup.send("❌ Invalid delay times. Ensure `min_delay` is greater than 0 and less than or equal to `max_delay`.")

    files = get_files(interaction.guild.id)
    cfg = {
        "enabled": True, 
        "voucher_role_id": str(voucher_role.id), 
        "target_role_id": str(target_role.id), 
        "channel_id": str(channel.id),
        "min_delay": min_delay,
        "max_delay": max_delay
    }
    save_json(files["config"], cfg)

    gid = str(interaction.guild.id)
    if gid in auto_vouch_tasks:
        auto_vouch_tasks[gid].cancel()
    auto_vouch_tasks[gid] = bot.loop.create_task(auto_vouch_loop(gid))

    await interaction.followup.send(
        f"✅ **Auto Vouch Enabled!**\n"
        f"• **Voucher Role:** {voucher_role.mention}\n"
        f"• **Target Role:** {target_role.mention}\n"
        f"• **Channel:** {channel.mention}\n"
        f"• **Delay Range:** {min_delay}s to {max_delay}s"
    )

@bot.tree.command(name="stopautovouch", description="Stop user auto vouch")
async def stopautovouch(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    files = get_files(interaction.guild.id)
    cfg = load_json(files["config"], {})
    cfg["enabled"] = False
    save_json(files["config"], cfg)
    
    if gid in auto_vouch_tasks:
        auto_vouch_tasks[gid].cancel()
        del auto_vouch_tasks[gid]

    await interaction.response.send_message("🛑 User Auto Vouch stopped.", ephemeral=True)

@bot.tree.command(name="servervouch", description="Start automated server vouches with custom delay")
@app_commands.describe(
    role="Role of members to give server reviews",
    channel="Channel to post embeds",
    min_delay="Minimum time delay in seconds (Default: 90)",
    max_delay="Maximum time delay in seconds (Default: 150)"
)
async def servervouch(
    interaction: discord.Interaction, 
    role: discord.Role, 
    channel: discord.TextChannel,
    min_delay: int = 90,
    max_delay: int = 150
):
    await interaction.response.defer(ephemeral=True)

    if min_delay <= 0 or max_delay <= 0 or min_delay > max_delay:
        return await interaction.followup.send("❌ Invalid delay times. Ensure `min_delay` is greater than 0 and less than or equal to `max_delay`.")

    files = get_files(interaction.guild.id)
    cfg = {
        "enabled": True, 
        "role_id": str(role.id), 
        "channel_id": str(channel.id),
        "min_delay": min_delay,
        "max_delay": max_delay
    }
    save_json(files["server_config"], cfg)

    gid = str(interaction.guild.id)
    if gid in server_vouch_tasks:
        server_vouch_tasks[gid].cancel()
    server_vouch_tasks[gid] = bot.loop.create_task(server_vouch_loop(gid))

    await interaction.followup.send(
        f"✅ **Server Vouch Enabled!**\n"
        f"• **Reviewer Role:** {role.mention}\n"
        f"• **Channel:** {channel.mention}\n"
        f"• **Delay Range:** {min_delay}s to {max_delay}s"
    )

@bot.tree.command(name="stopservervouch", description="Stop server vouch")
async def stopservervouch(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    files = get_files(interaction.guild.id)
    cfg = load_json(files["server_config"], {})
    cfg["enabled"] = False
    save_json(files["server_config"], cfg)

    if gid in server_vouch_tasks:
        server_vouch_tasks[gid].cancel()
        del server_vouch_tasks[gid]

    await interaction.response.send_message("🛑 Server Vouch stopped.", ephemeral=True)

@bot.tree.command(name="setvouch", description="Modify user vouches (Admin Only)")
@app_commands.choices(action=[
    app_commands.Choice(name="Set Exact Value", value="set"),
    app_commands.Choice(name="Add Vouches", value="add"),
    app_commands.Choice(name="Remove Vouches", value="remove")
])
async def setvouch(interaction: discord.Interaction, user: discord.Member, action: app_commands.Choice[str], amount: int):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)

    files = get_files(interaction.guild.id)
    manual = load_json(files["manual_counts"], {})
    cur_adj = manual.get(str(user.id), 0)

    if action.value == "set":
        base = sum(1 for v in load_json(files["user_vouches"], []) if v.get("to_id") == str(user.id))
        manual[str(user.id)] = amount - base
    elif action.value == "add":
        manual[str(user.id)] = cur_adj + amount
    elif action.value == "remove":
        manual[str(user.id)] = cur_adj - amount

    save_json(files["manual_counts"], manual)
    new_total = get_vouch_count(interaction.guild.id, user.id)
    new_rank = get_mm_rank(new_total)
    await interaction.response.send_message(f"✅ Updated **{user.display_name}** total vouches to **{new_total}** (Rank: **{new_rank}**)", ephemeral=True)

@bot.tree.command(name="vouches", description="Check user vouches and current Middleman Rank")
async def vouches(interaction: discord.Interaction, user: discord.Member):
    count = get_vouch_count(interaction.guild.id, user.id)
    rank = get_mm_rank(count)
    await interaction.response.send_message(f"📊 **{user.display_name}** has **{count}** total vouches.\n🏆 **Middleman Rank:** {rank}", ephemeral=True)

@bot.tree.command(name="leaderboard", description="Top 10 vouched users")
async def leaderboard(interaction: discord.Interaction):
    counts = {}
    for m in interaction.guild.members:
        cnt = get_vouch_count(interaction.guild.id, m.id)
        if cnt > 0:
            counts[m.id] = cnt

    sorted_list = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    description = "\n".join([f"**#{i+1}** <@{user_id}> - **{cnt}** vouches (🏆 {get_mm_rank(cnt)})" for i, (user_id, cnt) in enumerate(sorted_list)]) or "No vouches recorded."

    embed = discord.Embed(title=f"🏆 {interaction.guild.name} Middleman Leaderboard", description=description, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

# ==========================================
# 5. ENTRY POINT
# ==========================================
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
