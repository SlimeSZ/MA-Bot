import asyncio
import aiohttp
from DexTwo import DexTwo
import statistics
from env import TOKEN, REVIVAL_WEBHOOK
from datetime import datetime, timedelta

class TokenRevivalMonitor:
    def __init__(self):
        self.dex = DexTwo()
        self.revival_webhook = "https://discord.com/api/webhooks/1320785724714254466/vogQV02tbX4xo5ldYmDZnwrnaYbNgZLkOGNi5g170ileo5rFzwz7Mowd1QaRw3YTXw0c"
        self.monitoring_tasks = {}
        self.token_data = {}
        self.interval_times = [1, 3, 5, 7]  # Even shorter intervals
        self.scanning_interval = 20  # 30 seconds
        self.scanning_duration = 5  # 5 minutes total
        #self.interval_times = [1, 3, 5, 7, 10, 13, 16, 19]
        #self.scanning_interval = 1 #15
        #self.scanning_duration = 10 #60
        self.dip_threshold = 10
        self.pump_threshold = 10
        self.last_message_ids = {}
        
    async def start_revival_monitoring(self, session, ca, token_name):
        if ca not in self.monitoring_tasks:
            print(f"\nStarting revival monitoring for {token_name} ({ca})")
            task = asyncio.create_task(self.monitor_token_revival(session, ca, token_name))
            self.monitoring_tasks[ca] = task
            
    async def calculate_baseline_mc(self, session, ca, token_name):
        print(f"\nCalculating baseline MC for {token_name}")
        samples = []
        
        for minutes in self.interval_times:
            try:
                await asyncio.sleep(minutes * 5)
                await self.dex.fetch_mc(session, ca)
                current_mc = self.dex.token_fdv
                
                if current_mc and current_mc > 0:
                    samples.append(current_mc)
                    print(f"Sample at {minutes}min: ${current_mc:,.2f}")
                    
            except Exception as e:
                print(f"Error sampling MC at {minutes}min: {e}")
                
        if not samples:
            print("No valid samples collected")
            return None
            
        weights = list(range(1, len(samples) + 1))
        weighted_avg = sum(s * w for s, w in zip(samples, weights)) / sum(weights)
        
        trimmed_mean = statistics.mean(sorted(samples)[1:-1]) if len(samples) > 4 else statistics.mean(samples)
        
        baseline = (weighted_avg + trimmed_mean) / 2
        print(f"Calculated baseline MC: ${baseline:,.2f}")
        return baseline
        
    async def monitor_token_revival(self, session, ca, token_name):
        try:
            baseline_mc = await self.calculate_baseline_mc(session, ca, token_name)
            if not baseline_mc:
                print(f"Could not establish baseline for {token_name}")
                return
                
            self.token_data[ca] = {
                'baseline_mc': baseline_mc,
                'monitoring_active': True,
                'revival_detected': False
            }
            
            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=self.scanning_duration)
            
            while datetime.now() < end_time:
                try:
                    await asyncio.sleep(self.scanning_interval * 30)
                    await self.dex.fetch_mc(session, ca)
                    current_mc = self.dex.token_fdv
                    
                    if not current_mc:
                        continue
                        
                    baseline = self.token_data[ca]['baseline_mc']
                    pct_from_baseline = ((current_mc - baseline) / baseline) * 100
                    
                    print(f"\nToken: {token_name}")
                    print(f"Current MC: ${current_mc:,.2f}")
                    print(f"Baseline MC: ${baseline:,.2f}")
                    print(f"Change from baseline: {pct_from_baseline:.2f}%")
                    print(f"Monitoring status - Active: {self.token_data[ca]['monitoring_active']}, Revival: {self.token_data[ca]['revival_detected']}")
                    
                    if pct_from_baseline <= -self.dip_threshold:
                        print(f"Significant dip detected: {pct_from_baseline:.2f}%")
                        self.token_data[ca]['monitoring_active'] = True
                        
                    elif self.token_data[ca]['monitoring_active']:
                        if pct_from_baseline >= self.pump_threshold:
                            print("Revival detected!")
                            if not self.token_data[ca]['revival_detected']:
                                await self.send_revival_alert(session, ca, token_name, baseline, current_mc, pct_from_baseline)
                                self.token_data[ca]['revival_detected'] = True
                                
                except Exception as e:
                    print(f"Error in revival monitoring loop: {e}")
                    await asyncio.sleep(30)
                    
        except Exception as e:
            print(f"Fatal error in revival monitoring for {token_name}: {e}")
        finally:
            if ca in self.monitoring_tasks:
                del self.monitoring_tasks[ca]
                
    async def send_revival_alert(self, session, ca, token_name, baseline_mc, current_mc, percent_change):
        try:
            data = {
                "username": "Token Revival Alert",
                "embeds": [{
                    "title": "🔄 Token Revival Detected! 📈",
                    "description": f"Token `{token_name}` has shown revival activity!",
                    "fields": [
                        {
                            "name": "Contract Address",
                            "value": f"`{ca}`",
                            "inline": False
                        },
                        {
                            "name": "Baseline Market Cap",
                            "value": f"${baseline_mc:,.2f}",
                            "inline": True
                        },
                        {
                            "name": "Current Market Cap",
                            "value": f"${current_mc:,.2f}",
                            "inline": True
                        },
                        {
                            "name": "Percentage Increase",
                            "value": f"{percent_change:.2f}%",
                            "inline": True
                        }
                    ],
                    "color": 0x00ff00
                }]
            }
            
            async with session.post(self.revival_webhook, json=data) as response:
                if response.status == 204:
                    print(f"Revival alert sent successfully for {token_name}!")
                else:
                    print(f"Failed to send revival alert: {response.status}")
                    
        except Exception as e:
            print(f"Error sending revival alert: {e}")

