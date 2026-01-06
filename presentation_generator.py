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
        
        print(f"\n🔍 STARTING AI-DRIVEN PDF ANALYSIS:")
        print(f"📄 Total PDF pages: {len(pages_data)}")
        
        # Build complete document content for AI analysis
        total_pages = len(pages_data)
        full_content = ""
        page_summaries = []
        
        for i, page in enumerate(pages_data):
            page_text = page.get('text', '')
            page_num = page.get('page_number', i+1)
            has_image = bool(page.get('full_page_image'))
            
            print(f"\n📖 PAGE {page_num} ANALYSIS:")
            print(f"  📝 Text length: {len(page_text)} characters")
            print(f"  🖼️ Has image: {'✓' if has_image else '✗'}")
            
            if page_text:
                # Show first 200 chars of each page
                preview = page_text[:200].replace('\n', ' ').strip()
                print(f"  📄 Content preview: {preview}...")
                
                # Add to full content with clear page markers
                full_content += f"\n--- PAGE {page_num} ---\n{page_text}\n"
                
                # Create page summary for AI
                page_summaries.append({
                    "page": page_num,
                    "content_length": len(page_text),
                    "has_image": has_image,
                    "preview": page_text[:300] + "..." if len(page_text) > 300 else page_text
                })
            else:
                print(f"  ⚠️ No text content found on page {page_num}")
        
        print(f"📊 Document statistics:")
        print(f"  - Total pages: {total_pages}")
        print(f"  - Pages with text: {len([p for p in page_summaries if p['content_length'] > 0])}")
        print(f"  - Pages with images: {len([p for p in page_summaries if p['has_image']])}")
        
        # Send EVERYTHING to AI for intelligent analysis
        analysis_prompt = f"""
        You are analyzing a {total_pages}-page product catalog/document. Your task is to create a comprehensive presentation structure that covers ALL content systematically.

        COMPLETE DOCUMENT CONTENT:
        {full_content}

        TASK: Create a presentation that covers the ENTIRE document comprehensively. 

        REQUIREMENTS:
        1. Analyze ALL content and identify natural sections/topics
        2. Create enough slides to cover everything important (aim for {max(8, total_pages // 6)} to {min(25, total_pages // 4)} slides)
        3. Group related pages together intelligently 
        4. Ensure each major topic/product gets adequate coverage
        5. Don't skip content - be comprehensive
        6. Assign specific page ranges to each slide based on content relevance

        SLIDE STRUCTURE GUIDELINES:
        - Start with introduction/overview (typically pages 1-3)
        - Create dedicated slides for each major product category or topic section
        - Group 2-4 related pages per slide maximum
        - End with conclusion/warranty/contact (typically last few pages)

        OUTPUT FORMAT (JSON):
        {{
            "title": "Document Title",
            "subtitle": "Brief description",
            "total_pages_analyzed": {total_pages},
            "slides": [
                {{
                    "slide_number": 1,
                    "focus_area": "Descriptive slide title",
                    "category": "intro|features|products|customization|conclusion",
                    "relevant_pages": [1, 2, 3],
                    "content_summary": "Brief summary of what this slide covers",
                    "image_strategy": "show_multiple"
                }}
            ]
        }}

        Be thorough - this should be a comprehensive presentation covering the entire document!
        """
        
        print(f"\n🤖 SENDING TO AI FOR ANALYSIS:")
        print(f"  📊 Total content size: {len(full_content)} characters")
        print(f"  📋 Sample content being sent to AI (first 500 chars):")
        print(f"     {full_content[:500]}")
        print(f"  🎯 Requesting {max(8, total_pages // 6)} to {min(25, total_pages // 4)} slides")
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert presentation analyst. Create comprehensive, intelligent slide structures that cover entire documents systematically. Always output valid JSON."},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=4000,
                temperature=0.1
            )
            
            content = response.choices[0].message['content']
            print(f"\n🧠 AI RESPONSE RECEIVED:")
            print(f"  📊 Response length: {len(content)} characters")
            print(f"  📋 Raw AI response (first 1000 chars):")
            print(f"     {content[:1000]}...")
            
            # Extract JSON from response
            import json
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_content = json_match.group()
                print(f"\n📝 EXTRACTED JSON ({len(json_content)} chars):")
                print(f"     {json_content[:500]}...")
                
                structure = json.loads(json_content)
                slides_count = len(structure.get('slides', []))
                print(f"\n✅ AI SUCCESSFULLY GENERATED {slides_count} SLIDES for {total_pages} pages")
                print(f"📊 Title: {structure.get('title', 'Unknown')}")
                print(f"📊 Subtitle: {structure.get('subtitle', 'Unknown')}")
                
                # Show detailed slide breakdown
                print(f"\n📋 DETAILED AI-GENERATED SLIDE STRUCTURE:")
                for i, slide in enumerate(structure.get('slides', [])):
                    focus = slide.get('focus_area', 'Unknown')
                    pages = slide.get('relevant_pages', [])
                    category = slide.get('category', 'general')
                    summary = slide.get('content_summary', 'No summary')
                    print(f"\n  🎯 SLIDE {i+1}: {focus}")
                    print(f"     Category: {category}")
                    print(f"     Pages: {pages}")
                    print(f"     Summary: {summary}")
                
                return structure
            else:
                print("❌ Could not parse AI JSON response")
                return self._create_smart_fallback(pages_data)
                
        except Exception as e:
            print(f"❌ AI analysis failed: {e}")
            return self._create_smart_fallback(pages_data)
    
    def _create_smart_fallback(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create intelligent fallback when AI fails"""
        total_pages = len(pages_data)
        target_slides = max(6, min(20, total_pages // 5))  # Reasonable slide count
        pages_per_slide = max(2, total_pages // target_slides)
        
        slides = []
        for i in range(target_slides):
            start_page = i * pages_per_slide + 1
            end_page = min((i + 1) * pages_per_slide, total_pages)
            
            if i == 0:
                focus_area = "Introduction & Overview"
                category = "intro"
            elif i == target_slides - 1:
                focus_area = "Summary & Conclusion"
                category = "conclusion"
            else:
                focus_area = f"Section {i}: Content Overview"
                category = "products"
            
            slides.append({
                "slide_number": i + 1,
                "focus_area": focus_area,
                "category": category,
                "relevant_pages": list(range(start_page, end_page + 1)),
                "image_strategy": "show_multiple"
            })
        
        return {
            "title": pages_data[0].get('pdf_name', 'Document'),
            "subtitle": "Intelligent Content Analysis",
            "total_pages_analyzed": total_pages,
            "slides": slides
        }
    
    def _create_fallback_structure(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a simple fallback structure if AI analysis fails"""
        return self._create_dynamic_fallback_structure(pages_data, 6)
    
    def _create_dynamic_fallback_structure(self, pages_data: List[Dict[str, Any]], target_slides: int) -> Dict[str, Any]:
        """Create a dynamic fallback structure based on page count"""
        slides = []
        pages_per_slide = max(1, len(pages_data) // target_slides)
        
        # Introduction slide
        slides.append({
            "slide_number": 1,
            "focus_area": "Introduction",
            "category": "intro",
            "key_points": ["Welcome to our product catalog", "Discover our range of solutions"],
            "relevant_pages": list(range(1, min(4, len(pages_data) + 1))),
            "image_strategy": "show_multiple"
        })
        
        # Content slides
        for i in range(1, target_slides - 1):
            start_page = (i - 1) * pages_per_slide + 1
            end_page = min(i * pages_per_slide + 1, len(pages_data))
            slides.append({
                "slide_number": i + 1,
                "focus_area": f"Products Section {i}",
                "category": "products",
                "key_points": [f"Showcasing items from pages {start_page}-{end_page}"],
                "relevant_pages": list(range(start_page, end_page + 1)),
                "image_strategy": "show_multiple"
            })
        
        # Conclusion slide
        slides.append({
            "slide_number": target_slides,
            "focus_area": "Conclusion",
            "category": "conclusion",
            "key_points": ["Thank you for exploring our catalog"],
            "relevant_pages": [len(pages_data)],
            "image_strategy": "single"
        })
        
        return {
            "title": f"{pages_data[0]['pdf_name']}",
            "subtitle": f"Comprehensive catalog presentation",
            "total_pages_analyzed": len(pages_data),
            "slides": slides
        }
    

    def generate_slide_content(self, slide_info: Dict, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate detailed content for a specific slide"""
        
        slide_num = slide_info.get('slide_number', 0)
        focus_area = slide_info.get('focus_area', 'Unknown')
        print(f"\n🎯 GENERATING SLIDE {slide_num}: {focus_area}")
        
        # Get relevant pages
        relevant_pages = []
        requested_pages = slide_info.get('relevant_pages', [])
        print(f"📄 Requested pages: {requested_pages}")
        
        for page_num in requested_pages:
            for page in pages_data:
                if page['page_number'] == page_num:
                    relevant_pages.append(page)
                    page_text = page.get('text', '')
                    preview = page_text[:150].replace('\n', ' ') if page_text else 'No text'
                    print(f"  ✓ Found page {page_num}: {len(page_text)} chars, Image: {'✓' if page.get('full_page_image') else '✗'}")
                    print(f"    📄 Content: {preview}...")
        
        if not relevant_pages:
            relevant_pages = pages_data[:3]  # Fallback to first 3 pages
            print(f"⚠️ No requested pages found, using fallback: pages 1-3")
        
        # Combine relevant content and show what's being sent to AI
        slide_content = ""
        print(f"\n📝 COMBINING CONTENT FOR AI:")
        for page in relevant_pages:
            page_text = page.get('text', '')
            slide_content += f"Page {page['page_number']}: {page_text}\n"
            print(f"  📖 Added page {page['page_number']}: {len(page_text)} characters")
        
        print(f"📊 Total content for this slide: {len(slide_content)} characters")
        print(f"🤖 FULL CONTENT being sent to AI ({len(slide_content)} chars):")
        print(f"   📝 First 400 chars: {slide_content[:400]}...")
        if len(slide_content) > 600:
            print(f"   📝 Last 200 chars: ...{slide_content[-200:]}")
        print(f"   ✅ Complete content (not truncated) will be sent to AI")
        
        focus_area = slide_info.get('focus_area', slide_info.get('title', 'Content'))
        category = slide_info.get('category', 'general')
        image_strategy = slide_info.get('image_strategy', 'show_multiple')
        
        # Extract key information from the content
        page_numbers = [p.get('page_number', 0) for p in relevant_pages]
        
        # Build detailed, context-aware content
        content_prompt = f"""
        Create detailed presentation content for: {focus_area}
        
        Content context:
        - Covers pages: {page_numbers}
        - Number of related pages: {len(relevant_pages)}
        
        Source content from these specific pages:
        {slide_content}
        
        Requirements:
        - Create comprehensive content (6-8 sentences)
        - Reference specific features, models, or benefits mentioned in the source
        - Mention page ranges when relevant (\"As shown on pages X-Y\")
        - Be specific about product details (names, features, benefits)
        - Flow naturally while being informative
        - Since multiple images will be shown, reference variety and different aspects
        - Use the actual product names and technical terms from the source material
        
        Focus areas by category:
        - intro: Brand introduction, heritage, manufacturing quality
        - features: Specific technologies, engineering details, performance benefits
        - energy: Energy ratings, glass systems, efficiency measures
        - products: Detailed product specifications, styles, operation features
        - customization: Color options, design choices, personalization features
        - conclusion: Warranty details, support, company commitment
        
        Write as natural, informative speaking content that teaches the viewer about the products.
        """
        
        print(f"\n🤖 SENDING CONTENT GENERATION REQUEST TO AI...")
        print(f"🎯 Slide focus: {focus_area}")
        print(f"📂 Category: {category}")
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"You are creating content for a visual presentation slide in the '{category}' section. The slide will display multiple product images sequentially while you speak. Create engaging narrative that works with visual storytelling."},
                    {"role": "user", "content": content_prompt}
                ],
                max_tokens=400,
                temperature=0.2
            )
            
            generated_content = response.choices[0].message['content']
            
            print(f"\n✅ AI GENERATED CONTENT FOR SLIDE:")
            print(f"📝 Generated content ({len(generated_content)} chars):")
            print(f"   {generated_content}")
            print(f"\n📊 Slide completion summary:")
            print(f"   - Pages used: {[p.get('page_number') for p in relevant_pages]}")
            print(f"   - Images available: {sum(1 for p in relevant_pages if p.get('full_page_image'))}")
            print(f"   - Content length: {len(generated_content)} characters")
            
            return {
                "slide_number": slide_info['slide_number'],
                "title": slide_info.get('focus_area', slide_info.get('title', 'Content')),
                "content": generated_content,
                "relevant_pages": relevant_pages,
                "has_images": any(page.get('full_page_image') for page in relevant_pages),
                "category": category,
                "image_strategy": image_strategy
            }
            
        except Exception as e:
            logger.error(f"Error generating slide content: {e}")
            # Create category-appropriate fallback content
            if category == 'intro':
                fallback_content = "Welcome to our comprehensive catalog. Let's explore the exceptional range of products and solutions we offer."
            elif category == 'products':
                fallback_content = f"Here you can see our diverse selection showcasing quality and innovation across {len(relevant_pages)} different options."
            elif category == 'customization':
                fallback_content = "We offer extensive customization options to perfectly match your specific requirements and preferences."
            else:
                fallback_content = "This section highlights important features and benefits from our collection."
            
            return {
                "slide_number": slide_info['slide_number'],
                "title": slide_info.get('focus_area', slide_info.get('title', 'Content')),
                "content": fallback_content,
                "relevant_pages": relevant_pages,
                "has_images": any(page.get('full_page_image') for page in relevant_pages),
                "category": category,
                "image_strategy": image_strategy
            }
    
    def create_full_presentation(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a complete presentation from PDF pages"""
        
        # Store pages data for later use
        self.pages_data = pages_data
        
        # Analyze structure
        structure = self.analyze_pdf_structure(pages_data)
        
        print(f"\n🔧 CREATING PRESENTATION SEGMENTS...")
        
        # Generate presentation segments
        self.segments = []
        for i, slide_info in enumerate(structure.get('slides', [])):
            print(f"\n📋 Processing slide {i+1}/{len(structure.get('slides', []))}")
            slide_content = self.generate_slide_content(slide_info, pages_data)
            
            # Get relevant page images
            images = []
            print(f"🖼️ Loading images for {len(slide_content.get('relevant_pages', []))} pages...")
            for page in slide_content.get('relevant_pages', []):
                if page.get('full_page_image'):
                    try:
                        with open(page['full_page_image'], 'rb') as img_file:
                            img_data = base64.b64encode(img_file.read()).decode()
                            images.append(f"data:image/png;base64,{img_data}")
                        print(f"  ✓ Loaded image from page {page.get('page_number')}")
                    except Exception as e:
                        print(f"  ❌ Failed to load image from page {page.get('page_number')}: {e}")
                else:
                    print(f"  ⚪ No image on page {page.get('page_number')}")
            
            # Calculate timing for images
            words = slide_content['content'].split()
            total_duration = max(8, len(words) / 2.5)  # ~150 words per minute, minimum 8 seconds
            
            image_timing = None
            if len(images) > 1:
                # Distribute images evenly throughout the speech
                image_timing = []
                for j in range(len(images)):
                    timing = (total_duration / len(images)) * j
                    image_timing.append(timing)
                print(f"⏰ Image timing calculated: {[f'{t:.1f}s' for t in image_timing]}")
            
            print(f"📊 Slide summary:")
            print(f"  - Duration: {total_duration:.1f} seconds")
            print(f"  - Images: {len(images)}")
            print(f"  - Category: {slide_content.get('category', 'general')}")
            print(f"  - Strategy: {slide_content.get('image_strategy', 'show_multiple')}")
            print(f"  - Text preview: {slide_content['content'][:100]}...")
            
            # Create presentation segment
            segment = PresentationSegment(
                id=i,
                text=slide_content['content'],
                images=images,
                duration_seconds=int(total_duration),
                pdf_page=slide_content.get('relevant_pages', [{}])[0].get('page_number'),
                pdf_name=slide_content.get('relevant_pages', [{}])[0].get('pdf_name'),
                category=slide_content.get('category', 'general'),
                image_strategy=slide_content.get('image_strategy', 'show_multiple'),
                image_timing=image_timing
            )
            self.segments.append(segment)
        
        print(f"\n🎉 PRESENTATION CREATION COMPLETE!")
        print(f"📊 Final Statistics:")
        print(f"  - Total slides: {len(self.segments)}")
        print(f"  - Total duration: {sum(seg.duration_seconds for seg in self.segments)} seconds")
        print(f"  - Slides with images: {len([seg for seg in self.segments if seg.images])}")
        print(f"  - Total images: {sum(len(seg.images) for seg in self.segments)}")
        
        category_breakdown = {}
        for seg in self.segments:
            cat = getattr(seg, 'category', 'general')
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
        print(f"  - Category breakdown: {category_breakdown}")
        
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