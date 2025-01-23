from telethon import TelegramClient
import asyncio

api_id = API_ID_HERE
api_hash = 'API_HASH_HERE'
client = TelegramClient('anon', api_id, api_hash)

class SoulScannerBot:
   async def send_and_receive_message(self, ca):
       await client.start()
       await client.send_message('soul_scanner_bot', ca)
       await asyncio.sleep(5) # Increased wait time
   
       messages = await client.get_messages('soul_scanner_bot', limit=1)
       if not messages:
           return False
       return await self.process_message(ca, messages[0])

   async def process_message(self, ca, message):
       try:
           if not message.message:
               return False
               
           lines = message.message.split('\n')
           scans = int([line for line in lines if "⚡ Scans:" in line][0].split("Scans: ")[1].split(" |")[0])
           fresh = int([line for line in lines if "First 20:" in line][0].split("First 20: ")[1].split(" Fresh")[0])
           
           passes = scans >= 50 and fresh <= 5
           print(f"SoulScanner Results - Scans: {scans}, Fresh: {fresh}, Passes: {passes}")
           return passes
           
       except Exception as e:
           print(f"Error processing SoulScanner: {e}")
           return False

class BundleBot:
   async def send_and_receive_message(self, ca):
       await client.start()
       await client.send_message('TrenchScannerBot', ca)
       await asyncio.sleep(20) # Increased wait time

       messages = await client.get_messages('TrenchScannerBot', limit=1)
       if not messages:
           return None
       return await self.process_message(messages[0])

   async def process_message(self, message):
       try:
           if not message.message:
               return None
               
           lines = message.message.split('\n')
           bundle_line = [line for line in lines if "Total Bundles:" in line][0]
           
           # More robust parsing
           holding = int(bundle_line.split("Total Bundles:")[1].strip().split(" ")[0])
           total = int(bundle_line.split("/")[1].strip().split(" ")[0])
           
           holding_percentage = (holding / total * 100) if total > 0 else 0
           passes = holding_percentage < 30
           
           result = {
               'holding_percentage': holding_percentage,
               'passes_criteria': passes,
               'holding': holding,
               'total': total
           }
           
           print(f"Bundle Results - {result}")
           return result
           
       except Exception as e:
           print(f"Error processing Bundle Bot: {str(e)}")
           return None

async def main(ca=None):
    if not ca:
        return
    
    ssbot = SoulScannerBot()
    bndlebot = BundleBot()
    
    passes_soul = await ssbot.send_and_receive_message(ca)
    if passes_soul:
        bundle_result = await bndlebot.send_and_receive_message(ca)
        return bundle_result
    return None
