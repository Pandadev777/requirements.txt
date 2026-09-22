import discord
from discord.ext import commands, tasks
from discord import app_commands
import json, os, random, asyncio
from datetime import datetime
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "ULTRA V2 EMBED GOD - ONLINE"
Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)
DATA_FILE = "mm_data.json"

# ===== 50 RANKS =====
RANKS = [
    (0, "🥚 Beginner", 0x808080), (3, "🌱 Newbie MM", 0x00FF00), (5, "🔰 Junior MM", 0x32CD32),
    (8, "🛡️ Learning MM", 0x1E90FF), (10, "⚔️ Trusted MM", 0x4169E1), (15, "⭐ Rising MM", 0xFFD700),
    (20, "🔥 Skilled MM", 0xFF4500), (25, "💎 Advanced MM", 0x00CED1), (30, "👑 Pro MM", 0xFFD700),
    (35, "⚡ Super MM", 0xFF69B4), (40, "🌟 Expert MM", 0xFF1493), (45, "💫 Elite MM", 0x9400D3),
    (50, "🚀 Master MM", 0xFF0000), (60, "🔱 Legendary MM", 0x8B0000), (70, "💀 Mythic MM", 0x4B0082),
    (80, "🎯 Grandmaster MM", 0xFF8C00), (90, "🏆 Champion MM", 0xFFD700), (100, "🌌 Supreme MM", 0x4B0082),
    (115, "🔮 Celestial MM", 0x00FFFF), (130, "⚔️ Warlord MM", 0xDC143C), (145, "🧠 Sage MM", 0x20B2AA),
    (160, "🌀 Phantom MM", 0x7B68EE), (175, "🦁 Beast MM", 0xFF8C00), (190, "☠️ Reaper MM", 0x2F4F4F),
    (200, "🔥 Inferno MM", 0xFF4500), (220, "❄️ Frost MM", 0x00BFFF), (240, "⚡ Thunder MM", 0xFFFF00),
    (260, "🌪️ Storm MM", 0x4682B4), (280, "🌊 Tsunami MM", 0x1E90FF), (300, "🔥 Phoenix MM", 0xFF6347),
    (325, "💀 Deathless", 0x000000), (350, "👑 King of MM", 0xFFD700), (375, "🌠 Cosmic MM", 0x9932CC),
    (400, "🗡️ Overlord MM", 0x8B0000), (425, "🧬 Eternal MM", 0x00FF7F), (450, "🪐 Galaxy MM", 0x191970),
    (475, "🎖️ Titan MM", 0xB22222), (500, "🦾 Ultra MM", 0xFF00FF), (550, "🌋 Volcano MM", 0xFF4500),
    (600, "🌌 Universe MM", 0x000080), (650, "🧿 Divine MM", 0xFFD700), (700, "♾️ Infinity MM", 0xFFFFFF),
    (750, "🕳️ Void King", 0x000000), (800, "🔱 The One", 0xFFD700), (850, "🏆 GOAT MM", 0xFFD700),
    (900, "💎 Diamond GOAT", 0x00FFFF), (950, "🌟 Star GOAT", 0xFFD700), (1000, "🚀 Legend GOAT", 0xFF0000),
    (1200, "👑 GOD OF MM", 0xFFD700), (1500, "🌌 GOD+", 0x9400D3), (2000, "⚡ GODX", 0xFFFF00),
    (3000, "💀 ULTRA GOD", 0x000000), (5000, "👑 ETERNAL GOD", 0xFFD700)
]

def get_rank_data(count):
    data = RANKS[0]
    for req, name, color in RANKS:
        if count >= req: data = (req, name, color)
        else: break
    return data

def get_next(count):
    for req, name, color in RANKS:
        if count < req: return req-count, name
    return 0, "MAX"

def load():
    if not os.path.exists(DATA_FILE): return {"users":{}, "server":0, "config":{"autovouch_user":{}, "autoserver":{}}}
    with open(DATA_FILE,'r') as f: return json.load(f)
def save(d):
    with open(DATA_FILE,'w') as f: json.dump(f,d,indent=2)

