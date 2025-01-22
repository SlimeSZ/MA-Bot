import asyncio
import aiohttp
from datetime import datetime, timedelta
import statistics

from MAbot import DexScreenerAPI
from marketcap import MarketcapFetcher
from machannelscraper import ADScraper

class TokenMonitor:
    def __init__(self):
        self.dex = DexScreenerAPI()
        self.mc_rpc = MarketcapFetcher()
        self.ma_channel = ADScraper()

        self.monitoring_tasks = {}
        self.last_message_ids = {}

        self.all_cas = {}

        self.initial_marketcaps = {}

        self.hundredk_range = range(100000, 200000)
        self.hundredk_range_tokens = {}
        self.hundredk_token_time = 600

        self.twohundredk_range = range(200001, 350000)
        self.twohundredk_range_tokens = {}
        self.twohundredk_token_time = None

        self.dead_tokens = {}
        self.dead_token_threshold_to_break = 100000

        self.token_revivals = {}

        self.base_line_intervals = [1, 3, 5, 7, 10, 15]
        self.baseline_token_data = {}
        self.baseline_scanning_duration = 20
        self.dip_threshold = 50
        self.pump_threshold = 50

        self.token_significant_mc_increase_webhook_url = ""


    
    async def store_multialerts(self):
        pass #this functionality will be performed in machannelscraper.py

    async def fetch_token_marketcap(self, ca: str) -> float:
        marketcap = self.mc_rpc.calculate_marketcap(ca)
        
        #conditions go here
        if marketcap in range(self.hundredk_range):
            await self.store_as_100k_mc_range(ca)

    


    #for any multi-alert, store initial marketcap using sol rpc file
    #scan for mc increases over 5 min intervals up to 2hrs
    async def notify_significant_marketcap_increase(self, ca: str):
        initial_marketcap = self.mc_rpc.calculate_marketcap(ca)
        self.initial_marketcaps[ca] = {
            'marketcap': initial_marketcap,
            'timestamp': datetime.now(),
            'alerts_sent': set()
        }
        current_time = datetime.now()

        time_intervals = {5, 10, 15, 20, 25, 30, 35, 40, 45, 60, 80, 100, 119}

        for token_ca, data in self.initial_marketcaps.items():
            time_difference = (current_time - data['timestamp']).total_seconds() / 60
            current_marketcap = self.mc_rpc.calculate_marketcap(token_ca)

            percentage_increase =   ((current_marketcap - data['marketcap']) / data['marketcap']) * 100

            if percentage_increase >= 300 and '300' not in data['alerts_sent']:
                await self.token_significant_mc_increase_webhook(
                    token_ca, initial_marketcap, data['marketcap'], percentage_increase
                    )
            elif percentage_increase >= 200 and '200' not in data['alerts_sent']:
                data['alerts_sent'].add('200')
                await self.token_significant_mc_increase_webhook(
                    token_ca, initial_marketcap, data['marketcap'], percentage_increase
                    )
            elif percentage_increase >= 100 and '100' not in data['alerts_sent']:
                data['alerts_sent'].add('100')
                await self.token_significant_mc_increase_webhook(
                    token_ca, initial_marketcap, data['marketcap'], percentage_increase
                    )

            if time_difference >= 120:
                self.initial_marketcaps.pop(token_ca, None)

            

