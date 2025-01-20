# flaggedtoken.py


from datetime import datetime
from typing import Dict, Tuple
import os
import re

class TokenTransactionTracker:
    def __init__(self):
        self.tracked_tokens: Dict[str, Dict] = {}
    
    def initialize_token(self, ca: str, token_name: str = "Unknown"):
        if ca not in self.tracked_tokens:
            self.tracked_tokens[ca] = {
                'name': token_name,
                'buys': [],
                'sells': [],
                'buy_count': 0,
                'sell_count': 0,
                'first_seen': datetime.now()
            }
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Flagged: {token_name} ({ca[:8]}...)")
    
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

        if is_buy:
            token_data['buys'].append({
                'amount': amount,
                'channel': channel,
                'timestamp': datetime.now(),
                'description': tx_description
            })
            token_data['buy_count'] += 1
        else:
            token_data['sells'].append({
                'amount': amount,
                'channel': channel,
                'timestamp': datetime.now(),
                'description': tx_description
            })
            token_data['sell_count'] += 1

        await self.display_stats(ca)

    async def display_stats(self, ca: str):
        if ca not in self.tracked_tokens:
            return
        
        token = self.tracked_tokens[ca]
        os.system('cls' if os.name == 'nt' else 'clear')
        
        tracking_duration = datetime.now() - token['first_seen']
        hours = tracking_duration.total_seconds() / 3600

        print(f"\n=== Token Transaction Tracker ===")
        print(f"Token: {token['name']}")
        print(f"Contract: {ca}")
        print(f"Tracking Duration: {tracking_duration.seconds // 3600}h {(tracking_duration.seconds % 3600) // 60}m")
        print("\nTransaction Summary:")
        print(f"Total Buys: {token['buy_count']}")
        print(f"Total Sells: {token['sell_count']}")
        
        if hours > 0:
            print(f"\nHourly Rates:")
            print(f"Buy Rate: {token['buy_count'] / hours:.1f} trades/hour")
            print(f"Sell Rate: {token['sell_count'] / hours:.1f} trades/hour")
        
        print("\nRecent Transactions:")
        all_txs = ([(tx, True) for tx in token['buys']] + 
                  [(tx, False) for tx in token['sells']])
        all_txs.sort(key=lambda x: x[0]['timestamp'], reverse=True)
        
        for tx, is_buy in all_txs[:10]:
            tx_type = "BUY " if is_buy else "SELL"
            timestamp = tx['timestamp'].strftime('%H:%M:%S')
            print(f"{timestamp} | {tx_type} | {tx['amount']:.2f} SOL | {tx['channel']}")

    def stop_tracking(self, ca: str):
        if ca in self.tracked_tokens:
            del self.tracked_tokens[ca]
            print(f"\nStopped tracking {ca}")

# Global instance that can be imported by other files
tracker = TokenTransactionTracker()