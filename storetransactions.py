from datetime import datetime
import os
import re
from typing import Dict, Tuple
import asyncio, aiohttp
from env import SLAK_WEBHOOK

WEBHOOK_URL = SLAK_WEBHOOK

class TransactionTracker:
    def __init__(self):
        self.tracked_tokens: Dict[str, Dict] = {}
    
    async def flag_token(self, ca: str, token_name: str, tx_description: str):
        if ca not in self.tracked_tokens:
            self.tracked_tokens[ca] = {
                'ca': ca,
                'token_name': token_name,
                'transactions': [],
                'buy_amount': 0,
                'sell_amount': 0,
            }
            print(f"\nStarted Tracking {token_name}\nCA: |{ca}|")
        #check for buys &/or sells
        if "swapped" in tx_description:
            if "swapped" and "SOL for" in tx_description:
                await self.add_buy_amount(ca, tx_description)
            elif "for" and "SOL on" in tx_description:
                await self.add_sell_amount(ca, tx_description)
        
        
        
    #----------------------------------------
    #SELL Integration
    #----------------------------------------

    async def process_sell_transaction(self, ca: str, token_name: str, tx_description: str):
        await self.flag_token(ca, token_name, tx_description)
        await self.update_sell_totals(ca)
        await self.send_webhook(ca)

    
    async def extract_sell_amounts(self, tx_description: str) -> float:
        pattern = r'swapped [\d,.]+ \w+ for ([\d,.]+) SOL'
        match = re.search(pattern, tx_description)
        if match:
            try:
                sell_amount = float(match.group(1).replace(',', ''))
                return sell_amount
            except ValueError:
                return 0.0
        return 0.0
    
    async def add_sell_amount(self, ca: str, tx_description: str):
        if ca in self.tracked_tokens:
            sell_amount = await self.extract_sell_amounts(tx_description)
            self.tracked_tokens[ca]['sell_amount'] += sell_amount
            self.tracked_tokens[ca]['transactions'].append(tx_description)

            print(f"New Sell of: {sell_amount} for {self.tracked_tokens[ca]['token_name']}")
            print(f"New Transaction: {self.tracked_tokens[ca]['transactions']}")

        else:
            print(F"Token not being tracked")

    async def update_sell_totals(self, ca: str):
        if ca in self.tracked_tokens:
            print(f"\nTotal sells for {self.tracked_tokens[ca]['token_name']}: "
                f"{self.tracked_tokens[ca]['sell_amount']:.2f} SOL")

#----------------------------------------
    #Buy Integration
#----------------------------------------

    async def process_buy_transaction(self, ca: str, token_name: str, tx_description: str):
        await self.flag_token(ca, token_name, tx_description)
        await self.update_buy_totals(ca)
        await self.send_webhook(ca)

    
    async def extract_buy_amounts(self, tx_description: str) -> float:
        pattern = r'swapped ([\d,.]+) SOL for'  # Changed pattern to match buy transactions
        match = re.search(pattern, tx_description)
        if match:
            try:
                buy_amount = float(match.group(1).replace(',', ''))
                return buy_amount
            except ValueError:
                return 0.0
        return 0.0
    
    async def add_buy_amount(self, ca: str, tx_description: str):
        if ca in self.tracked_tokens:
            buy_amount = await self.extract_buy_amounts(tx_description)
            self.tracked_tokens[ca]['buy_amount'] += buy_amount
            self.tracked_tokens[ca]['transactions'].append(tx_description)

            print(f"New Buy of: {buy_amount} for {self.tracked_tokens[ca]['token_name']}")
            print(f"New Transaction: {self.tracked_tokens[ca]['transactions']}")

        else:
            print(F"Token not being tracked")

    async def update_buy_totals(self, ca: str):
        if ca in self.tracked_tokens:
            print(f"\nTotal Buys for {self.tracked_tokens[ca]['token_name']}: "
                f"{self.tracked_tokens[ca]['buy_amount']:.2f} SOL")    


#--------------------------------

    async def print_final_summary(self, ca: str):
        if ca in self.tracked_tokens:
            token = self.tracked_tokens[ca]
            print(f"\n{'=' * 30}")
            print(f"Final Summary for {token['token_name']}")
            print(f"Total Buys: {token['buy_amount']:.2f} SOL")
            print(f"Total Sells: {token['sell_amount']:.2f} SOL")
            print(f"{'=' * 30}")

    async def send_webhook(self, ca: str):
        if ca not in self.tracked_tokens:
            return
            
        token = self.tracked_tokens[ca]
        tx_list = "\n".join(token['transactions'])

        data = {
            "username": "Tx & Buy Tracker",
            "embeds": [{
                "title": f"Summary for: {token['token_name']}",
                "fields": [
                    {
                        "name": "Token Name",
                        "value": token['token_name'],
                        "inline": False
                    },
                    {
                        "name": "CA",
                        "value": token['ca'],
                        "inline": False
                    },
                    {
                        "name": "Tx Description(s)",
                        "value": tx_list[:1024] if tx_list else "No transactions",
                        "inline": False
                    },
                    {
                        "name": "Total buys",
                        "value": f"{token['buy_amount']:.2f} SOL",
                        "inline": True
                    },
                    {
                        "name": "Total sells",
                        "value": f"{token['sell_amount']:.2f} SOL",
                        "inline": True
                    }
                ]
            }]
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(WEBHOOK_URL, json=data) as response:
                    if response.status == 204:
                        print("Webhook sent successfully")
                    else:
                        print(f"Failed to send webhook: {response.status}")
            except Exception as e:
                print(f"Error sending webhook: {str(e)}")

        











# Test the functionality
async def main():
   tracker = TransactionTracker()
   descriptions = {
       "Kol	DpNVrt_gorillacapsol_50_13.3K has swapped 792,158.18 tor for 2.47 SOL on Raydium.",
       "HF	BDFMk_Dex_BS_Chua_82 has swapped 2,992,414.77 22nd for 1.42 SOL on Raydium.",
       "Kol	DpNVrt_gorillacapsol_50_13.3K has swapped 883,212.31 tor for 3.78 SOL on Raydium.",
       "HF BDFMk_Dex_BS_Chua_82 has swapped 1.5 SOL for 625,281.2 FIFTY on Raydium.",
       "Smart nig_70 has swapped 11.09 SOL for 29,759,514.17 ledger cto on Pumpfun 💊."
   }

   for desc in descriptions:
       if "swapped" and "SOL for" in desc:
           await tracker.process_buy_transaction('test_ca', 'test_name', desc)
       elif "for" and "SOL on" in desc:
           await tracker.process_sell_transaction('test_ca', 'test_name', desc)
           
   await tracker.print_final_summary('test_ca')

if __name__ == "__main__":
   asyncio.run(main())

    # Flow:
# 1. MAbot.py detects new transaction
# 2. Calls process_transaction(ca, token_name, tx_description)
# 3. process_transaction:
#    - Initializes tracking if new token (flag_token)
#    - Adds transaction and updates amounts (add_transaction)
#    - Updates running totals (update_sell/buy_totals)

    