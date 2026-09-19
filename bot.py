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

# ------------------------------------------------------------------------------
# 1. FLASK WEB SERVER (Keep-Alive)
# ------------------------------------------------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "⚡ Advanced MM Vouch Bot - Active and Operational"

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
    cursor.execute("SELECT COUNT(*) FROM vouches WHERE guild_id = ? AND target_id = ?", (guild_id, target_id))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_mm_rank(vouch_count: int) -> str:
    if vouch_count >= 900:
        return "🌌 Apex Middleman"
    elif vouch_count >= 800:
        return "🛡️ Master Middleman"
    elif vouch_count >= 700:
        return "👑 Premier Middleman"
    elif vouch_count >= 600:
        return "💎 Top Middleman"
    elif vouch_count >= 500:
        return "🌟 Expert Middleman"
    elif vouch_count >= 400:
        return "⭐ Quality Middleman"
    elif vouch_count >= 300:
        return "🏅 Verified Middleman"
    elif vouch_count >= 200:
        return "🥉 Trusted Middleman"
    elif vouch_count >= 100:
        return "🥈 Reliable Middleman"
    else:
        return "🥉 Entry Middleman"

active_tasks = {
    "user_autovouch": {},
    "server_autovouch": {}
}

# ------------------------------------------------------------------------------
# 3. DISCORD BOT SETUP
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

