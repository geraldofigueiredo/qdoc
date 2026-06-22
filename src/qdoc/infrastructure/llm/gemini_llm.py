from google import genai
from qdoc.infrastructure.config import settings
from qdoc.domain.repository import LLMService
from typing import List

class GeminiLLMService(LLMService):
    def __init__(self):
        if settings.GOOGLE_CLOUD_PROJECT:
            self.client = genai.Client(
                vertexai=True,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION
            )
        else:
            self.client = genai.Client()
        self.model_id = settings.GENAI_MODEL

    def _generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt
        )
        return response.text

    def evaluate_results(self, query: str, context_chunks: List[str]) -> bool:
        context = "\n---\n".join(context_chunks)
        prompt = f"""
        You are an expert evaluator for technical documentation.
        Original Query: {query}
        
        Retrieved Documentation Chunks:
        {context}
        
        Task: Determine if the provided chunks contain enough information to answer the query comprehensively.
        Respond ONLY with 'YES' or 'NO'.
        """
        response = self._generate(prompt).strip().upper()
        return "YES" in response

    def generate_answer(self, query: str, context_chunks: List[str]) -> str:
        context = "\n---\n".join(context_chunks)
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
        return self._generate(prompt)

    def augment_query(self, original_query: str, current_query: str, context_chunks: List[str]) -> str:
        context_section = ""
        if context_chunks:
            preview = "\n---\n".join(context_chunks[:4])
            context_section = f"\nInformation already retrieved:\n{preview}\n\nGenerate a query that finds the MISSING parts not covered above."

        prompt = f"""
        We are searching for information to answer: "{original_query}"
        Our last search query was: "{current_query}"
        {context_section}
        Generate a new, better search query (single line) to find the missing information in a technical documentation database.
        Output ONLY the new query string.
        """
        return self._generate(prompt).strip().replace('"', '')
