import logging
import json
from typing import List, Dict, Any, Optional

try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger("ladas.memory.rag")

class RAGMemoryStorage:
    """
    RAG Semantic Memory for LADAS tracking successful task execution traces.
    Connects to a local vector database (ChromaDB) to embed trace semantics.
    """
    def __init__(self, db_path: str = "./ladas_chromadb"):
        self.db_path = db_path
        self._collection_name = "task_traces"
        self.collection = None
        
        if chromadb is None:
            logger.warning("chromadb not installed. RAG memory module will operate in fallback mock mode.")
            return
            
        try:
            import os
            from openai import OpenAI
            # Set up NVIDIA API client for embeddings
            self.embed_client = OpenAI(
                api_key=os.getenv("NVIDIA_API_KEY"),
                base_url="https://integrate.api.nvidia.com/v1"
            )
            self.embed_model = "nvidia/nv-embedqa-e5-v5"

            # Persistent local client
            self.client = chromadb.PersistentClient(path=self.db_path)
            # Create or get the trace collection
            self.collection = self.client.get_or_create_collection(name=self._collection_name)
            logger.info("ChromaDB successfully initialized for RAG Semantic Memory using NVIDIA embeddings.")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB or OpenAI SDK: {e}")

    def store_successful_trace(self, trace_id: str, intent_description: str, execution_trace: List[Dict[str, Any]]):
        """
        Serialized the successful execution sequence and embeds the intent description.
        Called exclusively upon hitting FSMState.TASK_COMPLETE.
        """
        if self.collection is None:
            logger.debug(f"Mock RAG: Storing trace {trace_id} for '{intent_description}'")
            return
            
        try:
            # Serialize trace actions into a lightweight string
            serialized_trace = json.dumps(execution_trace)
            
            # Embed the intent description using NVIDIA APIs
            response = self.embed_client.embeddings.create(
                input=[intent_description],
                model=self.embed_model,
                encoding_format="float",
                extra_body={"input_type": "passage", "truncate": "NONE"}
            )
            embedding = response.data[0].embedding
            
            # Upsert into ChromaDB with explicitly generated NVIDIA embeddings
            self.collection.upsert(
                documents=[intent_description],
                embeddings=[embedding],
                metadatas=[{"trace_data": serialized_trace}],
                ids=[trace_id]
            )
            logger.info(f"Successfully embedded trace {trace_id} into RAG Memory using NVIDIA nim.")
            
        except Exception as e:
            logger.error(f"Failed to upsert trace into RAG database: {e}")

    def retrieve_similar_intents(self, current_intent: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Queries the vector DB for historically successful execution paths based on semantic similarity
        of the requested intent. To be injected into the LLM system prompt context window.
        """
        if self.collection is None:
             logger.debug("Mock RAG: Returning empty context list.")
             return []
             
        try:
             # Embed incoming query using NVIDIA API
             response = self.embed_client.embeddings.create(
                 input=[current_intent],
                 model=self.embed_model,
                 encoding_format="float",
                 extra_body={"input_type": "query", "truncate": "NONE"}
             )
             query_embedding = response.data[0].embedding
             
             results = self.collection.query(
                 query_embeddings=[query_embedding],
                 n_results=top_k
             )
             
             retrieved = []
             # Chroma returns a list for each query provided.
             if results["metadatas"] and len(results["metadatas"]) > 0:
                 for meta_dict in results["metadatas"][0]:
                     trace_str = meta_dict.get("trace_data", "[]")
                     try:
                         retrieved.append(json.loads(trace_str))
                     except json.JSONDecodeError:
                         continue
                         
             return retrieved
             
        except Exception as e:
             logger.error(f"Querying RAG database failed: {e}")
             return []
