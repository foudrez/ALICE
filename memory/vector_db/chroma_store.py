import os
import logging
from datetime import datetime
try:
    import chromadb
except ImportError:
    logging.error("ChromaDB not installed. Run: pip install chromadb")

class VectorMemory:
    def __init__(self, persist_directory="assets/memory_db"):
        logging.info("[Memory L2] Initializing Vector Database (ChromaDB)...")
        # Ensure the directory exists
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize persistent local storage
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Get or create the collection for ALICE's memories
        self.collection = self.client.get_or_create_collection(
            name="alice_long_term_memory",
            metadata={"hnsw:space": "cosine"} # Cosine similarity is best for text
        )

    def add_memory(self, text: str, role: str):
        """Stores a conversation turn or fact into the vector database."""
        if not text.strip():
            return
            
        doc_id = f"mem_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        metadata = {
            "role": role, 
            "timestamp": datetime.now().isoformat()
        }
        
        self.collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[doc_id]
        )

    def query_memory(self, query: str, n_results: int = 3) -> list:
        """Retrieves semantically similar past interactions."""
        if self.collection.count() == 0:
            return []
            
        # We cap n_results to the total items to avoid errors on fresh databases
        safe_n_results = min(n_results, self.collection.count())
        
        results = self.collection.query(
            query_texts=[query],
            n_results=safe_n_results
        )
        
        # Format results into a readable string for the LLM
        retrieved_contexts = []
        if results['documents'] and results['documents'][0]:
            for idx, doc in enumerate(results['documents'][0]):
                role = results['metadatas'][0][idx]['role']
                timestamp = results['metadatas'][0][idx]['timestamp'][:10] # Just the date
                retrieved_contexts.append(f"[{timestamp}] {role.upper()} SAID: {doc}")
                
        return retrieved_contexts