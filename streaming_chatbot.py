import openai
import os
from typing import List, Dict, Any, Generator
from dotenv import load_dotenv
import json
import time

load_dotenv()

class StreamingChatbot:
    def __init__(self, vector_store=None):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.vector_store = vector_store
        self.conversation_history = []
        self.max_history = 10  # Keep last 10 exchanges
        
    def search_context(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Search for relevant context from vector store"""
        if not self.vector_store:
            return []
        
        try:
            results = self.vector_store.search(query, k=k)
            return results
        except Exception as e:
            print(f"Error searching context: {e}")
            return []
    
    def build_context_prompt(self, query: str, relevant_pages: List[Dict[str, Any]]) -> str:
        """Build context prompt with relevant pages and history"""
        
        # Build context from relevant pages
        context = ""
        if relevant_pages:
            context += "RELEVANT CONTEXT FROM DOCUMENTS:\n\n"
            for i, page in enumerate(relevant_pages, 1):
                context += f"[Context {i}] - {page['pdf_name']} (Page {page['page_number']}):\n"
                # Limit content length
                content = page['text'][:800] + "..." if len(page['text']) > 800 else page['text']
                context += f"{content}\n\n"
        
        # Add conversation history
        history_context = ""
        if self.conversation_history:
            history_context = "CONVERSATION HISTORY:\n\n"
            for exchange in self.conversation_history[-6:]:  # Last 3 exchanges
                history_context += f"User: {exchange['user']}\n"
                history_context += f"Assistant: {exchange['assistant']}\n\n"
        
        return context, history_context
    
    def generate_streaming_response(self, query: str) -> Generator[str, None, None]:
        """Generate streaming response using OpenAI API with RAG"""
        
        # Search for relevant context
        relevant_pages = self.search_context(query)
        context, history = self.build_context_prompt(query, relevant_pages)
        
        # Build system message
        system_message = {
            "role": "system",
            "content": """You are a helpful AI assistant that answers questions based on PDF documents and conversation history. 
            
            Guidelines:
            1. Use the provided context from documents to answer questions accurately
            2. Reference specific pages/documents when relevant (e.g., "According to page 3...")
            3. Consider conversation history for context
            4. If context doesn't contain enough information, say so clearly
            5. Be conversational and helpful
            6. For presentation requests, structure your response clearly with headings and bullet points
            7. When discussing visuals/images, mention that they are available in the relevant pages"""
        }
        
        # Build user message
        user_content = f"""
        {history}
        
        {context}
        
        Current Question: {query}
        """
        
        user_message = {
            "role": "user", 
            "content": user_content.strip()
        }
        
        # Create messages list with history
        messages = [system_message]
        
        # Add recent conversation history (formatted properly)
        for exchange in self.conversation_history[-4:]:  # Last 2 exchanges
            messages.append({"role": "user", "content": exchange['user']})
            messages.append({"role": "assistant", "content": exchange['assistant']})
        
        # Add current user message
        messages.append(user_message)
        
        try:
            # Create streaming response
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=1500,
                temperature=0.7,
                stream=True
            )
            
            full_response = ""
            for chunk in response:
                if 'choices' in chunk and len(chunk['choices']) > 0:
                    delta = chunk['choices'][0].get('delta', {})
                    if 'content' in delta:
                        content = delta['content']
                        full_response += content
                        yield content
            
            # Store in conversation history
            self.add_to_history(query, full_response, relevant_pages)
            
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            yield error_msg
            self.add_to_history(query, error_msg, [])
    
    def add_to_history(self, user_query: str, assistant_response: str, context_pages: List[Dict[str, Any]]):
        """Add exchange to conversation history"""
        self.conversation_history.append({
            "user": user_query,
            "assistant": assistant_response,
            "context_pages": [p['page_id'] for p in context_pages],
            "timestamp": time.time()
        })
        
        # Keep history manageable
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation"""
        if not self.conversation_history:
            return "No conversation history"
        
        summary = f"Conversation History ({len(self.conversation_history)} exchanges):\n\n"
        for i, exchange in enumerate(self.conversation_history[-5:], 1):
            summary += f"{i}. Q: {exchange['user'][:50]}...\n"
            summary += f"   A: {exchange['assistant'][:50]}...\n\n"
        
        return summary
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
    
    def get_related_pages(self, query: str) -> List[Dict[str, Any]]:
        """Get pages related to the current query for display"""
        return self.search_context(query, k=5)