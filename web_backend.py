from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import os
import tempfile
from typing import List, AsyncGenerator, Dict
import aiofiles
import logging

from pdf_processor import PDFProcessor
from vector_store import VectorStore
from streaming_chatbot import StreamingChatbot
from presentation_generator import PresentationGenerator
from conversation_controller import ConversationController
from rag_engine import RAGEngine
from voice_handler import VoiceHandler
from pdf_cache_manager import PDFCacheManager
from models import UserMessage, BotResponse, PricingRequest, ConversationMode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PDF AI Assistant")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global variables for session management
vector_store = None
chatbot = None
presentation_generator = None
conversation_controller = None
rag_engine = None
voice_handler = None
pdf_cache_manager = None
pages_data = []
presentation_data = None

# WebSocket connections
active_connections: Dict[str, WebSocket] = {}
presentation_tasks: Dict[str, asyncio.Task] = {}
websocket_connections: Dict[str, WebSocket] = {}

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    context_pages: List[dict] = []

class SlideRequest(BaseModel):
    slide_number: int

def restart_presentation_streaming(conversation_id: str):
    """Restart presentation streaming for a conversation"""
    if conversation_id in websocket_connections and conversation_id in active_connections:
        websocket = websocket_connections[conversation_id]
        # Cancel existing task if any
        if conversation_id in presentation_tasks:
            task = presentation_tasks[conversation_id]
            if not task.done():
                task.cancel()
        
        # Check if this is resuming from an interruption
        state = conversation_controller.get_state(conversation_id) if conversation_controller else None
        if state and state.interrupted_segment_text:
            # Send the interrupted segment for resumption
            logger.info(f"Sending interrupted segment for resumption: {conversation_id}")
            
            segment = conversation_controller.presentation_generator.get_segment(state.current_segment)
            if segment:
                resume_message = {
                    "type": "presentation_resume",
                    "text": state.interrupted_segment_text,
                    "images": segment.images,
                    "segment_id": segment.id
                }
                asyncio.create_task(websocket.send_text(json.dumps(resume_message)))
                logger.info(f"Sent presentation resume message for segment {segment.id}")
            
            # Clear the interrupted state
            state.interrupted_segment_text = None
            return True
        
        # Start new task
        new_task = asyncio.create_task(stream_presentation(conversation_id, websocket))
        presentation_tasks[conversation_id] = new_task
        logger.info(f"Restarted presentation streaming for {conversation_id}")
        return True
    return False

@app.get("/")
async def read_root():
    return FileResponse('index.html')

