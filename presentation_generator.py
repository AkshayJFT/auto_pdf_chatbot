import openai
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class PresentationGenerator:
    def __init__(self):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
    def analyze_pdf_structure(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the PDF structure to create presentation outline"""
        
        # Combine all text content
        full_content = ""
        for page in pages_data:
            full_content += f"\n--- Page {page['page_number']} ---\n"
            full_content += page['text']
        
        # Analyze content structure
        analysis_prompt = f"""
        Analyze this PDF content and create a presentation structure:
        
        {full_content[:4000]}...
        
        Please provide:
        1. Main title/topic of the document
        2. Key sections/chapters (max 8-10 slides)
        3. Brief description of each section
        4. Suggested slide titles
        
        Format as JSON:
        {{
            "title": "Main Title",
            "subtitle": "Brief description", 
            "slides": [
                {{
                    "slide_number": 1,
                    "title": "Introduction",
                    "key_points": ["Point 1", "Point 2"],
                    "relevant_pages": [1, 2]
                }}
            ]
        }}
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a presentation expert who creates structured presentations from documents."},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=1500,
                temperature=0.3
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
            "title": f"{pages_data[0]['pdf_name']} Presentation",
            "subtitle": f"Overview of {len(pages_data)} pages",
            "slides": [
                {
                    "slide_number": i + 1,
                    "title": f"Page {page['page_number']}",
                    "key_points": [page['text'][:100] + "..." if page['text'] else "Visual content"],
                    "relevant_pages": [page['page_number']]
                }
                for i, page in enumerate(pages_data[:10])  # Limit to 10 slides
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
        
        content_prompt = f"""
        Create detailed slide content for: {slide_info['title']}
        
        Based on this content:
        {slide_content[:2000]}...
        
        Provide:
        1. Slide title
        2. Main heading
        3. 3-5 bullet points
        4. Key insights or conclusions
        5. Important details
        
        Format as clear, presentation-ready content.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a presentation expert creating engaging slide content."},
                    {"role": "user", "content": content_prompt}
                ],
                max_tokens=800,
                temperature=0.4
            )
            
            generated_content = response.choices[0].message['content']
            
            return {
                "slide_number": slide_info['slide_number'],
                "title": slide_info['title'],
                "content": generated_content,
                "relevant_pages": relevant_pages,
                "has_images": any(page.get('full_page_image') for page in relevant_pages)
            }
            
        except Exception as e:
            print(f"Error generating slide content: {e}")
            return {
                "slide_number": slide_info['slide_number'],
                "title": slide_info['title'],
                "content": f"Content from pages: {', '.join(map(str, slide_info.get('relevant_pages', [])))}",
                "relevant_pages": relevant_pages,
                "has_images": any(page.get('full_page_image') for page in relevant_pages)
            }
    
    def create_full_presentation(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a complete presentation from PDF pages"""
        
        # Analyze structure
        structure = self.analyze_pdf_structure(pages_data)
        
        # Generate detailed slides
        detailed_slides = []
        for slide_info in structure.get('slides', []):
            slide_content = self.generate_slide_content(slide_info, pages_data)
            detailed_slides.append(slide_content)
        
        return {
            "title": structure.get('title', 'PDF Presentation'),
            "subtitle": structure.get('subtitle', 'Generated Presentation'),
            "total_slides": len(detailed_slides),
            "slides": detailed_slides
        }