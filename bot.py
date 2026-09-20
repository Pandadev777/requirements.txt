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
# 1. FLASK WEB SERVER (Keep-Alive)
# ------------------------------------------------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "⚡ MM Vouch Bot - Active and Operational"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ------------------------------------------------------------------------------
# 2. DATABASE SETUP & HELPER FUNCTIONS
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
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def generate_vouch_id():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def get_vouch_count(guild_id: int, target_id: int) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vouches WHERE guild_id = ? AND target_id = ?", (guild_id, target_id))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_mm_rank(vouch_count: int) -> str:
    """Returns a Middleman rank title based on total completed vouches."""
    if vouch_count >= 100:
        return "👑 **Legendary Middleman**"
    elif vouch_count >= 50:
        return "💎 **Master Middleman**"
    elif vouch_count >= 25:
        return "🥇 **Senior Middleman**"
    elif vouch_count >= 10:
        return "🥈 **Trusted Middleman**"
    else:
        return "🥉 **Novice Middleman**"

def save_vouch_to_db(vouch_id: str, guild_id: int, voucher_id: int, target_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vouches (vouch_id, guild_id, voucher_id, target_id) VALUES (?, ?, ?, ?)",
        (vouch_id, guild_id, voucher_id, target_id)
    )
    conn.commit()
    conn.close()

active_tasks = {
    "user_autovouch": {},
    "server_autovouch": {}
}

# ------------------------------------------------------------------------------
# 3. DISCORD BOT SETUP & EMBED BUILDER
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

def build_mm_vouch_embed(
    guild: discord.Guild, 
    voucher: discord.Member, 
    target: discord.Member, 
    vouch_id: str, 
    total_vouches: int,
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
        # Set recipient profile picture on the right side of the embed
        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)

    embed.add_field(name="📈 Total Deals Vouched", value=f"**{total_vouches}**", inline=False)
    
    # Display the exact vouch time right below the vouch details
    embed.add_field(
        name="⏰ Time of Vouch", 
        value=f"<t:{current_time_unix}:F> (<t:{current_time_unix}:R>)", 
        inline=False
    )

    # Server icon and name in footer
    footer_icon = guild.icon.url if guild.icon else None
    embed.set_footer(text=f"{guild.name} • Vouch ID: {vouch_id}", icon_url=footer_icon)

    return embed

# ------------------------------------------------------------------------------
# 4. BACKGROUND AUTO-VOUCH LOOPS
# ------------------------------------------------------------------------------
async def auto_vouch_user_loop(
    channel: discord.TextChannel, 
    voucher_role: discord.Role, 
    recipient_role: discord.Role, 
    min_delay_sec: int,
    max_delay_sec: int
):
    guild = channel.guild
    while True:
        try:
            delay = random.randint(min_delay_sec, max_delay_sec)
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

            v_id = generate_vouch_id()

            save_vouch_to_db(v_id, guild.id, voucher.id, recipient.id)
            total_vouches = get_vouch_count(guild.id, recipient.id)

            message_content = f"✅ 🎉 {recipient.mention} received a MM vouch! Now at **({total_vouches})** vouches."
            
            embed = build_mm_vouch_embed(
                guild, voucher, recipient, v_id, 
                total_vouches=total_vouches, is_server=False
            )
            await channel.send(content=message_content, embed=embed)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in user auto-vouch loop ({guild.name}): {e}")

