from duckduckgo_search import DDGS
import logging

def perform_web_search(query, max_results=3):
    """
    Uses the official DuckDuckGo library to search.
    This is much more reliable than manual HTML scraping.
    """
    print(f"\n[🌐 ALICE is searching the web for: '{query}']")
    
    try:
        # The 'text' method is the standard way to search
        # We use a context manager to ensure the connection closes properly
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
        if not results:
            return "Web search completed, but no results were returned for this query."
        
        # Format for LLM consumption
        formatted_context = "INTERNET SEARCH RESULTS:\n"
        for i, res in enumerate(results):
            # res['body'] contains the snippet text
            formatted_context += f"Source {i+1} ({res.get('title', 'Unknown')}): {res.get('body', '')}\n"
            
        print("[✅ Web Search Success]")
        return formatted_context

    except Exception as e:
        error_msg = f"[❌ Web Search Failed: {str(e)}]"
        print(error_msg)
        return "The web search tool encountered an error and could not reach the internet."