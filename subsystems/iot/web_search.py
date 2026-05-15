import asyncio
import logging
import asyncddgs as AsyncDDGS
from core.event_bus import EventBus

class WebSearchAgent:
    def __init__(self, bus: EventBus):
        self.bus = bus
        # Listen for the Brain requesting a web search
        self.bus.subscribe("TOOL_CALL_REQUESTED", self._execute_tool)

    async def get_available_tools(self) -> list:
        """
        Dynamically fetches the web search tool schema.
        Passed to the LLM during the System Prompt assembly.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Searches the internet for real-time information, news, weather, or facts you do not know.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The highly specific search query to look up."
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    async def _execute_tool(self, tool_data: dict):
        """Executes the action requested by the LLM."""
        function_name = tool_data.get("name")
        kwargs = tool_data.get("arguments", {})
        
        if function_name == "search_web":
            await self._perform_search(kwargs.get("query"))

    async def _perform_search(self, query: str):
        """Asynchronously scrapes DuckDuckGo for the top 3 results."""
        if not query:
            return

        logging.info(f"[Web] Browsing the internet for: '{query}'...")
        
        try:
            # Using AsyncDDGS to prevent blocking the main event loop
            async with AsyncDDGS() as ddgs:
                # Fetch the top 3 text results
                results = [r async for r in ddgs.text(query, max_results=3)]
                
            if results:
                # Format the results for the LLM to read easily
                formatted_results = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
                logging.info("[Web] Search complete. Injecting knowledge into Brain.")
                
                # Send the data back to the LLM so it can answer the user
                await self.bus.publish(
                    "TOOL_EXECUTION_SUCCESS", 
                    f"Web Search Results for '{query}':\n{formatted_results}"
                )
            else:
                logging.warning(f"[Web] No results found for '{query}'.")
                await self.bus.publish("TOOL_EXECUTION_FAILED", f"No web search results found for '{query}'.")
                
        except Exception as e:
            logging.error(f"[Web] Search pipeline failed: {e}")
            await self.bus.publish("TOOL_EXECUTION_FAILED", f"Web search failed due to an error: {e}")