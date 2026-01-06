import uuid
from typing import Dict, Optional
from models import ConversationState, ConversationMode, BotResponse, UserMessage, ConversationMessage
from presentation_generator import PresentationGenerator
from rag_engine import RAGEngine
from conversation_history import ConversationHistory
import asyncio
import logging

logger = logging.getLogger(__name__)

class ConversationController:
    def __init__(self, presentation_generator: PresentationGenerator, rag_engine: RAGEngine):
        self.presentation_generator = presentation_generator
        self.rag_engine = rag_engine
        self.conversations: Dict[str, ConversationState] = {}
        self.restart_presentation_callback = None
        self.conversation_history = ConversationHistory()
        
    def create_conversation(self) -> str:
        conversation_id = str(uuid.uuid4())
        self.conversations[conversation_id] = ConversationState(
            conversation_id=conversation_id,
            mode=ConversationMode.PRESENTATION,
            current_segment=0,
            presentation_paused=False,
            paused_at_segment=None,
            paused_mid_segment=False,
            pause_timestamp=None
        )
        return conversation_id
    
    def set_restart_presentation_callback(self, callback):
        self.restart_presentation_callback = callback
        
    def get_state(self, conversation_id: str) -> Optional[ConversationState]:
        return self.conversations.get(conversation_id)
        
    async def handle_message(self, conversation_id: str, message: UserMessage) -> BotResponse:
        state = self.get_state(conversation_id)
        if not state:
            raise ValueError(f"Conversation {conversation_id} not found")
            
        # Add user message to history
        self.conversation_history.add_message(
            conversation_id, 
            "user", 
            message.text,
            message_type="question"
        )
        
        # If in presentation mode and user interrupts
        if state.mode == ConversationMode.PRESENTATION and message.text:
            # The current segment being displayed is the one we want to resume from
            currently_displaying_segment = max(0, state.current_segment - 1)
            logger.info(f"User interrupted during segment {currently_displaying_segment} (next would be {state.current_segment})")
            
            # Capture the interrupted segment for precise resume
            interrupted_segment = self.presentation_generator.get_segment(currently_displaying_segment)
            if interrupted_segment:
                state.interrupted_segment_text = interrupted_segment.text
                logger.info(f"Captured interrupted segment text for precise resume")
            
            state.mode = ConversationMode.RAG
            state.presentation_paused = True
            state.paused_at_segment = currently_displaying_segment
            state.paused_mid_segment = True  # This is always a mid-segment pause for questions
            
            # Get conversation context from our history manager
            conversation_context = self.conversation_history.get_formatted_context(conversation_id)
            response = await self.rag_engine.answer_question(message.text, conversation_context)
            
            # Add assistant response to history
            self.conversation_history.add_message(
                conversation_id,
                "assistant",
                response.text,
                message_type="rag_answer",
                metadata={"sources": response.sources}
            )
            
            # Schedule resuming presentation if not complete
            total_segments = self.presentation_generator.get_total_segments()
            if currently_displaying_segment < total_segments - 1:
                asyncio.create_task(self._resume_presentation_after_delay(conversation_id, 3))
            else:
                logger.info(f"Presentation already complete, staying in RAG mode")
            
            return response
            
        # If already in RAG mode
        elif state.mode == ConversationMode.RAG:
            # Get conversation context from our history manager
            conversation_context = self.conversation_history.get_formatted_context(conversation_id)
            response = await self.rag_engine.answer_question(message.text, conversation_context)
            
            # Add assistant response to history
            self.conversation_history.add_message(
                conversation_id,
                "assistant",
                response.text,
                message_type="rag_answer",
                metadata={"sources": response.sources}
            )
            
            return response
    
    def _build_conversation_context(self, history) -> str:
        """Build conversation context from history for better responses"""
        if not history:
            return ""
        
        context_parts = []
        for msg in history[-6:]:  # Use last 6 messages for context
            role = "User" if msg.get('role') == "user" else "Assistant"
            content = msg.get('content', '')
            context_parts.append(f"{role}: {content}")
        
        return "\n".join(context_parts) if context_parts else ""
            
    async def get_next_segment(self, conversation_id: str) -> Optional[BotResponse]:
        state = self.get_state(conversation_id)
        if not state or state.mode != ConversationMode.PRESENTATION or state.presentation_paused:
            return None
            
        segment = self.presentation_generator.get_segment(state.current_segment)
        if segment:
            response = BotResponse(
                type="presentation",
                text=segment.text,
                images=segment.images,
                segment_id=segment.id,
                category=getattr(segment, 'category', None),
                image_strategy=getattr(segment, 'image_strategy', 'show_multiple'),
                image_timing=getattr(segment, 'image_timing', None)
            )
            
            # Add presentation segment to history
            self.conversation_history.add_message(
                conversation_id,
                "assistant",
                segment.text,
                message_type="presentation",
                metadata={
                    "segment_id": segment.id,
                    "pdf_page": segment.pdf_page,
                    "pdf_name": segment.pdf_name
                }
            )
            
            logger.info(f"Presenting segment {state.current_segment} of {self.presentation_generator.get_total_segments() - 1}")
            state.current_segment += 1
            logger.info(f"Next segment will be {state.current_segment} of {self.presentation_generator.get_total_segments()}")
            return response
        else:
            # Presentation finished
            state.mode = ConversationMode.RAG
            conclusion_text = "That concludes our presentation! Feel free to ask any questions about the documents."
            
            # Add conclusion to history
            self.conversation_history.add_message(
                conversation_id,
                "assistant",
                conclusion_text,
                message_type="presentation"
            )
            
            return BotResponse(
                type="presentation",
                text=conclusion_text,
                images=[]
            )
            
    async def _resume_presentation_after_delay(self, conversation_id: str, delay: int):
        await asyncio.sleep(delay)
        state = self.get_state(conversation_id)
        if state and state.presentation_paused and state.paused_at_segment is not None:
            # Check if presentation is complete
            total_segments = self.presentation_generator.get_total_segments()
            if state.paused_at_segment >= total_segments - 1:
                # Presentation completed during pause, switch to RAG permanently
                state.mode = ConversationMode.RAG
                state.presentation_paused = False
                state.paused_at_segment = None
                state.interrupted_segment_text = None
                logger.info(f"Presentation completed, staying in RAG mode")
            else:
                # Resume from the same segment that was interrupted with the exact text
                state.current_segment = state.paused_at_segment
                state.mode = ConversationMode.PRESENTATION
                state.presentation_paused = False
                paused_segment = state.paused_at_segment
                
                logger.info(f"Resuming presentation from segment {state.current_segment} (continuing interrupted segment {paused_segment})")
                
                # If we have the interrupted segment text, we'll send a special resume message
                if state.interrupted_segment_text and self.restart_presentation_callback:
                    # Send the interrupted segment as a resume message instead of restarting streaming
                    segment = self.presentation_generator.get_segment(paused_segment)
                    if segment:
                        from models import BotResponse
                        resume_response = BotResponse(
                            type="presentation_resume",
                            text=state.interrupted_segment_text,
                            images=segment.images,
                            segment_id=segment.id
                        )
                        
                        # We need to send this directly to the websocket connection
                        # This will be handled by the web backend
                        logger.info(f"Prepared resume message for interrupted segment")
                
                # Clear interruption state
                state.paused_at_segment = None
                state.interrupted_segment_text = None
                state.paused_mid_segment = False
                
                # Restart the presentation streaming
                if self.restart_presentation_callback:
                    success = self.restart_presentation_callback(conversation_id)
                    if success:
                        logger.info(f"Successfully restarted presentation streaming for {conversation_id}")
                    else:
                        logger.error(f"Failed to restart presentation streaming for {conversation_id}")
                else:
                    logger.warning("No restart callback available")
            
    def is_presentation_active(self, conversation_id: str) -> bool:
        state = self.get_state(conversation_id)
        is_active = state and state.mode == ConversationMode.PRESENTATION and not state.presentation_paused
        if state:
            logger.debug(f"Presentation active check: mode={state.mode}, paused={state.presentation_paused}, result={is_active}")
        return is_active
    
    def get_conversation_summary(self, conversation_id: str) -> dict:
        """Get conversation statistics and summary"""
        return self.conversation_history.get_summary(conversation_id)