def stars(r): return "⭐" * r
def bar(count):
    total = 20
    filled = min(count % 10, 10) * 2 if count < 100 else 20
    if count >= 100: filled = 20
    else: filled = int((count % 10)/10*20)
    return "█" * filled + "░" * (total-filled)

# ===== VOUCH BUTTONS =====
class VouchButtons(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
    @discord.ui.button(label="📊 View Profile", style=discord.ButtonStyle.blurple, emoji="👑")
    async def profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load()
        uid = str(self.user_id)
        if uid not in data["users"]: return await interaction.response.send_message("No vouches yet", ephemeral=True)
        count = data["users"][uid]["count"]
        _, rank, _ = get_rank_data(count)
        await interaction.response.send_message(f"👑 {interaction.client.get_user(int(uid)).mention if interaction.client.get_user(int(uid)) else 'User'} is **{rank}** with **{count}** vouches", ephemeral=True)
    @discord.ui.button(label="🏆 Leaderboard", style=discord.ButtonStyle.gray, emoji="📈")
    async def lb(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Use `$leaderboard` to see top MMs!", ephemeral=True)

# ===== $vouch =====
@bot.hybrid_command(name="vouch", description="Vouch a MM - God Embed")
@app_commands.describe(member="Middleman to vouch", rating="Stars 1-5", trade="Trade details")
async def vouch(ctx, member: discord.Member, rating: int, trade: str = "Legit & Trusted MM"):
    if not 1 <= rating <= 5: return await ctx.send(embed=discord.Embed(description="❌ **Rating must be 1-5**", color=0xFF0000), ephemeral=True)
    if member.id == ctx.author.id: return await ctx.send(embed=discord.Embed(description="❌ **Self vouch not allowed**", color=0xFF0000), ephemeral=True)
    if member.bot: return await ctx.send(embed=discord.Embed(description="❌ **Can't vouch bots**", color=0xFF0000), ephemeral=True)

    data = load()
    uid = str(member.id)
    if uid not in data["users"]: data["users"][uid] = {"count":0,"ratings":[],"history":[]}
    data["users"][uid]["count"] += 1
    data["users"][uid]["ratings"].append(rating)
    data["users"][uid]["history"].append({"by":ctx.author.id,"rating":rating,"trade":trade,"time":str(datetime.now())})
    save(data)

    count = data["users"][uid]["count"]
    avg = sum(data["users"][uid]["ratings"])/len(data["users"][uid]["ratings"])
    _, rank_name, rank_color = get_rank_data(count)
    left, next_name = get_next(count)

    embed = discord.Embed(color=rank_color, timestamp=datetime.now())
    embed.set_author(name=f"💎 NEW VOUCH RECEIVED • {rank_name}", icon_url=member.display_avatar.url)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👤 Middleman", value=f"**{member.mention}**\n`{member.id}`\n{rank_name}", inline=True)
    embed.add_field(name="⭐ Rating", value=f"{stars(rating)} **({rating}/5)**\nAvg: **{avg:.1f}/5**\nTotal Ratings: **{len(data['users'][uid]['ratings'])}**", inline=True)
    embed.add_field(name="📦 Trade", value=f"```{trade}```\nBy {ctx.author.mention}", inline=False)
    embed.add_field(name="📊 Career Stats", value=f"**Total Vouches:** `{count}`\n**Rank:** `{rank_name}`\n**Progress:** `{bar(count)}` {count%10}/10\n**Next:** {next_name} in `{left}` vouches", inline=False)
    embed.set_footer(text=f"🆔 Vouch ID: MM-{count:04d} • Enhanced Career System", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)

    view = VouchButtons(member.id)
    await ctx.send(content=f"🚀 ||{member.mention}||", embed=embed, view=view)

# ===== AUTOVOUCH USER - COOL EMBED =====
@tasks.loop(seconds=90)
async def auto_vouch_loop():
    try:
        data=load(); cfg=data["config"].get("autovouch_user")
        if not cfg or not cfg.get("active"): return
        guild=bot.get_guild(cfg["guild_id"]);
        if not guild: return
        channel=guild.get_channel(cfg["channel_id"]); v_role=guild.get_role(cfg["voucher_role_id"]); t_role=guild.get_role(cfg["target_role_id"])
        if not all([channel,v_role,t_role]): return
        targets=[m for m in t_role.members if not m.bot]
        if not targets: return
        target=random.choice(targets); rating=random.randint(3,5)
        uid=str(target.id)
        if uid not in data["users"]: data["users"][uid]={"count":0,"ratings":[],"history":[]}
        data["users"][uid]["count"]+=1; data["users"][uid]["ratings"].append(rating); save(data)
        count=data["users"][uid]["count"]
        _, rank_name, rank_color = get_rank_data(count)
        embed=discord.Embed(color=rank_color, timestamp=datetime.now())
        embed.set_author(name=f"AUTO VOUCH • {rank_name}", icon_url=target.display_avatar.url)
        embed.description = f"### 🚀 {target.mention} got **+1 vouch**\n**Now has {count} total vouches**\n{rank_name} {stars(rating)}\n`{bar(count)}`"
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=f"Auto System • {rank_name}")
        await channel.send(embed=embed)
    except discord.errors.HTTPException as e:
        if e.status==429: await asyncio.sleep(60)

@bot.hybrid_command(name="autovouch_user", description="Auto vouch system with roles")
@commands.has_permissions(administrator=True)
async def autovouch_user(ctx, voucher_role: discord.Role, target_role: discord.Role, delay: int = 90):
    delay=max(90,delay)
    data=load(); data["config"]["autovouch_user"]={"guild_id":ctx.guild.id,"channel_id":ctx.channel.id,"voucher_role_id":voucher_role.id,"target_role_id":target_role.id,"delay":delay,"active":True}; save(data)
    if auto_vouch_loop.is_running(): auto_vouch_loop.stop()
    auto_vouch_loop.change_interval(seconds=delay); auto_vouch_loop.start()
    embed=discord.Embed(title="🤖 AUTO VOUCH ENABLED • PRO MODE", description=f"**From:** {voucher_role.mention}\n**To:** {target_role.mention}\n**Delay:** `{delay}s` • Safe Anti-429\n**Ratings:** Random `3-5 ⭐`\n**Style:** `@user got +1 vouch now has (total)`", color=0x00FF00)
    embed.set_footer(text="50 Ranks • Auto Embed System")
    await ctx.send(embed=embed)

# ===== AUTOSERVER =====
@tasks.loop(seconds=180)
async def auto_server_loop():
    try:
        data=load(); cfg=data["config"].get("autoserver")
        if not cfg or not cfg.get("active"): return
        guild=bot.get_guild(cfg["guild_id"]); channel=guild.get_channel(cfg["channel_id"]) if guild else None
        if not channel: return
        data["server"]+=1; save(data)
        rating=random.randint(3,5)
        embed=discord.Embed(color=0x9B59B6, timestamp=datetime.now())
        embed.set_author(name="SERVER VOUCH • OFFICIAL", icon_url=guild.icon.url if guild.icon else None)
        embed.description = f"### 🌟 **Server got +1 vouch**\n**Now has {data['server']} total server vouches**\n{stars(rating)} `({rating}/5)`\n`{bar(data['server'])}`"
        embed.set_footer(text=f"Server Reputation • {data['server']} vouches")
        await channel.send(embed=embed)
    except: await asyncio.sleep(120)

@bot.hybrid_command(name="autoserver_vouch", description="Auto server vouch - Ratings only")
@commands.has_permissions(administrator=True)
async def autoserver_vouch(ctx, delay: int = 180):
    delay=max(180,delay)
    data=load(); data["config"]["autoserver"]={"guild_id":ctx.guild.id,"channel_id":ctx.channel.id,"delay":delay,"active":True}; save(data)
    if auto_server_loop.is_running(): auto_server_loop.stop()
    auto_server_loop.change_interval(seconds=delay); auto_server_loop.start()
    embed=discord.Embed(title="🏢 AUTO SERVER VOUCH ENABLED", description=f"**Delay:** `{delay}s`\n**Mode:** Ratings Only ⭐\n**Embed:** Professional", color=0x9B59B6)
    await ctx.send(embed=embed)

# ===== SETVOUCH =====
@bot.hybrid_command(name="setvouch", description="Set vouch - Interlinked")
@commands.has_permissions(administrator=True)
async def setvouch(ctx, target: str, member: discord.Member = None, amount: int = 0):
    data=load()
    if target.lower()=="user":
        if not member: return await ctx.send(embed=discord.Embed(description="❌ Use `$setvouch user @User 100`", color=0xFF0000))
        uid=str(member.id)
        if uid not in data["users"]: data["users"][uid]={"count":0,"ratings":[],"history":[]}
        data["users"][uid]["count"]=amount; save(data)
        _, rank_name, rank_color = get_rank_data(amount)
        embed=discord.Embed(title="✅ VOUCH UPDATED • INTERLINKED", color=rank_color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Total", value=f"`{amount}`", inline=True)
        embed.add_field(name="Rank", value=f"**{rank_name}**", inline=True)
        embed.set_footer(text="Synced with leaderboard & autovouch embeds")
        await ctx.send(embed=embed)
    elif target.lower()=="server":
        data["server"]=amount; save(data)
        await ctx.send(embed=discord.Embed(title="✅ SERVER VOUCH SET", description=f"Server: **{amount}** vouches", color=0x00FF00))

# ===== LEADERBOARD - GOD LEVEL =====
@bot.hybrid_command(name="leaderboard", description="Top MMs - God Embed")
async def leaderboard(ctx):
    data=load()
    if not data["users"]: return await ctx.send(embed=discord.Embed(description="No vouches yet", color=0xFF0000))
    sorted_users=sorted(data["users"].items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    embed=discord.Embed(title="🏆 MIDDLEMAN LEADERBOARD • TOP 10", description=f"**🌟 Server:** `{data['server']}` vouches\n**👥 Total MMs:** `{len(data['users'])}`\n━━━━━━━━━━━━━━━━━━━━", color=0xFFD700, timestamp=datetime.now())
    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    for i,(uid,info) in enumerate(sorted_users,1):
        try: user=await bot.fetch_user(int(uid)); name=user.display_name
        except: name=f"User {uid[:4]}"
        _, rank_name, _ = get_rank_data(info["count"])
        avg=sum(info["ratings"])/len(info["ratings"]) if info["ratings"] else 0
        medals={1:"🥇",2:"🥈",3:"🥉"}
        medal=medals.get(i, f"`#{i}`")
        embed.add_field(name=f"{medal} {name} • {rank_name}", value=f"**{info['count']}** vouches | {stars(int(avg))} `{avg:.1f}` | {bar(info['count'])}", inline=False)
    embed.set_footer(text="Interlinked • $vouch • $setvouch • autovouch • 50 Ranks", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="stopautovouch", description="Stop all auto")
@commands.has_permissions(administrator=True)
async def stopautovouch(ctx):
    data=load(); data["config"]["autovouch_user"]={}; data["config"]["autoserver"]={}; save(data)
    if auto_vouch_loop.is_running(): auto_vouch_loop.stop()
    if auto_server_loop.is_running(): auto_server_loop.stop()
    await ctx.send(embed=discord.Embed(title="🛑 ALL AUTO STOPPED", color=0xFF0000))

@bot.hybrid_command(name="sync", description="Sync commands")
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await ctx.defer()
    synced=await bot.tree.sync()
    await ctx.send(embed=discord.Embed(description=f"✅ **Synced {len(synced)} commands** - Both `$` and `/` work", color=0x00FF00))

@bot.event
async def on_ready():
    print(f"✅ ULTRA V2 ONLINE: {bot.user}")
    data=load()
    if data["config"].get("autovouch_user",{}).get("active"):
        if not auto_vouch_loop.is_running():
            auto_vouch_loop.change_interval(seconds=max(90,data["config"]["autovouch_user"].get("delay",90)))
            auto_vouch_loop.start()
    if data["config"].get("autoserver",{}).get("active"):
        if not auto_server_loop.is_running():
            auto_server_loop.change_interval(seconds=max(180,data["config"]["autoserver"].get("delay",180)))
            auto_server_loop.start()

bot.run(os.getenv("DISCORD_TOKEN"))
