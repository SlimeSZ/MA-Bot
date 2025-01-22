import requests
import asyncio
import aiohttp
import re
import time
from datetime import datetime
#from token_revival import TokenRevivalMonitor
from env import TOKEN, MULTI_ALERT_WEBHOOK, TWOX_WEBHOOK
from typing import Dict, Tuple
from marketcap import MarketcapFetcher


from flaggedtoken import tracker


class DexScreenerAPI:
    def __init__(self):
        self.reset_data()
        self.marketcap_fetcher = MarketcapFetcher()
    
    def reset_data(self):
        self.token_ca = None
        self.token_mc = None
        self.token_created_at = None

        self.token_5m_vol = None
        self.token_1h_vol = None
        self.token_6h_vol = None
        self.token_24h_vol = None

        self.token_5m_buys = None
        self.token_5m_sells = None
        self.token_1h_buys = None
        self.token_1h_sells = None
        self.token_6h_buys = None
        self.token_6h_sells = None
        self.token_24h_buys = None
        self.token_24h_sells = None

        self.token_5m_price_change = None
        self.token_1h_price_change = None
        self.token_6h_price_change = None
        self.token_24h_price_change = None

        self.token_liquidity = None

        self.has_tg = False
        self.has_x = False
        self.x_link = None
        self.tg_link = None
        self.token_on_dex = False
        self.token_on_pump = False
        
        self.token_dex_url = None

        
    async def fetch_token_data_from_dex(self, session, ca):
        self.reset_data()
        #print(f"\n=== Fetching DexScreener Data for {ca[:8]}... ===")

        url = f"https://api.dexscreener.com/latest/dex/search?q={ca}"
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    #print(f"[ERROR] Dex Screener API Returned Status: {response.status}")
                    return
                
                json_data = await response.json()
                if not json_data or 'pairs' not in json_data or not json_data['pairs']:
                    #print(f"[INFO] No pairs found for {ca[:8]}... - Token might be on Pump")
                    self.token_on_pump = True
                    return
                
                self.token_on_dex = True

                found_pair = False
                for pair in json_data['pairs']:
                    found_pair = True
                    #print("\nToken Metrics:")
                    #get mc
                    self.token_mc = float(pair.get('fdv', 0))
                    if self.token_mc == "Unknown" or self.token_mc == "unknown":
                        self.token_mc = self.marketcap_fetcher.calculate_marketcap(ca)
                    #print(f"- Market Cap: ${self.token_mc:,.2f}")
                    #self.token_name = pair.get('baseToken', {}).get('name', '')
                    #print(f"- Token Name: {self.token_name}")

                    #get volume
                    volume_data = pair.get('volume', {})
                    self.token_5m_vol = float(volume_data.get('m5', 0))
                    self.token_1h_vol = float(volume_data.get('h1', 0))
                    self.token_6h_vol = float(volume_data.get('h6', 0))
                    self.token_24h_vol = float(volume_data.get('h24', 0))
                    #print(f"- 1h Volume: ${self.token_1h_vol:,.2f}")

                    #get buys & sells
                    txns_data = pair.get('txns', {})
                    m5_txns = txns_data.get('m5', {})
                    self.token_5m_buys = int(m5_txns.get('buys', 0))
                    self.token_5m_sells = int(m5_txns.get('sells', 0))
                    h1_txns = txns_data.get('h1', {})
                    self.token_1h_buys = int(h1_txns.get('buys', 0))
                    self.token_1h_sells = int(h1_txns.get('sells', 0))
                    h24_txns = txns_data.get('h24', {})
                    self.token_24h_buys = int(h24_txns.get('buys', 0))
                    self.token_24h_sells = int(h24_txns.get('sells', 0))

                    #get price change
                    priceChange_data = pair.get('priceChange', {})
                    self.token_5m_price_change = priceChange_data.get('m5', 0)
                    self.token_1h_price_change = priceChange_data.get('h1', 0)
                    self.token_24h_price_change = priceChange_data.get('h24', 0)

                    #get liquidity
                    liquidity_data = pair.get('liquidity', {})
                    self.token_liquidity = float(liquidity_data.get('usd', 0))
                    #print(f"- Liquidity: ${self.token_liquidity:,.2f}")
                    
                    #x, tg, and dex url
                    info = pair.get('info', {})
                    socials = info.get('socials', [])
                    for social in socials:
                        if social['type'] == 'telegram':
                            self.has_tg = True
                            self.tg_link = social.get('url', 'No Telegram Link')
                        if social['type'] == 'twitter':
                            self.has_x = True
                            self.x_link = social.get('url', 'No Twitter Link')
                    self.token_dex_url = pair.get('url', '')
                    
                    #print("\nSocial Links:")
                    #print(f"- Telegram: {'Yes' if self.has_tg else 'No'}")
                    #print(f"- Twitter: {'Yes' if self.has_x else 'No'}")
                    #print(f"- DEX URL: {self.token_dex_url}")
                    break
                    
        except Exception as e:
            print(f"[ERROR] Error in fetching Data from Dex for {ca[:8]}...: \n{str(e)}")