def build_advanced_vouch_embed(
    guild: discord.Guild, 
    voucher, 
    target, 
    vouch_id: str, 
    total_vouches: int,
    is_server: bool = False,
    enable_ranks: bool = False
) -> discord.Embed:
    embed = discord.Embed(
        title="🛡️ TRANSACTION VOUCH VERIFIED",
        color=0x2B2D31,
        timestamp=datetime.utcnow()
    )

    # Voucher Details
    v_name = f"**{voucher.display_name}**\n(`@{voucher.name}`)" if hasattr(voucher, "name") else f"**{voucher}**"
    embed.add_field(name="👤 Voucher", value=f"{v_name}\n{voucher.mention}", inline=True)

    # Recipient Details
    if is_server:
        embed.add_field(name="🏢 Recipient", value=f"**{guild.name}**\n*(Official Server)*", inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
    else:
        t_name = f"**{target.display_name}**\n(`@{target.name}`)" if hasattr(target, "name") else f"**{target}**"
        recipient_value = f"{t_name}\n{target.mention}"
        
        if enable_ranks:
            rank = get_mm_rank(total_vouches)
            recipient_value += f"\n🏆 **Rank:** `{rank}`"
            
        embed.add_field(name="🎯 Recipient", value=recipient_value, inline=True)
        if hasattr(target, "display_avatar"):
            embed.set_thumbnail(url=target.display_avatar.url)

    # Total Vouches Field
    embed.add_field(name="📈 Total Vouches", value=f"**{total_vouches}** Vouches Verified", inline=False)

    # Metadata Footer
    unix_time = int(datetime.utcnow().timestamp())
    embed.add_field(name="⏰ Time", value=f"<t:{unix_time}:F> (<t:{unix_time}:R>)", inline=False)

    embed.set_footer(
        text=f"Server: {guild.name} • Total Vouches: {total_vouches} • Vouch ID: {vouch_id}",
        icon_url=guild.icon.url if guild.icon else None
    )
    return embed

def save_vouch_to_db(vouch_id: str, guild_id: int, voucher_id: int, target_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vouches (vouch_id, guild_id, voucher_id, target_id, timestamp) VALUES (?, ?, ?, ?, ?)",
        (vouch_id, guild_id, voucher_id, target_id, datetime.utcnow())
    )
    conn.commit()
    conn.close()

# ------------------------------------------------------------------------------
# 4. BACKGROUND AUTO-VOUCH LOOPS
# ------------------------------------------------------------------------------
async def auto_vouch_user_loop(
    channel: discord.TextChannel, 
    voucher_role: discord.Role, 
    recipient_role: discord.Role, 
    enable_ranks: bool,
    min_delay_sec: int,
    max_delay_sec: int
):
    guild = channel.guild
    while True:
        try:
            # Custom randomized time gap in seconds
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

            message_content = f"🎉 {recipient.mention} got +1 vouch, now at **({total_vouches})** vouches!"
            
            embed = build_advanced_vouch_embed(
                guild, voucher, recipient, v_id, 
                total_vouches=total_vouches, is_server=False, 
                enable_ranks=enable_ranks
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

            message_content = f"🎉 **{guild.name}** got +1 vouch, now at **({total_vouches})** vouches!"

            embed = build_advanced_vouch_embed(
                guild, voucher, None, v_id, 
                total_vouches=total_vouches, is_server=True, 
                enable_ranks=False
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
@bot.tree.command(name="vouch", description="Submit an official vouch for a user.")
@app_commands.describe(
    user="The member to vouch for", 
    enable_ranks="Show Middleman Rank in vouch embed?"
)
async def vouch(
    interaction: discord.Interaction, 
    user: discord.Member, 
    enable_ranks: bool = True
):
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ You cannot vouch for yourself!", ephemeral=True)
        return

    v_id = generate_vouch_id()
    save_vouch_to_db(v_id, interaction.guild.id, interaction.user.id, user.id)
    total_vouches = get_vouch_count(interaction.guild.id, user.id)

    message_content = f"🎉 {user.mention} got +1 vouch, now at **({total_vouches})** vouches!"

    embed = build_advanced_vouch_embed(
        interaction.guild, interaction.user, user, v_id, 
        total_vouches=total_vouches, is_server=False, enable_ranks=enable_ranks
    )
    await interaction.response.send_message(content=message_content, embed=embed)

# 2. /autovouch_start
@bot.tree.command(name="autovouch_start", description="Start user auto-vouching loop with custom time gaps.")
@app_commands.describe(
    voucher_role="Role providing vouches",
    recipient_role="Role receiving vouches",
    min_delay_seconds="Minimum time gap in seconds (Default: 300 / 5 min)",
    max_delay_seconds="Maximum time gap in seconds (Default: 420 / 7 min)",
    enable_ranks="Show MM Rank badges?"
)
@app_commands.checks.has_permissions(administrator=True)
async def autovouch_start(
    interaction: discord.Interaction, 
    voucher_role: discord.Role, 
    recipient_role: discord.Role, 
    min_delay_seconds: int = 300,  # 5 Minutes
    max_delay_seconds: int = 420,  # 7 Minutes
    enable_ranks: bool = True
):
    guild_id = interaction.guild.id
    if guild_id in active_tasks["user_autovouch"]:
        await interaction.response.send_message("⚠️ User Auto-Vouch is already active! Stop it with `/autovouch_stop` first.", ephemeral=True)
        return

    if min_delay_seconds < 1 or max_delay_seconds < min_delay_seconds:
        await interaction.response.send_message("❌ Minimum delay must be at least 1 second and Max delay must be greater than or equal to Min delay.", ephemeral=True)
        return

    task = asyncio.create_task(
        auto_vouch_user_loop(
            interaction.channel, voucher_role, recipient_role, 
            enable_ranks, min_delay_seconds, max_delay_seconds
        )
    )
    active_tasks["user_autovouch"][guild_id] = task

    embed = discord.Embed(
        title="🚀 User Auto-Vouch System Online",
        description=(
            f"Auto-vouching active in {interaction.channel.mention}.\n\n"
            f"**Configuration:**\n"
            f"• **Time Gap:** `{min_delay_seconds}` to `{max_delay_seconds}` Seconds ({round(min_delay_seconds/60, 1)} - {round(max_delay_seconds/60, 1)} Min)\n"
            f"• **Vouchers:** {voucher_role.mention}\n"
            f"• **Recipients:** {recipient_role.mention}\n"
            f"• **Enable MM Ranks:** `{enable_ranks}`"
        ),
        color=0x57F287
    )
    await interaction.response.send_message(embed=embed)

# 3. /autovouch_stop
@bot.tree.command(name="autovouch_stop", description="Stop active user auto-vouching loop.")
@app_commands.checks.has_permissions(administrator=True)
async def autovouch_stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    task = active_tasks["user_autovouch"].pop(guild_id, None)

    if task:
        task.cancel()
        await interaction.response.send_message("🛑 **User Auto-Vouch** loop stopped successfully.")
    else:
        await interaction.response.send_message("❌ No active User Auto-Vouch loop found.", ephemeral=True)

# 4. /server_vouch_start
@bot.tree.command(name="server_vouch_start", description="Start server auto-vouching loop with custom time gaps.")
@app_commands.describe(
    voucher_role="Role vouching for server", 
    min_delay_seconds="Minimum time gap in seconds (Default: 300 / 5 min)",
    max_delay_seconds="Maximum time gap in seconds (Default: 420 / 7 min)"
)
@app_commands.checks.has_permissions(administrator=True)
async def server_vouch_start(
    interaction: discord.Interaction, 
    voucher_role: discord.Role, 
    min_delay_seconds: int = 300,  # 5 Minutes
    max_delay_seconds: int = 420   # 7 Minutes
):
    guild_id = interaction.guild.id
    if guild_id in active_tasks["server_autovouch"]:
        await interaction.response.send_message("⚠️ Server Auto-Vouch is already active! Stop it with `/server_vouch_stop` first.", ephemeral=True)
        return

    if min_delay_seconds < 1 or max_delay_seconds < min_delay_seconds:
        await interaction.response.send_message("❌ Minimum delay must be at least 1 second and Max delay must be greater than or equal to Min delay.", ephemeral=True)
        return

    task = asyncio.create_task(
        auto_vouch_server_loop(
            interaction.channel, voucher_role, 
            min_delay_seconds, max_delay_seconds
        )
    )
    active_tasks["server_autovouch"][guild_id] = task

    embed = discord.Embed(
        title="🚀 Server Auto-Vouch System Online",
        description=(
            f"Server Auto-vouching active in {interaction.channel.mention}.\n\n"
            f"**Configuration:**\n"
            f"• **Time Gap:** `{min_delay_seconds}` to `{max_delay_seconds}` Seconds ({round(min_delay_seconds/60, 1)} - {round(max_delay_seconds/60, 1)} Min)\n"
            f"• **Vouchers:** {voucher_role.mention}"
        ),
        color=0x57F287
    )
    await interaction.response.send_message(embed=embed)

# 5. /server_vouch_stop
@bot.tree.command(name="server_vouch_stop", description="Stop active server auto-vouching loop.")
@app_commands.checks.has_permissions(administrator=True)
async def server_vouch_stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    task = active_tasks["server_autovouch"].pop(guild_id, None)

    if task:
        task.cancel()
        await interaction.response.send_message("🛑 **Server Auto-Vouch** loop stopped successfully.")
    else:
        await interaction.response.send_message("❌ No active Server Auto-Vouch loop found.", ephemeral=True)

# 6. /vouches
@bot.tree.command(name="vouches", description="Check vouches for a user or the server.")
@app_commands.describe(user="User profile to check", show_rank="Show MM Rank on profile?")
async def vouches(interaction: discord.Interaction, user: discord.Member = None, show_rank: bool = True):
    target_id = user.id if user else 0
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vouches WHERE target_id = ? AND guild_id = ?", (target_id, interaction.guild.id))
    total_vouches = cursor.fetchone()[0]
    conn.close()

    embed = discord.Embed(title="📊 TRUST & REPUTATION PROFILE", color=0x5865F2)
    if user:
        embed.set_author(name=f"{user.display_name} (@{user.name})", icon_url=user.display_avatar.url)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="User", value=f"{user.mention}\n`@{user.name}`", inline=True)
        
        if show_rank:
            embed.add_field(name="🏆 Middleman Rank", value=f"`{get_mm_rank(total_vouches)}`", inline=True)
    else:
        embed.set_author(name=f"{interaction.guild.name}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.add_field(name="Target", value="🏢 Server Profile", inline=True)

    embed.add_field(name="Total Vouches", value=f"**{total_vouches}** Verified", inline=True)
    await interaction.response.send_message(embed=embed)

# ------------------------------------------------------------------------------
# 6. INITIALIZATION
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is missing.")
    bot.run(TOKEN)
