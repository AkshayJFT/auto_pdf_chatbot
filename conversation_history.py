import json
from typing import List, Dict, Optional, Any
from datetime import datetime
import os
import logging
from collections import deque

logger = logging.getLogger(__name__)

class ConversationHistory:
    def __init__(self, max_history: int = 20, save_dir: str = "conversation_history"):
        self.max_history = max_history
        self.save_dir = save_dir
        self.history: Dict[str, deque] = {}  # conversation_id -> history deque
        self.ensure_save_dir()
        
    def ensure_save_dir(self):
        """Ensure save directory exists"""
        os.makedirs(self.save_dir, exist_ok=True)
        
    def add_message(self, conversation_id: str, role: str, content: str, 
                   message_type: str = "text", metadata: Optional[Dict[str, Any]] = None):
        """Add a message to conversation history"""
        if conversation_id not in self.history:
            self.history[conversation_id] = deque(maxlen=self.max_history)
            
        message = {
            "role": role,  # "user", "assistant", "system"
            "content": content,
            "type": message_type,  # "text", "presentation", "question"
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.history[conversation_id].append(message)
        logger.debug(f"Added {role} message to conversation {conversation_id[:8]}...")
        
    def get_context(self, conversation_id: str, max_messages: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation context"""
        if conversation_id not in self.history:
            return []
            
        messages = list(self.history[conversation_id])
        
        # Get last N messages, but ensure we include important context
        if len(messages) <= max_messages:
            return messages
            
        # Smart context selection - prioritize questions and answers
        important_messages = []
        regular_messages = []
        
        for msg in messages[-max_messages*2:]:  # Look at more messages
            if msg["type"] in ["question", "rag_answer"]:
                important_messages.append(msg)
            else:
                regular_messages.append(msg)
                
        # Combine, prioritizing important messages
        context = important_messages[-max_messages//2:] + regular_messages[-(max_messages//2):]
        context.sort(key=lambda x: x["timestamp"])  # Keep chronological order
        
        return context[-max_messages:]
        
    def get_formatted_context(self, conversation_id: str, max_messages: int = 10) -> str:
        """Get formatted context string for LLM"""
        context = self.get_context(conversation_id, max_messages)
        
        if not context:
            return ""
            
        formatted_parts = []
        for msg in context:
            role = msg["role"].capitalize()
            content = msg["content"]
            
            # Add context about message type
            if msg["type"] == "presentation":
                formatted_parts.append(f"{role} (presenting): {content[:200]}...")
            elif msg["type"] == "question":
                formatted_parts.append(f"{role} (question): {content}")
            elif msg["type"] == "rag_answer":
                formatted_parts.append(f"{role} (answer): {content}")
            else:
                formatted_parts.append(f"{role}: {content}")
                
        return "\n\n".join(formatted_parts)
        
    def save_conversation(self, conversation_id: str):
        """Save conversation history to file"""
        if conversation_id not in self.history:
            return
            
        filepath = os.path.join(self.save_dir, f"{conversation_id}.json")
        
        try:
            history_list = list(self.history[conversation_id])
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(history_list, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved conversation history to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save conversation history: {e}")
            
    def load_conversation(self, conversation_id: str) -> bool:
        """Load conversation history from file"""
        filepath = os.path.join(self.save_dir, f"{conversation_id}.json")
        
        if not os.path.exists(filepath):
            return False
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                history_list = json.load(f)
                
            self.history[conversation_id] = deque(history_list, maxlen=self.max_history)
            logger.info(f"Loaded conversation history from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to load conversation history: {e}")
            return False
            
    def get_summary(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation summary statistics"""
        if conversation_id not in self.history:
            return {"message_count": 0}
            
        messages = list(self.history[conversation_id])
        
        summary = {
            "message_count": len(messages),
            "user_messages": sum(1 for m in messages if m["role"] == "user"),
            "assistant_messages": sum(1 for m in messages if m["role"] == "assistant"),
            "questions_asked": sum(1 for m in messages if m["type"] == "question"),
            "presentation_segments": sum(1 for m in messages if m["type"] == "presentation")
        }
        
        if messages:
            summary["first_message"] = messages[0]["timestamp"]
            summary["last_message"] = messages[-1]["timestamp"]
            
        return summary
        
    def clear_conversation(self, conversation_id: str):
        """Clear conversation history"""
        if conversation_id in self.history:
            self.history[conversation_id].clear()
            logger.info(f"Cleared conversation history for {conversation_id[:8]}...")