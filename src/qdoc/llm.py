from google import genai
from qdoc.config import settings
from typing import List, Optional

class LLMEngine:
    def __init__(self):
        self.client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION
        )
        self.model_id = settings.GENAI_MODEL

    def generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt
        )
        return response.text

    def evaluate_results(self, query: str, chunks: List[str]) -> bool:
        """Evaluate if the retrieved chunks are sufficient to answer the query."""
        context = "\n---\n".join(chunks)
        prompt = f"""
        You are an expert evaluator for technical documentation.
        Original Query: {query}
        
        Retrieved Documentation Chunks:
        {context}
        
        Task: Determine if the provided chunks contain enough information to answer the query comprehensively.
        Respond ONLY with 'YES' or 'NO'.
        """
        response = self.generate(prompt).strip().upper()
        return "YES" in response

    def generate_answer(self, query: str, chunks: List[str]) -> str:
        """Generate a condensed response based strictly on the provided chunks."""
        context = "\n---\n".join(chunks)
        prompt = f"""
        You are a GCP technical oracle. Use ONLY the provided documentation context to answer the query.
        If the answer is not in the context, say you don't know.
        Do NOT hallucinate or use outside knowledge.
        
        Context:
        {context}
        
        Query: {query}
        
        Instructions:
        1. Condense the information.
        2. Be faithful to the documentation.
        3. Cite specific parts if applicable.
        """
        return self.generate(prompt)

    def augment_query(self, original_query: str, last_query: str) -> str:
        """Generate a new search query to find missing information."""
        prompt = f"""
        We are searching for information to answer: "{original_query}"
        Our last search query was: "{last_query}"
        The results were insufficient.
        
        Generate a new, better search query (single line) to find the missing information in a technical documentation database.
        Output ONLY the new query string.
        """
        return self.generate(prompt).strip().replace('"', '')
