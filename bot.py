import asyncio
import os
import random
import sqlite3
import string
import threading
import time
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# ------------------------------------------------------------------------------
# 1. FLASK KEEP-ALIVE SERVER (FOR RENDER / KOYEB)
# ------------------------------------------------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "⚡ Middleman Vouch Bot - Online and Ready"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ------------------------------------------------------------------------------
# 2. DATABASE ARCHITECTURE & HELPER FUNCTIONS
# ------------------------------------------------------------------------------
DB_NAME = "vouches.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Table for individual vouch logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vouches (
            vouch_id TEXT PRIMARY KEY,
            guild_id INTEGER,
            voucher_id INTEGER,
            target_id INTEGER, -- 0 represents Server Vouch
            rating INTEGER,
            comment TEXT,
            timestamp INTEGER
        )
    """)
    
    # Table for manual total vouches overrides/tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vouch_counts (
            guild_id INTEGER,
            target_id INTEGER,
            count INTEGER,
            PRIMARY KEY (guild_id, target_id)
        )
    """)
    conn.commit()
    conn.close()

def generate_vouch_id() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def get_vouch_count(guild_id: int, target_id: int) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT count FROM vouch_counts WHERE guild_id = ? AND target_id = ?", (guild_id, target_id))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def add_vouch(guild_id: int, voucher_id: int, target_id: int, rating: int, comment: str = None) -> tuple[str, int]:
    v_id = generate_vouch_id()
    now = int(time.time())
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Insert vouch record
    cursor.execute(
        "INSERT INTO vouches (vouch_id, guild_id, voucher_id, target_id, rating, comment, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (v_id, guild_id, voucher_id, target_id, rating, comment, now)
    )
    
    # Update total count
    cursor.execute("""
        INSERT INTO vouch_counts (guild_id, target_id, count)
        VALUES (?, ?, 1)
        ON CONFLICT(guild_id, target_id) DO UPDATE SET count = count + 1
    """, (guild_id, target_id))
    
    conn.commit()
    
    # Fetch updated count
    cursor.execute("SELECT count FROM vouch_counts WHERE guild_id = ? AND target_id = ?", (guild_id, target_id))
    total_count = cursor.fetchone()[0]
    
    conn.close()
    return v_id, total_count

