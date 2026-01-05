import streamlit as st
import os
import tempfile
from pdf_processor import PDFProcessor
from vector_store import VectorStore
from chatbot import PDFChatbot
from PIL import Image

# Page config
st.set_page_config(
    page_title="PDF Chatbot",
    page_icon="📚",
    layout="wide"
)

# Initialize session state
if 'vector_store' not in st.session_state:
    st.session_state.vector_store = None
if 'chatbot' not in st.session_state:
    st.session_state.chatbot = None
if 'processed_pdfs' not in st.session_state:
    st.session_state.processed_pdfs = False
if 'current_page_index' not in st.session_state:
    st.session_state.current_page_index = 0
if 'search_results' not in st.session_state:
    st.session_state.search_results = []

def display_page_content(page_data):
    """Display a single page's content with full page image"""
    st.subheader(f"📄 {page_data['pdf_name']} - Page {page_data['page_number']}")
    
    # Create two columns: text on left, page image on right
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Display text content
        st.write("**Text Content:**")
        if page_data['text']:
            # Limit text length for better layout
            text_preview = page_data['text'][:500] + "..." if len(page_data['text']) > 500 else page_data['text']
            st.write(text_preview)
            if len(page_data['text']) > 500:
                with st.expander("Show full text"):
                    st.write(page_data['text'])
        else:
            st.write("*No text content found on this page*")
    
    with col2:
        # Display full page image
        st.write("**Full Page:**")
        if 'full_page_image' in page_data and os.path.exists(page_data['full_page_image']):
            try:
                page_image = Image.open(page_data['full_page_image'])
                st.image(page_image, caption=f"Page {page_data['page_number']}", use_column_width=True)
            except Exception as e:
                st.error(f"Error loading page image: {e}")
        else:
            st.warning("Full page image not available")
            
            # Fallback: show individual extracted images if available
            if page_data.get('images'):
                st.write(f"**Extracted Images ({len(page_data['images'])}):**")
                for i, img_info in enumerate(page_data['images']):
                    try:
                        if os.path.exists(img_info['image_path']):
                            image = Image.open(img_info['image_path'])
                            st.image(image, caption=f"Image {i+1}", width=200)
                    except Exception as e:
                        st.error(f"Error loading image: {e}")

def main():
    st.title("📚 PDF Chatbot with Images")
    st.markdown("Upload PDFs and chat with their content while viewing related images!")
    
    # Sidebar for PDF upload and processing
    with st.sidebar:
        st.header("📁 PDF Upload")
        
        # File uploader
        uploaded_files = st.file_uploader(
            "Choose PDF files",
            type="pdf",
            accept_multiple_files=True,
            help="Upload multiple PDF files to create your knowledge base"
        )
        
        if uploaded_files and st.button("Process PDFs"):
            with st.spinner("Processing PDFs..."):
                # Initialize vector store and chatbot
                if st.session_state.vector_store is None:
                    st.session_state.vector_store = VectorStore()
                if st.session_state.chatbot is None:
                    st.session_state.chatbot = PDFChatbot()
                
                # Save uploaded files temporarily
                temp_paths = []
                for uploaded_file in uploaded_files:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(uploaded_file.getvalue())
                        temp_paths.append(tmp.name)
                
                # Process PDFs
                processor = PDFProcessor()
                pages_data = processor.process_multiple_pdfs(temp_paths)
                
                # Create embeddings
                st.session_state.vector_store.create_embeddings(pages_data)
                st.session_state.processed_pdfs = True
                
                # Clean up temporary files
                for temp_path in temp_paths:
                    os.unlink(temp_path)
                
                st.success(f"Processed {len(pages_data)} pages from {len(uploaded_files)} PDFs!")
        
        st.markdown("---")
        
        # View mode selection
        st.header("👀 View Mode")
        view_mode = st.radio(
            "Choose viewing style:",
            ["Multiple Pages", "Single Page", "Chat Only"],
            help="Select how to display search results"
        )
        
        if st.session_state.search_results:
            st.info(f"Found {len(st.session_state.search_results)} relevant pages")
    
    # Main area
    if not st.session_state.processed_pdfs:
        st.info("👆 Please upload and process your PDF files using the sidebar")
        st.markdown("""
        ### How to use:
        1. **Upload PDFs**: Use the sidebar to upload your PDF files
        2. **Process**: Click 'Process PDFs' to extract content and create searchable embeddings
        3. **Chat**: Ask questions about your PDFs
        4. **View**: Choose between different viewing modes to see results
        """)
        return
    
    # Chat interface
    st.header("💬 Chat with your PDFs")
    
    # Query input
    query = st.text_input(
        "Ask a question about your PDFs:",
        placeholder="e.g., What are the key findings? How does process X work?",
        key="user_query"
    )
    
    if query:
        if st.session_state.vector_store is None:
            st.error("Please upload and process PDFs first!")
            return
            
        with st.spinner("Searching and generating response..."):
            # Search for relevant pages
            search_results = st.session_state.vector_store.search(query, k=5)
            st.session_state.search_results = search_results
            st.session_state.current_page_index = 0
            
            # Generate response
            response = st.session_state.chatbot.generate_response(query, search_results)
            
            # Display response
            st.markdown("**🤖 Response:**")
            st.write(response)
    
    # Display results based on view mode
    if st.session_state.search_results:
        st.markdown("---")
        
        if view_mode == "Single Page":
            st.header("📖 Page View")
            
            # Navigation
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                if st.button("← Previous") and st.session_state.current_page_index > 0:
                    st.session_state.current_page_index -= 1
                    st.experimental_rerun()
            
            with col2:
                st.write(f"Page {st.session_state.current_page_index + 1} of {len(st.session_state.search_results)}")
            
            with col3:
                if st.button("Next →") and st.session_state.current_page_index < len(st.session_state.search_results) - 1:
                    st.session_state.current_page_index += 1
                    st.experimental_rerun()
            
            # Display current page
            if st.session_state.search_results:
                current_page = st.session_state.search_results[st.session_state.current_page_index]
                display_page_content(current_page)
                
                # Similarity score
                st.caption(f"Relevance Score: {current_page.get('similarity_score', 0):.3f}")
        
        elif view_mode == "Multiple Pages":
            st.header("📚 All Relevant Pages")
            
            for i, page_data in enumerate(st.session_state.search_results):
                st.markdown("---")
                st.subheader(f"📄 {page_data['pdf_name']} - Page {page_data['page_number']} (Score: {page_data.get('similarity_score', 0):.3f})")
                display_page_content(page_data)
    
    # Footer
    st.markdown("---")
    st.markdown("*Built with Streamlit, OpenAI, and PyMuPDF*")

if __name__ == "__main__":
    main()