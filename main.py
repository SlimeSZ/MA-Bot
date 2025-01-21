# main.py
import asyncio
from MAbot import Main as BotMain
from flaggedtoken import TokenTransactionTracker

async def run_interface(scraper):
    while True:
        print("\n🎮 Token Tracker Commands:")
        print("1️⃣ Start tracking token")
        print("2️⃣ Stop tracking token")
        print("3️⃣ List tracked tokens")
        print("4️⃣ Exit")
        
        choice = input("\n📥 Enter your choice (1-4): ")
        
        if choice == "1":
            ca = input("🔑 Enter token CA: ")
            token_name = input(f"📝 Enter token name: ")
            await scraper.flag_token_for_tracking(ca)
            print(f"\n✅ Started tracking {token_name}")
            
        elif choice == "2":
            ca = input("🔑 Enter token CA to stop tracking: ")
            await scraper.stop_tracking_token(ca)
            
        elif choice == "3":
            await scraper.list_tracked_tokens()
            
        elif choice == "4":
            print("👋 Exiting...")
            break
            
        else:
            print("❌ Invalid choice. Please try again.")
        
        await asyncio.sleep(1)

async def main():
    # Initialize the bot
    bot = BotMain()
    
    # Create tasks for both the bot and interface
    bot_task = asyncio.create_task(bot.run_bot())
    interface_task = asyncio.create_task(run_interface(bot.scraper))
    
    try:
        # Run both tasks concurrently
        await asyncio.gather(bot_task, interface_task)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    asyncio.run(main())