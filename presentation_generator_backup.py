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

    def _segment_content_intelligently(self, slide_info: Dict, pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use AI to intelligently segment content into focused segments"""
        
        slide_num = slide_info.get('slide_number', 0)
        focus_area = slide_info.get('focus_area', 'Unknown')
        print(f"\n🧠 AI SEGMENTATION FOR SLIDE {slide_num}: {focus_area}")
        
        # Get relevant pages
        relevant_pages = []
        requested_pages = slide_info.get('relevant_pages', [])
        print(f"📄 Analyzing pages: {requested_pages}")
        
        for page_num in requested_pages:
            for page in pages_data:
                if page['page_number'] == page_num:
                    relevant_pages.append(page)
                    page_text = page.get('text', '')
                    preview = page_text[:100].replace('\n', ' ') if page_text else 'No text'
                    print(f"  📖 Page {page_num}: {len(page_text)} chars - {preview}...")
        
        if not relevant_pages:
            relevant_pages = pages_data[:3]
            print(f"⚠️ Using fallback: pages 1-3")
        
        # Combine content for AI analysis
        combined_content = ""
        page_details = []
        for page in relevant_pages:
            page_text = page.get('text', '')
            combined_content += f"PAGE {page['page_number']}:\n{page_text}\n\n"
            page_details.append({
                "page_number": page['page_number'],
                "content_length": len(page_text),
                "has_image": bool(page.get('full_page_image'))
            })
        
        print(f"📊 Total content: {len(combined_content)} characters across {len(relevant_pages)} pages")
        
        # Ask AI to intelligently segment the content
        segmentation_prompt = f"""
        Analyze this content and intelligently create focused segments based on the document structure.
        
        CONTENT TO SEGMENT:
        {combined_content}
        
        PAGE DETAILS:
        {page_details}
        
        ANALYZE THE CONTENT AND DETERMINE:
        1. Is each page describing a completely different product/item? (e.g., different door models, window types, product variants)
        2. Are pages describing different aspects of the same topic? (e.g., features, benefits, specifications of one product)
        3. Is there a natural grouping that makes sense? (e.g., similar products, related features)
        
        SEGMENTATION APPROACH:
        - If you detect that each page is a distinct product → Create ONE SEGMENT PER PAGE
        - If pages are variations of the same product → Group by meaningful distinctions
        - If pages flow as one topic → Create fewer, more comprehensive segments
        - Trust your analysis of the content structure
        
        Maximum segments allowed: {len(page_details)} (you can create one per page if needed)
        
        OUTPUT JSON FORMAT:
        {{
            "segments": [
                {{
                    "segment_title": "Extract the specific name/title from the content",
                    "relevant_pages": [page_numbers],
                    "main_topic": "What this segment specifically covers",
                    "content_summary": "Key information about this segment"
                }}
            ]
        }}
        
        Focus area: {focus_area}
        Category: {slide_info.get('category', 'general')}
        
        IMPORTANT: Let the content guide your segmentation. If it's a product catalog with 15 different doors, create 15 segments. If it's a feature document, group related content logically.
        """
        
        try:
            print(f"🤖 REQUESTING AI SEGMENTATION...")
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert content analyzer. Analyze document structure and create intelligent segments. If each page is a distinct product/item, create individual segments. If pages flow together, group them logically. Let the content structure guide you. Always output valid JSON."},
                    {"role": "user", "content": segmentation_prompt}
                ],
                max_tokens=1500,
                temperature=0.1
            )
            
            content = response.choices[0].message['content']
            print(f"📝 AI segmentation response: {content[:300]}...")
            
            # Parse JSON response
            import json
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                segmentation = json.loads(json_match.group())
                segments = segmentation.get('segments', [])
                
                print(f"✅ AI CREATED {len(segments)} FOCUSED SEGMENTS:")
                for i, seg in enumerate(segments):
                    print(f"  🎯 Segment {i+1}: {seg.get('segment_title', 'Unknown')}")
                    print(f"     📄 Pages: {seg.get('relevant_pages', [])}")
                    print(f"     🏷️ Topic: {seg.get('main_topic', 'No topic')}")
                
                return segments
            else:
                print("❌ Could not parse AI segmentation JSON")
                return self._create_single_segment(slide_info, relevant_pages)
                
        except Exception as e:
            print(f"❌ AI segmentation failed: {e}")
            return self._create_single_segment(slide_info, relevant_pages)
    
    def _create_single_segment(self, slide_info: Dict, relevant_pages: List[Dict]) -> List[Dict]:
        """Fallback to create single segment"""
        return [{
            "segment_title": slide_info.get('focus_area', 'Content'),
            "relevant_pages": [p.get('page_number', 0) for p in relevant_pages],
            "main_topic": f"Content from pages {[p.get('page_number', 0) for p in relevant_pages]}",
            "content_summary": slide_info.get('content_summary', 'Product information and details')
        }]

    def generate_slide_content(self, slide_info: Dict, pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate detailed content segments for a slide using AI segmentation"""
        
        # First, intelligently segment the content
        segments = self._segment_content_intelligently(slide_info, pages_data)
        
        slide_segments = []
        
        for seg_idx, segment in enumerate(segments):
            print(f"\n🎯 GENERATING SEGMENT {seg_idx + 1}: {segment.get('segment_title', 'Unknown')}")
            
            # Get pages for this specific segment
            segment_pages = []
            for page_num in segment.get('relevant_pages', []):
                for page in pages_data:
                    if page['page_number'] == page_num:
                        segment_pages.append(page)
                        print(f"  📖 Using page {page_num}: {len(page.get('text', ''))} chars")
            
            if not segment_pages:
                print(f"⚠️ No pages found for segment, skipping")
                continue
            
            # Build segment content
            segment_content = ""
            for page in segment_pages:
                page_text = page.get('text', '')
                segment_content += f"Page {page['page_number']}: {page_text}\n"
            
            print(f"📊 Segment content: {len(segment_content)} characters")
            print(f"🤖 FULL CONTENT for segment (not truncated): {len(segment_content)} chars")
            
            # Generate focused content for this segment
            content_prompt = f"""
            Create detailed presentation content for: {segment.get('segment_title', 'Content')}
            
            FOCUS: {segment.get('main_topic', 'Product information')}
            
            Content from specific pages:
            {segment_content}
            
            Requirements:
            - Create focused content (4-6 sentences) about THIS specific topic only
            - Reference specific features, models, or benefits mentioned in the source
            - Be specific about product details (names, features, benefits)
            - Use actual product names and technical terms from the source material
            - Since this is a focused segment, go deep into the specifics of this topic
            - Mention relevant page numbers when appropriate
            
            Category context: {slide_info.get('category', 'general')}
            Write as natural, informative speaking content about this specific topic.
            """
            
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": f"Create focused presentation content for one specific topic. Be detailed and informative about this single subject."},
                        {"role": "user", "content": content_prompt}
                    ],
                    max_tokens=300,
                    temperature=0.2
                )
                
                generated_content = response.choices[0].message['content']
                
                print(f"✅ GENERATED FOCUSED CONTENT:")
                print(f"   📝 Content ({len(generated_content)} chars): {generated_content[:150]}...")
                print(f"   📄 Pages: {[p.get('page_number') for p in segment_pages]}")
                print(f"   🖼️ Images: {sum(1 for p in segment_pages if p.get('full_page_image'))}")
                
                slide_segments.append({
                    "slide_number": f"{slide_info['slide_number']}.{seg_idx + 1}",
                    "title": segment.get('segment_title', 'Content'),
                    "content": generated_content,
                    "relevant_pages": segment_pages,
                    "has_images": any(page.get('full_page_image') for page in segment_pages),
                    "category": slide_info.get('category', 'general'),
                    "image_strategy": slide_info.get('image_strategy', 'show_multiple')
                })
                
            except Exception as e:
                print(f"❌ Error generating segment content: {e}")
                # Create fallback content for this segment
                fallback_content = f"Here we explore {segment.get('segment_title', 'important features')} as detailed in our catalog pages."
                slide_segments.append({
                    "slide_number": f"{slide_info['slide_number']}.{seg_idx + 1}",
                    "title": segment.get('segment_title', 'Content'),
                    "content": fallback_content,
                    "relevant_pages": segment_pages,
                    "has_images": any(page.get('full_page_image') for page in segment_pages),
                    "category": slide_info.get('category', 'general'),
                    "image_strategy": slide_info.get('image_strategy', 'show_multiple')
                })
        
        print(f"\n🎉 CREATED {len(slide_segments)} FOCUSED SEGMENTS from slide {slide_info['slide_number']}")
        return slide_segments
    
    def create_full_presentation(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a complete presentation from PDF pages"""
        
        # Store pages data for later use
        self.pages_data = pages_data
        
        # Analyze structure
        structure = self.analyze_pdf_structure(pages_data)
        
        print(f"\n🔧 CREATING PRESENTATION SEGMENTS WITH INTELLIGENT SEGMENTATION...")
        
        # Generate presentation segments
        self.segments = []
        segment_counter = 0
        
        for i, slide_info in enumerate(structure.get('slides', [])):
            print(f"\n📋 Processing slide {i+1}/{len(structure.get('slides', []))} with AI segmentation")
            
            # Get multiple focused segments for this slide
            slide_segments = self.generate_slide_content(slide_info, pages_data)
            
            # Convert each segment to PresentationSegment
            for slide_segment in slide_segments:
                # Get relevant page images
                images = []
                print(f"🖼️ Loading images for segment: {slide_segment['title']}")
                for page in slide_segment.get('relevant_pages', []):
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
                words = slide_segment['content'].split()
                total_duration = max(8, len(words) / 2.5)  # ~150 words per minute, minimum 8 seconds
                
                image_timing = None
                if len(images) > 1:
                    # Distribute images evenly throughout the speech
                    image_timing = []
                    for j in range(len(images)):
                        timing = (total_duration / len(images)) * j
                        image_timing.append(timing)
                    print(f"⏰ Image timing calculated: {[f'{t:.1f}s' for t in image_timing]}")
                
                print(f"📊 Segment summary:")
                print(f"  - Title: {slide_segment['title']}")
                print(f"  - Duration: {total_duration:.1f} seconds")
                print(f"  - Images: {len(images)}")
                print(f"  - Category: {slide_segment.get('category', 'general')}")
                print(f"  - Strategy: {slide_segment.get('image_strategy', 'show_multiple')}")
                print(f"  - Text preview: {slide_segment['content'][:100]}...")
                
                # Create presentation segment
                segment = PresentationSegment(
                    id=segment_counter,
                    text=slide_segment['content'],
                    images=images,
                    duration_seconds=int(total_duration),
                    pdf_page=slide_segment.get('relevant_pages', [{}])[0].get('page_number'),
                    pdf_name=slide_segment.get('relevant_pages', [{}])[0].get('pdf_name'),
                    category=slide_segment.get('category', 'general'),
                    image_strategy=slide_segment.get('image_strategy', 'show_multiple'),
                    image_timing=image_timing
                )
                self.segments.append(segment)
                segment_counter += 1
        
        print(f"\n🎉 INTELLIGENT SEGMENTATION COMPLETE!")
        print(f"📊 Final Statistics:")
        print(f"  - Total focused segments: {len(self.segments)}")
        print(f"  - Total duration: {sum(seg.duration_seconds for seg in self.segments)} seconds")
        print(f"  - Segments with images: {len([seg for seg in self.segments if seg.images])}")
        print(f"  - Total images: {sum(len(seg.images) for seg in self.segments)}")
        
        category_breakdown = {}
        for seg in self.segments:
            cat = getattr(seg, 'category', 'general')
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
        print(f"  - Category breakdown: {category_breakdown}")
        
        logger.info(f"Created presentation with {len(self.segments)} focused segments using AI segmentation")
        
        return {
            "title": structure.get('title', 'PDF Presentation'),
            "subtitle": structure.get('subtitle', 'Generated Presentation'),
            "total_slides": len(self.segments),
            "slides": [{
                "slide_number": seg.id + 1,
                "title": f"Segment {seg.id + 1}",
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