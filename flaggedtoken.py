from datetime import datetime
from typing import Dict, Tuple
import os
import re

class TokenTransactionTracker:
    def __init__(self):
        self.tracked_tokens: Dict[str, Dict] = {}
    
    def initialize_token(self, ca: str):
        if ca not in self.tracked_tokens:
            self.tracked_tokens[ca] = {
                'ca': ca,
                'buys': [],
                'sells': [],
                'buy_count': 0,
                'sell_count': 0,
                'first_seen': datetime.now()
            }
            print(f"\n🎯 [TRACKING STARTED] Now tracking ({ca[:8]}...)")
            print("Watching for transactions...")
    
    def extract_sol_amount(self, tx_description: str) -> Tuple[float, bool]:
        description = tx_description.lower()

        if description.split(" on ")[0].strip().endswith("sol"):
            return 0, False
        
        if "swapped" not in description:
            return 0, False
        
        if re.search(r'\sfor\s+[\d,.]+\s+sol\s', description):
            try:
                amount = float(re.search(r'\sfor\s+([\d,.]+)\s+sol\s', description).group(1))
                return amount, False
            except (AttributeError, ValueError):
                return 0, False
            
        parts = description.split()
        try:
            for i, word in enumerate(parts):
                if word == "swapped":
                    next_word = parts[i + 1]
                    if next_word.replace(".", "").isdigit() and parts[i + 2] == "sol":
                        return float(next_word), True
        except (IndexError, ValueError):
            pass
            
        return 0, False
    
    async def process_transaction(self, ca: str, tx_description: str, channel: str):
        if ca not in self.tracked_tokens:
            return
        
        amount, is_buy = self.extract_sol_amount(tx_description)
        if amount == 0:
            return
        
        token_data = self.tracked_tokens[ca]
        timestamp = datetime.now().strftime('%H:%M:%S')

        if is_buy:
            print(f"\n💚 [{timestamp}] BUY | {ca[:8]}... | {amount:.2f} SOL | {channel}")
            print(f"📝 {tx_description}")
            token_data['buys'].append({
                'amount': amount,
                'channel': channel,
                'timestamp': datetime.now(),
                'description': tx_description
            })
            token_data['buy_count'] += 1
        else:  # This is a sell
            print(f"\n❌ [{timestamp}] SELL | {ca[:8]}... | {amount:.2f} SOL | {channel}")
            print(f"📝 {tx_description}")
            token_data['sells'].append({
                'amount': amount,
                'channel': channel,
                'timestamp': datetime.now(),
                'description': tx_description
            })
            token_data['sell_count'] += 1

    async def display_stats(self, ca: str):
        if ca not in self.tracked_tokens:
            return
        
        token = self.tracked_tokens[ca]
        tracking_duration = datetime.now() - token['first_seen']
        hours = tracking_duration.total_seconds() / 3600

        print(f"\n📊 === Token Stats for {ca[:8]}... ===")
        print(f"⏰ Tracking Duration: {tracking_duration.seconds // 3600}h {(tracking_duration.seconds % 3600) // 60}m")
        print("\n📈 Transaction Summary:")
        print(f"💚 Total Buys: {token['buy_count']}")
        print(f"❌ Total Sells: {token['sell_count']}")
        
        if hours > 0:
            print(f"\n⚡ Hourly Rates:")
            print(f"💫 Buy Rate: {token['buy_count'] / hours:.1f} trades/hour")
            print(f"📉 Sell Rate: {token['sell_count'] / hours:.1f} trades/hour")

    def stop_tracking(self, ca: str):
        if ca in self.tracked_tokens:
            del self.tracked_tokens[ca]
            print(f"\n🛑 [STOPPED] No longer tracking {ca[:8]}...")

    async def list_tracked_tokens(self):
        if not self.tracked_tokens:
            print("\n❌ No tokens currently being tracked")
            return

        print("\n📋 Currently Tracked Tokens:")
        for ca, data in self.tracked_tokens.items():
            # First line shows CA and counts
            print(f"🔍 {ca[:8]}... | Buys: {data['buy_count']} | Sells: {data['sell_count']}")
            
            # Show buy amounts if any exist
            if data['buys']:
                for tx in sorted(data['buys'], key=lambda x: x['timestamp'], reverse=True)[:3]:
                    print(f"    💚 Bought: {tx['amount']:.2f} SOL - {tx['channel']}")
            
            # Show sell amounts if any exist
            if data['sells']:
                for tx in sorted(data['sells'], key=lambda x: x['timestamp'], reverse=True)[:3]:
                    print(f"    ❌ Sold: {tx['amount']:.2f} SOL - {tx['channel']}")
            
            print("")  # Add spacing between tokens

# Global instance that can be imported by other files
tracker = TokenTransactionTracker()