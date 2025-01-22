import discord
from discord import app_commands
from discord.ext import commands
import asyncio, aiohttp
from storetransactions import TransactionTracker
from env import BOT_TOKEN

WEBHOOK_URL = "https://discord.com/api/webhooks/1331652748902535218/kuBKMyECNZpfa7M0Bx3egzk-bpLI0WXug4bz0MY5kYGFZrcupcnpvHZIpAM3i6IBiKaX"
TOKEN = BOT_TOKEN

class Bot(commands.Bot):
    def __init__(self):
        # Set specific intents instead of all
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents)
        self.tracker = TransactionTracker()
        
    async def setup_hook(self):
        await self.tree.sync()
        print("Commands synced!")

bot = Bot()

@bot.tree.command(name="track", description="Track a contract address")
async def track(interaction: discord.Interaction, ca: str):
    await interaction.response.defer()

    token_name = f'TOKEN_{ca}'
    
    # Test descriptions for demo
    test_descriptions = {
        "test_ca_1": [
            "User1 has swapped 1.5 SOL for 625,281.2 TokenA on Raydium.",
            "User2 has swapped 792,158.18 TokenA for 2.47 SOL on Raydium."
        ],
        "test_ca_2": [
            "User3 has swapped 11.09 SOL for 29,759,514.17 TokenB on Raydium.",
            "User4 has swapped 883,212.31 TokenB for 3.78 SOL on Raydium."
        ]
    }
    
    await bot.tracker.flag_token(ca, token_name, "")
    
    # Process test descriptions if available
    if ca in test_descriptions:
        for desc in test_descriptions[ca]:
            if "swapped" and "SOL for" in desc:
                await bot.tracker.process_buy_transaction(ca, token_name, desc)
            elif "for" and "SOL on" in desc:
                await bot.tracker.process_sell_transaction(ca, token_name, desc)
    
    await interaction.followup.send(f"Started tracking {token_name} ({ca})")

@bot.tree.command(name="summary", description="Get summary for a contract address")
async def summary(interaction: discord.Interaction, ca: str):
    await interaction.response.defer()
    
    if ca in bot.tracker.tracked_tokens:
        token = bot.tracker.tracked_tokens[ca]
        embed = discord.Embed(title=f"Summary for {token['token_name']}")
        embed.add_field(name="Total Buys", value=f"{token['buy_amount']:.2f} SOL", inline=True)
        embed.add_field(name="Total Sells", value=f"{token['sell_amount']:.2f} SOL", inline=True)
        
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"No data found for {ca}")

if __name__ == "__main__":
    bot.run(TOKEN)
