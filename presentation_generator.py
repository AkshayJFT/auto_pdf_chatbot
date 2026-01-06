import openai
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from models import PresentationSegment
from typing import Optional
import base64
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class PresentationGenerator:
    def __init__(self):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.segments: List[PresentationSegment] = []
        self.pages_data: List[Dict[str, Any]] = []
        
    def analyze_pdf_structure(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the PDF structure to create presentation outline"""
        
        # Combine all text content
        full_content = ""
        for page in pages_data:
            full_content += f"\n--- Page {page['page_number']} ---\n"
            full_content += page['text']
        
        # Analyze content structure
        analysis_prompt = f"""
        Analyze this PDF content and create a brief presentation structure for visual storytelling:
        
        {full_content[:8000]}...
        
        Create 4-6 concise segments that focus on:
        1. Brief introduction (what this is about)
        2. Key features and benefits 
        3. Product types or categories
        4. Customization options (colors, designs, etc.)
        5. Conclusion with main value proposition
        
        Each segment should be BRIEF (2-3 sentences max) since images will tell most of the story.
        
        Format as JSON:
        {{
            "title": "Main Product/Topic",
            "subtitle": "Brief tagline", 
            "slides": [
                {{
                    "slide_number": 1,
                    "focus_area": "Introduction",
                    "key_points": ["Brief point 1", "Brief point 2"],
                    "relevant_pages": [1, 2]
                }}
            ]
        }}
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a presentation expert who creates focused presentations. Create concise content - no slide titles,  compelling points. Focus on: intro → features & benefits → product types → customizations → conclusion. Keep each segment to 3-5 sentences maximum since images will convey most details."},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            content = response.choices[0].message['content']
            # Try to extract JSON from response
            import json
            try:
                return json.loads(content)
            except:
                # Fallback if JSON parsing fails
                return self._create_fallback_structure(pages_data)
                
        except Exception as e:
            print(f"Error analyzing PDF structure: {e}")
            return self._create_fallback_structure(pages_data)
    
    def _create_fallback_structure(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a simple fallback structure if AI analysis fails"""
        return {
            "title": f"{pages_data[0]['pdf_name']}",
            "subtitle": f"Visual presentation with key highlights",
            "slides": [
                {
                    "slide_number": i + 1,
                    "focus_area": f"Section {i + 1}",
                    "key_points": [f"Key content from page {page['page_number']}"],
                    "relevant_pages": [page['page_number']]
                }
                for i, page in enumerate(pages_data[:6])  # Limit to 6 brief slides
            ]
        }
    
    def generate_slide_content(self, slide_info: Dict, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate detailed content for a specific slide"""
        
        # Get relevant pages
        relevant_pages = []
        for page_num in slide_info.get('relevant_pages', []):
            for page in pages_data:
                if page['page_number'] == page_num:
                    relevant_pages.append(page)
        
        # Combine relevant content
        slide_content = ""
        for page in relevant_pages:
            slide_content += f"Page {page['page_number']}: {page['text']}\n"
        
        focus_area = slide_info.get('focus_area', slide_info.get('title', 'Content'))
        content_prompt = f"""
        Create presentation content for: {focus_area}
        
        Based on this content:
        {slide_content[:2000]}...
        
        Requirements:
        - NO slide titles or headers
        - 4-5 sentences  
        - Focus on key benefits and compelling points
        - Speak directly about the product/topic
        - Make it conversational and engaging
        
        Write as natural speaking content, not bullet points. Make sure from provide a clear narrative flow by firstunderstanding the whole context of the PDF. And dont provide content image wise but content and related images.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a presentation expert who creates focused presentations. Create concise content - no slide titles,  compelling points. Focus on: intro → features & benefits → product types → customizations → conclusion. Keep each segment to 3-5 sentences maximum since images will convey most details."},
                    {"role": "user", "content": content_prompt}
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            generated_content = response.choices[0].message['content']
            
            return {
                "slide_number": slide_info['slide_number'],
                "title": slide_info.get('focus_area', slide_info.get('title', 'Content')),
                "content": generated_content,
                "relevant_pages": relevant_pages,
                "has_images": any(page.get('full_page_image') for page in relevant_pages)
            }
            
        except Exception as e:
            print(f"Error generating slide content: {e}")
            # Create brief fallback content
            if slide_content:
                # Use first 200 characters and make it conversational
                content_preview = slide_content[:200].strip()
                # Remove any "Page X:" prefixes
                import re
                content_preview = re.sub(r'^Page \d+:\s*', '', content_preview)
                fallback_content = f"Here we can see {content_preview}..." if content_preview else f"This section highlights key information from the document."
            else:
                fallback_content = f"This visual showcases important details from our product catalog."
            
            return {
                "slide_number": slide_info['slide_number'],
                "title": slide_info.get('focus_area', slide_info.get('title', 'Content')),
                "content": fallback_content,
                "relevant_pages": relevant_pages,
                "has_images": any(page.get('full_page_image') for page in relevant_pages)
            }
    
    def create_full_presentation(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a complete presentation from PDF pages"""
        
        # Store pages data for later use
        self.pages_data = pages_data
        
        # Analyze structure
        structure = self.analyze_pdf_structure(pages_data)
        
        # Generate presentation segments
        self.segments = []
        for i, slide_info in enumerate(structure.get('slides', [])):
            slide_content = self.generate_slide_content(slide_info, pages_data)
            
            # Get relevant page images
            images = []
            for page in slide_content.get('relevant_pages', []):
                if page.get('full_page_image'):
                    try:
                        with open(page['full_page_image'], 'rb') as img_file:
                            img_data = base64.b64encode(img_file.read()).decode()
                            images.append(f"data:image/png;base64,{img_data}")
                    except Exception as e:
                        logger.warning(f"Could not load image {page['full_page_image']}: {e}")
            
            # Create presentation segment
            segment = PresentationSegment(
                id=i,
                text=slide_content['content'],
                images=images,
                duration_seconds=max(5, len(slide_content['content'].split()) // 25),  # ~150 words per minute
                pdf_page=slide_content.get('relevant_pages', [{}])[0].get('page_number'),
                pdf_name=slide_content.get('relevant_pages', [{}])[0].get('pdf_name')
            )
            self.segments.append(segment)
        
        logger.info(f"Created presentation with {len(self.segments)} segments")
        
        return {
            "title": structure.get('title', 'PDF Presentation'),
            "subtitle": structure.get('subtitle', 'Generated Presentation'),
            "total_slides": len(self.segments),
            "slides": [{
                "slide_number": seg.id + 1,
                "title": f"Section {seg.id + 1}",
                "content": seg.text,
                "relevant_pages": seg.pdf_page,
                "has_images": len(seg.images) > 0
            } for seg in self.segments]
        }
    
    def get_segment(self, segment_id: int) -> Optional[PresentationSegment]:
        """Get a specific presentation segment"""
        if 0 <= segment_id < len(self.segments):
            return self.segments[segment_id]
        return None
        
    def get_total_segments(self) -> int:
        """Get total number of presentation segments"""
        return len(self.segments)