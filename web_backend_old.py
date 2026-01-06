from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import os
import tempfile
from typing import List, AsyncGenerator
import aiofiles

from pdf_processor import PDFProcessor
from vector_store import VectorStore
from streaming_chatbot import StreamingChatbot
from presentation_generator import PresentationGenerator

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
pages_data = []
presentation_data = None

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    context_pages: List[dict] = []

class SlideRequest(BaseModel):
    slide_number: int

@app.get("/")
async def read_root():
    return FileResponse('index.html')

@app.post("/upload")
async def upload_pdfs(files: List[UploadFile] = File(...)):
    global vector_store, chatbot, presentation_generator, pages_data
    
    try:
        # Initialize components
        vector_store = VectorStore()
        chatbot = StreamingChatbot(vector_store)
        presentation_generator = PresentationGenerator()
        
        # Save uploaded files temporarily
        temp_paths = []
        for file in files:
            if not file.filename.endswith('.pdf'):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")
            
            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            content = await file.read()
            temp_file.write(content)
            temp_file.close()
            temp_paths.append(temp_file.name)
        
        # Process PDFs
        processor = PDFProcessor()
        pages_data = processor.process_multiple_pdfs(temp_paths)
        
        # Create embeddings
        vector_store.create_embeddings(pages_data)
        
        # Clean up temp files
        for temp_path in temp_paths:
            os.unlink(temp_path)
        
        return {
            "status": "success",
            "message": f"Processed {len(pages_data)} pages from {len(files)} PDFs",
            "pages_count": len(pages_data)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@app.post("/presentation/generate")
async def generate_presentation():
    global presentation_generator, pages_data, presentation_data
    
    if not presentation_generator or not pages_data:
        raise HTTPException(status_code=400, detail="Please upload PDFs first")
    
    try:
        presentation_data = presentation_generator.create_full_presentation(pages_data)
        
        # Optimize for shorter, broader coverage
        for slide in presentation_data["slides"]:
            # Shorten content but keep key points
            if len(slide["content"]) > 400:
                lines = slide["content"].split('\n')
                key_lines = [line for line in lines if any(keyword in line.lower() 
                           for keyword in ['key', 'main', 'important', '•', '-', '1.', '2.', '3.'])][:5]
                slide["content"] = '\n'.join(key_lines) if key_lines else slide["content"][:400] + "..."
        
        return {
            "status": "success",
            "presentation": presentation_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/presentation/slide/{slide_number}/stream")
async def stream_slide(slide_number: int):
    global presentation_data
    
    if not presentation_data:
        raise HTTPException(status_code=400, detail="No presentation generated")
    
    if slide_number < 0 or slide_number >= len(presentation_data["slides"]):
        raise HTTPException(status_code=400, detail="Invalid slide number")
    
    slide = presentation_data["slides"][slide_number]
    
    async def generate_slide_stream() -> AsyncGenerator[str, None]:
        try:
            # Send slide metadata first
            slide_info = {
                "type": "slide_info",
                "slide_number": slide["slide_number"],
                "title": slide["title"],
                "total_slides": presentation_data["total_slides"]
            }
            yield f"data: {json.dumps(slide_info)}\n\n"
            await asyncio.sleep(0.3)
            
            # Stream title
            title_data = {
                "type": "title",
                "content": slide["title"]
            }
            yield f"data: {json.dumps(title_data)}\n\n"
            await asyncio.sleep(0.5)
            
            # Stream content word by word
            content_words = slide["content"].split()
            streamed_content = ""
            
            for i, word in enumerate(content_words):
                streamed_content += word + " "
                content_data = {
                    "type": "content_chunk",
                    "word": word,
                    "full_content": streamed_content.strip(),
                    "progress": (i + 1) / len(content_words)
                }
                yield f"data: {json.dumps(content_data)}\n\n"
                await asyncio.sleep(0.08)  # Typing speed
            
            # Send images one by one
            if slide.get("relevant_pages"):
                for idx, page in enumerate(slide["relevant_pages"]):
                    if page.get("full_page_image") and os.path.exists(page["full_page_image"]):
                        # Convert to base64
                        import base64
                        with open(page["full_page_image"], "rb") as img_file:
                            img_data = base64.b64encode(img_file.read()).decode()
                        
                        image_data = {
                            "type": "image",
                            "page_number": page["page_number"],
                            "data": f"data:image/png;base64,{img_data}",
                            "image_index": idx,
                            "total_images": len([p for p in slide["relevant_pages"] if p.get("full_page_image")])
                        }
                        yield f"data: {json.dumps(image_data)}\n\n"
                        await asyncio.sleep(0.8)  # Pause between images
            
            # Send completion signal
            completion_data = {
                "type": "complete",
                "slide_number": slide["slide_number"]
            }
            yield f"data: {json.dumps(completion_data)}\n\n"
            
        except Exception as e:
            error_data = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate_slide_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

@app.get("/presentation/slide/{slide_number}")
async def get_slide(slide_number: int):
    global presentation_data
    
    if not presentation_data:
        raise HTTPException(status_code=400, detail="No presentation generated")
    
    if slide_number < 0 or slide_number >= len(presentation_data["slides"]):
        raise HTTPException(status_code=400, detail="Invalid slide number")
    
    slide = presentation_data["slides"][slide_number]
    
    # Add image data if available
    slide_with_images = slide.copy()
    if slide.get("relevant_pages"):
        images = []
        for page in slide["relevant_pages"]:
            if page.get("full_page_image") and os.path.exists(page["full_page_image"]):
                # Convert to base64 for web display
                import base64
                with open(page["full_page_image"], "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode()
                    images.append({
                        "page_number": page["page_number"],
                        "data": f"data:image/png;base64,{img_data}"
                    })
        slide_with_images["images"] = images
    
    return slide_with_images

@app.get("/pages/{page_id}/image")
async def get_page_image(page_id: str):
    global pages_data
    
    # Find the page
    for page in pages_data:
        if page["page_id"] == page_id:
            if page.get("full_page_image") and os.path.exists(page["full_page_image"]):
                return FileResponse(page["full_page_image"])
    
    raise HTTPException(status_code=404, detail="Image not found")

@app.delete("/chat/clear")
async def clear_chat():
    global chatbot
    
    if chatbot:
        chatbot.clear_history()
    
    return {"status": "success", "message": "Chat history cleared"}

@app.get("/status")
async def get_status():
    return {
        "status": "connected",
        "pdfs_loaded": len(pages_data) > 0,
        "pages_count": len(pages_data),
        "has_presentation": presentation_data is not None,
        "presentation_slides": len(presentation_data["slides"]) if presentation_data else 0
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)