class ScrapeMultiAlerts:
    def __init__(self):
        self.url = "https://discord.com/api/v10/channels/{}/messages"
        self.revival_monitor = TokenRevivalMonitor()
        self.revival_webhook = REVIVAL_WEBHOOK
        
    async def fetch_multi_alert(self, session, channel_id, channel_name):
        headers = {'authorization': TOKEN}

        processed_messages = set()
        url = self.url.format(channel_id)
        print(f"\nStarting to monitor channel: {channel_name}")
        
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
                                await self.process_multi_alerts(session, latest_message, channel_name)
                    else:
                        print(f"[ERROR] Failed to fetch messages from {channel_name}: Status {response.status}")
                await asyncio.sleep(5)

            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)

    async def process_multi_alerts(self, session, message, channel_name):
        try:
            embeds = message.get('embeds', [])
            if not embeds:
                return
            
            embed = embeds[0]
            fields = embed.get('fields', [])
            
            ca = None
            token_name = None
            
            for field in fields:
                name = field.get('name', '').strip().lower()
                value = field.get('value', '').strip()
                
                if name == 'ca':
                    ca = value.strip('`')
                    # In process_multi_alerts
                    if not ca or ca == "" or len(ca) < 10:  # Basic validation
                        print("Invalid CA format, skipping...")
                        return
                elif name == 'token name':
                    token_name = value.strip().replace('\x00', '')  # Remove null bytes
                    if not token_name:
                        token_name = "Unknown Token"
                    
            if ca and token_name:
                await self.revival_monitor.start_revival_monitoring(session, ca, token_name)
                
        except Exception as e:
            print(f"[ERROR] Error Processing MA BOT Messages: {str(e)}")

class Main:
    def __init__(self):
        self.bot = ScrapeMultiAlerts()
        
    async def run_bot(self):
        async with aiohttp.ClientSession() as session:
            # In Main.run_bot
            print("Starting Revival Monitor Bot...")
            tasks = [
                self.bot.fetch_multi_alert(session, '1298438610663768154', 'Multi Alert Bot')
            ]
            await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        main = Main()
        asyncio.run(main.run_bot())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Fatal error: {e}")