def set_vouch_count(guild_id: int, target_id: int, count: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO vouch_counts (guild_id, target_id, count)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id, target_id) DO UPDATE SET count = ?
    """, (guild_id, target_id, count, count))
    conn.commit()
    conn.close()

def get_mm_rank(vouch_count: int) -> str:
    """Assigns ranks every 100 vouches."""
    if vouch_count >= 500:
        return "💎 **Prime MM**"
    elif vouch_count >= 400:
        return "👑 **Master MM**"
    elif vouch_count >= 300:
        return "🟣 **Elite MM**"
    elif vouch_count >= 200:
        return "🔵 **Senior MM**"
    elif vouch_count >= 100:
        return "🟢 **Junior MM**"
    else:
        return "⚪ **Unranked MM**"

def render_stars(rating: int) -> str:
    return "⭐" * rating + "🔌" * (5 - rating)

# Default comment library for server auto-vouch
DEFAULT_SERVER_COMMENTS = [
    "Fast and reliable middleman service!", "Extremely safe trade, 10/10.",
    "Smooth transaction, highly recommended!", "Very professional MM.",
    "Best middleman server on Discord!", "Super quick response time.",
    "Legit and trustworthy deals.", "Always feel safe trading here.",
    "100% legit MM service.", "Quick and secure transaction.",
    "Instant transfer, love this server!", "Handled large deal perfectly.",
    "Friendly staff and fast MM.", "Zero hassle, great service.",
    "Kept both parties safe!", "Top tier middleman execution.",
    "Vouched! Seamless experience.", "Flawless service as always.",
    "Fastest MM service out there.", "Appreciate the safety provided!",
    "Super clean trade.", "Safe, trusted, and efficient.",
    "Will definitely use this MM server again!", "Highly professional environment.",
    "Trusted for big transactions.", "Quickest deal I have ever had.",
    "Amazing middleman, made it easy.", "Great service, no complaints!",
    "No doubts about safety here.", "Easiest trade ever thanks to this MM!"
]

active_tasks = {
    "user_autovouch": {},
    "server_autovouch": {}
}

# ------------------------------------------------------------------------------
# 3. DISCORD BOT SETUP & EMBED BUILDERS
# ------------------------------------------------------------------------------
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    init_db()
    print("Caching server member lists...")
    for guild in bot.guilds:
        try:
            await guild.chunk()
        except Exception as e:
            print(f"Failed to chunk guild {guild.name}: {e}")
            
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print(f"Logged in as {bot.user.name} ({bot.user.id})")

def build_vouch_embed(
    guild: discord.Guild, 
    voucher: discord.Member, 
    target: discord.Member, 
    vouch_id: str, 
    total_vouches: int,
    rating: int,
    comment: str = None,
    is_server: bool = False
) -> discord.Embed:
    current_time_unix = int(time.time())
    
    embed = discord.Embed(
        title="✅ VERIFIED VOUCH",
        color=0x2B2D31
    )

    embed.add_field(name="👤 Voucher", value=voucher.mention, inline=True)

    if is_server:
        embed.add_field(name="🏢 Recipient", value=f"**{guild.name}**", inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
    else:
        mm_rank = get_mm_rank(total_vouches)
        embed.add_field(name="🎯 Middleman", value=target.mention, inline=True)
        embed.add_field(name="🎖️ MM Rank", value=mm_rank, inline=True)
        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)

    embed.add_field(name="⭐ Rating", value=f"{render_stars(rating)} (`{rating}/5`)", inline=False)
    
    if comment:
        embed.add_field(name="💬 Comment", value=f"*{comment}*", inline=False)

    embed.add_field(name="📈 Total Deals Vouched", value=f"**{total_vouches}**", inline=True)
    embed.add_field(name="⏰ Time", value=f"<t:{current_time_unix}:R>", inline=True)

    footer_icon = guild.icon.url if guild.icon else None
    embed.set_footer(text=f"{guild.name} • Vouch ID: {vouch_id}", icon_url=footer_icon)

    return embed

# ------------------------------------------------------------------------------
# 4. BACKGROUND AUTO-VOUCH LOOPS
# ------------------------------------------------------------------------------
async def auto_vouch_user_loop(
    channel: discord.TextChannel, 
    voucher_role: discord.Role, 
    target_role: discord.Role, 
    min_delay_sec: int,
    max_delay_sec: int
):
    guild = channel.guild
    while True:
        try:
            delay = random.randint(min_delay_sec, max_delay_sec)
            await asyncio.sleep(delay)

            vouchers = [m for m in voucher_role.members if not m.bot]
            recipients = [m for m in target_role.members if not m.bot]

            if not vouchers or not recipients:
                continue

            voucher = random.choice(vouchers)
            recipient = random.choice(recipients)
            
            if voucher.id == recipient.id and len(vouchers) > 1:
                vouchers_filtered = [v for v in vouchers if v.id != recipient.id]
                voucher = random.choice(vouchers_filtered)

            rating = random.randint(3, 5)
            v_id, total_vouches = add_vouch(guild.id, voucher.id, recipient.id, rating)

            message_content = f"✅ 🎉 {recipient.mention} has received +1 vouch! **({total_vouches} Total Vouches)**"
            
            embed = build_vouch_embed(
                guild, voucher, recipient, v_id, 
                total_vouches=total_vouches, rating=rating, is_server=False
            )
            await channel.send(content=message_content, embed=embed)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in user auto-vouch loop ({guild.name}): {e}")

async def auto_vouch_server_loop(
    channel: discord.TextChannel, 
    voucher_role: discord.Role, 
    comments_list: list[str],
    min_delay_sec: int,
    max_delay_sec: int
):
    guild = channel.guild
    while True:
        try:
            delay = random.randint(min_delay_sec, max_delay_sec)
            await asyncio.sleep(delay)

            vouchers = [m for m in voucher_role.members if not m.bot]
            if not vouchers:
                continue

            voucher = random.choice(vouchers)
            rating = random.randint(3, 5)
            comment = random.choice(comments_list)

            v_id, total_vouches = add_vouch(guild.id, voucher.id, 0, rating, comment)

            message_content = f"✅ 🎉 **{guild.name}** has received +1 server vouch! **({total_vouches} Total Vouches)**"

            embed = build_vouch_embed(
                guild, voucher, None, v_id, 
                total_vouches=total_vouches, rating=rating, comment=comment, is_server=True
            )
            await channel.send(content=message_content, embed=embed)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in server auto-vouch loop ({guild.name}): {e}")

# ------------------------------------------------------------------------------
# 5. SLASH COMMANDS
# ------------------------------------------------------------------------------

# 1. /vouch
@bot.tree.command(name="vouch", description="Submit a manual vouch for a middleman.")
@app_commands.describe(
    middleman="The middleman you are vouching for",
    rating="Star rating from 1 to 5",
    comment="Optional review feedback"
)
@app_commands.choices(rating=[
    app_commands.Choice(name="⭐ 1 Star", value=1),
    app_commands.Choice(name="⭐⭐ 2 Stars", value=2),
    app_commands.Choice(name="⭐⭐⭐ 3 Stars", value=3),
    app_commands.Choice(name="⭐⭐⭐⭐ 4 Stars", value=4),
    app_commands.Choice(name="⭐⭐⭐⭐⭐ 5 Stars", value=5),
])
async def vouch(interaction: discord.Interaction, middleman: discord.Member, rating: int, comment: str = None):
    if middleman.id == interaction.user.id:
        await interaction.response.send_message("❌ You cannot vouch for yourself!", ephemeral=True)
        return

    v_id, total_vouches = add_vouch(interaction.guild.id, interaction.user.id, middleman.id, rating, comment)

    message_content = f"🎉 {middleman.mention} has received +1 vouch! **({total_vouches} Total Vouches)**"

    embed = build_vouch_embed(
        interaction.guild, interaction.user, middleman, v_id, 
        total_vouches=total_vouches, rating=rating, comment=comment, is_server=False
    )
    await interaction.response.send_message(content=message_content, embed=embed)

# 2. /autovouch_users
@bot.tree.command(name="autovouch_users", description="Start automated user vouching loop.")
@app_commands.describe(
    voucher_role="Role providing vouches",
    middleman_role="Role receiving vouches",
    min_delay_seconds="Minimum delay in seconds (Default: 300)",
    max_delay_seconds="Maximum delay in seconds (Default: 420)"
)
@app_commands.checks.has_permissions(administrator=True)
async def autovouch_users(
    interaction: discord.Interaction, 
    voucher_role: discord.Role, 
    middleman_role: discord.Role, 
    min_delay_seconds: int = 300,
    max_delay_seconds: int = 420
):
    guild_id = interaction.guild.id
    if guild_id in active_tasks["user_autovouch"]:
        await interaction.response.send_message("⚠️ Auto-vouch loop is already active! Stop it first.", ephemeral=True)
        return

    task = asyncio.create_task(
        auto_vouch_user_loop(
            interaction.channel, voucher_role, middleman_role, 
            min_delay_seconds, max_delay_seconds
        )
    )
    active_tasks["user_autovouch"][guild_id] = task

    embed = discord.Embed(
        title="🚀 User Auto-Vouch Active",
        description=(
            f"Active in {interaction.channel.mention}.\n\n"
            f"• **Delay:** `{min_delay_seconds}`s - `{max_delay_seconds}`s\n"
            f"• **Vouchers:** {voucher_role.mention}\n"
            f"• **Middlemen:** {middleman_role.mention}"
        ),
        color=0x57F287
    )
    await interaction.response.send_message(embed=embed)

# 3. /server_vouch
@bot.tree.command(name="server_vouch", description="Start automated server vouching loop.")
@app_commands.describe(
    voucher_role="Role providing vouches for the server",
    custom_comments="Comma-separated custom comments (Leave empty for default library)",
    min_delay_seconds="Minimum delay in seconds (Default: 300)",
    max_delay_seconds="Maximum delay in seconds (Default: 420)"
)
@app_commands.checks.has_permissions(administrator=True)
async def server_vouch(
    interaction: discord.Interaction, 
    voucher_role: discord.Role, 
    custom_comments: str = None,
    min_delay_seconds: int = 300,
    max_delay_seconds: int = 420
):
    guild_id = interaction.guild.id
    if guild_id in active_tasks["server_autovouch"]:
        await interaction.response.send_message("⚠️ Server Auto-Vouch is already active!", ephemeral=True)
        return

    comments_list = [c.strip() for c in custom_comments.split(",")] if custom_comments else DEFAULT_SERVER_COMMENTS

    task = asyncio.create_task(
        auto_vouch_server_loop(
            interaction.channel, voucher_role, comments_list,
            min_delay_seconds, max_delay_seconds
        )
    )
    active_tasks["server_autovouch"][guild_id] = task

    embed = discord.Embed(
        title="🚀 Server Auto-Vouch Active",
        description=(
            f"Active in {interaction.channel.mention}.\n\n"
            f"• **Vouchers:** {voucher_role.mention}\n"
            f"• **Comments Available:** `{len(comments_list)}`"
        ),
        color=0x57F287
    )
    await interaction.response.send_message(embed=embed)

# 4. /setvouch
@bot.tree.command(name="setvouch", description="Set total vouches count for a middleman or server.")
@app_commands.describe(user="Middleman to modify (Leave empty for server profile)", count="New total vouches")
@app_commands.checks.has_permissions(administrator=True)
async def setvouch(interaction: discord.Interaction, count: int, user: discord.Member = None):
    target_id = user.id if user else 0
    set_vouch_count(interaction.guild.id, target_id, count)
    
    target_name = user.mention if user else f"**{interaction.guild.name}**"
    await interaction.response.send_message(f"⚙️ Successfully set {target_name}'s total vouches to **{count}**.")

# 5. /removevouch
@bot.tree.command(name="removevouch", description="Remove a specific number of vouches from a user or server.")
@app_commands.describe(user="Middleman to modify (Leave empty for server profile)", count="Vouches to subtract")
@app_commands.checks.has_permissions(administrator=True)
async def removevouch(interaction: discord.Interaction, count: int, user: discord.Member = None):
    target_id = user.id if user else 0
    current = get_vouch_count(interaction.guild.id, target_id)
    new_count = max(0, current - count)
    
    set_vouch_count(interaction.guild.id, target_id, new_count)
    target_name = user.mention if user else f"**{interaction.guild.name}**"
    await interaction.response.send_message(f"🗑️ Deducted `{count}` vouches. {target_name} is now at **{new_count}** vouches.")

# 6. /vouches
@bot.tree.command(name="vouches", description="Check total vouches and MM rank for a user or server.")
@app_commands.describe(user="User profile to check (Leave empty for server profile)")
async def vouches(interaction: discord.Interaction, user: discord.Member = None):
    target_id = user.id if user else 0
    total_vouches = get_vouch_count(interaction.guild.id, target_id)

    embed = discord.Embed(title="📊 VOUCH PROFILE", color=0x5865F2)
    if user:
        embed.add_field(name="Middleman", value=user.mention, inline=True)
        embed.add_field(name="MM Rank", value=get_mm_rank(total_vouches), inline=True)
        if user.display_avatar:
            embed.set_thumbnail(url=user.display_avatar.url)
    else:
        embed.add_field(name="Target", value=f"🏢 **{interaction.guild.name}**", inline=True)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

    embed.add_field(name="Total Vouches", value=f"**{total_vouches}**", inline=False)
    
    footer_icon = interaction.guild.icon.url if interaction.guild.icon else None
    embed.set_footer(text=interaction.guild.name, icon_url=footer_icon)
    
    await interaction.response.send_message(embed=embed)

# 7. /vouch_leaderboard
@bot.tree.command(name="vouch_leaderboard", description="Display top middlemen in the server.")
async def vouch_leaderboard(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT target_id, count 
        FROM vouch_counts 
        WHERE guild_id = ? AND target_id != 0 AND count > 0
        ORDER BY count DESC 
        LIMIT 10
    """, (interaction.guild.id,))
    top_users = cursor.fetchall()
    conn.close()

    if not top_users:
        await interaction.response.send_message("❌ No middleman vouches recorded in this server yet.", ephemeral=True)
        return

    embed = discord.Embed(title=f"🏆 MIDDLEMAN LEADERBOARD", color=0xFEE75C)
    leaderboard_text = ""
    medals = ["🥇", "🥈", "🥉"]

    for idx, (target_id, count) in enumerate(top_users, start=1):
        member = interaction.guild.get_member(target_id)
        name = f"{member.mention}" if member else f"<@{target_id}>"
        rank_badge = medals[idx - 1] if idx <= 3 else f"`#{idx}`"
        
        leaderboard_text += f"{rank_badge} {name} • **{count}** Vouches ({get_mm_rank(count)})\n"

    embed.description = leaderboard_text
    footer_icon = interaction.guild.icon.url if interaction.guild.icon else None
    embed.set_footer(text=interaction.guild.name, icon_url=footer_icon)

    await interaction.response.send_message(embed=embed)

# ------------------------------------------------------------------------------
# 6. INITIALIZATION & EXECUTION
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is missing.")
    bot.run(TOKEN)
