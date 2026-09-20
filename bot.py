import asyncio
import os
import random
import sqlite3
import string
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# ------------------------------------------------------------------------------
# 1. FLASK WEB SERVER (For Render Hosting Keep-Alive)
# ------------------------------------------------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "MM Vouch Bot - Online and Operational"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ------------------------------------------------------------------------------
# 2. DATABASE SETUP
# ------------------------------------------------------------------------------
DB_NAME = "vouches.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
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

def generate_vouch_id():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

# Active background loop storage
active_tasks = {
    "user_autovouch": {},
    "server_autovouch": {}
}

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

# Helper: Fetch User cleanly (Prevents ID leak if uncached)
async def resolve_user(user_id: int) -> discord.User | str:
    if user_id == 0:
        return "Server"
    try:
        user = bot.get_user(user_id)
        if not user:
            user = await bot.fetch_user(user_id)
        return user
    except Exception:
        return "Unknown User"

# Helper: Get rank based on total vouches
def get_rank(total_vouches: int) -> int:
    rank = total_vouches // 100
    return min(rank, 10)

# Helper: Build Vouch Embed
def build_vouch_embed(guild: discord.Guild, voucher: discord.User | discord.Member, target: discord.User | discord.Member | None, rating: int, comment: str, vouch_id: str, total_vouches: int, is_server: bool = False) -> discord.Embed:
    stars = "⭐" * rating
    embed = discord.Embed(
        title="✨ New Verified Vouch ✨",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )

    # Top message
    # (This will be added outside the embed when sending, so keep for now)

    # Voucher details
    voucher_name = getattr(voucher, "display_name", str(voucher))
    embed.add_field(name="👤 Voucher", value=f"**{voucher_name}** ({voucher.mention})", inline=True)

    # Recipient details
    if is_server:
        embed.add_field(name="🏢 Recipient", value=f"**{guild.name}**", inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
    else:
        target_name = getattr(target, "display_name", str(target))
        embed.add_field(name="🎯 Recipient", value=f"**{target_name}** ({target.mention})", inline=True)
        if target and hasattr(target, "display_avatar"):
            embed.set_thumbnail(url=target.display_avatar.url)

    embed.add_field(name="⭐ Rating", value=f"{stars} (`{rating}/5`)", inline=False)
    # Removed feedback command from embed
    # embed.add_field(name="💬 Feedback", value=f"```\n{comment}\n```", inline=False)

    # Add rank
    rank = get_rank(total_vouches)
    embed.add_field(name="🏅 Rank", value=f"**Rank {rank}**", inline=True)

    embed.set_footer(
        text=f"Server: {guild.name} • Vouch ID: {vouch_id}",
        icon_url=guild.icon.url if guild.icon else None
    )
    return embed

# Save vouch to database
def save_vouch_to_db(vouch_id: str, guild_id: int, voucher_id: int, target_id: int, rating: int, comment: str):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO vouches VALUES (?, ?, ?, ?, ?, ?, ?)",
            (vouch_id, guild_id, voucher_id, target_id, rating, comment, datetime.utcnow())
        )
        conn.commit()

# Helper: Count total vouches for a target
def get_total_vouches(guild_id: int, target_id: int) -> int:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM vouches WHERE target_id = ? AND guild_id = ?",
            (target_id, guild_id)
        )
        count = cursor.fetchone()[0]
        return count

# Helper: Count total vouches for a user (used in /vouches)
def get_user_total_vouches(guild_id: int, user_id: int) -> int:
    return get_total_vouches(guild_id, user_id)

# Background auto-vouch user loop
async def auto_vouch_user_loop(channel: discord.TextChannel, voucher_role: discord.Role, recipient_role: discord.Role, comments: list):
    guild = channel.guild
    while True:
        try:
            delay = random.randint(180, 300)
            await asyncio.sleep(delay)

            vouchers = voucher_role.members
            recipients = recipient_role.members

            if not vouchers or not recipients:
                continue

            voucher = random.choice(vouchers)
            recipient = random.choice(recipients)
            rating = random.randint(3, 5)
            comment = random.choice(comments)
            v_id = generate_vouch_id()

            save_vouch_to_db(v_id, guild.id, voucher.id, recipient.id, rating, comment)
            total_vouches = get_total_vouches(guild.id, recipient.id)
            embed = build_vouch_embed(guild, voucher, recipient, rating, comment, v_id, total_vouches, is_server=False)
            top_msg = f"{recipient.mention} got vouched +1 and has {total_vouches} vouches!"
            await channel.send(content=top_msg, embed=embed)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in user auto-vouch loop ({guild.name}): {e}")

