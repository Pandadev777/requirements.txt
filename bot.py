import os
import sqlite3
import random
import string
import threading
from datetime import datetime, timedelta
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# --- FLASK FOR RENDER ---
app = Flask(__name__)
@app.route("/")
def home():
    return "Trusted Vouch Bot - Online"
@app.route("/health")
def health():
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

# --- DATABASE ---
DB_NAME = "vouches.db"
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS vouches (
        vouch_id TEXT PRIMARY KEY,
        guild_id INTEGER,
        voucher_id INTEGER,
        target_id INTEGER,
        rating INTEGER,
        comment TEXT,
        proof_url TEXT,
        timestamp DATETIME
    )""")
    conn.commit()
    conn.close()

def gen_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# --- BOT ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
cooldowns = {}

@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    print(f"Logged in as {bot.user} - Trusted System Ready")

def build_embed(guild, voucher, target, rating, comment, proof_url, vid):
    stars = "⭐" * rating
    embed = discord.Embed(title="✅ Verified Real Vouch", color=discord.Color.green(), timestamp=datetime.utcnow())
    embed.add_field(name="From", value=f"{voucher.mention} `{voucher.display_name}`", inline=True)
    embed.add_field(name="To", value=f"{target.mention} `{target.display_name}`", inline=True)
    embed.add_field(name="Rating", value=f"{stars} ({rating}/5)", inline=False)
    embed.add_field(name="Feedback", value=f"```{comment}```", inline=False)
    if proof_url:
        embed.set_image(url=proof_url)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text=f"ID: {vid} | {guild.name}")
    return embed

@bot.tree.command(name="vouch", description="Leave a real trusted vouch for someone you traded with")
@app_commands.describe(user="Who you traded with", rating="1-5 stars", comment="How was the trade?", proof="Screenshot proof of trade (optional but trusted)")
@app_commands.choices(rating=[
    app_commands.Choice(name="⭐ 1", value=1),
    app_commands.Choice(name="⭐⭐ 2", value=2),
    app_commands.Choice(name="⭐⭐⭐ 3", value=3),
    app_commands.Choice(name="⭐⭐⭐⭐ 4", value=4),
    app_commands.Choice(name="⭐⭐⭐⭐⭐ 5", value=5),
])
async def vouch(interaction: discord.Interaction, user: discord.Member, rating: app_commands.Choice[int], comment: str, proof: discord.Attachment = None):
    # --- Anti-abuse checks ---
    if user.id == interaction.user.id:
        return await interaction.response.send_message("❌ You can't vouch yourself.", ephemeral=True)
    if user.bot:
        return await interaction.response.send_message("❌ Can't vouch bots.", ephemeral=True)

    # Cooldown 1 hour
    last = cooldowns.get(interaction.user.id)
    if last and datetime.utcnow() - last < timedelta(hours=1):
        left = int((timedelta(hours=1) - (datetime.utcnow() - last)).total_seconds() / 60)
        return await interaction.response.send_message(f"⏳ Cooldown: Wait {left}m before vouching again.", ephemeral=True)

    proof_url = proof.url if proof else None
    vid = gen_id()

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO vouches VALUES (?,?,?,?,?,?,?,?)",
              (vid, interaction.guild.id, interaction.user.id, user.id, rating.value, comment, proof_url, datetime.utcnow()))
    conn.commit()
    conn.close()

    cooldowns[interaction.user.id] = datetime.utcnow()
    embed = build_embed(interaction.guild, interaction.user, user, rating.value, comment, proof_url, vid)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vouches", description="Check someone's trusted vouches")
async def vouches(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT rating FROM vouches WHERE target_id=? AND guild_id=?", (target.id, interaction.guild.id))
    rows = c.fetchall()
    conn.close()

    if not rows:
        return await interaction.response.send_message(f"{target.mention} has 0 vouches.", ephemeral=True)

    avg = round(sum(r[0] for r in rows) / len(rows), 2)
    embed = discord.Embed(title=f"📊 {target.display_name}'s Trusted Profile", color=discord.Color.blue())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Total Vouches", value=f"**{len(rows)}**", inline=True)
    embed.add_field(name="Average", value=f"⭐ {avg}/5", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vouch_leaderboard", description="Top most trusted members")
async def leaderboard(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT target_id, COUNT(*), AVG(rating) FROM vouches WHERE guild_id=? GROUP BY target_id ORDER BY COUNT(*) DESC LIMIT 10", (interaction.guild.id,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        return await interaction.response.send_message("No vouches yet.", ephemeral=True)

    desc = ""
    for i, (uid, cnt, avg) in enumerate(rows, 1):
        medal = ["🥇","🥈","🥉"][i-1] if i <=3 else f"#{i}"
        desc += f"{medal} <@{uid}> — **{cnt}** vouches (⭐ {avg:.1f})\n"

    embed = discord.Embed(title="🏆 Trusted Leaderboard", description=desc, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="remove_vouch", description="Remove a vouch by ID (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def remove_vouch(interaction: discord.Interaction, vouch_id: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM vouches WHERE vouch_id=? AND guild_id=?", (vouch_id, interaction.guild.id))
    conn.commit()
    deleted = c.rowcount
    conn.close()
    if deleted:
        await interaction.response.send_message(f"🗑️ Removed vouch `{vouch_id}`", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Vouch ID not found.", ephemeral=True)

# --- START ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("Set DISCORD_TOKEN in Render Env")
    bot.run(TOKEN)
