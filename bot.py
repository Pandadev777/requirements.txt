import discord
from discord.ext import commands, tasks
import json, os, random, asyncio
from datetime import datetime
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "MM Bot Running - Safe Mode"
Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)
DATA_FILE = "mm_data.json"

RANKS = [
    (0, "🥚 Beginner"), (5, "🌱 Newbie MM"), (10, "🛡️ Trusted"), (20, "⭐ Rising MM"),
    (30, "🔥 Skilled MM"), (40, "💎 Elite MM"), (50, "👑 Pro MM"), (60, "⚡ Super MM"),
    (75, "🌟 Legendary MM"), (90, "🚀 Godly MM"), (110, "💀 Mythic MM"), (130, "🎯 Master MM"),
    (150, "🏆 Champion MM"), (175, "💫 Celestial MM"), (200, "🔱 Immortal MM"),
    (225, "🌌 Void MM"), (250, "🐉 Dragon MM"), (275, "👁️ Abyss MM"), (300, "⚔️ Warlord MM"),
    (325, "🧠 Sage MM"), (350, "🌀 Phantom MM"), (375, "🦁 Beast MM"), (400, "☠️ Reaper MM"),
    (425, "🔮 Oracle MM"), (450, "🏅 Hall of Fame"), (475, "💈 Supreme MM"), (500, "👑 Emperor MM"),
    (550, "🌠 Cosmic MM"), (600, "🗡️ Overlord MM"), (650, "🧬 Eternal MM"), (700, "🪐 Galaxy MM"),
    (750, "🎖️ Titan MM"), (800, "🦾 Ultra MM"), (850, "🌋 Inferno MM"), (900, "❄️ Frost MM"),
    (950, "⚡ Thunder MM"), (1000, "🌪️ Storm MM"), (1100, "🌊 Tsunami MM"), (1200, "🔥 Phoenix MM"),
    (1300, "💀 Deathless MM"), (1400, "👑 King of MM"), (1500, "🌌 Universe MM"), (1600, "🧿 Divine MM"),
    (1750, "♾️ Infinity MM"), (1900, "🕳️ Void King"), (2000, "🔱 The One"), (2250, "🏆 GOAT MM"),
    (2500, "💎 Diamond GOAT"), (3000, "🌟 Star GOAT"), (4000, "🚀 Legend GOAT"), (5000, "👑 GOD OF MM")
]

def get_rank(c):
    r = RANKS[0][1]
    for req, name in RANKS:
        if c >= req: r = name
        else: break
    return r

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "server": 0, "config": {"autovouch_user": {}, "autoserver": {}}}
    with open(DATA_FILE, 'r') as f: return json.load(f)

def save_data(d):
    with open(DATA_FILE, 'w') as f: json.dump(d, f, indent=4)

def stars(r): return "⭐" * r + "☆" * (5-r) + f" ({r}/5)"

# SAFE DELAY LIMITS
MIN_USER_DELAY = 90   # 90 sec minimum - no more 429
MIN_SERVER_DELAY = 180 # 3 min minimum

@bot.hybrid_command(name="vouch", description="Vouch a middleman")
async def vouch(ctx, member: discord.Member, rating: int, *, trade_details: str = "Legit MM"):
    if not 1 <= rating <= 5: return await ctx.send("❌ Rating 1-5 only", ephemeral=True)
    if member.id == ctx.author.id: return await ctx.send("❌ No self-vouch!", ephemeral=True)
    data = load_data()
    uid = str(member.id)
    if uid not in data["users"]: data["users"][uid] = {"count":0, "ratings":[], "history":[]}
    data["users"][uid]["count"] += 1
    data["users"][uid]["ratings"].append(rating)
    save_data(data)
    total = data["users"][uid]["count"]
    await ctx.send(f"✅ {member.mention} got **+1 Vouch!** Total: **{total}** | {get_rank(total)} {stars(rating)}")

@bot.hybrid_command(name="autovouch_user", description="Start auto user vouch - safe mode")
@commands.has_permissions(administrator=True)
async def autovouch_user(ctx, voucher_role: discord.Role, target_role: discord.Role, delay_seconds: int = 90):
    if delay_seconds < MIN_USER_DELAY:
        delay_seconds = MIN_USER_DELAY
        await ctx.send(f"⚠️ Delay too low! Set to safe minimum: {MIN_USER_DELAY}s to avoid 429", ephemeral=True)
    data = load_data()
    data["config"]["autovouch_user"] = {"guild_id":ctx.guild.id,"channel_id":ctx.channel.id,"voucher_role_id":voucher_role.id,"target_role_id":target_role.id,"delay":delay_seconds,"active":True}
    save_data(data)
    if auto_vouch_loop.is_running(): auto_vouch_loop.stop()
    auto_vouch_loop.change_interval(seconds=delay_seconds)
    auto_vouch_loop.start()
    await ctx.send(embed=discord.Embed(title="🤖 Auto User Vouch ON [SAFE]", description=f"From: {voucher_role.mention} -> To: {target_role.mention}\nDelay: **{delay_seconds}s** (Anti-429)\nRating: 3-5⭐", color=discord.Color.blue()))

@bot.hybrid_command(name="autoserver_vouch", description="Start auto server vouch - safe mode")
@commands.has_permissions(administrator=True)
async def autoserver_vouch(ctx, delay_seconds: int = 180):
    if delay_seconds < MIN_SERVER_DELAY:
        delay_seconds = MIN_SERVER_DELAY
        await ctx.send(f"⚠️ Delay too low! Set to safe minimum: {MIN_SERVER_DELAY}s to avoid 429", ephemeral=True)
    data = load_data()
    data["config"]["autoserver"] = {"guild_id":ctx.guild.id,"channel_id":ctx.channel.id,"delay":delay_seconds,"active":True}
    save_data(data)
    if auto_server_loop.is_running(): auto_server_loop.stop()
    auto_server_loop.change_interval(seconds=delay_seconds)
    auto_server_loop.start()
    await ctx.send(embed=discord.Embed(title="🏢 Auto Server Vouch ON [SAFE]", description=f"Delay: **{delay_seconds}s** (Anti-429)", color=discord.Color.purple()))