@app.post("/upload")
async def upload_pdfs(files: List[UploadFile] = File(...)):
    global vector_store, chatbot, presentation_generator, rag_engine, pages_data, conversation_controller, pdf_cache_manager, presentation_data
    
    try:
        # Initialize cache manager
        if pdf_cache_manager is None:
            pdf_cache_manager = PDFCacheManager()
        
        # Save uploaded files temporarily
        temp_paths = []
        original_filenames = []
        for file in files:
            if not file.filename.endswith('.pdf'):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")
            
            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            content = await file.read()
            temp_file.write(content)
            temp_file.close()
            temp_paths.append(temp_file.name)
            original_filenames.append(file.filename)
        
        # Check if PDFs are already cached
        is_cached, files_hash = pdf_cache_manager.is_cached(temp_paths)
        
        if is_cached:
            logger.info(f"Loading cached results for hash {files_hash}")
            cached_results = pdf_cache_manager.load_cached_results(files_hash)
            
            if cached_results:
                pages_data, vector_store, presentation_data, presentation_generator = cached_results
                
                # Initialize other components
                rag_engine = RAGEngine(vector_store)
                conversation_controller = ConversationController(presentation_generator, rag_engine)
                conversation_controller.set_restart_presentation_callback(restart_presentation_streaming)
                chatbot = StreamingChatbot(vector_store)
                
                # Clean up temp files
                for temp_path in temp_paths:
                    os.unlink(temp_path)
                
                logger.info(f"Successfully loaded from cache: {len(pages_data)} pages, {len(presentation_generator.segments)} segments")
                
                return {
                    "status": "success",
                    "message": f"Loaded from cache: {len(pages_data)} pages from {len(files)} PDFs",
                    "pages_count": len(pages_data),
                    "presentation_slides": presentation_data.get("total_slides", 0),
                    "cached": True
                }
        
        # Process PDFs (not in cache)
        logger.info(f"Processing {len(files)} PDFs (not in cache)")
        
        # Initialize components
        vector_store = VectorStore()
        rag_engine = RAGEngine(vector_store)
        presentation_generator = PresentationGenerator()
        conversation_controller = ConversationController(presentation_generator, rag_engine)
        conversation_controller.set_restart_presentation_callback(restart_presentation_streaming)
        chatbot = StreamingChatbot(vector_store)
        
        # Process PDFs
        processor = PDFProcessor()
        pages_data = processor.process_multiple_pdfs(temp_paths)
        
        # Create embeddings
        vector_store.create_embeddings(pages_data)
        
        # Generate presentation
        presentation_data = presentation_generator.create_full_presentation(pages_data)
        
        # Cache the results with original filenames
        cache_hash = pdf_cache_manager.cache_processing_results(
            temp_paths, pages_data, vector_store, presentation_data, presentation_generator, original_filenames
        )
        
        # Clean up temp files
        for temp_path in temp_paths:
            os.unlink(temp_path)
        
        logger.info(f"Successfully processed and cached: {len(pages_data)} pages, cache hash: {cache_hash}")
        
        return {
            "status": "success",
            "message": f"Processed {len(pages_data)} pages from {len(files)} PDFs",
            "pages_count": len(pages_data),
            "presentation_slides": presentation_data.get("total_slides", 0),
            "cached": False,
            "cache_hash": cache_hash
        }
    
    except Exception as e:
        logger.error(f"Upload error: {e}")
        # Clean up temp files on error
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/conversation/start")
async def start_conversation():
    if not conversation_controller:
        raise HTTPException(status_code=400, detail="Please upload PDFs first")
    
    conversation_id = conversation_controller.create_conversation()
    return {"conversation_id": conversation_id}

@app.post("/api/pricing")
async def calculate_pricing(request: PricingRequest):
    # Basic pricing calculation - can be enhanced based on your needs
    total = 0
    breakdown = []
    
    for window in request.windows:
        base_price = 500  # Default base price
        window_total = base_price * window.get('quantity', 1)
        total += window_total
        
        breakdown.append({
            'type': window.get('type', 'standard'),
            'size': window.get('size', 'medium'),
            'quantity': window.get('quantity', 1),
            'unit_price': base_price,
            'subtotal': window_total
        })
    
    return {
        'breakdown': breakdown,
        'subtotal': total,
        'discount_rate': 0,
        'discount_amount': 0,
        'total': total
    }

@app.get("/api/voice/config")
async def get_voice_config():
    global voice_handler
    if not voice_handler:
        # Initialize voice handler if not already done
        voice_handler = VoiceHandler()
    
    return voice_handler.get_tts_config()

