import openai
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class PDFChatbot:
    def __init__(self):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.conversation_history = []
        
    def generate_response(self, query: str, relevant_pages: List[Dict[str, Any]]) -> str:
        """Generate chatbot response using OpenAI API with page context"""
        
        # Build context from relevant pages
        context = "Here are the relevant pages from the PDFs:\n\n"
        
        for i, page in enumerate(relevant_pages, 1):
            context += f"**Page {i} - {page['pdf_name']} (Page {page['page_number']})**\n"
            context += f"Content: {page['text'][:1000]}...\n"  # Limit content length
            if page['images']:
                context += f"This page contains {len(page['images'])} image(s)\n"
            context += "\n---\n\n"
        
        # Create system message
        system_message = {
            "role": "system",
            "content": """You are a helpful assistant that answers questions based on PDF content. 
            Use the provided page context to answer user questions accurately. 
            Reference specific pages when relevant (e.g., "According to page 3 of document X...").
            If the context doesn't contain enough information, say so clearly.
            Be conversational and helpful."""
        }
        
        # Create user message with context
        user_message = {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {query}"
        }
        
        # Add to conversation history
        messages = [system_message] + self.conversation_history + [user_message]
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            
            assistant_response = response.choices[0].message['content']
            
            # Update conversation history (keep last 5 exchanges)
            self.conversation_history.append(user_message)
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            if len(self.conversation_history) > 10:  # Keep last 5 exchanges
                self.conversation_history = self.conversation_history[-10:]
            
            return assistant_response
            
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []