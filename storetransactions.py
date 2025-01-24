from datetime import datetime
import os
import re
from typing import Dict, Tuple
import asyncio, aiohttp


class TransactionTracker:
    def __init__(self):
        self.tracked_tokens: Dict[str, Dict] = {}
        self.processed_txs = set()
        self.alerted_cas = set()
        self.bpi_alerted_cas = {}
        self.sell_pressure_alerted_cas = {}

        self.large_buys_wh = "https://discord.com/api/webhooks/1332066523681919017/Nk6tNc0Phlx9xNYtuBK_JIOskLnoBN7Jg_w3VOvqeCJVJTVz0xTqsiFlK28BdnxxqVl5"
        self.bpi_wh = "https://discord.com/api/webhooks/1332066601922596974/ml6KuhW1pMeKDLTVlZsrMSi0faWm386-UIOWSlJm5PB5j-vzkFRE62PauO8gkmrYefaV"
        self.sell_wh = "https://discord.com/api/webhooks/1332066657853505557/HXqQjdEdrTCwFH80yiQzeeBSgqnO4YWv9SdXE_Hkojj63XfvbGQy7MqCdeYhQxdNbK4_"
    
    async def flag_token_as_large_buys(self, ca: str, token_name: str, tx_description: str):
        if tx_description in self.processed_txs:
            return
        self.processed_txs.add(tx_description)
        
        if ca not in self.tracked_tokens:
            self.tracked_tokens[ca] = {
                'ca': ca,
                'token_name': token_name,
                'transactions': [],
                'buy_amount': 0,
                'sell_amount': 0,
                'last_alerted_buy': 0,
                'last_alerted_sell': 0
            }
            print(f"\nStarted Tracking {token_name}\nCA: |{ca}|")

        self.tracked_tokens[ca]['transactions'].append(tx_description)
        
        if "swapped" in tx_description:
            if "swapped" and "SOL for" in tx_description:
                await self.add_buy_amount(ca, tx_description)
                current_buys = self.tracked_tokens[ca]['buy_amount']
                current_sells = self.tracked_tokens[ca]['sell_amount']
                
                if current_buys >= 30:
                    if ca not in self.alerted_cas:
                        self.alerted_cas.add(ca)
                        self.tracked_tokens[ca]['last_alerted_buy'] = current_buys
                        self.tracked_tokens[ca]['last_alerted_sell'] = current_sells
                        await self.send_webhook(ca)
                    elif current_buys >= 500:  # Check for high volume threshold
                        if (abs(current_buys - self.tracked_tokens[ca]['last_alerted_buy']) >= 100 or 
                            abs(current_sells - self.tracked_tokens[ca]['last_alerted_sell']) >= 100):
                            self.tracked_tokens[ca]['last_alerted_buy'] = current_buys
                            self.tracked_tokens[ca]['last_alerted_sell'] = current_sells
                            await self.send_webhook(ca)
                    else:  # For buys between 30 and 500
                        if (abs(current_buys - self.tracked_tokens[ca]['last_alerted_buy']) >= 15 or 
                            abs(current_sells - self.tracked_tokens[ca]['last_alerted_sell']) >= 15):
                            self.tracked_tokens[ca]['last_alerted_buy'] = current_buys
                            self.tracked_tokens[ca]['last_alerted_sell'] = current_sells
                            await self.send_webhook(ca)

                await self.check_ratio(ca)

            elif "for" and "SOL on" in tx_description:
                await self.add_sell_amount(ca, tx_description)
                current_buys = self.tracked_tokens[ca]['buy_amount']
                current_sells = self.tracked_tokens[ca]['sell_amount']
                
                if ca in self.alerted_cas and (abs(current_buys - self.tracked_tokens[ca]['last_alerted_buy']) >= 15 or 
                                            abs(current_sells - self.tracked_tokens[ca]['last_alerted_sell']) >= 15):
                    self.tracked_tokens[ca]['last_alerted_buy'] = current_buys
                    self.tracked_tokens[ca]['last_alerted_sell'] = current_sells
                    await self.send_webhook(ca)
                await self.check_ratio(ca)
                await self.check_sell_pressure(ca)
        
    async def calculate_buy_sell_ratio(self, ca: str) -> float:
        if ca in self.tracked_tokens:
            token = self.tracked_tokens[ca]
            if token['sell_amount'] > 0 and token["buy_amount"] > 0:
                return token['buy_amount'] / token['sell_amount']
        return 0.0
    
    async def check_ratio(self, ca: str):
        ratio = await self.calculate_buy_sell_ratio(ca)
        min_buy_amount = 8.0
        min_sell_amount = 8.0
        current_buys = self.tracked_tokens[ca]['buy_amount']
        current_sells = self.tracked_tokens[ca]['sell_amount']

        if ratio >= 2.0 and current_buys >= min_buy_amount and current_sells >= min_sell_amount: #2:1 ratio
            if ca not in self.bpi_alerted_cas:
                self.bpi_alerted_cas[ca] = (current_buys, current_sells)
                await self.send_bpi_webhook(ca, ratio)
            else:
                last_buys, last_sells = self.bpi_alerted_cas[ca]
                if current_buys >= last_buys * 2 and current_sells >= last_sells * 2:
                    self.bpi_alerted_cas[ca] = (current_buys, current_sells)
                    await self.send_bpi_webhook(ca, ratio)

    async def send_bpi_webhook(self, ca: str, ratio: float):
        if ca not in self.tracked_tokens:
            return
        token = self.tracked_tokens[ca]

        data = {
            "username": "BPI Detection Bot",
            "embeds": [{
                "title": f"📈Heavy Buy Pressure Indicator📈 For: {token['token_name']}",
                "description": f"Buy/Sell ratio of {ratio:.1f} detected",
                "fields": [
                    {
                        "name": "Token Name",
                        "value": f"```{token['token_name']}```",
                        "inline": False
                    },
                    {
                        "name": "Contract Address",
                        "value": f"```{token['ca']}```",
                        "inline": False
                    },
                    {
                        "name": "Total Buys:",
                        "value": f"```{token['buy_amount']:.2f} SOL```",
                        "inline": False
                    },
                    {
                        "name": "Total Sells",
                        "value": f"```{token['sell_amount']:.2f} SOL```",
                        "inline": True
                    }
                ]
            }]
        }


        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.bpi_wh, json=data) as response:
                    if response.status == 204:
                        print("Webhook sent successfully")
                    else:
                        print(f"Failed to send webhook: {response.status}")
            except Exception as e:
                print(f"Error sending webhook: {str(e)}")
        
        
    #----------------------------------------
    #SELL Integration
    #----------------------------------------

    async def process_sell_transaction(self, ca: str, token_name: str, tx_description: str):
        await self.flag_token_as_large_buys(ca, token_name, tx_description)
        await self.update_sell_totals(ca)

    
    async def extract_sell_amounts(self, tx_description: str) -> float:
        pattern = r'swapped .+? for ([\d,\.]+) SOL'  # More flexible pattern
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
            if sell_amount > 0:
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


    async def check_sell_pressure(self, ca: str):
        if ca in self.tracked_tokens:
            token = self.tracked_tokens[ca]
            current_buys = token['buy_amount']
            current_sells = token['sell_amount']

            threshold = current_buys + 10.0
            percentage_exceeded = ((current_sells - threshold) / threshold) * 100
            
            if current_buys >= 10.0 and current_sells > current_buys + 10.0:
                if ca not in self.sell_pressure_alerted_cas:
                    self.sell_pressure_alerted_cas[ca] = percentage_exceeded
                    await self.send_sell_pressure_webhook(ca, percentage_exceeded)
                elif abs(percentage_exceeded - self.sell_pressure_alerted_cas[ca]) >= 20: #20% change in sell pressure
                    self.sell_pressure_alerted_cas[ca] = percentage_exceeded
                    await self.send_sell_pressure_webhook(ca, percentage_exceeded)
    
    async def send_sell_pressure_webhook(self, ca: str, percentage_exceeded: float):
        token = self.tracked_tokens[ca]
   
        data = {
            "username": "Sell Pressure Alert Bot",
            "embeds": [{
                "title": f"📉 Sell Pressure Detected For: {token['token_name']}\n Sells outweight Buys by: {percentage_exceeded:.2f}%",
                "description": "Token sells have exceeded buys",
                "fields": [
                    {
                        "name": "Token Name",
                        "value": f"`{token['token_name']}`",
                        "inline": False
                    },
                    {
                        "name": "'Contract Address'", 
                        "value": f"`{token['ca']}`",
                        "inline": False
                    },
                    {
                        "name": "Total Buys",
                        "value": f"`{token['buy_amount']:.2f}` SOL",
                        "inline": True
                    },
                    {
                        "name": "Total Sells",
                        "value": f"`{token['sell_amount']:.2f}` SOL",
                        "inline": True 
                    }
                ]
            }]
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.sell_wh, json=data) as response:
                    if response.status == 204:
                        print("Sell pressure webhook sent")
                    else:
                        print(f"Failed to send webhook: {response.status}")
            except Exception as e:
                print(f"Error sending webhook: {str(e)}")

