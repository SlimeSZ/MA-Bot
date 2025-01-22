from datetime import datetime
import os
import re
from typing import Dict, Tuple
import asyncio, aiohttp
from env import SLAK_WEBHOOK


class TransactionTracker:
    def __init__(self):
        self.tracked_tokens: Dict[str, Dict] = {}
        self.webhook_url = SLAK_WEBHOOK
        self.target_ca = "BSqMUYb6ePwKsby85zrXaDa4SNf6AgZ9YfA2c4mZpump"
    
    async def flag_token(self, ca: str, token_name: str, tx_description: str):
        if ca == self.target_ca:
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
        if ca == self.target_ca:
            await self.flag_token(ca, token_name, tx_description)
            await self.update_sell_totals(ca)
            await self.send_webhook(ca)

    
    async def extract_sell_amounts(self, tx_description: str) -> float:
        pattern = r'swapped [\d,.]+ \w+ for ([\d,\.]+) SOL'
        match = re.search(pattern, tx_description)
        print(f"Sell TX: {tx_description}")
        if match:
            try:
                amount_str = match.group(1)
                sell_amount = float(amount_str.replace(',', ''))
                print(f"Extracted sell amount: {sell_amount}")
                return sell_amount
            except ValueError:
                return 0.0
        print(f"No match found - Pattern failed to match: {pattern}")
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
        if ca == self.target_ca:
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
                async with session.post(self.webhook_url, json=data) as response:
                    if response.status == 204:
                        print("Webhook sent successfully")
                    else:
                        print(f"Failed to send webhook: {response.status}")
            except Exception as e:
                print(f"Error sending webhook: {str(e)}")

        

    # Flow:
# 1. MAbot.py detects new transaction
# 2. Calls process_transaction(ca, token_name, tx_description)
# 3. process_transaction:
#    - Initializes tracking if new token (flag_token)
#    - Adds transaction and updates amounts (add_transaction)
#    - Updates running totals (update_sell/buy_totals)

    