class AlefDaoScraper:
    def __init__(self):
        self.url = "https://discord.com/api/v10/channels/{}/messages"
        self.dex = DexScreenerAPI()

        self.last_message_ids = {}
        self.multi_alerted_cas = set()
        self.original_mcs = {}
        self.token_volume_data = {}
        self.monitoring_tasks = {}
        self.ca_to_tx_descriptions = {}  # Added for tracking transactions

        self.sol_tracker = SolAmountTracker()

        #wallet sets
        self.high_freq_cas = set()
        self.legend_cas = set()
        self.kol_alpha_cas = set()
        self.kol_regular_cas = set()
        self.whale_cas = set()
        self.smart_cas = set()
        self.challenge_cas = set()
        self.degen_cas = set()
        self.insider_wallet_cas = set()
        self.fresh_cas = set()
        self.fresh_5sol_1m_mc_cas = set()
        self.fresh_1h_cas = set()

        #webhooks
        self.multi_alert_webhook = MULTI_ALERT_WEBHOOK
        self.twox_webhook = TWOX_WEBHOOK

    async def flag_token_for_tracking(self, ca: str):
        tracker.initialize_token(ca)
        #print(f"Flagged token: {token_name} ({ca})")

    async def stop_tracking_token(self, ca: str):
        tracker.stop_tracking(ca)

    async def list_tracked_tokens(self):
        await tracker.list_tracked_tokens()


    
    async def swt_fetch_messages(self, session, channel_id, ca_set, channel_name):
        headers = {'authorization': TOKEN}

        processed_messages = set()
        url = self.url.format(channel_id)

        while True:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        messages = await response.json()
                        if messages:
                            latest_message = messages[0]
                            message_id = latest_message['id']
                            if message_id not in processed_messages:
                                processed_messages.add(message_id)
                                #print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] New message in {channel_name}")
                                await self.swt_process_messages(session, latest_message, ca_set, channel_name)
                    else:
                        print(f"[ERROR] Failed to fetch messages from {channel_name}: Status {response.status}")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"[ERROR] Exception in {channel_name} channel: {str(e)}")
                await asyncio.sleep(1)

    async def swt_process_messages(self, session, message, ca_set, channel_name):
        try:
            embeds = message.get('embeds', [])
            if not embeds:
                return

            embed = embeds[0]
            tx_description = embed.get('description', '')
            
            if not tx_description or "swapped" not in tx_description.lower():
                return

            fields = embed.get('fields', [])
            for field in fields:
                token_name = field.get('name', '').strip().lower()
                if token_name not in {'sol', 'useful links', 'buy with bonkbot', 'token address'}:
                    ca = field.get('value', '')
                    if ca and ca not in {'So11111111111111111111111111111111111111112', '[Wallet]', '[Neo]'}:
                        if ca in tracker.tracked_tokens:
                            await tracker.process_transaction(ca, tx_description, channel_name)
                        
                        sol_amount, is_buy = self.extract_sol_amount(tx_description)
                        if sol_amount > 0:
                            wallet_type = 'fresh' if 'fresh' in channel_name.lower() else 'swt'
                            if sol_amount >= 5.0:
                                await self.sol_tracker.add_transaction(
                                    ca=ca,
                                    sol_amount=sol_amount,
                                    tx_description=tx_description,
                                    channel_name=channel_name,
                                    wallet_type=wallet_type,
                                    token_name=token_name
                                )
                        
                        ca_set.add(ca)
                        if ca not in self.ca_to_tx_descriptions:
                            self.ca_to_tx_descriptions[ca] = []
                        if (tx_description, channel_name) not in self.ca_to_tx_descriptions[ca]:
                            self.ca_to_tx_descriptions[ca].append((tx_description, channel_name))

                        await self.check_for_multialert(session, token_name, ca)
                        return

        except Exception as e:
            print(f"[ERROR] Error Processing SWT Messages: {str(e)}")

    async def degen_fetch_messages(self, session, channel_id, ca_set, channel_name):
        headers = {'authorization': TOKEN}

        processed_messages = set()
        url = self.url.format(channel_id)
        #print(f"\nStarting to monitor channel: {channel_name}")

        while True:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        messages = await response.json()
                        if messages:
                            latest_message = messages[0]
                            message_id = latest_message['id']
                            if message_id not in processed_messages:
                                processed_messages.add(message_id)
                                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] New message in {channel_name}")
                                await self.degen_process_messages(session, latest_message, ca_set, channel_name)
                    else:
                        print(f"[ERROR] Failed to fetch messages from {channel_name}: Status {response.status}")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"[ERROR] Exception in {channel_name} channel: {str(e)}")
                await asyncio.sleep(5)


    async def degen_process_messages(self, session, message, ca_set, channel_name):
        try:
            embeds = message.get('embeds', [])
            if not embeds:
                print(f"[{channel_name}] No embeds found in message")
                return

            embed = embeds[0]
            #print(f"\n=== Processing Message from {channel_name} ===")

            fields = embed.get('fields', [])
            for field in fields:
                token_name = field.get('name', '').strip().lower()
                if token_name not in {'sol', 'useful links', 'buy with bonkbot', 'token address'}:
                    ca = field.get('value', '')
                    if ca and ca not in {'So11111111111111111111111111111111111111112', '[Wallet]', '[Neo]'}:
                        ca_set.add(ca)
                        """
                        if ca not in self.ca_to_tx_descriptions:
                            self.ca_to_tx_descriptions[ca] = []
                            if (tx_description, channel_name) not in self.ca_to_tx_descriptions[ca]:
                                self.ca_to_tx_descriptions[ca].append((tx_description, channel_name)
                        """
                        #print(f"Found new token:")
                        #print(f"- Name: {token_name}")
                        #print(f"- Contract: {ca[:20]}...")
                        #print(f"- Channel: {channel_name}")

                        await self.check_for_multialert(session, token_name, ca)
                        return

            #print("=== Message Processing Complete ===\n")

        except Exception as e:
            print(f"[ERROR] Error Processing SWT Messages: {str(e)}")

    async def fresh_channel_fetch_messages(self, session, channel_id, ca_set, channel_name):
            headers = {'authorization': TOKEN}

            processed_messages = set()
            url = self.url.format(channel_id)
            #print(f"\nStarting to monitor channel: {channel_name}")

            while True:
                try:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            messages = await response.json()
                            if messages:
                                latest_message = messages[0]
                                message_id = latest_message['id']
                                if message_id not in processed_messages:
                                    processed_messages.add(message_id)
                                    #print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] New message in {channel_name}")
                                    await self.fresh_channels_process_messages(session, latest_message, ca_set, channel_name)
                        else:
                            print(f"[ERROR] Failed to fetch messages from {channel_name}: Status {response.status}")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"[ERROR] Exception in {channel_name} channel: {str(e)}")
                    await asyncio.sleep(1)

    async def fresh_channels_process_messages(self, session, message, ca_set, channel_name):
        try:
            embeds = message.get('embeds', [])
            if not embeds:
                return

            embed = embeds[0]
            tx_description = embed.get('description', '')
            
            if not tx_description or "swapped" not in tx_description.lower():
                return
            
            token_name = embed.get('title', '').strip()
            if token_name.startswith('$'):
                token_name = token_name[1:]
            
            if not token_name:
                return

            fields = embed.get('fields', [])
            for field in fields:
                field_name = field.get('name', '').strip().lower()
                if field_name == "token address:":
                    ca = field.get('value', '').strip()
                    if ca and ca not in {'So11111111111111111111111111111111111111112', '[Wallet]', '[Neo]'}:
                        if ca in tracker.tracked_tokens:
                            await tracker.process_transaction(ca, tx_description, channel_name)
                        
                        sol_amount, is_buy = self.extract_sol_amount(tx_description)
                        if sol_amount > 0:
                            wallet_type = 'fresh' if 'fresh' in channel_name.lower() else 'swt'
                            if sol_amount >= 5.0:
                                await self.sol_tracker.add_transaction(
                                    ca=ca,
                                    sol_amount=sol_amount,
                                    tx_description=tx_description,
                                    channel_name=channel_name,
                                    wallet_type=wallet_type,
                                    token_name=token_name
                                )
                        
                        ca_set.add(ca)
                        if ca not in self.ca_to_tx_descriptions:
                            self.ca_to_tx_descriptions[ca] = []
                        if (tx_description, channel_name) not in self.ca_to_tx_descriptions[ca]:
                            self.ca_to_tx_descriptions[ca].append((tx_description, channel_name))

                        await self.check_for_multialert(session, token_name, ca)
                        return

        except Exception as e:
            print(f"[ERROR] Error Processing Messages from {channel_name}: {str(e)}")
        
    async def start_market_cap_monitoring(self, session, ca, token_name):
        """Start monitoring market cap for a specific token with task management"""
        if ca not in self.monitoring_tasks:
            task = asyncio.create_task(self.monitor_token_market_cap(session, ca, token_name))
            self.monitoring_tasks[ca] = task

    async def monitor_token_market_cap(self, session, ca, token_name):
        """Monitor individual token's market cap with improved error handling and retry logic"""
        retries = 0
        max_retries = 3
        
        while True:
            try:
                await self.dex.fetch_token_data_from_dex(session, ca)
                current_mc = self.dex.token_mc
                
                if current_mc is None or current_mc == 0:
                    retries += 1
                    if retries >= max_retries:
                        #print(f"Stopping monitoring for {ca} - No valid market cap data")
                        return
                    await asyncio.sleep(5)
                    continue

                if ca not in self.original_mcs:
                    self.original_mcs[ca] = current_mc
                    #print(f"Started monitoring {token_name} at ${current_mc:,.2f}")
                else:
                    original_mc = self.original_mcs[ca]
                    if original_mc > 0:
                        increase_percentage = ((current_mc - original_mc) / original_mc) * 100
                        if increase_percentage >= 100:

                            await self.send_marketcap_increase_webhook(
                                ca, increase_percentage, original_mc, current_mc, token_name
                            )
                            self.original_mcs[ca] = current_mc  # Update baseline

                await asyncio.sleep(50)  # Check every 50 seconds
                
            except Exception as e:
                print(f"Error monitoring market cap for {ca}: {e}")
                await asyncio.sleep(5)  # Backoff on error


    async def send_marketcap_increase_webhook(self, ca, increase_percentage, original_mc, new_mc, token_name):
        try:
            data = {
                "username": "Marketcap Alert Bot",
                "embeds": [
                    {
                        "title": "🚀 2x+ Alert!",
                        "description": (
                            f"Token  `{token_name}` has increased by {increase_percentage:.2f}%\n"
                            f"CA: `{ca}`"
                        ),
                        "fields": [
                            {
                                "name": "Original Market Cap",
                                "value": f"${original_mc:,.2f}",
                                "inline": True
                            },
                            {
                                "name": "Market Cap After Call",
                                "value": f"${new_mc:,.2f}",
                                "inline": True
                            },
                            {
                                "name": "Increase %: ",
                                "value": f"{increase_percentage:.2f}%",
                                "inline": True
                            }
                        ],
                        "color": 0x00ff00
                     }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.twox_webhook, json=data) as response:
                    if response.status == 204:
                        print(f"")
                    else:
                        print(f"Failed to send 2x alert webhook: {response.status}")


        except Exception as e:
            print(f"Error sending 2x webhook: {e}")


    def aggregate_sol_buys(self, tx_descriptions: list) -> dict:
        """Aggregate total SOL buys by wallet category using channel names"""
        buys = {
            "Legend Alpha": 0,    # Changed from "Legend" to match channel name
            "Kol Alpha": 0,
            "Kol Regular": 0,
            "Whale": 0,
            "Smart": 0,
            "Challenge": 0,
            "High Freq": 0,
            "Degen": 0,
            "Fresh": 0,
            "Fresh 5sol 1m MC": 0,  # Changed to match the channel name
            "Fresh 1h": 0,
            "Insider": 0          # Added for insider wallet tracking
        }

        seen_fresh_txs = set()
        
        for tx_description, channel_name in tx_descriptions:
            sol_amount, is_buy = self.extract_sol_amount(tx_description)
            if not is_buy:  
                continue

            if sol_amount > 0:
                # Map channel_name to the appropriate category
                if channel_name == 'Fresh' or 'freshly funded wallet' in tx_description.lower():
                    if tx_description in seen_fresh_txs:
                        continue
                    seen_fresh_txs.add(tx_description)
                    buys['Fresh'] += sol_amount
                elif channel_name == 'Fresh 5sol 1m MC':  # Updated to match channel name
                    buys['Fresh 5sol 1m MC'] += sol_amount
                elif channel_name == 'Fresh 1h':
                    buys['Fresh 1h'] += sol_amount
                elif channel_name == 'Legend Alpha':  # Updated to match channel name
                    buys['Legend Alpha'] += sol_amount
                elif channel_name == 'Kol Alpha':
                    buys['Kol Alpha'] += sol_amount
                elif channel_name == 'Kol Regular':
                    buys['Kol Regular'] += sol_amount
                elif channel_name == 'Whale':
                    buys['Whale'] += sol_amount
                elif channel_name == 'Smart':
                    buys['Smart'] += sol_amount
                elif channel_name == 'Challenge':
                    buys['Challenge'] += sol_amount
                elif channel_name == 'High Freq':
                    buys['High Freq'] += sol_amount
                elif channel_name == 'Insider':
                    buys['Insider'] += sol_amount
                elif channel_name == 'Degen':
                    buys['Degen'] += sol_amount
        return buys
    
    def extract_sol_amount(self, tx_description: str) -> Tuple[float, bool]:
        description = tx_description.lower()
        
        # If there's no swap, ignore the transaction
        if "swapped" not in description:
            return 0, False
        
        # Pattern 1: If format is "swapped X SOL for..."
        if "swapped" in description:
            parts = description.split()
            try:
                for i, word in enumerate(parts):
                    if word == "swapped":
                        next_word = parts[i + 1]
                        if next_word.replace(".", "").isdigit() and parts[i + 2].lower() == "sol":
                            return float(next_word), True  # This is a buy
            except (IndexError, ValueError):
                pass
        
        # Pattern 2: If format is "swapped X tokens for Y SOL"
        if re.search(r'\sfor\s+([\d,.]+)\s+sol\s', description):
            try:
                amount = float(re.search(r'\sfor\s+([\d,.]+)\s+sol\s', description).group(1))
                return amount, False  # This is a sell
            except (AttributeError, ValueError):
                pass
        
        return 0, False


    async def check_for_multialert(self, session, token_name, ca):
        """Check if token has been bought by both fresh and SOL tracker wallets"""
        if ca in self.multi_alerted_cas:
            #print(f"Token {token_name} already alerted for multi-ape, skipping... ")
            return

        fresh_ca_tracker_sets = {
            'Fresh': self.fresh_cas,
            'Fresh 1h': self.fresh_1h_cas,
            'Fresh 5sol 1m MC': self.fresh_5sol_1m_mc_cas
        }

        sol_tracker_sets = {
            'Legend Alpha': self.legend_cas,
            'Kol Alpha': self.kol_alpha_cas,
            'Kol Regular': self.kol_regular_cas,
            'Whale': self.whale_cas,
            'Smart': self.smart_cas,
            'Challenge': self.challenge_cas,
            'High Freq': self.high_freq_cas,
            'Degen': self.degen_cas,
            'Insider': self.insider_wallet_cas
        }

        fresh_wallet_name = next((name for name, ca_set in fresh_ca_tracker_sets.items() if ca in ca_set), None)
        sol_wallet_names = [name for name, ca_set in sol_tracker_sets.items() if ca in ca_set]

        if fresh_wallet_name and sol_wallet_names:
            self.multi_alerted_cas.add(ca)
            alert_time = datetime.now().strftime('%I:%M:%S %p')
            
            try:
                #revival_monitor = TokenRevivalMonitor()
                #await revival_monitor.start_revival_monitoring(session, ca, token_name)

                await self.dex.fetch_token_data_from_dex(session, ca)
                initial_volume = self.dex.token_5m_vol



                await self.start_market_cap_monitoring(session, ca, token_name)
                
                combined_description = "\n".join([desc for desc, _ in self.ca_to_tx_descriptions.get(ca, [])])
                sol_buys = self.aggregate_sol_buys(self.ca_to_tx_descriptions.get(ca, []))

                #print("\nMASOL Buy Amounts:")
                for wallet_type, amount in sol_buys.items():
                    if amount > 0:
                        print("")
                        #print(f"{wallet_type}: {amount:.2f} SOL")
                print("\nChannel Names and Transactions:")
                for desc, channel in self.ca_to_tx_descriptions.get(ca, []):
                    #print(f"{channel}: {desc}")
                    print("")

                sol_wallets_str = ', '.join(sol_wallet_names)
                
                market_cap_display = "${:,.2f}".format(self.dex.token_mc) if self.dex.token_mc else "Unknown"
                volume_display = "${:,.2f}".format(self.dex.token_5m_vol) if self.dex.token_5m_vol else "Unknown"
                
                """
                print(
                    f"{"-" * 15}\n"
                    f"\n=== Multi-Alert Found at {alert_time} ===\n"
                    f"Token: {token_name}\n"
                    f"CA: {ca}\n"
                    f"Market Cap: {market_cap_display}\n"
                    f"5m Volume: {volume_display}\n"
                    f"1h Volume: {self.dex.token_1h_vol}\n"
                    f"6h Volume: {self.dex.token_6h_vol}\n"
                    f"24h Volume: {self.dex.token_24h_vol}\n"
                    f"5m buys: {self.dex.token_5m_buys}\n"
                    f"5m sells: {self.dex.token_5m_sells}"
                    f"Liquidity: {self.dex.token_liquidity}\n"
                    f"Categories: {sol_wallets_str} and {fresh_wallet_name}\n"
                    f"TG: {self.dex.tg_link or 'No TG Link'}\n"
                    f"X: {self.dex.x_link or 'No X Link'}\n"
                    f"DEX: {self.dex.token_dex_url or 'No DEX URL'}\n"
                    f"{"-" * 15}\n"
                )
                """

                await self.send_webhook_message(
                    ca=ca,
                    title="🚨 Multi Alert Found! 🚨",
                    description=f"{token_name} was detected in multiple wallets at {alert_time}! ",
                    display_message=f"Aped by wallets in categories: {sol_wallets_str} and {fresh_wallet_name}",
                    token_name=token_name,
                    marketcap=self.dex.token_mc,
                    m5_vol=self.dex.token_5m_vol,
                    liquidity=self.dex.token_liquidity,
                    tg_link=self.dex.tg_link or "No TG Found",
                    x_link=self.dex.x_link or "No Twitter Link Found",
                    tx_description=combined_description,
                    token_dex_url=self.dex.token_dex_url,
                    sol_buys=sol_buys
                )

            except Exception as e:
                print(f"Error in multi-alert processing for {ca}: {e}")



    async def send_webhook_message(self, ca, title, description, display_message, token_name, marketcap, m5_vol, liquidity, tg_link, x_link, tx_description, token_dex_url, sol_buys):
        try:
            # Format buy amounts by channel
            buy_amounts = [f"{wallet}: {amount:.2f} SOL" for wallet, amount in sol_buys.items() if amount > 0]
            buy_summary = "\n".join(buy_amounts) if buy_amounts else "No significant buy amounts detected"
            
            data = {
                "username": "Multi Alert Bot",
                "embeds": [{
                    "title": title,
                    "description": description,
                    "fields": [
                        {
                            "name": "CA",
                            "value": f"`{ca.strip()}`",
                            "inline": False
                        },
                        {
                            "name": "Token Name",
                            "value": token_name,
                            "inline": False
                        },
                        {
                            "name": " ",
                            "value": display_message,
                            "inline": False
                        },
                        {
                            "name": "Marketcap 💰",
                            "value": f"${marketcap:,.2f}" if marketcap else "Unknown",
                            "inline": False
                        },
                        {
                            "name": "5m Volume 📊",
                            "value": f"${m5_vol:,.2f}" if m5_vol else "Unknown",
                            "inline": False
                        },
                        {
                            "name": "Liquidity 💸",
                            "value": f"${liquidity:,.2f}" if liquidity else "Unknown",
                            "inline": False
                        },
                        {
                            "name": "Telegram Link",
                            "value": tg_link,
                            "inline": False
                        },
                        {
                            "name": "Twitter Link",
                            "value": x_link,
                            "inline": False
                        },
                        {
                            "name": f"Transaction Details 🔄\n{'-' * 20}",
                            "value": tx_description[:1024] if tx_description else "No details",
                            "inline": False
                        },
                        {
                            "name": f"{"-" * 20}\nBuy Amounts 🛒",
                            "value": buy_summary,
                            "inline": False
                        },
                        {
                            "name": "Trade on DEX",
                            "value": token_dex_url or "No Dex Url Found",
                            "inline": False
                        }
                    ]
                }]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.multi_alert_webhook, json=data) as response:
                    if response.status == 204:
                        print("")
                        #print("Multi-alert webhook sent successfully!")
                    else:
                        print(f"Failed to send multi-alert webhook: {response.status}")

        except Exception as e:
            print(f"Error sending multi-alert webhook: {e}")


class SolAmountTracker:
    def __init__(self):
        self.ca_data = {}
        self.sol_alerted_cas = set()
        self.token_names = {}
        self.webhook_url = "https://discord.com/api/webhooks/1325996051731189841/92Yw97O80CvrIPFpgqBFS1rvDaSVzwHDtBRySMg633yYNWqVMkrcq0_ZDdkcTurbM73a"

    async def initialize_ca_tracking(self, ca, token_name=None):
        if ca not in self.ca_data:
            self.ca_data[ca] = {
                'large_buys': [],
                'transactions': []
            }
            if token_name:
                self.token_names[ca] = token_name
            
    async def add_transaction(self, ca, sol_amount, tx_description, channel_name, wallet_type, token_name=None):
        """Add a new transaction and update cumulative amounts"""
        #print(f"Processing transaction: {sol_amount} SOL from {channel_name} for {ca}")
        try:
            # First initialize tracking for this CA
            await self.initialize_ca_tracking(ca, token_name)
            
            # Add transaction and update amounts under lock protection
            transaction = {
                'amount': sol_amount,
                'description': tx_description,
                'channel': channel_name,
                'wallet_type': wallet_type,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if ca not in self.ca_data:
                return  # Safety check in case CA was removed
                
            self.ca_data[ca]['transactions'].append(transaction)
            
            # Update the appropriate amount counter
            if sol_amount >= 5.0:
                self.ca_data[ca]['large_buys'].append(transaction)
        
        # Check threshold after releasing lock to prevent deadlocks
            await self.check_alert_conditions(ca)
            
        except Exception as e:
            print(f"Error adding transaction for {ca}: {e}")
            raise e  # Re-raise to allow proper error handling upstream
        
    async def check_alert_conditions(self, ca):
        if ca in self.sol_alerted_cas:
            return
                
        try:

            if ca not in self.ca_data:
                return

            data = self.ca_data[ca]
            transactions = [tx for tx in data['transactions'] if tx['channel'].lower() != 'degen']
            
            alerts_to_send = []
            
            # Check for 10+ SOL buys first
            large_single_buys = [tx for tx in transactions if tx['amount'] >= 10.0]
            if large_single_buys:
                largest_buy = max(large_single_buys, key=lambda x: x['amount'])
                #print(f"Found 10+ SOL buy: {largest_buy['amount']} from {largest_buy['channel']}")
                alerts_to_send.append(('One 10+ sol buy', [largest_buy]))
            
            # Check for 5+ SOL buys from different channels
            five_plus_buys = [(tx['channel'], tx) for tx in transactions if tx['amount'] >= 5.0]
            channels_with_large_buys = {}
            
            for channel, tx in five_plus_buys:
                # Keep largest buy per channel
                if channel not in channels_with_large_buys or tx['amount'] > channels_with_large_buys[channel]['amount']:
                    channels_with_large_buys[channel] = tx
            
            if len(channels_with_large_buys) >= 2:
                # Take the two largest buys from different channels
                different_channel_buys = sorted(channels_with_large_buys.values(), 
                                            key=lambda x: x['amount'], 
                                            reverse=True)[:2]
                #print(f"Found 5+ SOL buys from different channels: {[tx['channel'] for tx in different_channel_buys]}")
                alerts_to_send.append(('Two 5+ sol buys', different_channel_buys))

            if alerts_to_send:
                self.sol_alerted_cas.add(ca)
                #print(f"Sending alerts for {ca}: {[alert[0] for alert in alerts_to_send]}")
                for alert_type, txs in alerts_to_send:
                    await self.send_alert(ca, alert_type, txs)

        except Exception as e:
            print(f"Error checking alert conditions: {str(e)}")
            self.sol_alerted_cas.discard(ca)
            raise e
            
    async def send_alert(self, ca, alert_type, triggering_transactions):
        try:
            dex = DexScreenerAPI()
            async with aiohttp.ClientSession() as session:
                await dex.fetch_token_data_from_dex(session, ca)            
            if ca not in self.ca_data:
                return

            token_name = self.token_names.get(ca, "Unknown Token")
            all_transactions = self.ca_data[ca]['transactions']

            tx_summary = "\n".join([
                f"• {tx['amount']:.2f} SOL - {tx['channel']} - {tx['timestamp']}"
                for tx in all_transactions
            ])

            if alert_type == 'Two 5+ sol buys':
                title = "🚨 Two 5+ SOL Buys Detected! 🚨"
                description = (
                    f"Token: `{token_name}`\n"
                    f"Two or more wallets have made 5+ SOL purchases!\n"
                    f"First Transaction: {triggering_transactions[0]['amount']:.2f} SOL from {triggering_transactions[0]['channel']}\n"
                    f"Second Transaction: {triggering_transactions[1]['amount']:.2f} SOL from {triggering_transactions[1]['channel']}"
                )
            else:  # single large buy
                title = "🚨 10+ SOL Buy Detected! 🚨"
                description = (
                    f"Token: `{token_name}`\n"
                    f"Transaction: {triggering_transactions[0]['amount']:.2f} SOL detected from {triggering_transactions[0]['channel']}!"
                )

            data = {
                "username": "SOL Alert Bot",
                "embeds": [{
                    "title": title,
                    "description": description,
                    "fields": [
                        {
                            "name": "Contract Address",
                            "value": f"`{ca}`",
                            "inline": False
                        },
                        {
                            "name": "Market Cap",
                            "value": f"${dex.token_mc:,.2f}" if dex.token_mc else "Unknown",
                            "inline": True
                        },
                        {
                            "name": "Liquidity",
                            "value": f"${dex.token_liquidity:,.2f}" if dex.token_liquidity else "Unknown",
                            "inline": True
                        },
                        {
                            "name": "5m Volume 📊",
                            "value": f"${dex.token_5m_vol:,.2f}" if dex.token_5m_vol else "Unknown",
                            "inline": True
                        },
                        {
                            "name": "Transaction History",
                            "value": tx_summary[:1024] if tx_summary else "No transactions recorded",
                            "inline": False
                        },
                        {
                            "name": "Links",
                            "value": f"📈 [DEX]({dex.token_dex_url})\n💬 [Telegram]({dex.tg_link})\n🐦 [Twitter]({dex.x_link})",
                            "inline": False
                        }
                    ],
                    "color": 0xFF0000
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=data) as response:
                    if response.status == 204:
                        print("")
                        #print(f"1 or 2 condition alert sent successfully for {token_name} ({ca})")
                    else:
                        print(f"Failed to send alert: {response.status}")
                        raise Exception(f"Webhook failed with status {response.status}")
                        
        except Exception as e:
            print(f"Error sending threshold alert: {e}")
            raise e  # Re-raise to trigger alert retry


        


    


class Main:
    def __init__(self):
        self.scraper = AlefDaoScraper()
        #print("\n=== Discord Multi Tracking Bot ===")
        #print("Initializing...")

    async def run_bot(self):
        #print(f"\nStarting Up Multi Tracking Bot...")
        #print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        #print("Connecting to Discord API...")
        
        async with aiohttp.ClientSession() as session:
            tasks = [
                # All channel names now match exactly with the buys dictionary
                self.scraper.swt_fetch_messages(session, '1279040666101485630', self.scraper.legend_cas, 'Legend Alpha'),
                self.scraper.swt_fetch_messages(session, '1280445495482781706', self.scraper.kol_alpha_cas, 'Kol Alpha'),
                self.scraper.swt_fetch_messages(session, '1273245344263569484', self.scraper.kol_regular_cas, 'Kol Regular'),
                self.scraper.swt_fetch_messages(session, '1273250694257705070', self.scraper.whale_cas, 'Whale'),
                self.scraper.swt_fetch_messages(session, '1280465862163304468', self.scraper.smart_cas, 'Smart'),
                self.scraper.swt_fetch_messages(session, '1277231510574862366', self.scraper.insider_wallet_cas, 'Insider'),
                self.scraper.swt_fetch_messages(session, '1283348335863922720', self.scraper.challenge_cas, 'Challenge'),
                self.scraper.swt_fetch_messages(session, '1273670414098501725', self.scraper.high_freq_cas, 'High Freq'),
                #self.scraper.degen_fetch_messages(session, '1278278627997384704', self.scraper.degen_cas, 'Degen'),

                self.scraper.fresh_channel_fetch_messages(session, '1281675800260640881', self.scraper.fresh_cas, 'Fresh'),
                self.scraper.fresh_channel_fetch_messages(session, '1281677424005746698', self.scraper.fresh_1h_cas, 'Fresh 1h'),
                self.scraper.fresh_channel_fetch_messages(session, '1281676746202026004', self.scraper.fresh_5sol_1m_mc_cas, 'Fresh 5sol 1m MC')
            ]

            try:
                #print("All monitoring tasks started successfully!")
                #print("Waiting for messages...\n")
                await asyncio.gather(*tasks)
            except Exception as e:
                print(f"[ERROR] Critical error in main execution:")
                print(f"Error details: {str(e)}")
                print("Attempting restart in 5 seconds...")
                await asyncio.sleep(5)
                await self.run_bot()

if __name__ == "__main__":
    try:
        main = Main()
        asyncio.run(main.run_bot())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Fatal error: {e}")