@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    await websocket.accept()
    active_connections[conversation_id] = websocket
    websocket_connections[conversation_id] = websocket
    
    try:
        # Start presentation automatically
        presentation_task = asyncio.create_task(stream_presentation(conversation_id, websocket))
        presentation_tasks[conversation_id] = presentation_task
        
        # Listen for user messages
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle control commands
            if 'command' in message_data:
                await handle_presentation_command(conversation_id, message_data['command'])
                continue
            
            # Handle user message
            user_message = UserMessage(**message_data)
            
            # If there's audio data and we're using server-side transcription
            if user_message.audio and voice_handler:
                transcript = await voice_handler.transcribe_audio(user_message.audio)
                if transcript:
                    user_message.text = transcript
                    
            # Process the message
            if user_message.text:
                # Check if this interrupts an ongoing presentation
                state = conversation_controller.get_state(conversation_id)
                if state and state.mode == ConversationMode.PRESENTATION and not state.presentation_paused:
                    # Cancel the current presentation streaming
                    if conversation_id in presentation_tasks:
                        task = presentation_tasks[conversation_id]
                        if not task.done():
                            task.cancel()
                            logger.info(f"Cancelled presentation streaming for {conversation_id}")
                
                response = await conversation_controller.handle_message(
                    conversation_id, user_message
                )
                
                # Send response
                await websocket.send_text(json.dumps(response.model_dump()))
                
                # Check if we need to restart presentation streaming
                updated_state = conversation_controller.get_state(conversation_id)
                if updated_state and updated_state.mode == ConversationMode.PRESENTATION and not updated_state.presentation_paused:
                    # Restart presentation streaming
                    new_task = asyncio.create_task(stream_presentation(conversation_id, websocket))
                    presentation_tasks[conversation_id] = new_task
                    logger.info(f"Restarted presentation streaming for {conversation_id}")
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {conversation_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if conversation_id in active_connections:
            del active_connections[conversation_id]
        if conversation_id in websocket_connections:
            del websocket_connections[conversation_id]
        if conversation_id in presentation_tasks:
            task = presentation_tasks[conversation_id]
            if not task.done():
                task.cancel()
            del presentation_tasks[conversation_id]

async def stream_presentation(conversation_id: str, websocket: WebSocket):
    """Stream presentation segments with proper timing"""
    try:
        await asyncio.sleep(1)  # Initial delay
    
        while conversation_id in active_connections:
            try:
                # Check if presentation is still active
                state = conversation_controller.get_state(conversation_id)
                if not state:
                    logger.info("No conversation state found, ending presentation")
                    return
                    
                # Only continue if in presentation mode and not paused
                if state.mode != ConversationMode.PRESENTATION:
                    logger.info(f"Mode is {state.mode}, ending presentation stream")
                    return
                    
                if state.presentation_paused:
                    logger.info(f"Presentation is paused, ending current stream (will restart when resumed)")
                    return
                    
                # Get next segment
                segment_response = await conversation_controller.get_next_segment(conversation_id)
                
                if segment_response:
                    # Send segment
                    await websocket.send_text(json.dumps(segment_response.model_dump()))
                    logger.info(f"Sent segment {segment_response.segment_id} - waiting for speech completion")
                    
                    # Calculate natural speech time
                    if voice_handler:
                        estimated_speech_time = voice_handler.estimate_speech_duration(segment_response.text)
                    else:
                        # Fallback estimation: 150 words per minute
                        words = len(segment_response.text.split())
                        estimated_speech_time = max(5, (words * 60) // 150)
                    
                    logger.info(f"Estimated speech time: {estimated_speech_time} seconds")
                    
                    # Wait for natural speech completion + small buffer
                    total_wait_time = estimated_speech_time + 2  # Add 2 seconds buffer
                    elapsed = 0
                    
                    while elapsed < total_wait_time:
                        await asyncio.sleep(0.5)  # Check every half second
                        elapsed += 0.5
                        
                        # Check for user interruption
                        current_state = conversation_controller.get_state(conversation_id)
                        if not current_state:
                            logger.info("No state found, ending presentation")
                            return
                            
                        # If user asked a question - stop immediately
                        if current_state.mode != ConversationMode.PRESENTATION or current_state.presentation_paused:
                            logger.info(f"User interrupted at {elapsed}s - stopping advancement")
                            return
                    
                    # Natural advancement after speech completion
                    logger.info(f"Speech completed for segment {segment_response.segment_id}, advancing to next")
                            
                else:
                    # Presentation finished naturally - no more segments
                    logger.info("Presentation completed - no more segments available")
                    return  # Exit function completely
                
            except asyncio.CancelledError:
                logger.info(f"Presentation streaming cancelled for {conversation_id}")
                break
            except Exception as e:
                logger.error(f"Presentation streaming error: {e}")
                break
    finally:
        logger.info(f"Presentation streaming ended for {conversation_id}")
        # Clean up task reference
        if conversation_id in presentation_tasks:
            del presentation_tasks[conversation_id]

async def handle_presentation_command(conversation_id: str, command: str):
    """Handle presentation control commands"""
    state = conversation_controller.get_state(conversation_id)
    if not state:
        logger.warning(f"No state found for conversation {conversation_id}")
        return
        
    # Ensure state has new fields (for compatibility)
    if not hasattr(state, 'paused_mid_segment'):
        state.paused_mid_segment = False
    if not hasattr(state, 'pause_timestamp'):
        state.pause_timestamp = None
    
    logger.info(f"COMMAND '{command}' - Current state: paused_mid_segment={state.paused_mid_segment}, paused_at_segment={state.paused_at_segment}")
    
    if command == 'pause_presentation':
        logger.info(f"Pausing presentation for {conversation_id}")
        import time
        state.presentation_paused = True
        state.pause_timestamp = time.time()
        # Store the currently displayed segment - don't subtract 1 since we want to resume this segment
        state.paused_at_segment = max(0, state.current_segment - 1)
        state.paused_mid_segment = True  # Mark as mid-segment pause
        logger.info(f"PAUSE STATE: paused_at_segment={state.paused_at_segment}, current_segment={state.current_segment}, paused_mid_segment={state.paused_mid_segment}")
        # Cancel current streaming task
        if conversation_id in presentation_tasks:
            task = presentation_tasks[conversation_id]
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled presentation streaming for pause: {conversation_id}")
                
    elif command == 'resume_presentation':
        logger.info(f"Resuming presentation for {conversation_id}")
        logger.info(f"RESUME STATE: paused_mid_segment={state.paused_mid_segment}, paused_at_segment={state.paused_at_segment}")
        state.presentation_paused = False
        # For mid-segment resume, send a special resume signal to frontend
        if state.paused_mid_segment and state.paused_at_segment is not None:
            logger.info(f"SENDING MID-SEGMENT RESUME for segment {state.paused_at_segment}")
            # Send resume signal to frontend instead of restarting segment
            if conversation_id in websocket_connections:
                import json
                websocket = websocket_connections[conversation_id]
                resume_message = {
                    "type": "resume_mid_segment",
                    "segment_id": state.paused_at_segment,
                    "pause_timestamp": state.pause_timestamp
                }
                asyncio.create_task(websocket.send_text(json.dumps(resume_message)))
                logger.info(f"Sent mid-segment resume signal for segment {state.paused_at_segment}")
            # Clear pause state
            state.paused_mid_segment = False
            state.pause_timestamp = None
            state.paused_at_segment = None
            
            # Don't restart streaming immediately - the current segment is already being displayed
            # The presentation will naturally continue to next segment when current one finishes
        else:
            logger.info(f"REGULAR RESUME - restarting segment from beginning")
            # Regular resume from segment start
            if state.paused_at_segment is not None:
                state.current_segment = state.paused_at_segment
                logger.info(f"Resuming from segment start {state.current_segment}")
                state.paused_at_segment = None
            # Restart presentation streaming
            if conversation_id in websocket_connections:
                websocket = websocket_connections[conversation_id]
                presentation_task = asyncio.create_task(stream_presentation(conversation_id, websocket))
                presentation_tasks[conversation_id] = presentation_task
            
    elif command == 'segment_complete':
        logger.info(f"Segment completed for {conversation_id}, moving to next")
        # Continue with presentation streaming to get next segment
        if conversation_id in websocket_connections:
            websocket = websocket_connections[conversation_id]
            presentation_task = asyncio.create_task(stream_presentation(conversation_id, websocket))
            presentation_tasks[conversation_id] = presentation_task
            
    elif command == 'next_slide':
        logger.info(f"Skipping to next slide for {conversation_id}")
        # Cancel current streaming
        if conversation_id in presentation_tasks:
            task = presentation_tasks[conversation_id]
            if not task.done():
                task.cancel()
                # Wait a bit for cancellation to complete
                await asyncio.sleep(0.1)
        
        # Check if we're at the end of presentation
        total_segments = conversation_controller.presentation_generator.get_total_segments()
        if state.current_segment >= total_segments:
            logger.info(f"Already at end of presentation for {conversation_id}")
            return
        
        # Move to next slide
        logger.info(f"Moving to segment {state.current_segment}")
        
        # Unpause if paused and restart streaming
        state.presentation_paused = False
        state.paused_at_segment = None
        state.paused_mid_segment = False
        
        if conversation_id in websocket_connections:
            websocket = websocket_connections[conversation_id]
            presentation_task = asyncio.create_task(stream_presentation(conversation_id, websocket))
            presentation_tasks[conversation_id] = presentation_task

@app.get("/status")
async def get_status():
    cache_stats = pdf_cache_manager.get_cache_stats() if pdf_cache_manager else {"total_entries": 0}
    
    return {
        "status": "connected",
        "pdfs_loaded": len(pages_data) > 0,
        "pages_count": len(pages_data),
        "has_presentation": presentation_data is not None,
        "presentation_slides": len(presentation_generator.segments) if presentation_generator else 0,
        "cache_stats": cache_stats
    }

@app.get("/api/cache/stats")
async def get_cache_stats():
    """Get detailed cache statistics"""
    if not pdf_cache_manager:
        return {"error": "Cache manager not initialized"}
    
    return pdf_cache_manager.get_cache_stats()

@app.delete("/api/cache/clear")
async def clear_cache():
    """Clear all cached data"""
    if not pdf_cache_manager:
        raise HTTPException(status_code=400, detail="Cache manager not initialized")
    
    success = pdf_cache_manager.clear_cache()
    if success:
        return {"status": "success", "message": "Cache cleared successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to clear cache")

@app.delete("/api/cache/entry/{cache_hash}")
async def remove_cache_entry(cache_hash: str):
    """Remove specific cache entry"""
    if not pdf_cache_manager:
        raise HTTPException(status_code=400, detail="Cache manager not initialized")
    
    success = pdf_cache_manager.remove_cache_entry(cache_hash)
    if success:
        return {"status": "success", "message": f"Cache entry {cache_hash} removed"}
    else:
        raise HTTPException(status_code=404, detail="Cache entry not found")

# Legacy endpoints for compatibility
@app.post("/chat/stream")
async def stream_chat(message: ChatMessage):
    global chatbot
    
    if not chatbot:
        raise HTTPException(status_code=400, detail="Please upload PDFs first")
    
    async def generate_response() -> AsyncGenerator[str, None]:
        try:
            # Get related pages for context
            related_pages = chatbot.search_context(message.message, k=3)
            
            # Send context info first
            if related_pages:
                context_info = {
                    "type": "context",
                    "pages": [
                        {
                            "pdf_name": page["pdf_name"],
                            "page_number": page["page_number"],
                            "similarity_score": page.get("similarity_score", 0)
                        } for page in related_pages
                    ]
                }
                yield f"data: {json.dumps(context_info)}\n\n"
            
            # Stream the response
            response_text = ""
            for chunk in chatbot.generate_streaming_response(message.message):
                response_text += chunk
                chunk_data = {
                    "type": "chunk",
                    "content": chunk,
                    "full_response": response_text
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
                await asyncio.sleep(0.01)  # Small delay for streaming effect
            
            # Send completion signal
            completion_data = {
                "type": "complete",
                "full_response": response_text,
                "related_pages": related_pages
            }
            yield f"data: {json.dumps(completion_data)}\n\n"
            
        except Exception as e:
            error_data = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

@app.delete("/chat/clear")
async def clear_chat():
    global chatbot
    
    if chatbot:
        chatbot.clear_history()
    
    return {"status": "success", "message": "Chat history cleared"}

@app.get("/pages/{page_id}/image")
async def get_page_image(page_id: str):
    global pages_data
    
    # Find the page
    for page in pages_data:
        if page["page_id"] == page_id:
            if page.get("full_page_image") and os.path.exists(page["full_page_image"]):
                return FileResponse(page["full_page_image"])
    
    raise HTTPException(status_code=404, detail="Image not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)