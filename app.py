import requests
import asyncio
import aiohttp
import re
import time
from datetime import datetime
from env import TOKEN, MA_CHANNEL_ID, TWOX_CHANNEL_ID
import os
import sqlite3
import create_tables

create_tables.create_tables()



class ADScraper:
    def __init__(self):
        self.url = "https://discord.com/api/v10/channels/{}/messages"
        self.last_message_ids = {}
        self.processed_messages = set()
        self.dex = Dex()  # This is now safe
        
        # Reset these values at start of each message processing
        self.reset_values()

    def reset_values(self):
        """Reset all instance variables for new message processing"""
        self.ca = None
        self.twoxca = None
        self.token_name = None
        self.has_tg = False
        self.has_x = False
        self.swt_buy_amount = 0
        self.fresh_buy_amount = 0
        self.swt_wallet_types = []
        self.fresh_wallet_type = None  

        self.token_volume_data = {}
        self.volume_tracking_tasks = {}
        self.marketcap_tracking_tasks = {}
        
        self.individual_amounts = {
            'legend': 0,
            'kol regular': 0,
            'kol alpha': 0,
            'smart': 0,
            'whale': 0,
            'challenge': 0,
            'high freq': 0,
            'insider': 0,
            'fresh': 0,
            'fresh 1h': 0,
            'fresh 5sol 1m mc': 0 
        }

    async def fetch_2x_channel(self, session, channel_id, channel_name):
        headers = {'authorization': TOKEN}
        url = self.url.format(channel_id)

        while True:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        messages = await response.json()
                        if messages:
                            latest_message = messages[0]
                            message_id = latest_message['id']
                            if message_id not in self.processed_messages:
                                print(f"Found new message in {channel_name}")
                                self.processed_messages.add(message_id)
                                await self.process_2x_channel(session, latest_message, channel_name)
                            else:
                                print(f"")
                        else:
                            print(f"No messages returned from api")
                    else:
                        print(f"Error failed to fetch messages from {channel_name}")
                await asyncio.sleep(15)
            except Exception as e:
                print(f"Error in fetching 2x messages: {str(e)}")
                await asyncio.sleep(5)

    def normalize(self, ca: str) -> str:
        return ca.strip().lower().replace('`', '')

    async def process_2x_channel(self, session, message, channel_name):
        try:
            embeds = message.get('embeds', [])
            if not embeds:
                print(f"No embeds found!")
                return
            
            embed = embeds[0]

            description = embed.get('description', '').lower()
            
            ca_match = re.search(r'ca:\s*`([^`]+)`', description, re.IGNORECASE)
            if not ca_match:
                print("No CA found in description")
                return
            
            ca = self.normalize(ca_match.group(1))
            print(f"Found CA: {ca}")

            conn = None
            try:
                conn = sqlite3.connect('mcdb.db')
                cursor = conn.cursor()

                cursor.execute('''
                SELECT id
                FROM multialerts
                WHERE LOWER(TRIM(REPLACE(ca, "`", ""))) = LOWER(TRIM(?))
                COLLATE NOCASE
                ''', (ca, ))

                result = cursor.fetchone()

                if result:
                    cursor.execute('UPDATE multialerts SET two_x = ? WHERE id = ?', (True, result[0]))
                    conn.commit()
                    print(f"Updated token {ca} as having a 2x! ")
                else:
                    print(f"CA {ca} from 2x alert not found in database")
                    
            except Exception as e:
                print(f"Error updating 2x status: {e}")
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()

            
        except Exception as e:
            print(str(e))
        
            


    async def fetch_ma_messages(self, session, channel_id, channel_name):
        headers = {'authorization': TOKEN}

        url = self.url.format(channel_id)

        while True:
            try:
                #print(f"Checking for new messages...")  # Debug line
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        messages = await response.json()
                        if messages:
                            latest_message = messages[0]
                            message_id = latest_message['id']
                            #print(f"Latest message ID: {message_id}")  # Debug line
                            #print(f"Processed messages count: {len(self.processed_messages)}")  # Debug line
                            
                            if message_id not in self.processed_messages:
                                print(f"New message detected! Processing...")  # Debug line
                                self.processed_messages.add(message_id)
                                await self.process_ma_messages(session, latest_message, channel_name)
                            else:
                                print("")  # Debug line
                        else:
                            print("No messages returned from API")  # Debug line
                    else:
                        print(f"Error Failed to fetch messages from {channel_name}")
                await asyncio.sleep(7)  # Reduced sleep time to be more responsive
            except Exception as e:
                print(f"Error in fetch_ma_messages: {str(e)}")
                await asyncio.sleep(5)

    async def process_ma_messages(self, session, message, channel_name):
        try:
            self.reset_values()

            embeds = message.get('embeds', [])
            if not embeds:
                print(f"No embeds found for MA Channel")
                return
            
            embed = embeds[0]

            title = embed.get('title', '').lower()
            if not title:
                print(f"No title found")
                return
            
            fields = embed.get('fields', [])
            for field in fields:
                token_fields = field.get('name', '').strip().lower()
                #ca
                if token_fields == "ca":
                    ca = self.normalize(field.get('value', ''))
                    print(ca)
                    if not ca:
                        print(f"Unable to fetch ca")
                        return
                #alert timestamp
                alert_time = datetime.now()
                #token name
                if token_fields == "token name":
                    token_name = field.get('value', '')
                    print(token_name)
                #socials
                if token_fields == "telegram link":
                    telegram_mssg = field.get('value', '').lower()
                    has_tg = telegram_mssg != "no tg found"
                    print(f"Has TG? {has_tg}")
                if token_fields == "twitter link":
                    twitter_mssg = field.get('value', '').lower()
                    has_x = twitter_mssg != "no twitter link found"
                    print(f"Has X? {has_x}")
                #buy amounts
                if "buy amounts" in token_fields:
                    buy_amounts_text = field.get('value', '').strip()
                    buy_lines = buy_amounts_text.split('\n')

                    for line in buy_lines:
                        if not line:
                            continue

                        parts = line.split(":")
                        if len(parts) != 2:
                            continue

                        wallet_type = parts[0].strip().lower()
                        try:
                            amount = float(parts[1].strip().split()[0])
                        except (ValueError, IndexError):
                            print(f"Error parsing amount for wallet type: {wallet_type}")
                            continue

                        #track individual amounts
                        if wallet_type in self.individual_amounts:
                            self.individual_amounts[wallet_type] = amount

                        if any(fresh_type in wallet_type for fresh_type in ['fresh', 'fresh 1h', 'fresh 5sol 1m mc']):
                            self.fresh_wallet_type = wallet_type
                            self.fresh_buy_amount = amount
                        else:
                            self.swt_wallet_types.append(wallet_type)
                            self.swt_buy_amount += amount
                    swt_wallet_types_str = ', '.join(self.swt_wallet_types)
                    print(f"Processed buy amounts - SWT: {self.swt_buy_amount}, Fresh: {self.fresh_buy_amount}")
                
            print(f"Fetching dex data for: {token_name}")
            await self.dex.fetch_tokenomics(session, ca)

            if self.dex.token_on_dex:
                alert_data = {
                    'token_name': token_name,
                    'ca': ca,
                    'alert_time': alert_time,
                    'swt_sol_amount': self.swt_buy_amount,
                    'fresh_sol_amount': self.fresh_buy_amount,
                    'swt_wallet_types_str': swt_wallet_types_str,
                    'fresh_wallet_type': self.fresh_wallet_type,
                    'has_x': has_x,
                    'has_tg': has_tg,
                    'liquidity': self.dex.token_liquidity,
                    'initial_marketcap': self.dex.token_fdv,
                    'volume_5m': self.dex.token_5m_vol,
                    'volume_1h': self.dex.token_1h_vol,
                    'volume_6h': self.dex.token_6h_vol,
                    'volume_24h': self.dex.token_24h_vol,
                    'buys_5m': self.dex.token_5m_buys,
                    'sells_5m': self.dex.token_5m_sells,
                    'buys_1h': self.dex.token_1h_buys,
                    'sells_1h': self.dex.token_1h_sells,
                    'buys_24h': self.dex.token_24h_buys,
                    'sells_24h': self.dex.token_24h_sells,
                    'price_change_5m': self.dex.token_5m_price_change,
                    'price_change_1h': self.dex.token_1h_price_change,
                    'price_change_24h': self.dex.token_24h_price_change,
                    'individual_amounts': self.individual_amounts,
                    'two_x': False
                }
                
                # First index initial data
                await self.index_ma_data_to_db(alert_data)
                
                # Then start volume tracking (don't wait for it)
                if ca not in self.volume_tracking_tasks:
                    initial_volume = self.dex.token_5m_vol
                    tracking_task = asyncio.create_task(
                        self.track_volume_intervals(session, ca, initial_volume)
                    )
                    self.volume_tracking_tasks[ca] = tracking_task

                if ca not in self.marketcap_tracking_tasks:
                    initial_marketcap = self.dex.token_fdv
                    tracking_task = asyncio.create_task(
                        self.track_marketcap_intervals(session, ca, initial_marketcap)
                    )
                    self.marketcap_tracking_tasks[ca] = tracking_task

            else:
                print(f"Dex data not found, awaiting to index into db until data found")
        except Exception as e:
            print(str(e))


    async def index_ma_data_to_db(self, alert_data):
        conn = None
        try:
            conn = sqlite3.connect('mcdb.db')
            conn.execute('PRAGMA foreign_keys = ON')  # Enable foreign key constraints
            cursor = conn.cursor()

            conn.execute('BEGIN')

            main_query = '''
            INSERT OR REPLACE INTO multialerts (
            token_name, ca, alert_time, swt_sol_amount, fresh_sol_amount,
            swt_wallet_type, fresh_wallet_type,
            has_x, has_tg, liquidity, initial_marketcap,
            volume_5m, volume_1h, volume_6h, volume_24h,
            buys_5m, sells_5m, buys_1h, sells_1h,
            buys_24h, sells_24h, price_change_5m,
            price_change_1h, price_change_24h,
            legend_amount, kol_regular_amount, kol_alpha_amount,
            smart_amount, whale_amount, challenge_amount,
            high_freq_amount, insider_amount,
            fresh_amount, fresh_1h_amount, fresh_5sol_1m_mc_amount,
            volume_initial, volume_1min, volume_3min, volume_5min, volume_10min, volume_20min, volume_40min, volume_60min,
            two_x
            )
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''

            individual_amounts = alert_data['individual_amounts']
            volume_data = self.token_volume_data.get(alert_data['ca'], {})
            
            cursor.execute(main_query, (
                alert_data['token_name'],
                alert_data['ca'],
                alert_data['alert_time'],
                alert_data['swt_sol_amount'],
                alert_data['fresh_sol_amount'],
                alert_data['swt_wallet_types_str'],
                alert_data['fresh_wallet_type'],
                alert_data['has_x'],
                alert_data['has_tg'],
                alert_data.get('liquidity', 0),
                alert_data.get('initial_marketcap', 0),
                alert_data.get('volume_5m', 0),
                alert_data.get('volume_1h', 0),
                alert_data.get('volume_6h', 0),
                alert_data.get('volume_24h', 0),
                alert_data.get('buys_5m', 0),
                alert_data.get('sells_5m', 0),
                alert_data.get('buys_1h', 0),
                alert_data.get('sells_1h', 0),
                alert_data.get('buys_24h', 0),
                alert_data.get('sells_24h', 0),
                alert_data.get('price_change_5m', 0),
                alert_data.get('price_change_1h', 0),
                alert_data.get('price_change_24h', 0),
                individual_amounts.get('legend', 0),
                individual_amounts.get('kol regular', 0),
                individual_amounts.get('kol alpha', 0),
                individual_amounts.get('smart', 0),
                individual_amounts.get('whale', 0),
                individual_amounts.get('challenge', 0),
                individual_amounts.get('high freq', 0),
                individual_amounts.get('insider', 0),
                individual_amounts.get('fresh', 0),
                individual_amounts.get('fresh 1h', 0),
                individual_amounts.get('fresh 5sol 1m mc', 0),
                volume_data.get('initial', 0),
                volume_data.get('1min', 0),
                volume_data.get('3min', 0),
                volume_data.get('5min', 0),
                volume_data.get('10min', 0),
                volume_data.get('20min', 0),
                volume_data.get('40min', 0),
                volume_data.get('60min', 0),
                False
            ))
            alert_id = cursor.lastrowid

        
            wallet_query = '''
            INSERT INTO wallet_amounts (alert_id, wallet_type, amount)
            VALUES (?, ?, ?)
            '''

            for wallet_type, amount in alert_data['individual_amounts'].items():
                if amount > 0:
                    cursor.execute(wallet_query, (alert_id, wallet_type, amount))

            conn.commit()
            print(f"Successfully indexed ma data")

        except sqlite3.IntegrityError as e:
            print(f"Database integrity error: {e}")
            if conn:
                conn.rollback()
        except Exception as e:
            print(f"Error indexing to database: {e}")
            print(f"Alert data keys: {alert_data.keys()}")  # Debug line
            if conn:
                conn.rollback()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    print(f"Error closing connection: {e}")

    async def update_marketcap_interval(self, ca, interval_name, marketcap):
        conn = None
        try:
            conn = sqlite3.connect('mcdb.db')
            cursor = conn.cursor()

            column_map = {
                '10min': 'marketcap_10min',
                '30min': 'marketcap_30min',
                '1hr': 'marketcap_1hr',
                '3hrs': 'marketcap_3hrs',
                '5hrs': 'marketcap_5hrs',
                '10hrs': 'marketcap_10hrs'
            }

            column_name = column_map[interval_name]
            update_query = f'''
            UPDATE multialerts 
            SET {column_name} = ? 
            WHERE ca = ?
            '''

            cursor.execute(update_query, (marketcap, ca))
            conn.commit()
            print(f"Successfully updated {interval_name} marketcap for {ca}")

        except Exception as e:
            print(f"Error updating {interval_name} marketcap: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    async def track_marketcap_intervals(self, session, ca, initial_marketcap):
        try:
            print(f"Starting marketcap tracking for {ca}")
            print(f"Initial marketcap: ${initial_marketcap:,.2f}" if initial_marketcap else "Initial marketcap: Unknown")

            intervals = {
                '10min': 600,    # 10 minutes
                '30min': 1800,   # 30 minutes
                '1hr': 3600,     # 1 hour
                '3hrs': 10800,   # 3 hours
                '5hrs': 18000,   # 5 hours
                '10hrs': 36000   # 10 hours
            }

            start_time = time.time()

            for interval_name, target_delay in sorted(intervals.items(), key=lambda x: x[1]):
                try:
                    elapsed = time.time() - start_time
                    wait_time = target_delay - elapsed
                    
                    if wait_time > 0:
                        print(f"\nWaiting {wait_time:.1f} seconds for {interval_name} marketcap check...")
                        await asyncio.sleep(wait_time)
                    
                    print(f"Fetching {interval_name} marketcap for {ca}...")
                    await self.dex.fetch_tokenomics(session, ca)
                    current_marketcap = self.dex.token_fdv
                    
                    # Update this interval's marketcap in database
                    await self.update_marketcap_interval(ca, interval_name, current_marketcap)
                    
                    print(f"Marketcap after {interval_name}: ${current_marketcap:,.2f}" if current_marketcap else f"Marketcap after {interval_name}: Unknown")
                    
                except Exception as e:
                    print(f"Error fetching {interval_name} marketcap for {ca}: {e}")
                    await self.update_marketcap_interval(ca, interval_name, 0)

        except Exception as e:
            print(f"Error in marketcap tracking for {ca}: {e}")
        finally:
            if ca in self.marketcap_tracking_tasks:
                del self.marketcap_tracking_tasks[ca]


    
    async def update_volume_interval(self, ca, interval_name, volume):
        """Update specific volume interval for a CA"""
        conn = None
        try:
            conn = sqlite3.connect('mcdb.db')
            cursor = conn.cursor()

            # Map interval name to column name
            column_map = {
                'initial': 'volume_initial',
                '1min': 'volume_1min',
                '3min': 'volume_3min',
                '5min': 'volume_5min',
                '10min': 'volume_10min',
                '20min': 'volume_20min',
                '40min': 'volume_40min',
                '60min': 'volume_60min'
            }

            column_name = column_map[interval_name]
            update_query = f'''
            UPDATE multialerts 
            SET {column_name} = ? 
            WHERE ca = ?
            '''
            
            cursor.execute(update_query, (volume, ca))
            conn.commit()
            print(f"Successfully updated {interval_name} volume for {ca}")

        except Exception as e:
            print(f"Error updating {interval_name} volume: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    async def track_volume_intervals(self, session, ca, initial_volume):
        try:
            print(f"Initial volume: ${initial_volume:,.2f} \nfor: {ca}" if initial_volume else "Initial volume: Unknown")

            # First update initial volume
            await self.update_volume_interval(ca, 'initial', initial_volume)

            intervals = {
                '1min': 60,
                '3min': 180,
                '5min': 300,
                '10min': 600,
                '20min': 1200,
                '40min': 2400,
                '60min': 3600
            }

            volumes = {
                'initial': initial_volume,
                '1min': None,
                '3min': None,
                '5min': None,
                '10min': None,
                '20min': None,
                '40min': None,
                '60min': None
            }

            start_time = time.time()

            for interval_name, target_delay in sorted(intervals.items(), key=lambda x: x[1]):
                try:
                    elapsed = time.time() - start_time
                    wait_time = target_delay - elapsed
                    
                    if wait_time > 0:
                        print(f"\nWaiting {wait_time:.1f} seconds for {interval_name} volume check...")
                        await asyncio.sleep(wait_time)
                    
                    print(f"Fetching {interval_name} volume for {ca}...")
                    await self.dex.fetch_tokenomics(session, ca)
                    current_volume = self.dex.token_5m_vol
                    volumes[interval_name] = current_volume
                    
                    # Update this interval's volume in database
                    await self.update_volume_interval(ca, interval_name, current_volume)
                    
                    print(f"Volume after {interval_name}: ${current_volume:,.2f}" if current_volume else f"Volume after {interval_name}: Unknown")
                    
                except Exception as e:
                    print(f"Error fetching {interval_name} volume for {ca}: {e}")
                    volumes[interval_name] = 0

            self.token_volume_data[ca] = volumes
            
            # Print final summary after all intervals are complete
            #print(f"\n{'='*20} Final Volume Summary for {ca} {'='*20}")
            #print(f"Initial: ${volumes['initial']:,.2f}" if volumes['initial'] else "Initial: Unknown")
            #print(f"1 minute: ${volumes['1min']:,.2f}" if volumes['1min'] else "1 minute: Unknown")
            #print(f"3 minutes: ${volumes['3min']:,.2f}" if volumes['3min'] else "3 minutes: Unknown")
            #print(f"5 minutes: ${volumes['5min']:,.2f}" if volumes['5min'] else "5 minutes: Unknown")
            #print("="*70)

        except Exception as e:
            print(f"Error in volume tracking for {ca}: {e}")
        finally:
            if ca in self.volume_tracking_tasks:
                del self.volume_tracking_tasks[ca]

class Dex:
    def __init__(self):
        self.token_fdv = None
        self.m5_vol = None
        self.h1_vol = None
        self.h6_vol = None
        self.h24_vol = None
        self.token_5m_vol = None
        self.token_1h_vol = None
        self.token_6h_vol = None
        self.token_24h_vol = None
        self.token_5m_buys = None
        self.token_5m_sells = None
        self.token_1h_buys = None
        self.token_1h_sells = None
        self.token_24h_buys = None
        self.token_24h_sells = None
        self.token_5m_price_change = None
        self.token_1h_price_change = None
        self.token_24h_price_change = None
        self.token_liquidity = None
        self.token_on_dex = False
        self.token_on_pump = False
    
    async def fetch_tokenomics(self, session, ca, max_retries=3):
        # Clean the contract address
        ca = ca.strip().replace('`', '')
        print(f"\nFetching Dex Data for: {ca}")
        url = f"https://api.dexscreener.com/latest/dex/search?q={ca}"
        print(f"Request URL: {url}")

        for attempt in range(max_retries):
            try:
                async with session.get(url) as response:
                    print(f"Response status: {response.status}")
                    if response.status != 200:
                        print(f"[ERROR] Attempt {attempt + 1}/{max_retries}")
                        if attempt < max_retries - 1:
                            print(f"Retrying in 60 seconds... ")
                            await asyncio.sleep(60)
                            continue
                        return
                    
                    json_data = await response.json()
                    #print(f"Raw API response: {json_data}")  # Debug print
                    
                    if not json_data:
                        print("json_data is empty")
                        continue
                        
                    if 'pairs' not in json_data:
                        print("'pairs' not in json_data")
                        continue
                        
                    if not json_data['pairs']:
                        print("json_data['pairs'] is empty")
                        continue

                    #print(f"Found {len(json_data['pairs'])} pairs")
                    self.token_on_dex = True

                    for pair in json_data['pairs']:
                        print(f"Processing pair: {pair.get('pairAddress', 'unknown')}")
                        try:
                            self.token_fdv = float(pair.get('fdv', 0))
                            print(f"- Market Cap: ${self.token_fdv:,.2f}")

                            # Volume data
                            volume_data = pair.get('volume', {})
                            self.token_5m_vol = float(volume_data.get('m5', 0))
                            self.token_1h_vol = float(volume_data.get('h1', 0))
                            self.token_6h_vol = float(volume_data.get('h6', 0))
                            self.token_24h_vol = float(volume_data.get('h24', 0))
                            print(f"- Volume Data Retrieved")
                            print(f"  - 5m: ${self.token_5m_vol:,.2f}")
                            print(f"  - 1h: ${self.token_1h_vol:,.2f}")
                            print(f"  - 6h: ${self.token_6h_vol:,.2f}")
                            print(f"  - 24h: ${self.token_24h_vol:,.2f}")

                            # Transaction data
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
                            print("- Transaction Data Retrieved")
                            print(f"  - 5m: {self.token_5m_buys} buys, {self.token_5m_sells} sells")
                            print(f"  - 1h: {self.token_1h_buys} buys, {self.token_1h_sells} sells")
                            print(f"  - 24h: {self.token_24h_buys} buys, {self.token_24h_sells} sells")

                            # Price changes
                            price_data = pair.get('priceChange', {})
                            self.token_5m_price_change = price_data.get('m5', 0)
                            self.token_1h_price_change = price_data.get('h1', 0) 
                            self.token_24h_price_change = price_data.get('h24', 0)
                            print("- Price Change Data Retrieved")
                            print(f"  - 5m: {self.token_5m_price_change}%")
                            print(f"  - 1h: {self.token_1h_price_change}%")
                            print(f"  - 24h: {self.token_24h_price_change}%")
                            
                            # Liquidity
                            liquidity_data = pair.get('liquidity', {})
                            self.token_liquidity = float(liquidity_data.get('usd', 0))
                            print(f"- Liquidity: ${self.token_liquidity:,.2f}")
                            
                            return  # Return after successful processing

                        except Exception as e:
                            print(f"Error processing pair data: {str(e)}")
                            print(f"Error type: {type(e)}")
                            import traceback
                            traceback.print_exc()
                            continue

                    print("No valid pairs processed")
                    return

            except aiohttp.ClientError as e:
                print(f"Network error: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(60)
                    continue
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                print(f"Error type: {type(e)}")
                import traceback
                traceback.print_exc()
                if attempt < max_retries - 1:
                    await asyncio.sleep(60)
                    continue

async def main():
    scraper = ADScraper()
    async with aiohttp.ClientSession() as session:
        tasks = [
            scraper.fetch_ma_messages(session, MA_CHANNEL_ID, 'Multi-Alert Channel'),
            scraper.fetch_2x_channel(session, TWOX_CHANNEL_ID, 'Two-x Channel')
        ]
        try:
            await asyncio.gather(*tasks)  # Remove await from inside the list
        except Exception as e:
            print(f"Error: {str(e)}")
            await asyncio.sleep(5)
if __name__ == "__main__":
    asyncio.run(main())
