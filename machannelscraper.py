import requests
import asyncio
import aiohttp
import re
import time
from datetime import datetime
import os
from env import TOKEN
from TGScraper import main as telegram_main
class ADScraper:
    def __init__(self):
        self.url = "https://discord.com/api/v10/channels/{}/messages"
        self.last_message_ids = {}
        self.processed_messages = set()        
        self.reset_values()

    def reset_values(self):
        self.ca = None


    def normalize(self, ca: str) -> str:
        return ca.strip().lower().replace('`', '')
        
            
    async def fetch_ma_messages(self, session, channel_id, channel_name):
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
                if token_fields == "ca":
                    ca = self.normalize(field.get('value', ''))
                    if ca:
                        await telegram_main(ca)
        except Exception as e:
            print(str(e))