#only if token remains in 100-200k range for >= 10 min, send alert or else add it to dead_tokens
#if from dead_tokens it gains momentum again, send an alert for revival
#
    async def store_as_100k_mc_range(self, ca: str, marketcap):
        if ca not in self.hundredk_range_tokens:
            self.hundredk_range_tokens[ca] = datetime.now()
            
        current_time = datetime.now()
        tokens_to_remove = []
        
        for token_ca, time_added in self.hundredk_range_tokens.items():
            time_difference = (current_time - time_added).total_seconds()
            if time_difference >= self.hundredk_token_time:
                current_mc = self.mc_rpc.calculate_marketcap(ca)
                await self.hundredk_range_webhook(ca, current_mc)
                print(f"Token {token_ca} remainded in 100 - 200k Marketcap range for {time_difference} minutes")
            else:
                if token_ca not in range(self.hundredk_range):
                    tokens_to_remove.append(token_ca)
        
        for token_ca in tokens_to_remove:
            self.hundredk_range_tokens.pop(token_ca)
            self.dead_tokens[ca] = datetime.now()

    async def store_as_250k_range(self, ca: str):
        if ca not in self.twohundredk_range_tokens:
            self.twohundredk_range_tokens[ca] = datetime.now()

        current_time = datetime.now()
        tokens_to_remove = []

        for token_ca, time_added in self.twohundredk_range_tokens.items():
            time_difference = (current_time - time_added).total_seconds()
            if time_difference >= self.twohundredk_token_time:
                current_mc = self.mc_rpc.calculate_marketcap(ca)
                await self.twohundredk_range_webhook(ca, current_mc)
                print(f"Token {token_ca} remainded in 200 - 350k Marketcap range for {time_difference} minutes")
            else:
                if token_ca not in range(self.twohundredk_range):
                    tokens_to_remove.append(token_ca)
            for token_ca in tokens_to_remove:
                self.twohundredk_range_tokens.pop(token_ca)

    #if a deadtoken breaks into that 100-200k threshold again, send an alert for revival
    async def scan_dead_tokens(self, ca: str):
        while True:
            current_time = datetime.now()
            tokens_to_remove = []

            for token_ca, time_added in self.dead_tokens.items():
                time_difference = (current_time - time_added).to_seconds() / 60
                current_dead_marketcap = self.mc_rpc.calculate_marketcap(ca)

                if current_dead_marketcap >= 100000:
                    self.token_revivals[token_ca] = datetime.now()
                    current_mc = self.mc_rpc.calculate_marketcap(ca)
                    await self.store_as_100k_mc_range(token_ca)
                    await self.dead_token_revival_webhook(token_ca, current_mc)
                    tokens_to_remove.append(token_ca)
                elif time_difference >= 30:
                    tokens_to_remove.append(token_ca)

            for token_ca in tokens_to_remove:
                self.dead_tokens.pop(token_ca, None)
            
            await asyncio.sleep(300)


