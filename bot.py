import os
import random
import sqlite3
import string
import threading
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# ------------------------------------------------------------------------------
# 1. FLASK WEB SERVER (For Render Web Service Hosting)
# ------------------------------------------------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Vouch Bot Status: Online"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ------------------------------------------------------------------------------
# 2. DATABASE SETUP (SQLite)
# ------------------------------------------------------------------------------
DB_NAME = "vouches.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vouches (
            vouch_id TEXT PRIMARY KEY,
            guild_id INTEGER,
            voucher_id INTEGER,
            target_id INTEGER, -- 0 represents Server Vouch
            rating INTEGER,
            comment TEXT,
            timestamp DATETIME
        )
    """)
    conn.commit()
    conn.close()

def generate_vouch_id():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

# ------------------------------------------------------------------------------
# 3. DISCORD BOT SETUP
# ------------------------------------------------------------------------------
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    init_db()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print(f"Logged in as {bot.user.name}")

# Helper: Create Vouch Embed
def create_vouch_embed(guild, voucher, target, rating, comment, vouch_id, is_server=False):
    stars = "⭐" * rating
    embed = discord.Embed(
        title="✨ New Vouch Submitted! ✨",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="👤 Voucher", value=voucher.mention, inline=True)
    if is_server:
        embed.add_field(name="🏢 Recipient", value=f"**{guild.name}** (Server)", inline=True)
    else:
        embed.add_field(name="🎯 Recipient", value=target.mention, inline=True)
    
    embed.add_field(name="⭐ Rating", value=f"{stars} ({rating}/5)", inline=False)
    embed.add_field(name="💬 Comment", value=f"```{comment}```", inline=False)
    embed.set_footer(text=f"Server: {guild.name} | Vouch ID: {vouch_id}")
    if target and hasattr(target, "display_avatar"):
        embed.set_thumbnail(url=target.display_avatar.url)
    else:
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    return embed

# ------------------------------------------------------------------------------
# 4. SLASH COMMANDS
# ------------------------------------------------------------------------------

# 1. /vouch
@bot.tree.command(name="vouch", description="Submit a manual vouch for a user.")
@app_commands.describe(user="The user to vouch for", rating="Rating out of 5 stars", comment="Your feedback/comment")
@app_commands.choices(rating=[
    app_commands.Choice(name="⭐ 1 Star", value=1),
    app_commands.Choice(name="⭐⭐ 2 Stars", value=2),
    app_commands.Choice(name="⭐⭐⭐ 3 Stars", value=3),
    app_commands.Choice(name="⭐⭐⭐⭐ 4 Stars", value=4),
    app_commands.Choice(name="⭐⭐⭐⭐⭐ 5 Stars", value=5),
])
async def vouch(interaction: discord.Interaction, user: discord.Member, rating: app_commands.Choice[int], comment: str):
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ You cannot vouch for yourself!", ephemeral=True)
        return
    
    v_id = generate_vouch_id()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vouches VALUES (?, ?, ?, ?, ?, ?, ?)",
        (v_id, interaction.guild.id, interaction.user.id, user.id, rating.value, comment, datetime.utcnow())
    )
    conn.commit()
    conn.close()

    embed = create_vouch_embed(interaction.guild, interaction.user, user, rating.value, comment, v_id)
    await interaction.response.send_message(embed=embed)

# 2. /autovouch
@bot.tree.command(name="autovouch", description="Generate random user-to-user vouches.")
@app_commands.describe(voucher_role="Role of members who will vouch", recipient_role="Role of members receiving vouches", comments_csv="Comma separated list of up to 30 comments")
async def autovouch(interaction: discord.Interaction, voucher_role: discord.Role, recipient_role: discord.Role, comments_csv: str):
    await interaction.response.defer()
    
    vouchers = voucher_role.members
    recipients = recipient_role.members
    
    if not vouchers or not recipients:
        await interaction.followup.send("❌ Not enough members found in one or both selected roles.")
        return

    comments = [c.strip() for c in comments_csv.split(",") if c.strip()]
    if not comments:
        await interaction.followup.send("❌ Please provide at least one valid comment.")
        return

    voucher = random.choice(vouchers)
    recipient = random.choice(recipients)
    rating = random.randint(3, 5)
    comment = random.choice(comments[:30])
    v_id = generate_vouch_id()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vouches VALUES (?, ?, ?, ?, ?, ?, ?)",
        (v_id, interaction.guild.id, voucher.id, recipient.id, rating, comment, datetime.utcnow())
    )
    conn.commit()
    conn.close()

    embed = create_vouch_embed(interaction.guild, voucher, recipient, rating, comment, v_id)
    await interaction.followup.send(embed=embed)

# 3. /server_vouch
@bot.tree.command(name="server_vouch", description="Generate an automated vouch for the server.")
@app_commands.describe(voucher_role="Role of members providing server vouch", comments_csv="Comma separated list of comments")
async def server_vouch(interaction: discord.Interaction, voucher_role: discord.Role, comments_csv: str):
    await interaction.response.defer()

    vouchers = voucher_role.members
    if not vouchers:
        await interaction.followup.send("❌ No members found in the specified voucher role.")
        return

    comments = [c.strip() for c in comments_csv.split(",") if c.strip()]
    if not comments:
        await interaction.followup.send("❌ Please provide at least one valid comment.")
        return

    voucher = random.choice(vouchers)
    rating = random.randint(3, 5)
    comment = random.choice(comments[:30])
    v_id = generate_vouch_id()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vouches VALUES (?, ?, ?, ?, ?, ?, ?)",
        (v_id, interaction.guild.id, voucher.id, 0, rating, comment, datetime.utcnow()) # 0 denotes server
    )
    conn.commit()
    conn.close()

    embed = create_vouch_embed(interaction.guild, voucher, None, rating, comment, v_id, is_server=True)
    await interaction.followup.send(embed=embed)

# 4. /set_vouch
@bot.tree.command(name="set_vouch", description="Set the total number of vouches for a user (Admin).")
@app_commands.checks.has_permissions(administrator=True)
async def set_vouch(interaction: discord.Interaction, user: discord.Member, count: int):
    if count < 0:
        await interaction.response.send_message("❌ Count cannot be negative.", ephemeral=True)
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vouches WHERE target_id = ? AND guild_id = ?", (user.id, interaction.guild.id))
    
    for _ in range(count):
        v_id = generate_vouch_id()
        cursor.execute(
            "INSERT INTO vouches VALUES (?, ?, ?, ?, ?, ?, ?)",
            (v_id, interaction.guild.id, interaction.user.id, user.id, 5, "Manual Admin Override Vouch", datetime.utcnow())
        )
    conn.commit()
    conn.close()

    await interaction.response.send_message(f"✅ Set **{user.display_name}**'s total vouches to **{count}**.")

# 5. /remove_vouch
@bot.tree.command(name="remove_vouch", description="Remove a specific vouch using its Vouch ID (Admin).")
@app_commands.checks.has_permissions(administrator=True)
async def remove_vouch(interaction: discord.Interaction, vouch_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id FROM vouches WHERE vouch_id = ? AND guild_id = ?", (vouch_id, interaction.guild.id))
    result = cursor.fetchone()

    if not result:
        await interaction.response.send_message("❌ Vouch ID not found.", ephemeral=True)
        conn.close()
        return

    cursor.execute("DELETE FROM vouches WHERE vouch_id = ? AND guild_id = ?", (vouch_id, interaction.guild.id))
    conn.commit()
    conn.close()

    await interaction.response.send_message(f"🗑️ Vouch ID **{vouch_id}** removed successfully.")

# 6. /vouches
@bot.tree.command(name="vouches", description="Check total vouches and average rating for a user or server.")
async def vouches(interaction: discord.Interaction, user: discord.Member = None):
    target_id = user.id if user else 0 # 0 for server
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT rating FROM vouches WHERE target_id = ? AND guild_id = ?", (target_id, interaction.guild.id))
    ratings = [row[0] for row in cursor.fetchall()]
    conn.close()

    total_vouches = len(ratings)
    avg_rating = round(sum(ratings) / total_vouches, 2) if total_vouches > 0 else 0.0

    embed = discord.Embed(title="📊 Vouch Profile", color=discord.Color.blue())
    if user:
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        embed.add_field(name="User", value=user.mention, inline=True)
    else:
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.add_field(name="Target", value="🏢 Server Vouches", inline=True)

    embed.add_field(name="Total Vouches", value=f"**{total_vouches}**", inline=True)
    embed.add_field(name="Average Rating", value=f"⭐ **{avg_rating}/5.0**", inline=True)
    await interaction.response.send_message(embed=embed)

# 7. /vouch_leaderboard
@bot.tree.command(name="vouch_leaderboard", description="Displays the server vouch leaderboard.")
async def vouch_leaderboard(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT target_id, COUNT(*) as cnt, AVG(rating) as avg_r 
        FROM vouches 
        WHERE guild_id = ? AND target_id != 0
        GROUP BY target_id 
        ORDER BY cnt DESC 
        LIMIT 10
    """, (interaction.guild.id,))
    results = cursor.fetchall()
    conn.close()

    if not results:
        await interaction.response.send_message("🏆 No vouches recorded yet!")
        return

    description = ""
    medals = ["🥇", "🥈", "🥉"]
    for idx, (target_id, count, avg_r) in enumerate(results, start=1):
        prefix = medals[idx-1] if idx <= 3 else f"`#{idx}`"
        description += f"{prefix} <@{target_id}> • **{count}** vouches (Avg: ⭐ {avg_r:.1f})\n"

    embed = discord.Embed(
        title="🏆 Vouch Leaderboard",
        description=description,
        color=discord.Color.purple(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Server: {interaction.guild.name}")
    await interaction.response.send_message(embed=embed)

# ------------------------------------------------------------------------------
# 5. INITIALIZATION
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # Start Flask server thread
    threading.Thread(target=run_flask, daemon=True).start()

    # Start Discord Bot
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable not set.")
    bot.run(TOKEN)
