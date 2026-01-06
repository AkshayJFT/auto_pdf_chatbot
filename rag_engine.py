import os
from typing import List, Dict, Any
import openai
from dotenv import load_dotenv
from vector_store import VectorStore
from models import BotResponse
import logging
import base64

load_dotenv()
logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self, vector_store: VectorStore = None):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        openai.api_key = self.openai_api_key
        
        # Use provided vector store or create a new one
        self.vector_store = vector_store
        if not self.vector_store:
            self.vector_store = VectorStore()
            
    async def answer_question(self, question: str, conversation_context: str = "") -> BotResponse:
        try:
            # Search relevant documents using vector store
            related_pages = self.vector_store.search_similar(question, k=3)
            
            if not related_pages:
                return BotResponse(
                    type="rag_answer",
                    text="I don't have enough information in the uploaded documents to answer that question. Could you please upload some PDF files first?",
                    images=[],
                    sources=[]
                )
            
            # Build context from related pages
            context_parts = []
            sources = []
            images = []
            
            for page in related_pages:
                context_parts.append(f"From {page['pdf_name']} page {page['page_number']}: {page['text'][:500]}...")
                sources.append(f"{page['pdf_name']} - Page {page['page_number']}")
                
                # Include page image if available
                if page.get('full_page_image'):
                    try:
                        # Convert image to base64 for web display
                        with open(page['full_page_image'], 'rb') as img_file:
                            img_data = base64.b64encode(img_file.read()).decode()
                            images.append(f"data:image/png;base64,{img_data}")
                    except Exception as e:
                        logger.warning(f"Could not load image {page['full_page_image']}: {e}")
            
            knowledge_context = "\n\n".join(context_parts)
            
            # Build messages with conversation history
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant that answers questions based on PDF documents. Use the provided context to give accurate, helpful answers. If the context doesn't contain enough information, say so clearly."
                }
            ]
            
            # Add conversation history if available
            if conversation_context:
                messages.append({
                    "role": "user",
                    "content": f"Conversation History:\n{conversation_context}\n\nDocument Context:\n{knowledge_context}\n\nCurrent Question: {question}"
                })
            else:
                messages.append({
                    "role": "user",
                    "content": f"Document Context:\n{knowledge_context}\n\nQuestion: {question}"
                })
            
            # Generate answer using OpenAI
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=300
                )
                
                answer = response.choices[0].message['content']
            except Exception as openai_error:
                logger.error(f"OpenAI API error: {openai_error}")
                # Fallback to a simple context-based response
                answer = f"Based on the documents, here's what I found: {knowledge_context[:200]}... Please let me know if you need more specific information."
            
            return BotResponse(
                type="rag_answer",
                text=answer,
                images=images[:2],  # Limit to 2 images to avoid overwhelming
                sources=sources
            )
            
        except Exception as e:
            logger.error(f"RAG error: {e}")
            return BotResponse(
                type="rag_answer",
                text="I apologize, but I'm having trouble processing your question. Could you please try rephrasing it?",
                images=[],
                sources=[]
            )