# Background auto-vouch server loop
async def auto_vouch_server_loop(channel: discord.TextChannel, voucher_role: discord.Role, comments: list):
    guild = channel.guild
    while True:
        try:
            delay = random.randint(180, 300)
            await asyncio.sleep(delay)

            vouchers = voucher_role.members
            if not vouchers:
                continue

            voucher = random.choice(vouchers)
            rating = random.randint(3, 5)
            comment = random.choice(comments)
            v_id = generate_vouch_id()

            # Server vouch, target_id=0
            save_vouch_to_db(v_id, guild.id, voucher.id, 0, rating, comment)
            total_vouches = get_total_vouches(guild.id, 0)
            embed = build_vouch_embed(guild, voucher, None, rating, comment, v_id, total_vouches, is_server=True)
            top_msg = f"Server got vouched +1 and has {total_vouches} vouches!"
            await channel.send(content=top_msg, embed=embed)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in server auto-vouch ({guild.name}): {e}")

# ------------------------------------------------------------------------------
# 4. SLASH COMMANDS
# ------------------------------------------------------------------------------
# 1. /vouch
@bot.tree.command(name="vouch", description="Submit a manual vouch for a user.")
@app_commands.describe(user="The member to vouch for", rating="Rating (1-5 stars)", comment="Feedback details")
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
    save_vouch_to_db(v_id, interaction.guild.id, interaction.user.id, user.id, rating.value, comment)
    total_vouches = get_total_vouches(interaction.guild.id, user.id)
    embed = build_vouch_embed(interaction.guild, interaction.user, user, rating.value, comment, v_id, total_vouches, is_server=False)
    top_msg = f"{user.mention} got vouched +1 and has {total_vouches} vouches!"
    await interaction.response.send_message(content=top_msg, embed=embed)

# 2. /autovouch_start
@bot.tree.command(name="autovouch_start", description="Start auto-vouching user-to-user every 2-5 minutes.")
@app_commands.describe(
    voucher_role="Role for member who gives vouch",
    recipient_role="Role for member who receives vouch",
    comments_csv="Comma separated comments (up to 30)"
)
@app_commands.checks.has_permissions(administrator=True)
async def autovouch_start(interaction: discord.Interaction, voucher_role: discord.Role, recipient_role: discord.Role, comments_csv: str):
    guild_id = interaction.guild.id
    if guild_id in active_tasks["user_autovouch"]:
        await interaction.response.send_message("⚠️ User Auto-Vouch is already running! Stop it first with `/autovouch_stop`.", ephemeral=True)
        return

    comments = [c.strip() for c in comments_csv.split(",") if c.strip()][:30]
    if not comments:
        await interaction.response.send_message("❌ Please provide at least one valid comment.", ephemeral=True)
        return

    task = asyncio.create_task(
        auto_vouch_user_loop(interaction.channel, voucher_role, recipient_role, comments)
    )
    active_tasks["user_autovouch"][guild_id] = task

    embed = discord.Embed(
        title="🚀 User Auto-Vouch Started",
        description=f"Auto-vouching active in {interaction.channel.mention}.\n**Interval:** Randomly every 2–5 minutes.\n**Voucher Role:** {voucher_role.mention}\n**Recipient Role:** {recipient_role.mention}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

# 3. /autovouch_stop
@bot.tree.command(name="autovouch_stop", description="Stop the user auto-vouch background loop.")
@app_commands.checks.has_permissions(administrator=True)
async def autovouch_stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    task = active_tasks["user_autovouch"].pop(guild_id, None)

    if task:
        task.cancel()
        await interaction.response.send_message("🛑 **User Auto-Vouch** system successfully stopped.")
    else:
        await interaction.response.send_message("❌ No active User Auto-Vouch loop found for this server.", ephemeral=True)

# 4. /server_vouch_start
@bot.tree.command(name="server_vouch_start", description="Start auto-vouching the Server every 2-5 minutes.")
@app_commands.describe(voucher_role="Role of members vouching for the server", comments_csv="Comma separated comments")
@app_commands.checks.has_permissions(administrator=True)
async def server_vouch_start(interaction: discord.Interaction, voucher_role: discord.Role, comments_csv: str):
    guild_id = interaction.guild.id
    if guild_id in active_tasks["server_autovouch"]:
        await interaction.response.send_message("⚠️ Server Auto-Vouch is already running! Stop it first with `/server_vouch_stop`.", ephemeral=True)
        return

    comments = [c.strip() for c in comments_csv.split(",") if c.strip()][:30]
    if not comments:
        await interaction.response.send_message("❌ Please provide at least one valid comment.", ephemeral=True)
        return

    task = asyncio.create_task(
        auto_vouch_server_loop(interaction.channel, voucher_role, comments)
    )
    active_tasks["server_autovouch"][guild_id] = task

    embed = discord.Embed(
        title="🚀 Server Auto-Vouch Started",
        description=f"Server Auto-vouching active in {interaction.channel.mention}.\n**Interval:** Randomly every 2–5 minutes.\n**Voucher Role:** {voucher_role.mention}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

# 5. /server_vouch_stop
@bot.tree.command(name="server_vouch_stop", description="Stop the server auto-vouch background loop.")
@app_commands.checks.has_permissions(administrator=True)
async def server_vouch_stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    task = active_tasks["server_autovouch"].pop(guild_id, None)

    if task:
        task.cancel()
        await interaction.response.send_message("🛑 **Server Auto-Vouch** system successfully stopped.")
    else:
        await interaction.response.send_message("❌ No active Server Auto-Vouch loop found for this server.", ephemeral=True)

# 6. /set_vouch
@bot.tree.command(name="set_vouch", description="Force-set total vouch count for a user (Admin).")
@app_commands.checks.has_permissions(administrator=True)
async def set_vouch(interaction: discord.Interaction, user: discord.Member, count: int):
    if count < 0:
        await interaction.response.send_message("❌ Count cannot be negative.", ephemeral=True)
        return

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vouches WHERE target_id = ? AND guild_id = ?", (user.id, interaction.guild.id))
        for _ in range(count):
            v_id = generate_vouch_id()
            cursor.execute(
                "INSERT INTO vouches VALUES (?, ?, ?, ?, ?, ?, ?)",
                (v_id, interaction.guild.id, interaction.user.id, user.id, 5, "Manual Admin Override Vouch", datetime.utcnow())
            )
        conn.commit()

    await interaction.response.send_message(f"✅ Set **{user.display_name}** ({user.mention}) total vouches to **{count}**.")

# 7. /remove_vouch
@bot.tree.command(name="remove_vouch", description="Remove a specific vouch using its Vouch ID (Admin).")
@app_commands.checks.has_permissions(administrator=True)
async def remove_vouch(interaction: discord.Interaction, vouch_id: str):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT target_id FROM vouches WHERE vouch_id = ? AND guild_id = ?", (vouch_id, interaction.guild.id))
        result = cursor.fetchone()

        if not result:
            await interaction.response.send_message("❌ Vouch ID not found.", ephemeral=True)
            return

        cursor.execute("DELETE FROM vouches WHERE vouch_id = ? AND guild_id = ?", (vouch_id, interaction.guild.id))
        conn.commit()

    await interaction.response.send_message(f"🗑️ Vouch ID **{vouch_id}** removed successfully.")

# 8. /vouches
@bot.tree.command(name="vouches", description="Check total vouches and average rating for a user or server.")
async def vouches(interaction: discord.Interaction, user: discord.Member = None):
    target_id = user.id if user else 0
    guild_id = interaction.guild.id
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT rating FROM vouches WHERE target_id = ? AND guild_id = ?", (target_id, guild_id))
        ratings = [row[0] for row in cursor.fetchall()]

        total_vouches = len(ratings)
        avg_rating = round(sum(ratings) / total_vouches, 2) if total_vouches > 0 else 0.0
        cursor.execute("SELECT COUNT(*) FROM vouches WHERE target_id = ? AND guild_id = ?", (target_id, guild_id))
        total_vouches_for_user = cursor.fetchone()[0]

    embed = discord.Embed(title="📊 Vouch Profile Overview", color=discord.Color.blue())

    if user:
        embed.set_author(name=f"{user.display_name}'s Stats", icon_url=user.display_avatar.url)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="User", value=f"**{user.display_name}** ({user.mention})", inline=True)
        top_msg = f"{user.mention} got vouched +1 and has {total_vouches_for_user} vouches!"
        await interaction.response.send_message(content=top_msg, embed=embed)
    else:
        embed.set_author(name=f"{interaction.guild.name}'s Stats", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.add_field(name="Target", value="🏢 Server Profile", inline=True)
        top_msg = f"Server got vouched +1 and has {total_vouches_for_user} vouches!"
        await interaction.response.send_message(content=top_msg, embed=embed)

# 9. /vouch_leaderboard
@bot.tree.command(name="vouch_leaderboard", description="Displays the top vouch leaderboard.")
async def vouch_leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    with sqlite3.connect(DB_NAME) as conn:
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

    if not results:
        await interaction.followup.send("🏆 No vouches recorded yet in this server!")
        return

    description = ""
    medals = ["🥇", "🥈", "🥉"]
    for idx, (target_id, count, avg_r) in enumerate(results, start=1):
        prefix = medals[idx-1] if idx <= 3 else f"`#{idx}`"
        resolved_user = await resolve_user(target_id)
        if isinstance(resolved_user, discord.User) or isinstance(resolved_user, discord.Member):
            user_str = f"**{resolved_user.display_name}** ({resolved_user.mention})"
        else:
            user_str = f"User (`ID: {target_id}`)"
        description += f"{prefix} {user_str} • **{int(count)}** vouches (⭐ {avg_r:.1f})\n"

    embed = discord.Embed(
        title="🏆 Server Vouch Leaderboard",
        description=description,
        color=discord.Color.purple(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Server: {interaction.guild.name}")
    await interaction.followup.send(embed=embed)

# ------------------------------------------------------------------------------
# 6. INITIALIZATION
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is missing.")
    bot.run(TOKEN)