async def auto_vouch_server_loop(
    channel: discord.TextChannel, 
    voucher_role: discord.Role, 
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
            v_id = generate_vouch_id()

            save_vouch_to_db(v_id, guild.id, voucher.id, 0)
            total_vouches = get_vouch_count(guild.id, 0)

            message_content = f"✅ 🎉 **{guild.name}** received a vouch! Now at **({total_vouches})** vouches."

            embed = build_mm_vouch_embed(
                guild, voucher, None, v_id, 
                total_vouches=total_vouches, is_server=True
            )
            await channel.send(content=message_content, embed=embed)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in server auto-vouch loop ({guild.name}): {e}")

# ------------------------------------------------------------------------------
# 5. SLASH COMMANDS
# ------------------------------------------------------------------------------

# 1. /setvouch
@bot.tree.command(name="setvouch", description="Submit an official vouch for a middleman.")
@app_commands.describe(user="The middleman to vouch for")
async def setvouch(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ You cannot vouch for yourself!", ephemeral=True)
        return

    v_id = generate_vouch_id()
    save_vouch_to_db(v_id, interaction.guild.id, interaction.user.id, user.id)
    total_vouches = get_vouch_count(interaction.guild.id, user.id)

    message_content = f"🎉 {user.mention} received a MM vouch! Now at **({total_vouches})** vouches."

    embed = build_mm_vouch_embed(
        interaction.guild, interaction.user, user, v_id, 
        total_vouches=total_vouches, is_server=False
    )
    await interaction.response.send_message(content=message_content, embed=embed)

# 2. /vouches
@bot.tree.command(name="vouches", description="Check middleman profile or server vouches.")
@app_commands.describe(user="Middleman profile to check (Leave empty for server profile)")
async def vouches(interaction: discord.Interaction, user: discord.Member = None):
    target_id = user.id if user else 0
    total_vouches = get_vouch_count(interaction.guild.id, target_id)

    embed = discord.Embed(title="📊 VOUCH PROFILE", color=0x5865F2)
    if user:
        mm_rank = get_mm_rank(total_vouches)
        embed.add_field(name="Middleman", value=user.mention, inline=True)
        embed.add_field(name="MM Rank", value=mm_rank, inline=True)
        if user.display_avatar:
            embed.set_thumbnail(url=user.display_avatar.url)
    else:
        embed.add_field(name="Target", value="🏢 Server Profile", inline=True)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

    embed.add_field(name="Total Vouches", value=f"**{total_vouches}**", inline=False)
    
    footer_icon = interaction.guild.icon.url if interaction.guild.icon else None
    embed.set_footer(text=interaction.guild.name, icon_url=footer_icon)
    
    await interaction.response.send_message(embed=embed)

# 3. /vouches_leaderboard
@bot.tree.command(name="vouches_leaderboard", description="Display top middlemen with the highest vouches.")
async def vouches_leaderboard(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT target_id, COUNT(*) as vouch_count 
        FROM vouches 
        WHERE guild_id = ? AND target_id != 0 
        GROUP BY target_id 
        ORDER BY vouch_count DESC 
        LIMIT 10
    """, (interaction.guild.id,))
    top_users = cursor.fetchall()
    conn.close()

    if not top_users:
        await interaction.response.send_message("❌ No middleman vouches recorded in this server yet.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"🏆 MIDDLEMAN LEADERBOARD",
        color=0xFEE75C
    )

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

# 4. /autovouch_start
@bot.tree.command(name="autovouch_start", description="Start middleman auto-vouching loop.")
@app_commands.describe(
    voucher_role="Role providing vouches",
    recipient_role="Role receiving vouches (Middlemen)",
    min_delay_seconds="Minimum delay in seconds (Default: 300)",
    max_delay_seconds="Maximum delay in seconds (Default: 420)"
)
@app_commands.checks.has_permissions(administrator=True)
async def autovouch_start(
    interaction: discord.Interaction, 
    voucher_role: discord.Role, 
    recipient_role: discord.Role, 
    min_delay_seconds: int = 300,
    max_delay_seconds: int = 420
):
    guild_id = interaction.guild.id
    if guild_id in active_tasks["user_autovouch"]:
        await interaction.response.send_message("⚠️ Auto-vouch loop is already active! Stop it with `/autovouch_stop` first.", ephemeral=True)
        return

    if min_delay_seconds < 1 or max_delay_seconds < min_delay_seconds:
        await interaction.response.send_message("❌ Minimum delay must be at least 1 second and Max delay must be greater than or equal to Min delay.", ephemeral=True)
        return

    task = asyncio.create_task(
        auto_vouch_user_loop(
            interaction.channel, voucher_role, recipient_role, 
            min_delay_seconds, max_delay_seconds
        )
    )
    active_tasks["user_autovouch"][guild_id] = task

    embed = discord.Embed(
        title="🚀 Middleman Auto-Vouch Active",
        description=(
            f"Running in {interaction.channel.mention}.\n\n"
            f"• **Delay Range:** `{min_delay_seconds}` - `{max_delay_seconds}` Seconds\n"
            f"• **Vouchers:** {voucher_role.mention}\n"
            f"• **Middlemen:** {recipient_role.mention}"
        ),
        color=0x57F287
    )
    footer_icon = interaction.guild.icon.url if interaction.guild.icon else None
    embed.set_footer(text=interaction.guild.name, icon_url=footer_icon)

    await interaction.response.send_message(embed=embed)

# 5. /autovouch_stop
@bot.tree.command(name="autovouch_stop", description="Stop active middleman auto-vouching loop.")
@app_commands.checks.has_permissions(administrator=True)
async def autovouch_stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    task = active_tasks["user_autovouch"].pop(guild_id, None)

    if task:
        task.cancel()
        await interaction.response.send_message("🛑 **Middleman Auto-Vouch** stopped.")
    else:
        await interaction.response.send_message("❌ No active auto-vouch loop found.", ephemeral=True)

# 6. /server_vouch_start
@bot.tree.command(name="server_vouch_start", description="Start server auto-vouching loop.")
@app_commands.describe(
    voucher_role="Role vouching for server", 
    min_delay_seconds="Minimum delay in seconds (Default: 300)",
    max_delay_seconds="Maximum delay in seconds (Default: 420)"
)
@app_commands.checks.has_permissions(administrator=True)
async def server_vouch_start(
    interaction: discord.Interaction, 
    voucher_role: discord.Role, 
    min_delay_seconds: int = 300,
    max_delay_seconds: int = 420
):
    guild_id = interaction.guild.id
    if guild_id in active_tasks["server_autovouch"]:
        await interaction.response.send_message("⚠️ Server Auto-Vouch is already active!", ephemeral=True)
        return

    task = asyncio.create_task(
        auto_vouch_server_loop(
            interaction.channel, voucher_role, 
            min_delay_seconds, max_delay_seconds
        )
    )
    active_tasks["server_autovouch"][guild_id] = task

    embed = discord.Embed(
        title="🚀 Server Auto-Vouch Active",
        description=f"Running in {interaction.channel.mention} with {voucher_role.mention}.",
        color=0x57F287
    )
    footer_icon = interaction.guild.icon.url if interaction.guild.icon else None
    embed.set_footer(text=interaction.guild.name, icon_url=footer_icon)

    await interaction.response.send_message(embed=embed)

# 7. /server_vouch_stop
@bot.tree.command(name="server_vouch_stop", description="Stop active server auto-vouching loop.")
@app_commands.checks.has_permissions(administrator=True)
async def server_vouch_stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    task = active_tasks["server_autovouch"].pop(guild_id, None)

    if task:
        task.cancel()
        await interaction.response.send_message("🛑 **Server Auto-Vouch** stopped.")
    else:
        await interaction.response.send_message("❌ No active Server Auto-Vouch loop found.", ephemeral=True)

# ------------------------------------------------------------------------------
# 6. INITIALIZATION
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is missing.")
    bot.run(TOKEN)
