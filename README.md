# PDF Chatbot with Images

A Streamlit-based chatbot that processes PDFs and allows you to chat with their content while viewing related images.

## Features

- **Page-level Processing**: Extracts text and images from each PDF page
- **OpenAI Integration**: Uses GPT-3.5-turbo for responses and text-embedding-3-small for search
- **Multiple View Modes**:
  - Chat Only: Just the conversation
  - Single Page: Navigate through relevant pages one at a time
  - Multiple Pages: View all relevant pages at once
- **Image Display**: Shows images from relevant PDF pages alongside text
- **Semantic Search**: Find relevant content using vector similarity

## Setup

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Set OpenAI API Key**:
Edit `.env` file and add your OpenAI API key:
```
OPENAI_API_KEY=your_openai_api_key_here
```

3. **Run the Application**:
```bash
streamlit run app.py
```

## How to Use

1. **Upload PDFs**: Use the sidebar to upload your PDF files (supports multiple files)
2. **Process**: Click 'Process PDFs' to extract content and create searchable embeddings
3. **Chat**: Ask questions about your PDFs in natural language
4. **View Results**: Choose your preferred viewing mode:
   - **Single Page**: Navigate through relevant pages with Previous/Next buttons
   - **Multiple Pages**: See all relevant pages in expandable sections

## Example Queries

- "What are the main conclusions?"
- "How does the authentication process work?"
- "Show me information about data analysis methods"
- "What charts or graphs are available?"

## File Structure

- `app.py`: Main Streamlit application
- `pdf_processor.py`: PDF text and image extraction
- `vector_store.py`: OpenAI embeddings and FAISS vector search
- `chatbot.py`: OpenAI chat integration
- `processed_pdfs/`: Directory for extracted images and data
- `.env`: Environment variables (API keys)

## Technical Details

- **PDF Processing**: PyMuPDF for text and image extraction
- **Vector Search**: FAISS with OpenAI embeddings
- **Chat**: OpenAI GPT-3.5-turbo with conversation memory
- **UI**: Streamlit with responsive image display