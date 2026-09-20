import os
import random
import string
import sqlite3
import threading
import time
import requests
from datetime import datetime
from flask import Flask
from gevent.pywsgi import WSGIServer

import discord
from discord import app_commands
from discord.ext import commands, tasks

# ==========================================
# 1. FLASK WEB SERVER (FOR RENDER HOSTING)
# ==========================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Vouch Bot Server is Online and Active!"

def run_flask():
    # Use gevent WSGI server for production hosting on Render
    port = int(os.environ.get("PORT", 8080))
    http_server = WSGIServer(('0.0.0.0', port), app)
    http_server.serve_forever()

# Keep-alive loop to ping render URL every 5 minutes to prevent sleep
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

def keep_alive_ping():
    while True:
        time.sleep(300)
        if RENDER_URL:
            try:
                requests.get(RENDER_URL)
            except Exception as e:
                print(f"Keep-alive ping failed: {e}")

# ==========================================
# 2. DATABASE SETUP
# ==========================================

DB_NAME = "vouches.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            vouch_count INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS server_vouches (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            vouch_count INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS vouch_logs (
            vouch_id TEXT PRIMARY KEY,
            vouched_by INTEGER,
            vouched_for INTEGER, -- 0 represents Server Vouch
            rating INTEGER,
            comment TEXT,
            timestamp DATETIME
        )
    ''')
    c.execute('INSERT OR IGNORE INTO server_vouches (id, vouch_count) VALUES (1, 0)')
    conn.commit()
    conn.close()

init_db()

# Database Helper Functions
def get_user_vouches(user_id: int) -> int:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT vouch_count FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def set_user_vouches(user_id: int, count: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO users (user_id, vouch_count) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET vouch_count = ?', (user_id, count, count))
    conn.commit()
    conn.close()

def add_user_vouch(user_id: int, increment: int = 1) -> int:
    current = get_user_vouches(user_id)
    new_count = max(0, current + increment)
    set_user_vouches(user_id, new_count)
    return new_count

def get_server_vouches() -> int:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT vouch_count FROM server_vouches WHERE id = 1')
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_server_vouch() -> int:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE server_vouches SET vouch_count = vouch_count + 1 WHERE id = 1')
    c.execute('SELECT vouch_count FROM server_vouches WHERE id = 1')
    row = c.fetchone()
    conn.commit()
    conn.close()
    return row[0]

def record_vouch_log(vouched_by: int, vouched_for: int, rating: int, comment: str) -> str:
    vouch_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO vouch_logs VALUES (?, ?, ?, ?, ?, ?)', 
              (vouch_id, vouched_by, vouched_for, rating, comment, datetime.utcnow()))
    conn.commit()
    conn.close()
    return vouch_id

def get_leaderboard_data():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT user_id, vouch_count FROM users ORDER BY vouch_count DESC LIMIT 10')
    rows = c.fetchall()
    conn.close()
    return rows

# ==========================================
# 3. HELPER UTILITIES & MM RANKS
# ==========================================

MM_RANKS = [
    (0, "🔰 Trainee Middleman"),
    (100, "🛡️ Novice Middleman"),
    (200, "⚔️ Elite Middleman"),
    (300, "💎 Diamond Middleman"),
    (400, "👑 Master Middleman"),
    (500, "🔮 Grandmaster Middleman"),
    (1000, "⚡ Mythic Overseer")
]

DEFAULT_COMMENTS = [
    "Super fast trade, highly trusted!",
    "Vouch! Smooth transaction with zero issues.",
    "10/10 Middleman service. Will use again!",
    "Legit and very polite MM. Thanks!",
    "Quick deal, super safe handling.",
    "Best MM experience I've had so far!",
    "Vouch! Very professional and swift.",
    "Trustworthy guy, done big trade safely."
]

def calculate_mm_rank(vouch_count: int) -> str:
    current_rank = MM_RANKS[0][1]
    for threshold, rank_name in MM_RANKS:
        if vouch_count >= threshold:
            current_rank = rank_name
        else:
            break
    return current_rank

# ==========================================
# 4. DISCORD BOT CONFIGURATION & COMMANDS
# ==========================================

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuration Stores for Automated Systems
auto_user_config = {
    "active": False,
    "channel_id": None,
    "vouncher_role_id": None,
    "target_role_id": None,
    "interval_minutes": 10
}

auto_server_config = {
    "active": False,
    "channel_id": None,
    "vouncher_role_id": None,
    "comments": DEFAULT_COMMENTS,
    "interval_minutes": 15
}

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

# --- SLASH COMMAND 1: MANUAL VOUCH ---
@bot.tree.command(name="vouch", description="Manually submit a vouch for a Middleman.")
@app_commands.describe(
    vouched_by="User who is giving the vouch",
    vouched_for="Middleman who received the vouch",
    rating="Star rating from 1 to 5",
    comment="Additional feedback details"
)
async def vouch(
    interaction: discord.Interaction, 
    vouched_by: discord.Member, 
    vouched_for: discord.Member, 
    rating: app_commands.Range[int, 1, 5], 
    comment: str
):
    total_vouches = add_user_vouch(vouched_for.id, 1)
    rank = calculate_mm_rank(total_vouches)
    v_id = record_vouch_log(vouched_by.id, vouched_for.id, rating, comment)

    stars = "⭐" * rating
    embed = discord.Embed(
        title="🌟 New Middleman Vouch Recorded!",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="👤 Vouched By", value=vouched_by.mention, inline=True)
    embed.add_field(name="🛡️ Middleman", value=vouched_for.mention, inline=True)
    embed.add_field(name="⭐ Rating", value=f"{stars} ({rating}/5)", inline=True)
    embed.add_field(name="💬 Comment", value=f"`{comment}`", inline=False)
    embed.add_field(name="🏅 MM Rank", value=f"**{rank}**", inline=True)
    embed.add_field(name="📈 Total Vouches", value=f"**{total_vouches}**", inline=True)
    embed.set_footer(text=f"Server: {interaction.guild.name} • Vouch ID: {v_id}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

    await interaction.response.send_message(
        content=f"{vouched_for.mention} has received a +1 vouch! (Total: **{total_vouches}**)",
        embed=embed
    )

# --- SLASH COMMAND 2: SET VOUCH ---
@bot.tree.command(name="setvouch", description="Set explicit vouch count for a user (Admin).")
@app_commands.checks.has_permissions(administrator=True)
async def set_vouch(interaction: discord.Interaction, user: discord.Member, count: int):
    set_user_vouches(user.id, max(0, count))
    rank = calculate_mm_rank(count)

    embed = discord.Embed(
        title="⚙️ Vouch Count Set",
        description=f"Updated vouches for {user.mention}.",
        color=discord.Color.blue()
    )
    embed.add_field(name="New Total", value=f"**{count}**", inline=True)
    embed.add_field(name="MM Rank", value=f"**{rank}**", inline=True)
    await interaction.response.send_message(embed=embed)

# --- SLASH COMMAND 3: REMOVE VOUCH ---
@bot.tree.command(name="removevouch", description="Remove vouches from a user (Admin).")
@app_commands.checks.has_permissions(administrator=True)
async def remove_vouch(interaction: discord.Interaction, user: discord.Member, amount: int = 1):
    new_total = add_user_vouch(user.id, -amount)
    rank = calculate_mm_rank(new_total)

    embed = discord.Embed(
        title="🔻 Vouch Removed",
        description=f"Removed **{amount}** vouch(es) from {user.mention}.",
        color=discord.Color.red()
    )
    embed.add_field(name="New Total", value=f"**{new_total}**", inline=True)
    embed.add_field(name="MM Rank", value=f"**{rank}**", inline=True)
    await interaction.response.send_message(embed=embed)

# --- SLASH COMMAND 4: CHECK VOUCHES ---
@bot.tree.command(name="vouches", description="Check how many vouches a user has.")
async def check_vouches(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    count = get_user_vouches(target.id)
    rank = calculate_mm_rank(count)

    embed = discord.Embed(
        title=f"📊 Vouch Profile: {target.display_name}",
        color=discord.Color.purple()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="✨ Total Vouches", value=f"**{count}**", inline=True)
    embed.add_field(name="🏅 MM Rank", value=f"**{rank}**", inline=True)
    embed.set_footer(text=f"Requested by {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

# --- SLASH COMMAND 5: LEADERBOARD ---
@bot.tree.command(name="vouchleaderboard", description="Display top Middlemen in the server.")
async def leaderboard(interaction: discord.Interaction):
    data = get_leaderboard_data()
    if not data:
        await interaction.response.send_message("No vouches recorded yet!")
        return

    embed = discord.Embed(
        title="🏆 Top Middlemen Leaderboard",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )

    leaderboard_text = ""
    medals = ["🥇", "🥈", "🥉"]

    for i, (u_id, count) in enumerate(data):
        rank_icon = medals[i] if i < 3 else f"`#{i+1}`"
        rank_name = calculate_mm_rank(count)
        leaderboard_text += f"{rank_icon} <@{u_id}> — **{count}** vouches ({rank_name})\n"

    embed.description = leaderboard_text
    embed.set_footer(text=f"Server: {interaction.guild.name}")
    await interaction.response.send_message(embed=embed)

# --- SLASH COMMAND 6: CONFIGURE AUTOVOUCH (USERS) ---
@bot.tree.command(name="autovouch_config", description="Configure auto-vouch for Middlemen.")
@app_commands.checks.has_permissions(administrator=True)
async def autovouch_config(
    interaction: discord.Interaction, 
    channel: discord.TextChannel, 
    voucher_role: discord.Role, 
    target_mm_role: discord.Role, 
    interval_minutes: int = 10,
    enable: bool = True
):
    auto_user_config.update({
        "active": enable,
        "channel_id": channel.id,
        "vouncher_role_id": voucher_role.id,
        "target_role_id": target_mm_role.id,
        "interval_minutes": max(1, interval_minutes)
    })
    
    if enable and not auto_user_vouch_task.is_running():
        auto_user_vouch_task.change_interval(minutes=interval_minutes)
        auto_user_vouch_task.start()
    elif not enable and auto_user_vouch_task.is_running():
        auto_user_vouch_task.stop()

    await interaction.response.send_message(
        f"✅ Auto User Vouch configured!\n**Status**: {'Active' if enable else 'Disabled'}\n"
        f"**Channel**: {channel.mention}\n**Interval**: Every {interval_minutes} minutes."
    )

# --- SLASH COMMAND 7: CONFIGURE SERVER VOUCH ---
@bot.tree.command(name="servervouch_config", description="Configure automated server vouches.")
@app_commands.checks.has_permissions(administrator=True)
async def servervouch_config(
    interaction: discord.Interaction, 
    channel: discord.TextChannel, 
    voucher_role: discord.Role, 
    comma_separated_comments: str,
    interval_minutes: int = 15,
    enable: bool = True
):
    comment_list = [c.strip() for c in comma_separated_comments.split(",") if c.strip()]
    if not comment_list:
        comment_list = DEFAULT_COMMENTS

    auto_server_config.update({
        "active": enable,
        "channel_id": channel.id,
        "vouncher_role_id": voucher_role.id,
        "comments": comment_list,
        "interval_minutes": max(1, interval_minutes)
    })

    if enable and not auto_server_vouch_task.is_running():
        auto_server_vouch_task.change_interval(minutes=interval_minutes)
        auto_server_vouch_task.start()
    elif not enable and auto_server_vouch_task.is_running():
        auto_server_vouch_task.stop()

    await interaction.response.send_message(
        f"✅ Auto Server Vouch configured!\n**Status**: {'Active' if enable else 'Disabled'}\n"
        f"**Channel**: {channel.mention}\n**Custom Comments**: {len(comment_list)} loaded."
    )

# ==========================================
# 5. BACKGROUND TASKS
# ==========================================

@tasks.loop(minutes=10)
async def auto_user_vouch_task():
    if not auto_user_config["active"]:
        return

    channel = bot.get_channel(auto_user_config["channel_id"])
    if not channel:
        return

    guild = channel.guild
    voucher_role = guild.get_role(auto_user_config["vouncher_role_id"])
    target_role = guild.get_role(auto_user_config["target_role_id"])

    if not voucher_role or not target_role:
        return

    vouchers = voucher_role.members
    targets = target_role.members

    if not vouchers or not targets:
        return

    vouched_by = random.choice(vouchers)
    vouched_for = random.choice(targets)
    rating = random.randint(3, 5)
    comment = random.choice(DEFAULT_COMMENTS)

    total_vouches = add_user_vouch(vouched_for.id, 1)
    rank = calculate_mm_rank(total_vouches)
    v_id = record_vouch_log(vouched_by.id, vouched_for.id, rating, comment)

    stars = "⭐" * rating
    embed = discord.Embed(
        title="🤖 Auto Middleman Vouch",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="👤 Vouched By", value=vouched_by.mention, inline=True)
    embed.add_field(name="🛡️ Middleman", value=vouched_for.mention, inline=True)
    embed.add_field(name="⭐ Rating", value=f"{stars} ({rating}/5)", inline=True)
    embed.add_field(name="💬 Comment", value=f"`{comment}`", inline=False)
    embed.add_field(name="🏅 MM Rank", value=f"**{rank}**", inline=True)
    embed.add_field(name="📈 Total Vouches", value=f"**{total_vouches}**", inline=True)
    embed.set_footer(text=f"Server: {guild.name} • Vouch ID: {v_id}", icon_url=guild.icon.url if guild.icon else None)

    await channel.send(
        content=f"{vouched_for.mention} has got +1 vouch! (Total: **{total_vouches}**)",
        embed=embed
    )

@tasks.loop(minutes=15)
async def auto_server_vouch_task():
    if not auto_server_config["active"]:
        return

    channel = bot.get_channel(auto_server_config["channel_id"])
    if not channel:
        return

    guild = channel.guild
    voucher_role = guild.get_role(auto_server_config["vouncher_role_id"])

    if not voucher_role or not voucher_role.members:
        return

    vouched_by = random.choice(voucher_role.members)
    rating = random.randint(3, 5)
    comment = random.choice(auto_server_config["comments"])

    total_server_vouches = add_server_vouch()
    v_id = record_vouch_log(vouched_by.id, 0, rating, comment)

    stars = "⭐" * rating
    embed = discord.Embed(
        title=f"🌐 Auto Server Vouch — {guild.name}",
        color=discord.Color.teal(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="👤 Vouched By", value=vouched_by.mention, inline=True)
    embed.add_field(name="🏛️ Target", value=f"**{guild.name}**", inline=True)
    embed.add_field(name="⭐ Rating", value=f"{stars} ({rating}/5)", inline=True)
    embed.add_field(name="💬 Comment", value=f"`{comment}`", inline=False)
    embed.add_field(name="📊 Server Total Vouches", value=f"**{total_server_vouches}**", inline=True)
    embed.set_footer(text=f"Vouch ID: {v_id}", icon_url=guild.icon.url if guild.icon else None)

    await channel.send(
        content=f"🎉 **{guild.name}** got +1 server vouch! (Total Server Vouches: **{total_server_vouches}**)",
        embed=embed
    )

# ==========================================
# 6. APPLICATION ENTRY POINT
# ==========================================

if __name__ == "__main__":
    # Start Flask Web Server Thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start Keep-Alive Ping Thread
    ping_thread = threading.Thread(target=keep_alive_ping, daemon=True)
    ping_thread.start()

    # Retrieve Discord Token
    BOT_TOKEN = os.environ.get("DISCORD_TOKEN")
    if not BOT_TOKEN:
        print("ERROR: DISCORD_TOKEN environment variable not set!")
    else:
        bot.run(BOT_TOKEN)
