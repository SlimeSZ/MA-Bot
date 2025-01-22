import asyncio
import aiohttp
import requests
import json
from typing import Dict, Any, Tuple

class MarketcapFetcher:
    def __init__(self, rpc_endpoint: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_endpoint = rpc_endpoint
        self.gecko_base_url = "https://api.geckoterminal.com/api/v2/simple/networks"
    
    async def get_token_supply(self, ca: str) -> float:
        payload = {
            "jsonrpc": "2.0", 
            "id": 1,
            "method": "getTokenSupply",
            "params": [ca]
            }
        
        try:
            response = requests.post(
                self.rpc_endpoint,
                json=payload,
                headers = {"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()

            if 'result' in data and 'value' in data['result']:
                data_supply = float(data['result']['value']['amount'])
                data_decimals = int(data['result']['value']['decimals'])
                supply = data_supply / (10 ** data_decimals)
                return supply
            else:
                raise ValueError("Supply data not found in rpc request")

        except (requests.RequestException, ValueError) as e:
            print(F"Error fetching token supply from Solana rpc: {e}")
            raise

    async def get_token_price(self, ca: str) -> float:
        url = f'{self.gecko_base_url}/solana/token_price/{ca}'
        try:
            response = requests.get(url, headers={'accept': 'application/json'})
            response.raise_for_status()
            data = response.json()

            if 'data' in data and 'attributes' in data['data']:
                return float(data['data']['attributes']['token_prices'][ca]) 
            else:
                raise ValueError("Price data not found in gecko response")
        except (requests.RequestException, ValueError) as e:
            print(f"Fatal error fetching gecko token price data: {e}")
            raise

    async def calculate_marketcap(self, ca: str) -> Dict[str, Any]:
        try:
            supply = await self.get_token_supply(ca)
            price = await self.get_token_price(ca)
            mc = price * supply
            print(f"MC: {mc}")

            return mc
        except Exception as e:
            print(F"Error calculating fetching data: {e}")
            raise
