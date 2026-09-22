import discord
from discord.ext import commands, tasks
import json, os, random
from datetime import datetime
from flask import Flask
from threading import Thread

# --- Render Keep Alive ---
app = Flask('')
@app.route('/')
def home(): return "Advanced MM Vouch Bot Running!"
Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)
DATA_FILE = "mm_data.json"

# --- 50 RANKS ---
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

def vouch_embed(target, total, rating, by=None, is_auto=False):
    e = discord.Embed(color=discord.Color.gold() if rating >=4 else discord.Color.orange())
    e.set_thumbnail(url=target.display_avatar.url)
    e.title = f"{'🤖 AUTO' if is_auto else '✅'} VOUCH ADDED"
    e.description = f"{target.mention} got **+1 Vouch!** Now has **{total}** vouches"
    e.add_field(name="⭐ Rating", value=stars(rating), inline=True)
    e.add_field(name="🏅 Rank", value=f"**{get_rank(total)}**", inline=True)
    e.add_field(name="📊 Total", value=f"**{total}**", inline=True)
    e.set_footer(text=f"Vouched by {by if by else 'Auto System'} • {datetime.now().strftime('%d/%m %I:%M %p')}")
    return e

# --- COMMANDS ---

@bot.hybrid_command(name="vouch", description="Vouch a middleman with rating 1-5")
async def vouch(ctx, member: discord.Member, rating: int, *, trade_details: str = "Legit MM"):
    if not 1 <= rating <= 5: return await ctx.send("❌ Rating 1-5 only", ephemeral=True)
    if member.id == ctx.author.id: return await ctx.send("❌ No self-vouch!", ephemeral=True)
    data = load_data()
    uid = str(member.id)
    if uid not in data["users"]: data["users"][uid] = {"count":0, "ratings":[], "history":[]}
    data["users"][uid]["count"] += 1
    data["users"][uid]["ratings"].append(rating)
    data["users"][uid]["history"].append({"by":ctx.author.id,"rating":rating,"details":trade_details,"time":str(datetime.now())})
    save_data(data)
    total = data["users"][uid]["count"]
    avg = sum(data["users"][uid]["ratings"])/len(data["users"][uid]["ratings"])

    embed = discord.Embed(title="✨ MIDDLEMAN VOUCH", color=discord.Color.green())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👤 Middleman", value=member.mention, inline=True)
    embed.add_field(name="🙋 By", value=ctx.author.mention, inline=True)
    embed.add_field(name="⭐ Rating", value=stars(rating), inline=False)
    embed.add_field(name="📝 Trade", value=trade_details, inline=False)
    embed.add_field(name="📈 Total", value=f"**{total}**", inline=True)
    embed.add_field(name="🏅 Rank", value=get_rank(total), inline=True)
    embed.add_field(name="💫 Avg", value=f"{avg:.1f}/5", inline=True)

    await ctx.send(embed=embed)
    await ctx.send(f"🎉 {member.mention} got **+1 Vouch!** Now has **{total}** vouches | {get_rank(total)} {stars(rating)}")

@bot.hybrid_command(name="autovouch_user", description="Start auto user vouch")
@commands.has_permissions(administrator=True)
async def autovouch_user(ctx, voucher_role: discord.Role, target_role: discord.Role, delay_seconds: int = 60):
    data = load_data()
    data["config"]["autovouch_user"] = {"guild_id":ctx.guild.id,"channel_id":ctx.channel.id,"voucher_role_id":voucher_role.id,"target_role_id":target_role.id,"delay":delay_seconds,"active":True}
    save_data(data)
    if not auto_vouch_loop.is_running(): auto_vouch_loop.start()
    else: auto_vouch_loop.change_interval(seconds=delay_seconds)
    await ctx.send(embed=discord.Embed(title="🤖 Auto User Vouch ON", description=f"From: {voucher_role.mention} -> To: {target_role.mention}\nDelay: {delay_seconds}s\nRating: 3-5⭐ random\nType: No comments, only stars", color=discord.Color.blue()))

@bot.hybrid_command(name="autoserver_vouch", description="Start auto server vouch")
@commands.has_permissions(administrator=True)
async def autoserver_vouch(ctx, delay_seconds: int = 120):
    data = load_data()
    data["config"]["autoserver"] = {"guild_id":ctx.guild.id,"channel_id":ctx.channel.id,"delay":delay_seconds,"active":True}
    save_data(data)
    if not auto_server_loop.is_running(): auto_server_loop.start()
    else: auto_server_loop.change_interval(seconds=delay_seconds)
    await ctx.send(embed=discord.Embed(title="🏢 Auto Server Vouch ON", description=f"Delay: {delay_seconds}s\nOnly Stars, No Comments", color=discord.Color.purple()))

@bot.hybrid_command(name="stopautovouch", description="Stop all auto vouches")
@commands.has_permissions(administrator=True)
async def stopautovouch(ctx, type: str = "all"):
    data = load_data()
    stopped = []
    if type.lower() in ["all", "user"]:
        data["config"]["autovouch_user"] = {}
        if auto_vouch_loop.is_running(): auto_vouch_loop.stop()
        stopped.append("User AutoVouch")
    if type.lower() in ["all", "server"]:
        data["config"]["autoserver"] = {}
        if auto_server_loop.is_running(): auto_server_loop.stop()
        stopped.append("Server AutoVouch")
    save_data(data)

    if stopped:
        await ctx.send(embed=discord.Embed(title="🛑 Auto Vouch Stopped", description=f"Stopped: {', '.join(stopped)}", color=discord.Color.red()))
    else:
        await ctx.send("Use: `$stopautovouch all` or `$stopautovouch user` or `$stopautovouch server`")

