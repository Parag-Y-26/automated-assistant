import aiohttp
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("ladas.tools.perplexity")

class PerplexitySearchTool:
    """
    Integrates the Perplexity API as a first-class tool to augment
    the LADAS engine when it encounters unknown errors or needs documentation.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.perplexity.ai/chat/completions"

    async def search(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Executes a web search query via Perplexity and returns the structured context.
        """
        if not self.api_key:
            logger.error("Perplexity API key not configured. Cannot perform web search.")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Prompt forces concise, highly relevant technical context
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a web search assistant augmenting an automated reasoning agent. Provide precise, actionable technical documentation, error code explanations, or UI instructions based strictly on your search results. Be as concise as possible."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "max_tokens": 1500,
            "temperature": 0.2
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    result = await response.json()
                    
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    citations = result.get("citations", [])
                    
                    logger.info(f"Perplexity Search Completed for query: '{query}'")
                    return {
                        "query": query,
                        "context": content,
                        "citations": citations
                    }
                    
        except aiohttp.ClientError as e:
            logger.error(f"Perplexity network request failed: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error during Perplexity search: {e}")
            return None
