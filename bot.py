import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, ButtonStyle
import aiosqlite
import asyncio
import os
import random
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
from aiohttp import web

# ==========================================
# 1. ASYNC HEALTH CHECK MICROSERVICE
# ==========================================
async def handle_ping(request: web.Request) -> web.Response:
    """Microservice endpoint for hosting platform health checks (Render, Railway, Koyeb)."""
    return web.json_response({"status": "ONLINE", "engine": "ULTRA V4 PRO ENGINE"}, status=200)

async def start_health_check() -> None:
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# ==========================================
# 2. CONFIGURATION & RANKS CONFIG
# ==========================================
DB_PATH = "mm_enterprise.db"

# Format: (Required Vouches, Rank Title, Color Hex)
RANKS: List[Tuple[int, str, int]] = [
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

def get_rank_details(vouch_count: int) -> Tuple[Tuple[int, str, int], int, str]:
    """Calculates current rank details and distance to the next rank tier."""
    current_rank = RANKS[0]
    next_req = 0
    next_name = "MAX TIER REACHED"
    
    for idx, (req, name, color) in enumerate(RANKS):
        if vouch_count >= req:
            current_rank = (req, name, color)
            if idx + 1 < len(RANKS):
                next_req = RANKS[idx + 1][0] - vouch_count
                next_name = RANKS[idx + 1][1]
            else:
                next_req = 0
                next_name = "MAX TIER REACHED"
        else:
            break
            
    return current_rank, next_req, next_name

def render_star_rating(rating: float) -> str:
    """Renders a visual 5-star metric string."""
    rounded_val = max(1, min(5, round(rating)))
    return "⭐" * rounded_val

# ==========================================
# 3. DATABASE MANAGEMENT LAYER
# ==========================================
class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                vouch_count INTEGER DEFAULT 0,
                rating_sum INTEGER DEFAULT 0,
                rating_count INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS vouches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id TEXT,
                author_id TEXT,
                rating INTEGER,
                trade_details TEXT,
                timestamp TEXT
            );
            
            CREATE TABLE IF NOT EXISTS server_stats (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_vouches INTEGER DEFAULT 0
            );
            
            INSERT OR IGNORE INTO server_stats (id, total_vouches) VALUES (1, 0);
            
            CREATE TABLE IF NOT EXISTS configuration (
                config_key TEXT PRIMARY KEY,
                config_value TEXT
            );
        """)
        await self.conn.commit()

    async def add_vouch(self, target_id: str, author_id: str, rating: int, trade_details: str) -> Dict[str, Any]:
        timestamp = datetime.utcnow().isoformat()
        
        async with self.conn.cursor() as cursor:
            # Update user profile
            await cursor.execute("""
                INSERT INTO users (user_id, vouch_count, rating_sum, rating_count)
                VALUES (?, 1, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    vouch_count = vouch_count + 1,
                    rating_sum = rating_sum + excluded.rating_sum,
                    rating_count = rating_count + 1
            """, (target_id, rating))
            
            # Log individual vouch record
            await cursor.execute("""
                INSERT INTO vouches (target_id, author_id, rating, trade_details, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (target_id, author_id, rating, trade_details, timestamp))
            
            # Update global server stats
            await cursor.execute("UPDATE server_stats SET total_vouches = total_vouches + 1 WHERE id = 1")
            
            # Retrieve updated user record
            await cursor.execute("SELECT vouch_count, rating_sum, rating_count FROM users WHERE user_id = ?", (target_id,))
            v_count, r_sum, r_count = await cursor.fetchone()
            
            await self.conn.commit()
            
        return {
            "vouch_count": v_count,
            "rating_avg": r_sum / r_count if r_count > 0 else rating,
            "rating_count": r_count
        }

    async def get_user_stats(self, user_id: str) -> Optional[Dict[str, Any]]:
        async with self.conn.execute("SELECT vouch_count, rating_sum, rating_count FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            
            v_count, r_sum, r_count = row
            return {
                "vouch_count": v_count,
                "rating_avg": r_sum / r_count if r_count > 0 else 0.0,
                "rating_count": r_count
            }

    async def get_leaderboard_data(self, limit: int = 50) -> List[Tuple[str, int, int, int]]:
        async with self.conn.execute("""
            SELECT user_id, vouch_count, rating_sum, rating_count 
            FROM users 
            ORDER BY vouch_count DESC 
            LIMIT ?
        """, (limit,)) as cursor:
            return await cursor.fetchall()

    async def get_server_total(self) -> int:
        async with self.conn.execute("SELECT total_vouches FROM server_stats WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def set_config(self, key: str, value: str) -> None:
        await self.conn.execute("INSERT OR REPLACE INTO configuration (config_key, config_value) VALUES (?, ?)", (key, value))
        await self.conn.commit()

    async def get_config(self, key: str) -> Optional[str]:
        async with self.conn.execute("SELECT config_value FROM configuration WHERE config_key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# ==========================================
# 4. ADVANCED INTERACTIVE UI COMPONENTS
# ==========================================
class ProfileView(discord.ui.View):
    def __init__(self, target_user: discord.User, db: DatabaseManager):
        super().__init__(timeout=180)
        self.target_user = target_user
        self.db = db

    @discord.ui.button(label="📊 View Extended Profile", style=ButtonStyle.primary, emoji="👑")
    async def view_profile(self, interaction: Interaction, button: discord.ui.Button):
        stats = await self.db.get_user_stats(str(self.target_user.id))
        
        if not stats:
            return await interaction.response.send_message("❌ This Middleman has no recorded stats.", ephemeral=True)

        v_count = stats["vouch_count"]
        r_avg = stats["rating_avg"]
        (_, rank_name, rank_color), next_req, next_name = get_rank_details(v_count)
        stars_display = render_star_rating(r_avg)

        embed = discord.Embed(
            title=f"👑 Profile Breakdown: {self.target_user.display_name}",
            color=rank_color,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=self.target_user.display_avatar.url)
        embed.add_field(name="Rank Tier", value=f"**{rank_name}**", inline=True)
        embed.add_field(name="Completed Vouches", value=f"`{v_count}`", inline=True)
        embed.add_field(name="Average Score", value=f"{stars_display} `({r_avg:.2f}/5.0)`", inline=True)
        embed.add_field(name="Next Rank Progression", value=f"`{next_req}` vouches needed for **{next_name}**", inline=False)
        embed.set_footer(text="Trade world Verification System", icon_url=interaction.guild.icon.url if interaction.guild else None)

        await interaction.response.send_message(embed=embed, ephemeral=True)

class LeaderboardPaginator(discord.ui.View):
    def __init__(self, data: List[Tuple[str, int, int, int]], server_total: int, author_id: int):
        super().__init__(timeout=120)
        self.data = data
        self.server_total = server_total
        self.author_id = author_id
        self.page = 0
        self.per_page = 5
        self.max_pages = max(1, (len(data) + self.per_page - 1) // self.per_page)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You are not authorized to use these controls.", ephemeral=True)
            return False
        return True

    def generate_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🏆 MIDDLEMAN LEADERBOARD • GLOBAL RANKS",
            description=f"**🌐 Server Total Vouches:** `{self.server_total}` | **👥 Ranked MMs:** `{len(self.data)}`\n━━━━━━━━━━━━━━━━━━━━",
            color=0xFFD700,
            timestamp=datetime.utcnow()
        )
        
        start_idx = self.page * self.per_page
        end_idx = start_idx + self.per_page
        page_items = self.data[start_idx:end_idx]

        medals = {0: "🥇", 1: "🥈", 2: "🥉"}

        for idx, (uid, v_count, r_sum, r_cnt) in enumerate(page_items, start=start_idx):
            avg_rating = (r_sum / r_cnt) if r_cnt > 0 else 0.0
            (_, rank_name, _), _, _ = get_rank_details(v_count)
            rank_badge = medals.get(idx, f"`#{idx + 1}`")
            stars_str = render_star_rating(avg_rating)

            embed.add_field(
                name=f"{rank_badge} <@{uid}> • {rank_name}",
                value=f"**Vouches:** `{v_count}` | **Rating:** {stars_str} `({avg_rating:.1f}/5)`",
                inline=False
            )

        embed.set_footer(text=f"Page {self.page + 1}/{self.max_pages} • Live Leaderboard")
        return embed

    @discord.ui.button(label="⏮ First", style=ButtonStyle.secondary)
    async def first_page(self, interaction: Interaction, button: discord.ui.Button):
        self.page = 0
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    @discord.ui.button(label="◀ Prev", style=ButtonStyle.primary)
    async def prev_page(self, interaction: Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.generate_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=ButtonStyle.primary)
    async def next_page(self, interaction: Interaction, button: discord.ui.Button):
        if self.page < self.max_pages - 1:
            self.page += 1
            await interaction.response.edit_message(embed=self.generate_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="⏭ Last", style=ButtonStyle.secondary)
    async def last_page(self, interaction: Interaction, button: discord.ui.Button):
        self.page = self.max_pages - 1
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

# ==========================================
# 5. CORE BOT ARCHITECTURE
# ==========================================
class EnterpriseMMBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="$", intents=intents, help_command=None)
        self.db = DatabaseManager(DB_PATH)

    async def setup_hook(self) -> None:
        await self.db.initialize()
        await start_health_check()
        self.auto_vouch_task.start()

    @tasks.loop(seconds=90)
    async def auto_vouch_task(self) -> None:
        try:
            raw_cfg = await self.db.get_config("autovouch_user")
            if not raw_cfg:
                return

            import json
            cfg = json.loads(raw_cfg)
            if not cfg.get("active"):
                return

            guild = self.get_guild(cfg["guild_id"])
            if not guild:
                return

            channel = guild.get_channel(cfg["channel_id"])
            target_role = guild.get_role(cfg["target_role_id"])
            if not channel or not target_role:
                return

            targets = [m for m in target_role.members if not m.bot]
            if not targets:
                return

            selected_target = random.choice(targets)
            simulated_rating = random.randint(3, 5)

            stats = await self.db.add_vouch(
                target_id=str(selected_target.id),
                author_id="AUTOMATED_SYSTEM",
                rating=simulated_rating,
                trade_details="Automated System Verification"
            )

            v_count = stats["vouch_count"]
            r_avg = stats["rating_avg"]
            (_, rank_name, rank_color), _, _ = get_rank_details(v_count)
            stars_display = render_star_rating(r_avg)

            embed = discord.Embed(color=rank_color, timestamp=datetime.utcnow())
            embed.set_author(name=f"VOUCH SYSTEM • {rank_name}", icon_url=selected_target.display_avatar.url)
            embed.description = (
                f"### 🚀 {selected_target.mention} received **+1 Vouch**\n"
                f"**Total Vouches:** `{v_count}`\n"
                f"**Rating:** {stars_display} `({r_avg:.1f}/5)`\n"
                f"**Rank:** {rank_name}"
            )
            embed.set_thumbnail(url=selected_target.display_avatar.url)
            embed.set_footer(text="Trade World Auto Verification Engine")

            await channel.send(embed=embed)

        except Exception as err:
            print(f"[AutoVouch Engine Exception]: {err}")

    @auto_vouch_task.before_loop
    async def before_auto_vouch(self) -> None:
        await self.wait_until_ready()

bot = EnterpriseMMBot()

# ==========================================
# 6. HYBRID COMMAND INTERACTION SUITE
# ==========================================
@bot.hybrid_command(name="vouch", description="Submit an official vouch for a Middleman")
@app_commands.describe(member="Middleman to vouch", rating="Star rating (1-5)", trade="Trade details")
@commands.cooldown(1, 10, commands.BucketType.user)
async def vouch(ctx: commands.Context, member: discord.Member, rating: int, trade: str = "Legit & Fast Trade"):
    if not 1 <= rating <= 5:
        return await ctx.send(embed=discord.Embed(description="❌ **Rating must be between 1 and 5 stars.**", color=0xFF0000), ephemeral=True)
    if member.id == ctx.author.id:
        return await ctx.send(embed=discord.Embed(description="❌ **You cannot vouch for yourself.**", color=0xFF0000), ephemeral=True)
    if member.bot:
        return await ctx.send(embed=discord.Embed(description="❌ **Bots cannot receive vouches.**", color=0xFF0000), ephemeral=True)

    stats = await bot.db.add_vouch(
        target_id=str(member.id),
        author_id=str(ctx.author.id),
        rating=rating,
        trade_details=trade
    )

    v_count = stats["vouch_count"]
    r_avg = stats["rating_avg"]
    (_, rank_name, rank_color), next_req, next_name = get_rank_details(v_count)
    stars_display = render_star_rating(r_avg)

    embed = discord.Embed(color=rank_color, timestamp=datetime.utcnow())
    embed.set_author(name=f"💎 VOUCH CONFIRMED • {rank_name}", icon_url=member.display_avatar.url)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👤 Middleman", value=f"{member.mention}\n`ID: {member.id}`\n**{rank_name}**", inline=True)
    embed.add_field(name="⭐ Rating", value=f"{render_star_rating(rating)} **({rating}/5)**\nAvg: {stars_display} **({r_avg:.1f}/5)**", inline=True)
    embed.add_field(name="📦 Trade Details", value=f"```\n{trade}\n```\n*Vouched by:* {ctx.author.mention}", inline=False)
    embed.add_field(name="📊 Progress", value=f"**Total:** `{v_count}` | **Next Rank:** `{next_name}` in `{next_req}` vouches", inline=False)
    embed.set_footer(text=f"🆔 Transaction ID: MM-{v_count:05d}", icon_url=ctx.guild.icon.url if ctx.guild else None)

    view = ProfileView(target_user=member, db=bot.db)
    await ctx.send(content=f"🚀 ||{member.mention}||", embed=embed, view=view)

@bot.hybrid_command(name="leaderboard", description="Displays the global Middleman Leaderboard")
async def leaderboard(ctx: commands.Context):
    data = await bot.db.get_leaderboard_data(limit=100)
    server_total = await bot.db.get_server_total()

    if not data:
        return await ctx.send(embed=discord.Embed(description="❌ No vouch data recorded yet.", color=0xFF0000))

    view = LeaderboardPaginator(data=data, server_total=server_total, author_id=ctx.author.id)
    await ctx.send(embed=view.generate_embed(), view=view)

@bot.hybrid_command(name="setvouch", description="Set a member or server's vouch totals (Admin Only)")
@commands.has_permissions(administrator=True)
async def setvouch(ctx: commands.Context, target: str, member: Optional[discord.Member] = None, amount: int = 0):
    target_clean = target.lower().strip()
    
    if target_clean == "user":
        if not member:
            return await ctx.send(embed=discord.Embed(description="❌ **Please mention a member:** `$setvouch user @Member 100`", color=0xFF0000))
        
        await bot.db.conn.execute("""
            INSERT INTO users (user_id, vouch_count, rating_sum, rating_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET vouch_count = excluded.vouch_count
        """, (str(member.id), amount, amount * 5))
        await bot.db.conn.commit()

        (_, rank_name, rank_color), _, _ = get_rank_details(amount)
        embed = discord.Embed(title="✅ DATABASE RECORD UPDATED", color=rank_color)
        embed.add_field(name="Target User", value=member.mention, inline=True)
        embed.add_field(name="New Total", value=f"`{amount}`", inline=True)
        embed.add_field(name="Assigned Rank", value=f"**{rank_name}**", inline=True)
        await ctx.send(embed=embed)

    elif target_clean == "server":
        await bot.db.conn.execute("UPDATE server_stats SET total_vouches = ? WHERE id = 1", (amount,))
        await bot.db.conn.commit()
        await ctx.send(embed=discord.Embed(title="✅ SERVER RECORD UPDATED", description=f"Server Total Set To: **{amount}**", color=0x00FF00))
    else:
        await ctx.send(embed=discord.Embed(description="❌ Invalid parameter. Must specify `user` or `server`.", color=0xFF0000))

@bot.hybrid_command(name="autovouch_user", description="Configure automated background vouches (Admin Only)")
@commands.has_permissions(administrator=True)
async def autovouch_user(ctx: commands.Context, voucher_role: discord.Role, target_role: discord.Role, delay: int = 90):
    import json
    delay_safe = max(60, delay)
    payload = {
        "guild_id": ctx.guild.id,
        "channel_id": ctx.channel.id,
        "voucher_role_id": voucher_role.id,
        "target_role_id": target_role.id,
        "delay": delay_safe,
        "active": True
    }
    
    await bot.db.set_config("autovouch_user", json.dumps(payload))

    if bot.auto_vouch_task.is_running():
        bot.auto_vouch_task.stop()

    bot.auto_vouch_task.change_interval(seconds=delay_safe)
    bot.auto_vouch_task.start()

    embed = discord.Embed(title="🤖 AUTOMATED VOUCH SYSTEM ONLINE", color=0x00FF00)
    embed.add_field(name="Target Group", value=target_role.mention, inline=True)
    embed.add_field(name="Loop Interval", value=f"`{delay_safe} seconds`", inline=True)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="sync", description="Sync command tree with Discord Gateway")
@commands.has_permissions(administrator=True)
async def sync(ctx: commands.Context):
    await ctx.defer()
    synced = await bot.tree.sync()
    await ctx.send(embed=discord.Embed(description=f"✅ **Synced {len(synced)} hybrid commands.**", color=0x00FF00))

@bot.event
async def on_ready():
    print(f"✅ ULTRA ENGINE V4: Logged in as {bot.user} (ID: {bot.user.id})")

# ==========================================
# 7. RUNNER ENTRY POINT
# ==========================================
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("❌ Error: DISCORD_TOKEN environment variable not found.")
