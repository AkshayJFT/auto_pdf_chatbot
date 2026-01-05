import streamlit as st
import os
import tempfile
import time
from pdf_processor import PDFProcessor
from vector_store import VectorStore
from streaming_chatbot import StreamingChatbot
from presentation_generator import PresentationGenerator
from PIL import Image

# Page config
st.set_page_config(
    page_title="PDF Chatbot Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for chat UI
st.markdown("""
<style>
.chat-container {
    max-height: 600px;
    overflow-y: auto;
    padding: 1rem;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    background-color: #f9f9f9;
}

.user-message {
    background-color: #007bff;
    color: white;
    padding: 10px 15px;
    border-radius: 15px 15px 5px 15px;
    margin: 10px 0;
    margin-left: 20%;
    text-align: right;
}

.assistant-message {
    background-color: #e9ecef;
    color: #333;
    padding: 10px 15px;
    border-radius: 15px 15px 15px 5px;
    margin: 10px 0;
    margin-right: 20%;
}

.context-info {
    background-color: #fff3cd;
    padding: 5px 10px;
    border-radius: 5px;
    font-size: 0.8em;
    margin: 5px 0;
}

.slide-container {
    border: 2px solid #007bff;
    border-radius: 10px;
    padding: 20px;
    margin: 10px 0;
    background-color: white;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    if 'vector_store' not in st.session_state:
        st.session_state.vector_store = None
    if 'streaming_chatbot' not in st.session_state:
        st.session_state.streaming_chatbot = None
    if 'presentation_generator' not in st.session_state:
        st.session_state.presentation_generator = None
    if 'processed_pdfs' not in st.session_state:
        st.session_state.processed_pdfs = False
    if 'pages_data' not in st.session_state:
        st.session_state.pages_data = []
    if 'presentation_data' not in st.session_state:
        st.session_state.presentation_data = None
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    if 'current_slide' not in st.session_state:
        st.session_state.current_slide = 0
    if 'show_presentation' not in st.session_state:
        st.session_state.show_presentation = False
    if 'related_pages' not in st.session_state:
        st.session_state.related_pages = []

def display_chat_message(message_type: str, content: str, context_info: str = None):
    """Display a chat message with proper styling"""
    if message_type == "user":
        st.markdown(f'<div class="user-message">{content}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="assistant-message">{content}</div>', unsafe_allow_html=True)
        if context_info:
            st.markdown(f'<div class="context-info">{context_info}</div>', unsafe_allow_html=True)

def display_related_pages(pages: list):
    """Display related pages in a compact format"""
    if not pages:
        return
    
    st.markdown("### 📄 Related Pages")
    for page in pages[:3]:  # Show top 3 pages
        with st.expander(f"📄 {page['pdf_name']} - Page {page['page_number']} (Score: {page.get('similarity_score', 0):.3f})"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                text_preview = page['text'][:300] + "..." if len(page['text']) > 300 else page['text']
                st.write(text_preview)
            
            with col2:
                if page.get('full_page_image') and os.path.exists(page['full_page_image']):
                    try:
                        page_image = Image.open(page['full_page_image'])
                        st.image(page_image, caption=f"Page {page['page_number']}", use_column_width=True)
                    except Exception as e:
                        st.error(f"Error loading image: {e}")

def display_presentation_slide(slide_data, presentation_data):
    """Display a presentation slide in chat mode"""
    st.markdown('<div class="slide-container">', unsafe_allow_html=True)
    
    # Slide header
    st.markdown(f"## 🎯 {slide_data['title']}")
    st.markdown(f"**Slide {slide_data['slide_number']} of {presentation_data['total_slides']}**")
    
    # Navigation
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        if st.button("◀️ Previous", key=f"prev_{slide_data['slide_number']}"):
            if st.session_state.current_slide > 0:
                st.session_state.current_slide -= 1
                st.experimental_rerun()
    
    with col2:
        if st.button("▶️ Next", key=f"next_{slide_data['slide_number']}"):
            max_slide = len(presentation_data['slides']) - 1
            if st.session_state.current_slide < max_slide:
                st.session_state.current_slide += 1
                st.experimental_rerun()
    
    with col3:
        if st.button("📋 All Slides", key=f"overview_{slide_data['slide_number']}"):
            st.session_state.show_presentation = False
            st.experimental_rerun()
    
    with col4:
        if st.button("❌ Close", key=f"close_{slide_data['slide_number']}"):
            st.session_state.show_presentation = False
            st.experimental_rerun()
    
    # Content layout
    col_content, col_visual = st.columns([2, 1])
    
    with col_content:
        st.markdown("### 📋 Content")
        st.markdown(slide_data['content'])
        
        if slide_data.get('relevant_pages'):
            page_nums = [str(p['page_number']) for p in slide_data['relevant_pages']]
            st.info(f"📄 Based on pages: {', '.join(page_nums)}")
    
    with col_visual:
        st.markdown("### 🖼️ Visuals")
        if slide_data.get('relevant_pages'):
            for page in slide_data['relevant_pages']:
                if page.get('full_page_image') and os.path.exists(page['full_page_image']):
                    try:
                        page_image = Image.open(page['full_page_image'])
                        st.image(page_image, caption=f"Page {page['page_number']}", use_column_width=True)
                    except:
                        pass
        else:
            st.info("No visuals for this slide")
    
    st.markdown('</div>', unsafe_allow_html=True)

def main():
    init_session_state()
    
    st.title("🤖 PDF Chatbot Pro")
    st.markdown("*Upload PDFs, chat with streaming responses, and view presentations!*")
    
    # Sidebar for PDF upload and controls
    with st.sidebar:
        st.header("📁 PDF Upload")
        
        # File uploader
        uploaded_files = st.file_uploader(
            "Choose PDF files",
            type="pdf",
            accept_multiple_files=True,
            help="Upload multiple PDF files"
        )
        
        if uploaded_files and st.button("🔄 Process PDFs"):
            with st.spinner("Processing PDFs and creating embeddings..."):
                # Initialize components
                if st.session_state.vector_store is None:
                    st.session_state.vector_store = VectorStore()
                if st.session_state.streaming_chatbot is None:
                    st.session_state.streaming_chatbot = StreamingChatbot(st.session_state.vector_store)
                if st.session_state.presentation_generator is None:
                    st.session_state.presentation_generator = PresentationGenerator()
                
                # Save and process files
                temp_paths = []
                for uploaded_file in uploaded_files:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(uploaded_file.getvalue())
                        temp_paths.append(tmp.name)
                
                # Process PDFs
                processor = PDFProcessor()
                pages_data = processor.process_multiple_pdfs(temp_paths)
                st.session_state.pages_data = pages_data
                
                # Create embeddings
                st.session_state.vector_store.create_embeddings(pages_data)
                st.session_state.processed_pdfs = True
                
                # Clean up
                for temp_path in temp_paths:
                    os.unlink(temp_path)
                
                st.success(f"Processed {len(pages_data)} pages!")
        
        st.markdown("---")
        
        # Presentation controls
        if st.session_state.processed_pdfs:
            st.header("🎯 Presentation")
            
            if st.button("📊 Generate Presentation"):
                with st.spinner("Creating presentation..."):
                    st.session_state.presentation_data = st.session_state.presentation_generator.create_full_presentation(
                        st.session_state.pages_data
                    )
                    st.success(f"Generated {st.session_state.presentation_data['total_slides']} slides!")
            
            if st.session_state.presentation_data:
                if st.button("🎯 Show Presentation"):
                    st.session_state.show_presentation = True
                    st.experimental_rerun()
                
                st.info(f"Presentation ready: {st.session_state.presentation_data['total_slides']} slides")
        
        st.markdown("---")
        
        # Chat controls
        st.header("💬 Chat Controls")
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_messages = []
            if st.session_state.streaming_chatbot:
                st.session_state.streaming_chatbot.clear_history()
            st.experimental_rerun()
        
        if st.session_state.streaming_chatbot:
            st.text_area(
                "Conversation Summary:",
                st.session_state.streaming_chatbot.get_conversation_summary(),
                height=150,
                disabled=True
            )
    
    # Main content area
    if not st.session_state.processed_pdfs:
        st.info("👆 Please upload and process your PDF files using the sidebar")
        st.markdown("""
        ### 🚀 Features:
        - **Streaming Chat**: Real-time responses with conversation memory
        - **RAG (Retrieval Augmented Generation)**: Answers from your PDF context
        - **Presentation Mode**: Auto-generated slides from PDF content
        - **Visual Context**: See related pages and images with responses
        - **Conversation History**: Maintains context across questions
        """)
        return
    
    # Display presentation if active
    if st.session_state.show_presentation and st.session_state.presentation_data:
        current_slide_data = st.session_state.presentation_data['slides'][st.session_state.current_slide]
        display_presentation_slide(current_slide_data, st.session_state.presentation_data)
        return
    
    # Chat interface
    st.header("💬 Chat Interface")
    
    # Chat history display
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.chat_messages:
            if message["role"] == "user":
                display_chat_message("user", message["content"])
            else:
                context_info = message.get("context_info", "")
                display_chat_message("assistant", message["content"], context_info)
    
    # Chat input
    user_input = st.chat_input("Ask a question about your PDFs...")
    
    if user_input:
        # Add user message
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        # Display user message immediately
        with chat_container:
            display_chat_message("user", user_input)
        
        # Generate streaming response
        if st.session_state.streaming_chatbot:
            # Get related pages for context
            related_pages = st.session_state.streaming_chatbot.get_related_pages(user_input)
            st.session_state.related_pages = related_pages
            
            # Create container for streaming response
            response_container = st.empty()
            full_response = ""
            
            # Stream the response
            for chunk in st.session_state.streaming_chatbot.generate_streaming_response(user_input):
                full_response += chunk
                response_container.markdown(f'<div class="assistant-message">{full_response}</div>', unsafe_allow_html=True)
                time.sleep(0.02)  # Small delay for visual effect
            
            # Add context info
            if related_pages:
                context_info = f"📄 Based on {len(related_pages)} related pages"
                st.session_state.chat_messages.append({
                    "role": "assistant", 
                    "content": full_response,
                    "context_info": context_info
                })
            else:
                st.session_state.chat_messages.append({"role": "assistant", "content": full_response})
            
            # Show related pages
            if related_pages:
                with st.expander("📄 View Related Pages"):
                    display_related_pages(related_pages)
        
        st.experimental_rerun()

if __name__ == "__main__":
    main()