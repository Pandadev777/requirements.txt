import asyncio
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

app = Flask(__name__)

@app.route("/")
def home():
    return "⚡ Advanced MM Vouch Bot - Active and Operational"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

DB_NAME = "vouches.db"

MIDDLEMAN_RANKS = [
    (100, "🥉 Bronze Middleman"),
    (200, "🥈 Silver Middleman"),
    (300, "🥇 Gold Middleman"),
    (400, "💎 Platinum Middleman"),
    (500, "💠 Diamond Middleman"),
    (600, "🔥 Elite Middleman"),
    (700, "⚜️ Master Middleman"),
    (800, "👑 Grandmaster Middleman"),
    (900, "🌟 Legendary Middleman"),
    (1000, "🏆 Mythic Middleman"),
]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vouches (
            vouch_id TEXT PRIMARY KEY,
            guild_id INTEGER,
            voucher_id INTEGER,
            target_id INTEGER,
            rating INTEGER,
            comment TEXT,
            timestamp DATETIME
        )
    """)
    conn.commit()
    conn.close()

def generate_vouch_id():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def get_vouch_count(guild_id: int, target_id: int) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM vouches WHERE guild_id = ? AND target_id = ?",
        (guild_id, target_id)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_middleman_rank(vouch_count: int):
    current_rank = "🔰 Unranked Middleman"
    next_rank_at = 100

    for threshold, rank_name in MIDDLEMAN_RANKS:
        if vouch_count >= threshold:
            current_rank = rank_name
        else:
            next_rank_at = threshold
            break
    else:
        next_rank_at = None

    if next_rank_at is None:
        progress = "Maximum rank reached"
    else:
        progress = f"{next_rank_at - vouch_count} vouches to next rank"

    return current_rank, progress

active_tasks = {
    "user_autovouch": {},
    "server_autovouch": {}
}

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

async def resolve_member(guild: discord.Guild, user_id: int):
    if user_id == 0:
        return "Server"

    member = guild.get_member(user_id)
    if not member:
        try:
            member = await guild.fetch_member(user_id)
        except Exception:
            try:
                member = await bot.fetch_user(user_id)
            except Exception:
                return None
    return member

def format_star_bar(rating: int) -> str:
    stars = "⭐" * rating
    bar = "█" * rating + "▒" * (5 - rating)
    return f"{stars} (`{bar}` **{rating}.0/5.0**)"

def build_advanced_vouch_embed(
    guild: discord.Guild,
    voucher,
    target,
    rating: int,
    vouch_id: str,
    is_server: bool = False,
    vouch_count: int = None
) -> discord.Embed:
    embed = discord.Embed(
        title="🛡️ TRANSACTION VOUCH VERIFIED",
        color=0x2B2D31,
        timestamp=datetime.utcnow()
    )

    v_name = (
        f"**{voucher.display_name}**\n(`@{voucher.name}`)"
        if hasattr(voucher, "name")
        else f"**{voucher}**"
    )
    embed.add_field(name="👤 Voucher", value=f"{v_name}\n{voucher.mention}", inline=True)

    if is_server:
        embed.add_field(
            name="🏢 Recipient",
            value=f"**{guild.name}**\n*(Official Server)*",
            inline=True
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        if vouch_count is None:
            vouch_count = get_vouch_count(guild.id, 0)

        rank_name, progress = get_middleman_rank(vouch_count)
        embed.add_field(
            name="🏅 Server Rank",
            value=f"{rank_name}\n`{vouch_count}` server vouches • {progress}",
            inline=True
        )
    else:
        t_name = (
            f"**{target.display_name}**\n(`@{target.name}`)"
            if hasattr(target, "name")
            else f"**{target}**"
        )
        embed.add_field(name="🎯 Recipient", value=f"{t_name}\n{target.mention}", inline=True)

        if hasattr(target, "display_avatar"):
            embed.set_thumbnail(url=target.display_avatar.url)

        if vouch_count is None:
            vouch_count = get_vouch_count(guild.id, target.id)

        rank_name, progress = get_middleman_rank(vouch_count)
        embed.add_field(
            name="🏅 Middleman Rank",
            value=f"{rank_name}\n`{vouch_count}` vouches • {progress}",
            inline=True
        )

    embed.add_field(name="📊 Satisfaction Rating", value=format_star_bar(rating), inline=False)

    unix_time = int(datetime.utcnow().timestamp())
    embed.add_field(name="⏰ Time", value=f"<t:{unix_time}:F> (<t:{unix_time}:R>)", inline=False)

    embed.set_footer(
        text=f"Server: {guild.name} • Vouch ID: {vouch_id} • Status: Verified ✔️",
        icon_url=guild.icon.url if guild.icon else None
    )
    return embed

def save_vouch_to_db(
    vouch_id: str,
    guild_id: int,
    voucher_id: int,
    target_id: int,
    rating: int
):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vouches VALUES (?, ?, ?, ?, ?, ?, ?)",
        (vouch_id, guild_id, voucher_id, target_id, rating, "", datetime.utcnow())
    )
    conn.commit()
    conn.close()

async def auto_vouch_user_loop(
    channel: discord.TextChannel,
    voucher_role: discord.Role,
    recipient_role: discord.Role
):
    guild = channel.guild
    while True:
        try:
            delay = random.randint(180, 300)
            await asyncio.sleep(delay)

            vouchers = [m for m in voucher_role.members if not m.bot]
            recipients = [m for m in recipient_role.members if not m.bot]

            if not vouchers or not recipients:
                continue

            voucher = random.choice(vouchers)
            recipient = random.choice(recipients)

            if voucher.id == recipient.id and len(vouchers) > 1:
                vouchers_filtered = [v for v in vouchers if v.id != recipient.id]
                voucher = random.choice(vouchers_filtered)

            rating = random.randint(3, 5)
            v_id = generate_vouch_id()

            save_vouch_to_db(v_id, guild.id, voucher.id, recipient.id, rating)
            count = get_vouch_count(guild.id, recipient.id)

            embed = build_advanced_vouch_embed(
                guild,
                voucher,
                recipient,
                rating,
                v_id,
                is_server=False,
                vouch_count=count
            )

            await channel.send(
                content=f"{recipient.mention} got **+1** vouch and is now at **{count}** vouches.",
                embed=embed
            )

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in user auto-vouch loop ({guild.name}): {e}")

async def auto_vouch_server_loop(
    channel: discord.TextChannel,
    voucher_role: discord.Role
):
    guild = channel.guild
    while True:
        try:
            delay = random.randint(180, 300)
            await asyncio.sleep(delay)

            vouchers = [m for m in voucher_role.members if not m.bot]
            if not vouchers:
                continue

            voucher = random.choice(vouchers)
            rating = random.randint(3, 5)
            v_id = generate_vouch_id()

            save_vouch_to_db(v_id, guild.id, voucher.id, 0, rating)
            count = get_vouch_count(guild.id, 0)

            embed = build_advanced_vouch_embed(
                guild,
                voucher,
                None,
                rating,
                v_id,
                is_server=True,
                vouch_count=count
            )

            await channel.send(
                content=f"🏢 **{guild.name}** got **+1** server vouch and is now at **{count}** vouches.",
                embed=embed
            )

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in server auto-vouch loop ({guild.name}): {e}")

@bot.tree.command(name="vouch", description="Submit an official vouch for a user.")
@app_commands.describe(
    user="The member to vouch for",
    rating="Rating (1-5 stars)"
)
@app_commands.choices(rating=[
    app_commands.Choice(name="⭐ 1 Star", value=1),
    app_commands.Choice(name="⭐⭐ 2 Stars", value=2),
    app_commands.Choice(name="⭐⭐⭐ 3 Stars", value=3),
    app_commands.Choice(name="⭐⭐⭐⭐ 4 Stars", value=4),
    app_commands.Choice(name="⭐⭐⭐⭐⭐ 5 Stars", value=5),
])
async def vouch(
    interaction: discord.Interaction,
    user: discord.Member,
    rating: app_commands.Choice[int]
):
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ You cannot vouch for yourself!", ephemeral=True)
        return

    v_id = generate_vouch_id()
    save_vouch_to_db(
        v_id,
        interaction.guild.id,
        interaction.user.id,
        user.id,
        rating.value
    )

    count = get_vouch_count(interaction.guild.id, user.id)
    embed = build_advanced_vouch_embed(
        interaction.guild,
        interaction.user,
        user,
        rating.value,
        v_id,
        is_server=False,
        vouch_count=count
    )

    await interaction.response.send_message(
        content=f"{user.mention} got **+1** vouch and is now at **{count}** vouches.",
        embed=embed
    )

@bot.tree.command(name="autovouch_start", description="Start user auto-vouching every 2-5 minutes.")
@app_commands.describe(
    voucher_role="Role of members providing vouches",
    recipient_role="Role of members receiving vouches"
)
@app_commands.checks.has_permissions(administrator=True)
async def autovouch_start(
    interaction: discord.Interaction,
    voucher_role: discord.Role,
    recipient_role: discord.Role
):
    guild_id = interaction.guild.id
    if guild_id in active_tasks["user_autovouch"]:
        await interaction.response.send_message(
            "⚠️ User Auto-Vouch is already active! Stop it with `/autovouch_stop` first.",
            ephemeral=True
        )
        return

    task = asyncio.create_task(
        auto_vouch_user_loop(interaction.channel, voucher_role, recipient_role)
    )
    active_tasks["user_autovouch"][guild_id] = task

    embed = discord.Embed(
        title="🚀 User Auto-Vouch System Online",
        description=(
            f"Auto-vouching deployed in {interaction.channel.mention}.\n\n"
            f"**Details:**\n"
            f"• **Interval:** 2 to 5 minutes (Randomized)\n"
            f"• **Vouchers:** {voucher_role.mention}\n"
            f"• **Recipients:** {recipient_role.mention}"
        ),
        color=0x57F287
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="autovouch_stop", description="Stop active user auto-vouching loop.")
@app_commands.checks.has_permissions(administrator=True)
async def autovouch_stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    task = active_tasks["user_autovouch"].pop(guild_id, None)

    if task:
        task.cancel()
        await interaction.response.send_message("🛑 **User Auto-Vouch** loop terminated successfully.")
    else:
        await interaction.response.send_message("❌ No active User Auto-Vouch loop found.", ephemeral=True)

@bot.tree.command(name="server_vouch_start", description="Start server auto-vouching every 2-5 minutes.")
@app_commands.describe(
    voucher_role="Role of members vouching for the server"
)
@app_commands.checks.has_permissions(administrator=True)
async def server_vouch_start(
    interaction: discord.Interaction,
    voucher_role: discord.Role
):
    guild_id = interaction.guild.id
    if guild_id in active_tasks["server_autovouch"]:
        await interaction.response.send_message(
            "⚠️ Server Auto-Vouch is already active! Stop it with `/server_vouch_stop` first.",
            ephemeral=True
        )
        return

    task = asyncio.create_task(
        auto_vouch_server_loop(interaction.channel, voucher_role)
    )
    active_tasks["server_autovouch"][guild_id] = task

    embed = discord.Embed(
        title="🚀 Server Auto-Vouch System Online",
        description=(
            f"Server Auto-vouching deployed in {interaction.channel.mention}.\n\n"
            f"**Details:**\n"
            f"• **Interval:** 2 to 5 minutes (Randomized)\n"
            f"• **Vouchers:** {voucher_role.mention}"
        ),
        color=0x57F287
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="server_vouch_stop", description="Stop active server auto-vouching loop.")
@app_commands.checks.has_permissions(administrator=True)
async def server_vouch_stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    task = active_tasks["server_autovouch"].pop(guild_id, None)

    if task:
        task.cancel()
        await interaction.response.send_message("🛑 **Server Auto-Vouch** loop terminated successfully.")
    else:
        await interaction.response.send_message("❌ No active Server Auto-Vouch loop found.", ephemeral=True)

@bot.tree.command(name="set_vouch", description="Set explicit vouch count for a user (Admin).")
@app_commands.checks.has_permissions(administrator=True)
async def set_vouch(
    interaction: discord.Interaction,
    user: discord.Member,
    count: int
):
    if count < 0:
        await interaction.response.send_message("❌ Count cannot be negative.", ephemeral=True)
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM vouches WHERE target_id = ? AND guild_id = ?",
        (user.id, interaction.guild.id)
    )

    for _ in range(count):
        v_id = generate_vouch_id()
        cursor.execute(
            "INSERT INTO vouches VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                v_id,
                interaction.guild.id,
                interaction.user.id,
                user.id,
                5,
                "",
                datetime.utcnow()
            )
        )

    conn.commit()
    conn.close()

    await interaction.response.send_message(
        f"✅ Set **{user.display_name}** (`@{user.name}`) vouches to **{count}**."
    )

@bot.tree.command(name="remove_vouch", description="Remove a specific vouch via Vouch ID (Admin).")
@app_commands.checks.has_permissions(administrator=True)
async def remove_vouch(interaction: discord.Interaction, vouch_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT target_id FROM vouches WHERE vouch_id = ? AND guild_id = ?",
        (vouch_id, interaction.guild.id)
    )
    result = cursor.fetchone()

    if not result:
        await interaction.response.send_message("❌ Vouch ID not found.", ephemeral=True)
        conn.close()
        return

    cursor.execute(
        "DELETE FROM vouches WHERE vouch_id = ? AND guild_id = ?",
        (vouch_id, interaction.guild.id)
    )
    conn.commit()
    conn.close()

    await interaction.response.send_message(f"🗑️ Vouch ID **{vouch_id}** purged from database.")

@bot.tree.command(name="vouches", description="Check vouches for a user or the server.")
async def vouches(interaction: discord.Interaction, user: discord.Member = None):
    target_id = user.id if user else 0

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT rating FROM vouches WHERE target_id = ? AND guild_id = ?",
        (target_id, interaction.guild.id)
    )
    ratings = [row[0] for row in cursor.fetchall()]
    conn.close()

    total_vouches = len(ratings)
    avg_rating = round(sum(ratings) / total_vouches, 2) if total_vouches > 0 else 0.0
    rank_name, progress = get_middleman_rank(total_vouches)

    embed = discord.Embed(title="📊 TRUST & REPUTATION PROFILE", color=0x5865F2)

    if user:
        embed.set_author(
            name=f"{user.display_name} (@{user.name})",
            icon_url=user.display_avatar.url
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="User", value=f"{user.mention}\n`@{user.name}`", inline=True)
        embed.add_field(
            name="🏅 Middleman Rank",
            value=f"{rank_name}\n{progress}",
            inline=True
        )
    else:
        embed.set_author(
            name=f"{interaction.guild.name}",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.add_field(name="Target", value="🏢 Server Profile", inline=True)
        embed.add_field(
            name="🏅 Server Rank",
            value=f"{rank_name}\n{progress}",
            inline=True
        )

    embed.add_field(name="Total Vouches", value=f"**{total_vouches}** Verified", inline=True)
    embed.add_field(name="Average Score", value=f"⭐ **{avg_rating} / 5.0**", inline=True)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vouch_leaderboard", description="Displays top vouched members.")
async def vouch_leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()

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
        await interaction.followup.send("🏆 No vouches registered in this server yet!")
        return

    description = ""
    medals = ["🥇", "🥈", "🥉"]

    for idx, (target_id, count, avg_r) in enumerate(results, start=1):
        prefix = medals[idx - 1] if idx <= 3 else f"`#{idx}`"
        resolved_member = await resolve_member(interaction.guild, target_id)
        rank_name, _ = get_middleman_rank(count)

        if resolved_member:
            name_str = f"**{resolved_member.display_name}** (`@{resolved_member.name}`)"
        else:
            name_str = f"Unknown User (`{target_id}`)"

        description += (
            f"{prefix} {name_str} • **{count}** vouches "
            f"(⭐ `{avg_r:.1f}`) • {rank_name}\n"
        )

    embed = discord.Embed(
        title="🏆 TRUST LEADERBOARD",
        description=description,
        color=0xFEE75C,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Server: {interaction.guild.name}")
    await interaction.followup.send(embed=embed)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is missing.")

    bot.run(TOKEN)
