import os
import sys
import asyncio
import logging

# Ensure the root ALICE directory is in the Python path
# This prevents "ModuleNotFoundError" when modules try to import each other
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.orchestrator import AliceOrchestrator

# Configure the global logging format for the entire application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)

ASCII_BANNER = """
   ___    __    _____ __________
  /   |  / /   /  _/ ____/ ____/
 / /| | / /    / // /   / __/   
/ ___ |/ /____/ // /___/ /___   
/_/  |_/_____/___/\\____/_____/  

System Version: 1.0.0
Initializing Cognitive Architecture...
"""

async def shutdown(alice_instance):
    """Gracefully shuts down all background tasks and Websockets."""
    logging.info("\n[System] Shutdown signal received. Closing neural pathways...")
    # If you added a specific stop() method to your orchestrator, call it here
    # await alice_instance.stop()
    
    # Cancel all running async tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    await asyncio.gather(*tasks, return_exceptions=True)
    logging.info("[System] ALICE successfully deactivated. Goodbye.")

async def run_app():
    print(ASCII_BANNER)
    # Instantiate the Central Nervous System
    alice = AliceOrchestrator()
    try:
        # Ignite the main execution loop
        await alice.run()
    except KeyboardInterrupt:
        # Catch Ctrl+C and await the shutdown coroutine
        await shutdown(alice)



if __name__ == "__main__":
    asyncio.run(run_app())