#----------------------------------------
    #Buy Integration
#----------------------------------------

    async def process_buy_transaction(self, ca: str, token_name: str, tx_description: str):
        await self.flag_token_as_large_buys(ca, token_name, tx_description)
        await self.update_buy_totals(ca)

    
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
            if buy_amount > 0:
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
        
        buy_txs = []
        sell_txs = []

        for tx in token['transactions']:
            if "swapped" and "SOL for" in tx:
                buy_txs.append(tx)
            elif "for" and "SOL on" in tx:
                sell_txs.append(tx)

        last_buys = buy_txs[-3:] if buy_txs else []
        last_sells = sell_txs[-3:] if sell_txs else []

        tx_display = ""
        if last_buys:
            tx_display += f"`Recent Buys:`\n" + "\n".join(last_buys) + "\n\n"
        if last_sells:
            tx_display += "`Recent Sells:`\n" + "\n".join(last_sells)

        data = {
            "username": "Tx & Buy Tracker",
            "embeds": [{
                "title": f"Large Buys Detected For: {token['token_name']}\n🪙Transaction Data: ",
                "fields": [
                    {
                        "name": "**Token Name**",
                        "value": f"`{token['token_name']}`",
                        "inline": False
                    },
                    {
                        "name": f"Contract Address",
                        "value": f"`{token['ca']}`",
                        "inline": False
                    },
                    {
                        "name": f"Recent Transactions\n{'-'*10}",
                        "value": tx_display[:1024] if tx_display else "No transactions",
                        "inline": False
                    },
                    {
                        "name": "`Total buys📈`",
                        "value": f"{token['buy_amount']:.2f} SOL",
                        "inline": True
                    },
                    {
                        "name": "`Total sells📉`",
                        "value": f"{token['sell_amount']:.2f} SOL",
                        "inline": True
                    }
                ]
            }]
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.large_buys_wh, json=data) as response:
                    if response.status == 204:
                        print("Webhook sent successfully")
                    else:
                        print(f"Failed to send webhook: {response.status}")
            except Exception as e:
                print(f"Error sending webhook: {str(e)}")