@bot.hybrid_command(name="stopautovouch", description="Stop auto vouches")
@commands.has_permissions(administrator=True)
async def stopautovouch(ctx, type: str = "all"):
    data = load_data()
    stopped = []
    if type.lower() in ["all", "user"]:
        data["config"]["autovouch_user"] = {}
        if auto_vouch_loop.is_running(): auto_vouch_loop.stop()
        stopped.append("User")
    if type.lower() in ["all", "server"]:
        data["config"]["autoserver"] = {}
        if auto_server_loop.is_running(): auto_server_loop.stop()
        stopped.append("Server")
    save_data(data)
    await ctx.send(embed=discord.Embed(title="🛑 Stopped", description=f"Stopped: {', '.join(stopped) if stopped else 'Nothing'}", color=discord.Color.red()))

@bot.hybrid_command(name="setvouch", description="Set vouch count")
@commands.has_permissions(administrator=True)
async def setvouch(ctx, target: str, member: discord.Member = None, amount: int = 0):
    data = load_data()
    if target.lower() == "user" and member:
        uid = str(member.id)
        if uid not in data["users"]: data["users"][uid] = {"count":0,"ratings":[],"history":[]}
        data["users"][uid]["count"] = amount
        save_data(data)
        await ctx.send(f"✅ {member.mention} set to **{amount}** | {get_rank(amount)}")
    elif target.lower() == "server":
        data["server"] = amount
        save_data(data)
        await ctx.send(f"✅ Server set to **{amount}**")
    else:
        await ctx.send("Use: `$setvouch user @User 100` or `$setvouch server 50`")

@bot.hybrid_command(name="leaderboard", description="Top MMs")
async def leaderboard(ctx):
    data = load_data()
    if not data["users"]: return await ctx.send("No vouches yet!")
    sorted_users = sorted(data["users"].items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    embed = discord.Embed(title="🏆 LEADERBOARD", description=f"Server: **{data['server']}**", color=discord.Color.gold())
    for i, (uid, info) in enumerate(sorted_users, 1):
        try:
            u = await bot.fetch_user(int(uid))
            name = u.display_name
        except: name = f"ID:{uid}"
        embed.add_field(name=f"{i}. {name}", value=f"{info['count']} vouches | {get_rank(info['count'])}", inline=False)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="sync", description="Sync commands - use once only")
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await ctx.defer()
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ Synced {len(synced)} commands globally. Don't use again for 1 hour.")
    except Exception as e:
        await ctx.send(f"❌ {e} - Wait 1 hour, you are rate limited")

@tasks.loop(seconds=90)
async def auto_vouch_loop():
    try:
        data = load_data()
        cfg = data["config"].get("autovouch_user")
        if not cfg or not cfg.get("active"): return
        guild = bot.get_guild(cfg["guild_id"])
        if not guild: return
        channel = guild.get_channel(cfg["channel_id"])
        v_role = guild.get_role(cfg["voucher_role_id"])
        t_role = guild.get_role(cfg["target_role_id"])
        if not all([channel, v_role, t_role]): return
        v_members = [m for m in v_role.members if not m.bot]
        t_members = [m for m in t_role.members if not m.bot]
        if not v_members or not t_members: return
        target = random.choice(t_members)
        rating = random.randint(3,5)
        uid = str(target.id)
        if uid not in data["users"]: data["users"][uid] = {"count":0,"ratings":[],"history":[]}
        data["users"][uid]["count"] += 1
        data["users"][uid]["ratings"].append(rating)
        save_data(data)
        total = data["users"][uid]["count"]
        await channel.send(f"🚀 {target.mention} got **+1 Vouch!** Now has **{total}** | {get_rank(total)} {stars(rating)}")
        await asyncio.sleep(2) # anti-spam gap
    except discord.errors.HTTPException as e:
        if e.status == 429:
            print("Rate limited, sleeping 60s")
            await asyncio.sleep(60)

@tasks.loop(seconds=180)
async def auto_server_loop():
    try:
        data = load_data()
        cfg = data["config"].get("autoserver")
        if not cfg or not cfg.get("active"): return
        guild = bot.get_guild(cfg["guild_id"])
        channel = guild.get_channel(cfg["channel_id"]) if guild else None
        if not channel: return
        data["server"] += 1
        save_data(data)
        rating = random.randint(4,5)
        await channel.send(f"🌟 **Server +1 Vouch!** Total **{data['server']}** {stars(rating)}")
    except discord.errors.HTTPException as e:
        if e.status == 429:
            print("Server vouch rate limited, sleeping 120s")
            await asyncio.sleep(120)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} - SAFE MODE, No Auto Sync")
    data = load_data()
    try:
        if data["config"].get("autovouch_user", {}).get("active"):
            if not auto_vouch_loop.is_running():
                delay = max(MIN_USER_DELAY, data["config"]["autovouch_user"].get("delay",90))
                auto_vouch_loop.change_interval(seconds=delay)
                auto_vouch_loop.start()
        if data["config"].get("autoserver", {}).get("active"):
            if not auto_server_loop.is_running():
                delay = max(MIN_SERVER_DELAY, data["config"]["autoserver"].get("delay",180))
                auto_server_loop.change_interval(seconds=delay)
                auto_server_loop.start()
    except Exception as e:
        print(e)

bot.run(os.getenv("DISCORD_TOKEN"))