@bot.hybrid_command(name="setvouch", description="Set vouch count")
@commands.has_permissions(administrator=True)
async def setvouch(ctx, target: str, member: discord.Member = None, amount: int = 0):
    data = load_data()
    if target.lower() == "user":
        if not member: return await ctx.send("Usage: `$setvouch user @User 100`")
        uid = str(member.id)
        if uid not in data["users"]: data["users"][uid] = {"count":0,"ratings":[],"history":[]}
        data["users"][uid]["count"] = amount
        save_data(data)
        await ctx.send(embed=discord.Embed(title="✅ Vouch Set", description=f"{member.mention} set to **{amount}**\nRank: **{get_rank(amount)}**", color=discord.Color.green()))
    elif target.lower() == "server":
        data["server"] = amount
        save_data(data)
        await ctx.send(embed=discord.Embed(title="✅ Server Vouch Set", description=f"Server set to **{amount}**", color=discord.Color.green()))
    else:
        await ctx.send("Use: `$setvouch user @User 100` or `$setvouch server 50`")

@bot.hybrid_command(name="leaderboard", description="Top middlemans")
async def leaderboard(ctx):
    data = load_data()
    if not data["users"]: return await ctx.send("No vouches yet!")
    sorted_users = sorted(data["users"].items(), key=lambda x: x[1]["count"], reverse=True)[:15]
    embed = discord.Embed(title="🏆 MIDDLEMAN LEADERBOARD", description=f"Server Vouches: **{data['server']}**", color=discord.Color.gold())
    for i, (uid, info) in enumerate(sorted_users, 1):
        try:
            u = await bot.fetch_user(int(uid))
            name = u.display_name
        except: name = f"ID:{uid}"
        avg = sum(info["ratings"])/len(info["ratings"]) if info["ratings"] else 0
        embed.add_field(name=f"{i}. {name} - {get_rank(info['count'])}", value=f"Vouches: **{info['count']}** | Avg: {avg:.1f}⭐", inline=False)
    embed.set_footer(text="50 Ranks System • Blox Fruits MM")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="sync", description="Force sync slash commands")
@commands.has_permissions(administrator=True)
async def sync(ctx):
    m = await ctx.send("🔄 Syncing...")
    try:
        synced1 = await bot.tree.sync()
        synced2 = await bot.tree.sync(guild=ctx.guild)
        await m.edit(content="", embed=discord.Embed(title="✅ SYNC DONE", description=f"Global: {len(synced1)} | Server: {len(synced2)}\nCommands: vouch, autovouch_user, autoserver_vouch, stopautovouch, setvouch, leaderboard, sync", color=discord.Color.green()))
    except Exception as e:
        await m.edit(content=f"❌ {e}")

# --- LOOPS ---
@tasks.loop(seconds=60)
async def auto_vouch_loop():
    data = load_data()
    cfg = data["config"].get("autovouch_user")
    if not cfg or not cfg.get("active"): return
    guild = bot.get_guild(cfg["guild_id"])
    channel = guild.get_channel(cfg["channel_id"]) if guild else None
    if not guild or not channel: return
    v_role = guild.get_role(cfg["voucher_role_id"])
    t_role = guild.get_role(cfg["target_role_id"])
    if not v_role or not t_role: return
    v_members = [m for m in v_role.members if not m.bot]
    t_members = [m for m in t_role.members if not m.bot]
    if not v_members or not t_members: return
    by = random.choice(v_members)
    target = random.choice(t_members)
    rating = random.randint(3,5)
    uid = str(target.id)
    if uid not in data["users"]: data["users"][uid] = {"count":0,"ratings":[],"history":[]}
    data["users"][uid]["count"] += 1
    data["users"][uid]["ratings"].append(rating)
    save_data(data)
    total = data["users"][uid]["count"]
    await channel.send(f"🚀 {target.mention} got **+1 Vouch!** Now has **{total}** | {get_rank(total)}")
    await channel.send(embed=vouch_embed(target, total, rating, by.display_name, True))

@tasks.loop(seconds=120)
async def auto_server_loop():
    data = load_data()
    cfg = data["config"].get("autoserver")
    if not cfg or not cfg.get("active"): return
    guild = bot.get_guild(cfg["guild_id"])
    channel = guild.get_channel(cfg["channel_id"]) if guild else None
    if not guild or not channel: return
    rating = random.randint(4,5)
    data["server"] += 1
    save_data(data)
    embed = discord.Embed(title="🏢 SERVER VOUCH", color=discord.Color.green())
    embed.description = f"Server got **+1 Vouch!** Total: **{data['server']}**\n{stars(rating)}"
    await channel.send(f"🌟 **Server +1 Vouch!** Now **{data['server']}** total {stars(rating)}")
    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try: await bot.tree.sync()
    except: pass
    data = load_data()
    if data["config"].get("autovouch_user", {}).get("active"):
        if not auto_vouch_loop.is_running():
            auto_vouch_loop.change_interval(seconds=data["config"]["autovouch_user"].get("delay",60))
            auto_vouch_loop.start()
    if data["config"].get("autoserver", {}).get("active"):
        if not auto_server_loop.is_running():
            auto_server_loop.change_interval(seconds=data["config"]["autoserver"].get("delay",120))
            auto_server_loop.start()

bot.run(os.getenv("DISCORD_TOKEN"))
