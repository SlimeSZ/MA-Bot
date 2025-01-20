import requests
import json
from typing import Dict, Any, Tuple

class SolanaTokenAnalyzer:
    def __init__(self, rpc_endpoint: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_endpoint = rpc_endpoint
        self.gecko_base_url = "https://api.geckoterminal.com/api/v2/simple/networks"

    def get_token_price(self, token_address: str) -> float:
        """Fetch token price from GeckoTerminal."""
        url = f'{self.gecko_base_url}/solana/token_price/{token_address}'
        
        try:
            response = requests.get(url, headers={'accept': 'application/json'})
            response.raise_for_status()
            data = response.json()
            
            # Extract the price from the response
            if 'data' in data and 'attributes' in data['data']:
                return float(data['data']['attributes']['token_prices'][token_address])
            raise ValueError("Price data not found in response")
            
        except (requests.RequestException, ValueError) as e:
            print(f"Error fetching token price: {e}")
            raise

    def get_token_supply(self, token_address: str) -> float:
        """Fetch token supply using Solana RPC."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenSupply",
            "params": [token_address]
        }
        
        try:
            response = requests.post(
                self.rpc_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            
            if 'result' in data and 'value' in data['result']:
                supply = float(data['result']['value']['amount'])
                decimals = int(data['result']['value']['decimals'])
                # Adjust supply based on decimals
                actual_supply = supply / (10 ** decimals)
                return actual_supply
            
            raise ValueError("Supply data not found in response")
            
        except (requests.RequestException, ValueError) as e:
            print(f"Error fetching token supply: {e}")
            raise

    def calculate_market_cap(self, token_address: str) -> Dict[str, Any]:
        """Calculate market cap by fetching price and supply."""
        try:
            price = self.get_token_price(token_address)
            supply = self.get_token_supply(token_address)
            market_cap = price * supply
            
            return {
                "token_address": token_address,
                "price": price,
                "total_supply": supply,
                "market_cap": market_cap,
                "success": True
            }
            
        except Exception as e:
            return {
                "token_address": token_address,
                "error": str(e),
                "success": False
            }

# Example usage
if __name__ == "__main__":
    # Initialize the analyzer
    analyzer = SolanaTokenAnalyzer()
    
    # Token address to analyze
    token_address = "TOKEN_ADDRESS"
    
    try:
        # Calculate market cap
        result = analyzer.calculate_market_cap(token_address)
        
        if result["success"]:
            print("\nToken Analysis Results:")
            print(f"Address: {result['token_address']}")
            print(f"Price: ${result['price']:.6f}")
            print(f"Total Supply: {result['total_supply']:,.2f}")
            print(f"Market Cap: ${result['market_cap']:,.2f}")
        else:
            print(f"Error: {result['error']}")
            
    except Exception as e:
        print(f"An error occurred: {e}")