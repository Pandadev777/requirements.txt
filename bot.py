import discord, os
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "Test Bot"
Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"TEST SUCCESS - Logged as {client.user} - NO RATE LIMIT")
    print("If you see this, your IP is NOT banned anymore.")

client.run(os.getenv("DISCORD_TOKEN"))
