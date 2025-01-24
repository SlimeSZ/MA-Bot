from telethon import TelegramClient
import asyncio
import aiohttp

#api id and api hash

class SoulScannerBot:
   async def send_and_receive_message(self, ca: str):
       await client.start()
       await client.send_message('soul_scanner_bot', ca)
       await asyncio.sleep(5) # Increased wait time
   
       messages = await client.get_messages('soul_scanner_bot', limit=1)
       if not messages:
           return False
       return await self.process_message(ca, messages[0])

   async def process_message(self, ca: str, message):
       try:
           if not message.message:
               return False
               
           lines = message.message.split('\n')

           scans = int([line for line in lines if "⚡ Scans:" in line][0].split("Scans: ")[1].split(" |")[0])
           fresh = int([line for line in lines if "First 20:" in line][0].split("First 20: ")[1].split(" Fresh")[0])
           sniper_percent = float([line for line in lines if "Snipers:" in line][0].split("•")[1].strip().split(" ")[0].replace('%', ''))
           
           passes = scans >= 50 and fresh <= 5 and sniper_percent < 50
           print(f"SoulScanner Results for CA: {ca}\n- Scans: {scans}, Fresh: {fresh}, Sniper %: {sniper_percent}, Pass? {passes}")
           return passes
           
       except Exception as e:
           print(f"Error processing SoulScanner: {e}")
           return False

class BundleBot:
    async def send_and_receive_message(self, ca: str):
       await client.start()
       await client.send_message('TrenchScannerBot', ca)
       await asyncio.sleep(13) # Increased wait time

       messages = await client.get_messages('TrenchScannerBot', limit=1)
       if not messages:
           return None

       
       return await self.process_message(messages[0], ca)
    
    async def process_message(self, message, ca: str):
        try:
            if not message.message:
                return None
                
            if "There was a server error" in message.message:
                print(f"Bundle bot down but soul scanner criteria met for: {ca}")
                await self.send_conditional_webhook(ca)
                return None
                
            lines = message.message.split('\n')
            percentage_lines = [line for line in lines if "Current Held Percentage:" in line]
            if not percentage_lines:
                print(f"Bundle bot down but soul scanner criteria met for: {ca}")
                await self.send_conditional_webhook(ca)
                return None

            percentage_line = percentage_lines[0]  # Now safe to index since we checked if list exists
            holding_percentage = float(percentage_line.split("Current Held Percentage:")[1].strip().replace('%', ''))
            passes = holding_percentage < 30           
            result = {
                'holding_percentage': holding_percentage,
                'passes_criteria': passes,
            }
            
            print(f"Bundle Bot Results:\n{result}")
            await self.send_full_webhook(ca)
            return result
            
        except Exception as e:
            print(f"Exception as {e}: Bundle bot down soul scanner criteria met for: {ca}")
            return None

    async def send_full_webhook(self, ca: str):
        try:
            normalized_ca = await self.normalize(ca)
            async with aiohttp.ClientSession() as session:
                await session.post(
                    BOT_WEBHOOK,
                    json={'content': f'Token Passed both Soul Scanner & Bundle Bot criteria\n{normalized_ca}'}  
                )
        except Exception as e:
            print(f"Error sending full soul_scanner & bundle_bot webhook:\n{str(e)}")
            
    async def normalize(self, ca: str) -> str:
    # Remove all whitespace and special characters
        clean_ca = ''.join(c for c in ca if c.isalnum() or c == 'p')  # Keeps only alphanumeric + 'p' for 'pump'
        return clean_ca.lower()

    async def send_conditional_webhook(self, ca: str):
        try:
            normalized_ca = await self.normalize(ca)
            async with aiohttp.ClientSession() as session:
                await session.post(
                    BOT_WEBHOOK,
                    json={'content': normalized_ca}
                )
        except Exception as e:
            print(f"Error sending webhook: {str(e)}")

#prod
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

#testing

"""
async def main():
    ca = 'HUgwkZF3uNUE8bfLownZjcHC8RgEwf2DSSMsRGp6pump'
    ssbot = SoulScannerBot()
    bndlebot = BundleBot()

    passes_soul = await ssbot.send_and_receive_message(ca)
    if passes_soul:
        bundle_result = await bndlebot.send_and_receive_message(ca)
        return bundle_result
    return None
if __name__ == "__main__":
    asyncio.run(main())
"""