#base line component for general revivals and momentum detection
    async def calculate_baseline(self, ca: str):
        samples = []
        
        for minutes in self.base_line_intervals:
            try:
                await asyncio.sleep(minutes * 5) #whats * 5 do?
                current_mc = await self.mc_rpc.calculate_marketcap(ca)
                if current_mc and current_mc > 0:
                    samples.append(current_mc)
            except Exception as e:
                print(f"Error sampling mc for: {ca}\n{str(e)}")

        
        if not samples:
            return None, None, None
        
        weights = list(range(1, len(samples) + 1))
        weighted_avg = sum(s * w for s, w in zip(samples, weights)) / sum(weights)
        trimmed_mean = statistics.mean(sorted(samples)[1:-1]) if len(samples) > 4 else statistics.mean(samples)
        baseline = (weighted_avg + trimmed_mean) / 2

        return weighted_avg, trimmed_mean, baseline

    async def detect_momentum(self, ca: str):
        try:
            baseline_mc = await self.calculate_baseline(ca)
            if not baseline_mc:
                return
            
            self.baseline_token_data[ca] = {
                'baseline_mc': baseline_mc,
                'monitoring_active': True,
                'momentum_detected': False,
                'dip_mc': None,
                'pump_mc': None
            }

            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=self.baseline_scanning_duration)
            while datetime.now() < end_time:
                try:
                    await asyncio.sleep(600) #??
                    current_mc = await self.mc_rpc.calculate_marketcap(ca)
                    if not current_mc:
                        continue

                    baseline = self.baseline_token_data[ca]['baseline_mc']
                    pct_from_baseline = ((current_mc - baseline) / baseline) * 100 #??

                    if pct_from_baseline <= -self.dip_threshold:
                        self.baseline_token_data[ca]['monitoring_active'] = True
                        self.baseline_token_data[ca]['dip_mc'] = current_mc
                    elif self.baseline_token_data[ca]['monitoring_active']:
                        if pct_from_baseline >= self.pump_threshold:
                            self.baseline_token_data[ca]['pump_mc'] = current_mc
                            weighted_avg, trimmed_mean = await self.calculate_baseline(ca)
                            await self.baseline_revival_webhook(
                                ca=ca, 
                                weighted_avg=weighted_avg, 
                                trimmed_mean=trimmed_mean, 
                                baseline_mc=baseline_mc, 
                                current_mc=current_mc,
                                dip_mc=self.baseline_token_data[ca]['dip_mean'],
                                pump_mc=self.baseline_token_data[ca]['pump_mean']
                                )
                            self.baseline_token_data[ca]['revival_detected'] = True
                except Exception as e:
                    print(F'Error in baseline/revival detection: {e}')
                    await asyncio.sleep(30)
        except Exception as e:
            print(f"Fatal error monitoring baseline calculations for: {ca}")
        finally:
            if ca in self.monitoring_tasks:
                del self.monitoring_tasks[ca]



    #webhooks
    async def token_significant_mc_increase_webhook(self, ca, initial_mc, new_mc, percentage_increase):
        try:
            data = {
                "username": "Significant Marketcap Increase Since Alert For:",
                "embeds": [{
                    "fields": [{
                        "name": "CA",
                        "value": ca,
                        "inline": False
                    },
                    {
                        "name": "Initial Marketcap",
                        "value": initial_mc,
                        "inline": False
                    },
                    {
                        "name": "New Marketcap",
                        "value": new_mc,
                        "inline": False
                    },
                    {
                        "name": "% Increase",
                        "value": percentage_increase,
                        "inline": False
                    }
                    ]
                }]
            }
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(self.token_significant_mc_increase_webhook, json=data) as response:
                        if response.status == 204:
                            print(f"Successfully sent token significant mc increase webhook")
                        else:
                            print(f"Failed to send webhook")
                except Exception as e:
                    print(f"Error sending webhook: {str(e)}")        
        except Exception as e:
            print(f"Error sending significant mc increase webhook: {e}")


    async def hundredk_range_webhook(self, ca, marketcap):
        try:
            data = {
                "username": "Token Showing Stability in 100k - 200k Marketcap Range",
                "embeds": [{
                    "fields": [{
                        "name": "CA",
                        "value": ca,
                        "inline": False
                    },
                    {
                        "name": "Marketcap",
                        "value": marketcap,
                        "inline": False
                    }
                    ]
                }]
            }
            async with aiohttp #CREATE AND USE SAME SESSION
        except Exception as e:
            print(f"Failed to send 100k range webhook alert: {str(e)}")

    async def twohundredk_range_webhook(self, ca, marketcap):
        try:
            data = {
                "username": "Token Showing Stability in 200k - 350k Marketcap Range",
                "embeds": [{
                    "fields": [{
                        "name": "CA",
                        "value": ca,
                        "inline": False
                    },
                    {
                        "name": "Marketcap",
                        "value": marketcap,
                        "inline": False
                    }
                    ]
                }]
            }
            async with aiohttp #CREATE AND USE SAME SESSION
        except Exception as e:
            print(f"Failed to send 200k range webhook alert: {str(e)}")


    async def dead_token_revival_webhook(self, ca, marketcap):
        try:
            data = {
                "username": "Dead Token Revival",
                "title": "Token that dropped under 100k MC Range within 10 minutes showing signs of activity",
                "embeds": [{
                    "fields": [{
                        "name": "CA",
                        "value": ca,
                        "inline": False
                    },
                    {
                        "name": "Current Marketcap",
                        "value": marketcap,
                        "inline": False
                    }
                    ]
                }]
            }
            async with aiohttp #CREATE AND USE SAME SESSION
        except Exception as e:
            print(f"Failed to send Dead token revival webhook alert: {str(e)}")


    async def baseline_revival_webhook(self, ca, weighted_avg, trim_mean, baseline_mc, current_mc, dip_mc, pump_mc):
        try:
            data = {
                "username": "Baseline Revival Detected",
                "title": "Token that stayed within {} Marketcap Range for x minutes has Pumped ",
                "embeds": [{
                    "fields": [{
                        "name": "CA",
                        "value": ca,
                        "inline": False
                    },
                    {
                        "name": "Current Marketcap",
                        "value": current_mc,
                        "inline": False
                    },
                    {
                        "name": "Baseline Marketcap",
                        "value": baseline_mc,
                        "inline": False
                    },
                    {
                        "name": "Marketcap Dipped to:",
                        "value": dip_mc,
                        "inline": False
                    },
                    {
                        "name": "Marketcap has now Pumped to:",
                        "value": pump_mc,
                        "inline": False
                    },
                    {   
                        "name": "Weighted Average",
                        "value": weighted_avg,
                        "inline": False
                    },
                    {
                        "name": "Trim Mean",
                        "value": trim_mean,
                        "inline": False
                    }
                    ]
                }]
            }
            async with aiohttp #CREATE AND USE SAME SESSION
        except Exception as e:
            print(f"Failed to send 200k range webhook alert: {str(e)}")


