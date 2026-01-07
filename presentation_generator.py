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
    
    def detect_pdf_structure(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Dynamically detect PDF structure and content type"""
        
        total_pages = len(pages_data)
        full_content = self._build_complete_content(pages_data)
        
        print(f"\n🔍 ADAPTIVE STRUCTURE DETECTION for {total_pages} pages")
        print(f"📊 Content size: {len(full_content)} characters")
        
        # AI-driven structure detection
        detection_prompt = f"""
        Analyze this {total_pages}-page document and determine its structure and content type.
        
        DOCUMENT CONTENT (first 8000 characters):
        {full_content[:8000]}
        
        ANALYSIS TASKS:
        1. CONTENT TYPE DETECTION:
           - Is this a product catalog, manual, report, brochure, technical doc, or other?
           - What is the primary purpose of this document?
        
        2. STRUCTURE ANALYSIS:
           - Does it follow intro → content → conclusion pattern?
           - Is it just products/items without intro/conclusion?
           - Is each page a separate item/product/topic?
           - Are there clear sections or is it continuous narrative?
        
        3. CONTENT DENSITY:
           - How much unique information per page?
           - Are pages standalone or interconnected?
           - What's the optimal information grouping size?
        
        4. PRESENTATION STRATEGY:
           - How many slides would effectively cover this content?
           - Should we group pages or treat individually?
           - What's the natural segmentation pattern?
        
        OUTPUT JSON:
        {{
            "document_type": "product_catalog|user_manual|brochure|technical_report|mixed_content",
            "content_pattern": "sequential_products|continuous_narrative|sectioned_content|reference_material",
            "structure_detected": {{
                "has_introduction": true/false,
                "has_conclusion": true/false,
                "has_clear_sections": true/false,
                "pages_are_standalone": true/false
            }},
            "optimal_strategy": {{
                "recommended_slides": number,
                "pages_per_slide": "1|2-3|3-5|variable",
                "segmentation_approach": "one_per_page|topic_groups|content_flow|adaptive"
            }},
            "content_categories": ["detected", "category", "types"],
            "complexity_score": 1-10
        }}
        """
        
        try:
            print(f"🤖 SENDING TO AI FOR STRUCTURE DETECTION...")
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert document analyzer. Analyze document structure and determine optimal presentation strategy. Always output valid JSON."},
                    {"role": "user", "content": detection_prompt}
                ],
                max_tokens=1000,
                temperature=0.1
            )
            
            content = response.choices[0].message['content']
            print(f"📝 Structure detection response: {content[:300]}...")
            
            # Parse JSON response
            import json
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                structure = json.loads(json_match.group())
                
                print(f"\n✅ STRUCTURE DETECTED:")
                print(f"  📋 Document type: {structure.get('document_type', 'unknown')}")
                print(f"  🔄 Content pattern: {structure.get('content_pattern', 'unknown')}")
                print(f"  📊 Complexity score: {structure.get('complexity_score', 5)}/10")
                print(f"  🎯 Recommended slides: {structure.get('optimal_strategy', {}).get('recommended_slides', 'unknown')}")
                print(f"  📄 Pages per slide: {structure.get('optimal_strategy', {}).get('pages_per_slide', 'unknown')}")
                
                return structure
            else:
                print("❌ Could not parse structure detection JSON")
                return self._create_fallback_structure(pages_data)
                
        except Exception as e:
            print(f"❌ Structure detection failed: {e}")
            return self._create_fallback_structure(pages_data)
    
    def _build_complete_content(self, pages_data: List[Dict[str, Any]]) -> str:
        """Build complete document content for analysis"""
        full_content = ""
        for i, page in enumerate(pages_data):
            page_text = page.get('text', '')
            page_num = page.get('page_number', i+1)
            if page_text:
                full_content += f"\n--- PAGE {page_num} ---\n{page_text}\n"
        return full_content
    
    def _create_fallback_structure(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create fallback structure when AI detection fails"""
        total_pages = len(pages_data)
        return {
            "document_type": "mixed_content",
            "content_pattern": "sectioned_content",
            "structure_detected": {
                "has_introduction": True,
                "has_conclusion": True,
                "has_clear_sections": True,
                "pages_are_standalone": False
            },
            "optimal_strategy": {
                "recommended_slides": max(5, min(20, total_pages // 4)),
                "pages_per_slide": "2-4",
                "segmentation_approach": "adaptive"
            },
            "content_categories": ["general"],
            "complexity_score": 5
        }
    
    def calculate_optimal_slides(self, structure_analysis: Dict, pages_data: List[Dict]) -> Dict:
        """Calculate optimal slide count based on content analysis"""
        
        total_pages = len(pages_data)
        document_type = structure_analysis.get('document_type', 'mixed_content')
        content_pattern = structure_analysis.get('content_pattern', 'sectioned_content')
        complexity = structure_analysis.get('complexity_score', 5)
        pages_are_standalone = structure_analysis.get('structure_detected', {}).get('pages_are_standalone', False)
        
        print(f"\n📊 CALCULATING OPTIMAL SLIDES:")
        print(f"  📄 Total pages: {total_pages}")
        print(f"  📋 Document type: {document_type}")
        print(f"  🔄 Content pattern: {content_pattern}")
        print(f"  📊 Complexity: {complexity}/10")
        print(f"  🎯 Standalone pages: {pages_are_standalone}")
        
        # Page size categories with different strategies
        if total_pages <= 15:
            return self._small_pdf_strategy(structure_analysis, pages_data)
        elif total_pages <= 50:
            return self._medium_pdf_strategy(structure_analysis, pages_data)
        elif total_pages <= 100:
            return self._large_pdf_strategy(structure_analysis, pages_data)
        else:
            return self._xlarge_pdf_strategy(structure_analysis, pages_data)
    
    def _small_pdf_strategy(self, analysis: Dict, pages_data: List) -> Dict:
        """Strategy for 10-15 page PDFs"""
        total_pages = len(pages_data)
        pages_are_standalone = analysis.get('structure_detected', {}).get('pages_are_standalone', False)
        document_type = analysis.get('document_type', 'mixed_content')
        
        if pages_are_standalone or document_type == 'product_catalog':
            # Each page is unique product/item
            slide_count = total_pages
            strategy = "individual_pages"
            pages_per_slide = 1
        else:
            # Group related content
            slide_count = max(3, total_pages // 2)
            strategy = "content_groups"
            pages_per_slide = 2
        
        print(f"  🔧 Small PDF strategy: {strategy}")
        print(f"  📊 Slides: {slide_count}, Pages per slide: {pages_per_slide}")
        
        return {
            "slide_count": slide_count,
            "pages_per_slide": pages_per_slide,
            "strategy": strategy
        }
    
    def _medium_pdf_strategy(self, analysis: Dict, pages_data: List) -> Dict:
        """Strategy for 16-50 page PDFs"""
        total_pages = len(pages_data)
        document_type = analysis.get('document_type', 'mixed_content')
        complexity = analysis.get('complexity_score', 5)
        
        if document_type == 'product_catalog':
            # Product catalogs can have more slides
            slide_count = min(25, total_pages // 2)
            strategy = "product_focused"
            pages_per_slide = "1-3"
        else:
            # Other types need balanced approach
            slide_count = max(8, min(15, total_pages // 3))
            strategy = "topic_grouping"
            pages_per_slide = "2-4"
        
        print(f"  🔧 Medium PDF strategy: {strategy}")
        print(f"  📊 Slides: {slide_count}, Pages per slide: {pages_per_slide}")
        
        return {
            "slide_count": slide_count,
            "pages_per_slide": pages_per_slide,
            "strategy": strategy
        }
    
    def _large_pdf_strategy(self, analysis: Dict, pages_data: List) -> Dict:
        """Strategy for 51-100 page PDFs"""
        total_pages = len(pages_data)
        document_type = analysis.get('document_type', 'mixed_content')
        complexity = analysis.get('complexity_score', 5)
        
        if document_type == 'product_catalog':
            # Product catalogs can have many slides
            slide_count = min(30, total_pages // 3)
            strategy = "product_grouping"
            pages_per_slide = "2-4"
        else:
            # Other types need more condensed approach
            slide_count = min(20, total_pages // 5)
            strategy = "topic_condensation"
            pages_per_slide = "4-6"
        
        print(f"  🔧 Large PDF strategy: {strategy}")
        print(f"  📊 Slides: {slide_count}, Pages per slide: {pages_per_slide}")
        
        return {
            "slide_count": slide_count,
            "pages_per_slide": pages_per_slide,
            "strategy": strategy
        }
    
    def _xlarge_pdf_strategy(self, analysis: Dict, pages_data: List) -> Dict:
        """Strategy for 100+ page PDFs"""
        total_pages = len(pages_data)
        document_type = analysis.get('document_type', 'mixed_content')
        
        if document_type == 'product_catalog':
            # Large catalogs need category-based approach
            slide_count = min(40, total_pages // 4)
            strategy = "category_grouping"
            pages_per_slide = "3-6"
        else:
            # Large documents need high-level overview approach
            slide_count = min(25, total_pages // 8)
            strategy = "high_level_overview"
            pages_per_slide = "6-10"
        
        print(f"  🔧 XLarge PDF strategy: {strategy}")
        print(f"  📊 Slides: {slide_count}, Pages per slide: {pages_per_slide}")
        
        return {
            "slide_count": slide_count,
            "pages_per_slide": pages_per_slide,
            "strategy": strategy
        }
    
    def process_by_content_type(self, structure_analysis: Dict, slide_config: Dict, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Route processing based on detected content type"""
        
        document_type = structure_analysis.get('document_type', 'mixed_content')
        
        print(f"\n🎯 CONTENT-TYPE SPECIFIC PROCESSING: {document_type}")
        
        processors = {
            'product_catalog': self._process_product_catalog,
            'user_manual': self._process_user_manual,
            'brochure': self._process_brochure,
            'technical_report': self._process_technical_report,
            'mixed_content': self._process_mixed_content
        }
        
        processor = processors.get(document_type, self._process_generic)
        return processor(structure_analysis, slide_config, pages_data)
    
    def _process_product_catalog(self, analysis: Dict, slide_config: Dict, pages_data: List) -> Dict:
        """Specialized processing for product catalogs"""
        
        total_pages = len(pages_data)
        slide_count = slide_config.get('slide_count', 10)
        pages_are_standalone = analysis.get('structure_detected', {}).get('pages_are_standalone', False)
        
        print(f"🛍️ PRODUCT CATALOG PROCESSING:")
        print(f"  📄 {total_pages} pages → {slide_count} product-focused slides")
        print(f"  🎯 Pages are standalone: {pages_are_standalone}")
        
        # For product catalogs with standalone pages, create one slide per page
        if pages_are_standalone:
            print(f"  📄 Creating individual slides for each product page")
            slides = []
            for i, page in enumerate(pages_data):
                slides.append({
                    "slide_number": i + 1,
                    "focus_area": f"Product Page {page.get('page_number', i + 1)}",
                    "category": "products",
                    "relevant_pages": [page.get('page_number', i + 1)],
                    "content_summary": f"Individual product from page {page.get('page_number', i + 1)}",
                    "image_strategy": "show_multiple"
                })
            
            return {
                "title": "Product Catalog",
                "subtitle": "Individual Product Showcase",
                "slides": slides
            }
        
        # For grouped product catalogs, use AI to create structured slides
        else:
            catalog_prompt = f"""
            This is a product catalog with {total_pages} pages. Create product-focused slides.
            
            CONTENT: {self._build_complete_content(pages_data)[:6000]}
            
            PRODUCT CATALOG APPROACH:
            1. Identify individual products or product groups
            2. Each slide focuses on 1-3 related products maximum
            3. Don't force intro/conclusion if content is just products
            4. Group by product categories, series, or types naturally
            5. Maintain specific product names and details
            6. Create {slide_count} slides total
            
            OUTPUT JSON:
            {{
                "title": "Product Catalog Title",
                "subtitle": "Product Showcase",
                "slides": [
                    {{
                        "slide_number": 1,
                        "focus_area": "Specific Product Name/Category",
                        "category": "products",
                        "relevant_pages": [1, 2],
                        "content_summary": "Product details and features",
                        "image_strategy": "show_multiple"
                    }}
                ]
            }}
            """
            
            return self._call_ai_with_specialized_prompt(catalog_prompt, 'product_catalog', slide_count)
    
    def _process_technical_report(self, analysis: Dict, slide_config: Dict, pages_data: List) -> Dict:
        """Specialized processing for technical reports"""
        
        slide_count = slide_config.get('slide_count', 15)
        
        print(f"📊 TECHNICAL REPORT PROCESSING:")
        print(f"  📄 Technical document → {slide_count} topic-based slides")
        
        report_prompt = f"""
        This is a technical report/document. Create technical topic-focused slides.
        
        CONTENT: {self._build_complete_content(pages_data)[:6000]}
        
        TECHNICAL REPORT APPROACH:
        1. Identify main technical topics and sections
        2. Group related technical concepts together
        3. Maintain logical flow of information
        4. Each slide covers one major technical aspect
        5. Preserve technical accuracy and detail level
        6. Create {slide_count} slides total
        
        OUTPUT: Create slides that maintain technical coherence and logical progression.
        """
        
        return self._call_ai_with_specialized_prompt(report_prompt, 'technical_report', slide_count)
    
    def _process_user_manual(self, analysis: Dict, slide_config: Dict, pages_data: List) -> Dict:
        """Specialized processing for user manuals"""
        
        slide_count = slide_config.get('slide_count', 12)
        
        print(f"📖 USER MANUAL PROCESSING:")
        print(f"  📄 Manual → {slide_count} instructional slides")
        
        manual_prompt = f"""
        This is a user manual. Create instructional slides.
        
        CONTENT: {self._build_complete_content(pages_data)[:6000]}
        
        USER MANUAL APPROACH:
        1. Follow logical instructional flow
        2. Group related procedures together
        3. Maintain step-by-step clarity
        4. Create intro → instructions → conclusion structure
        5. Focus on usability and clarity
        6. Create {slide_count} slides total
        """
        
        return self._call_ai_with_specialized_prompt(manual_prompt, 'user_manual', slide_count)
    
    def _process_brochure(self, analysis: Dict, slide_config: Dict, pages_data: List) -> Dict:
        """Specialized processing for brochures"""
        
        slide_count = slide_config.get('slide_count', 8)
        
        print(f"📄 BROCHURE PROCESSING:")
        print(f"  📄 Marketing material → {slide_count} promotional slides")
        
        brochure_prompt = f"""
        This is a brochure/marketing material. Create promotional slides.
        
        CONTENT: {self._build_complete_content(pages_data)[:6000]}
        
        BROCHURE APPROACH:
        1. Follow marketing flow: intro → features → benefits → conclusion
        2. Highlight key selling points
        3. Maintain promotional tone
        4. Group related benefits together
        5. Create compelling presentation flow
        6. Create {slide_count} slides total
        """
        
        return self._call_ai_with_specialized_prompt(brochure_prompt, 'brochure', slide_count)
    
    def _process_mixed_content(self, analysis: Dict, slide_config: Dict, pages_data: List) -> Dict:
        """Specialized processing for mixed content"""
        
        slide_count = slide_config.get('slide_count', 10)
        
        print(f"🔄 MIXED CONTENT PROCESSING:")
        print(f"  📄 Diverse content → {slide_count} adaptive slides")
        
        mixed_prompt = f"""
        This document has mixed content types. Create adaptive slides.
        
        CONTENT: {self._build_complete_content(pages_data)[:6000]}
        
        MIXED CONTENT APPROACH:
        1. Analyze content sections and adapt strategy per section
        2. Maintain logical flow throughout
        3. Group similar content types together
        4. Adapt slide focus based on content type
        5. Create coherent overall presentation
        6. Create {slide_count} slides total
        """
        
        return self._call_ai_with_specialized_prompt(mixed_prompt, 'mixed_content', slide_count)
    
    def _process_generic(self, analysis: Dict, slide_config: Dict, pages_data: List) -> Dict:
        """Generic processing fallback"""
        
        slide_count = slide_config.get('slide_count', 10)
        
        print(f"⚙️ GENERIC PROCESSING:")
        print(f"  📄 Unknown type → {slide_count} general slides")
        
        # Fall back to original logic
        return self.analyze_pdf_structure(pages_data)
    
    def _call_ai_with_specialized_prompt(self, prompt: str, doc_type: str, slide_count: int) -> Dict:
        """Helper to call AI with specialized prompts"""
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"You are an expert in creating presentations from {doc_type} documents. Create structured slide layouts that match the document type. Always output valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=3000,
                temperature=0.1
            )
            
            content = response.choices[0].message['content']
            print(f"📝 {doc_type} processing response: {content[:200]}...")
            
            # Parse JSON response
            import json
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                structure = json.loads(json_match.group())
                slides_count = len(structure.get('slides', []))
                print(f"✅ Created {slides_count} specialized slides for {doc_type}")
                return structure
            else:
                print(f"❌ Could not parse {doc_type} JSON response")
                return self._create_fallback_structure_for_type(doc_type, slide_count)
                
        except Exception as e:
            print(f"❌ {doc_type} processing failed: {e}")
            return self._create_fallback_structure_for_type(doc_type, slide_count)
    
    def _create_fallback_structure_for_type(self, doc_type: str, slide_count: int) -> Dict:
        """Create fallback structure for specific document type"""
        
        category_mapping = {
            'product_catalog': 'products',
            'user_manual': 'features',
            'brochure': 'features',
            'technical_report': 'technical',
            'mixed_content': 'general'
        }
        
        slides = []
        for i in range(slide_count):
            slides.append({
                "slide_number": i + 1,
                "focus_area": f"{doc_type.title()} Section {i + 1}",
                "category": category_mapping.get(doc_type, 'general'),
                "relevant_pages": [i + 1, i + 2],
                "content_summary": f"Content from {doc_type}",
                "image_strategy": "show_multiple"
            })
        
        return {
            "title": f"{doc_type.title()} Presentation",
            "subtitle": "Generated Presentation",
            "slides": slides
        }
    
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

    def adaptive_segmentation(self, slide_info: Dict, pages_data: List[Dict[str, Any]], structure_analysis: Dict) -> List[Dict[str, Any]]:
        """Adaptive segmentation based on content analysis"""
        
        strategy = structure_analysis.get('optimal_strategy', {}).get('segmentation_approach', 'adaptive')
        document_type = structure_analysis.get('document_type', 'mixed_content')
        
        print(f"\n🎯 ADAPTIVE SEGMENTATION: {strategy} for {document_type}")
        
        segmentation_strategies = {
            'one_per_page': self._segment_one_per_page,
            'topic_groups': self._segment_by_topics,
            'content_flow': self._segment_by_flow,
            'adaptive': self._segment_adaptively
        }
        
        segmenter = segmentation_strategies.get(strategy, self._segment_adaptively)
        return segmenter(slide_info, pages_data, structure_analysis)
    
    def _segment_one_per_page(self, slide_info: Dict, pages_data: List[Dict], analysis: Dict) -> List[Dict[str, Any]]:
        """Each page becomes its own segment - ideal for product catalogs"""
        
        segments = []
        requested_pages = slide_info.get('relevant_pages', [])
        
        print(f"📄 ONE-PER-PAGE SEGMENTATION for pages: {requested_pages}")
        
        for page_num in requested_pages:
            page_data = self._get_page_data(page_num, pages_data)
            if not page_data:
                continue
            
            # AI analysis for single page
            single_page_prompt = f"""
            Analyze this single page and create focused content:
            
            PAGE {page_num} CONTENT:
            {page_data.get('text', '')}
            
            Create a specific segment title and topic for this page.
            Focus on what makes this page unique and valuable.
            Extract the main product/topic name if possible.
            
            OUTPUT JSON:
            {{
                "segment_title": "Specific name/title from content",
                "main_topic": "What this page specifically covers",
                "content_summary": "Key information"
            }}
            """
            
            segment_data = self._get_ai_segment_analysis(single_page_prompt, [page_data])
            segment_data['relevant_pages'] = [page_num]
            segments.append(segment_data)
        
        return segments
    
    def _segment_by_topics(self, slide_info: Dict, pages_data: List[Dict], analysis: Dict) -> List[Dict[str, Any]]:
        """Group pages by related topics"""
        
        relevant_pages = self._get_relevant_pages_data(slide_info, pages_data)
        
        print(f"🏷️ TOPIC-BASED SEGMENTATION for {len(relevant_pages)} pages")
        
        topic_prompt = f"""
        Analyze these pages and group them by related topics:
        
        CONTENT: {self._combine_pages_content(relevant_pages)}
        
        GROUP BY TOPICS:
        1. Identify main topics/themes across these pages
        2. Group pages that share similar topics
        3. Each group should have 1-3 pages maximum
        4. Create clear topic-based segments
        
        OUTPUT: Groups of pages organized by topic similarity.
        """
        
        return self._ai_guided_segmentation(topic_prompt, relevant_pages)
    
    def _segment_by_flow(self, slide_info: Dict, pages_data: List[Dict], analysis: Dict) -> List[Dict[str, Any]]:
        """Segment based on content flow and logical breaks"""
        
        relevant_pages = self._get_relevant_pages_data(slide_info, pages_data)
        
        print(f"🔄 FLOW-BASED SEGMENTATION for {len(relevant_pages)} pages")
        
        flow_prompt = f"""
        Analyze content flow and create logical segments:
        
        CONTENT: {self._combine_pages_content(relevant_pages)}
        
        FLOW ANALYSIS:
        1. Identify natural breaks in content flow
        2. Create segments that maintain logical progression
        3. Each segment should cover one complete concept/section
        4. Preserve narrative or instructional flow
        
        OUTPUT: Segments that maintain content flow coherence.
        """
        
        return self._ai_guided_segmentation(flow_prompt, relevant_pages)
    
    def _segment_adaptively(self, slide_info: Dict, pages_data: List[Dict], analysis: Dict) -> List[Dict[str, Any]]:
        """AI decides optimal segmentation based on content analysis"""
        
        relevant_pages = self._get_relevant_pages_data(slide_info, pages_data)
        content_density = analysis.get('complexity_score', 5)
        document_type = analysis.get('document_type', 'mixed_content')
        pages_are_standalone = analysis.get('structure_detected', {}).get('pages_are_standalone', False)
        
        print(f"🧠 ADAPTIVE SEGMENTATION:")
        print(f"  📊 Complexity: {content_density}/10")
        print(f"  📋 Type: {document_type}")
        print(f"  🎯 Standalone: {pages_are_standalone}")
        
        adaptive_prompt = f"""
        Analyze this content and determine optimal segmentation:
        
        CONTENT: {self._combine_pages_content(relevant_pages)}
        
        CONTEXT:
        - Document type: {document_type}
        - Content complexity: {content_density}/10
        - Pages are standalone: {pages_are_standalone}
        - Pages available: {len(relevant_pages)}
        
        DECISION FRAMEWORK:
        1. If pages_are_standalone OR document_type is product_catalog → Segment per page
        2. If pages share common themes → Group by theme
        3. If content flows continuously → Create logical breaks
        4. If mixed content → Use hybrid approach
        
        CONSTRAINTS:
        - Minimum segment size: 1 page
        - Maximum segment size: 3 pages for product catalogs, 4 pages for others
        - Each segment must have clear focus
        
        Create segments that make the most sense for this specific content type and structure.
        """
        
        return self._ai_guided_segmentation(adaptive_prompt, relevant_pages)
    
    def _get_page_data(self, page_num: int, pages_data: List[Dict]) -> Dict:
        """Get data for specific page number"""
        for page in pages_data:
            if page.get('page_number') == page_num:
                return page
        return None
    
    def _get_relevant_pages_data(self, slide_info: Dict, pages_data: List[Dict]) -> List[Dict]:
        """Get relevant pages data for slide"""
        relevant_pages = []
        requested_pages = slide_info.get('relevant_pages', [])
        
        for page_num in requested_pages:
            page_data = self._get_page_data(page_num, pages_data)
            if page_data:
                relevant_pages.append(page_data)
        
        if not relevant_pages:
            relevant_pages = pages_data[:3]  # fallback
            
        return relevant_pages
    
    def _combine_pages_content(self, pages_data: List[Dict]) -> str:
        """Combine content from multiple pages"""
        combined = ""
        for page in pages_data:
            page_text = page.get('text', '')
            page_num = page.get('page_number', 0)
            combined += f"PAGE {page_num}:\n{page_text}\n\n"
        return combined
    
    def _get_ai_segment_analysis(self, prompt: str, pages_data: List[Dict]) -> Dict:
        """Get AI analysis for segment"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Analyze content and create focused segments. Always output valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            content = response.choices[0].message['content']
            
            import json
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._create_single_segment_fallback(pages_data)
                
        except Exception as e:
            print(f"❌ Segment analysis failed: {e}")
            return self._create_single_segment_fallback(pages_data)
    
    def _ai_guided_segmentation(self, prompt: str, pages_data: List[Dict]) -> List[Dict]:
        """AI-guided segmentation with structured output"""
        try:
            enhanced_prompt = prompt + """
            
            OUTPUT JSON FORMAT:
            {
                "segments": [
                    {
                        "segment_title": "Extract specific name/title from content",
                        "relevant_pages": [page_numbers],
                        "main_topic": "What this segment specifically covers",
                        "content_summary": "Key information about this segment"
                    }
                ]
            }
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert content analyzer. Create intelligent segments based on content structure. Always output valid JSON with segments array."},
                    {"role": "user", "content": enhanced_prompt}
                ],
                max_tokens=1500,
                temperature=0.1
            )
            
            content = response.choices[0].message['content']
            
            import json
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                segmentation = json.loads(json_match.group())
                segments = segmentation.get('segments', [])
                
                print(f"✅ AI created {len(segments)} focused segments")
                return segments
            else:
                return [self._create_single_segment_fallback(pages_data)]
                
        except Exception as e:
            print(f"❌ AI segmentation failed: {e}")
            return [self._create_single_segment_fallback(pages_data)]
    
    def _create_single_segment_fallback(self, pages_data: List[Dict]) -> Dict:
        """Create single segment fallback"""
        page_numbers = [p.get('page_number', 0) for p in pages_data]
        return {
            "segment_title": f"Content from pages {page_numbers}",
            "relevant_pages": page_numbers,
            "main_topic": "Combined content",
            "content_summary": "Information from multiple pages"
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
            - Create brief content (2-3 sentences) about THIS specific topic only
            - Highlight the most important feature or benefit
            - Use actual product names from the source material
            - Keep it concise since viewers can see the detailed image
            - Focus on what makes this product unique or valuable
            
            Category context: {slide_info.get('category', 'general')}
            Write as natural, informative speaking content about this specific topic.
            """
            
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": f"Create brief presentation content for one specific topic. Be concise since viewers can see detailed images."},
                        {"role": "user", "content": content_prompt}
                    ],
                    max_tokens=100,
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
        """Create a complete presentation from PDF pages using adaptive processing"""
        
        # Store pages data for later use
        self.pages_data = pages_data
        
        return self.create_adaptive_presentation(pages_data)
    
    def create_adaptive_presentation(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generic presentation creation that adapts to any PDF type and size"""
        
        print(f"🔍 ADAPTIVE PROCESSING: Analyzing {len(pages_data)}-page document")
        
        # Step 1: Detect document structure and type
        structure_analysis = self.detect_pdf_structure(pages_data)
        
        # Step 2: Calculate optimal slides based on analysis
        slide_config = self.calculate_optimal_slides(structure_analysis, pages_data)
        
        # Step 3: Process using content-type specific logic
        presentation_structure = self.process_by_content_type(structure_analysis, slide_config, pages_data)
        
        print(f"\n🔧 CREATING ADAPTIVE PRESENTATION SEGMENTS...")
        
        # Step 4: Generate segments using adaptive strategy
        self.segments = []
        segment_counter = 0
        
        for i, slide_info in enumerate(presentation_structure.get('slides', [])):
            print(f"\n📋 Processing slide {i+1}/{len(presentation_structure.get('slides', []))} with adaptive segmentation")
            
            # Get multiple focused segments for this slide using adaptive strategy
            slide_segments = self.adaptive_segmentation(slide_info, pages_data, structure_analysis)
            
            # Generate content for each segment and convert to PresentationSegment
            for seg_idx, segment_info in enumerate(slide_segments):
                print(f"\n🎯 GENERATING SEGMENT {seg_idx + 1}: {segment_info.get('segment_title', 'Unknown')}")
                
                # Get pages for this specific segment
                segment_pages = []
                for page_num in segment_info.get('relevant_pages', []):
                    page_data = self._get_page_data(page_num, pages_data)
                    if page_data:
                        segment_pages.append(page_data)
                        print(f"  📖 Using page {page_num}: {len(page_data.get('text', ''))} chars")
                
                if not segment_pages:
                    print(f"⚠️ No pages found for segment, skipping")
                    continue
                
                # Generate focused content for this segment
                generated_content = self._generate_segment_content(segment_info, segment_pages, structure_analysis)
                
                # Convert to PresentationSegment
                presentation_segment = self._create_presentation_segment(
                    segment_info, segment_pages, generated_content, segment_counter, slide_info
                )
                
                self.segments.append(presentation_segment)
                segment_counter += 1
        
        print(f"\n🎉 ADAPTIVE PRESENTATION COMPLETE!")
        print(f"📊 Final Statistics:")
        print(f"  - Total adaptive segments: {len(self.segments)}")
        print(f"  - Total duration: {sum(seg.duration_seconds for seg in self.segments)} seconds")
        print(f"  - Document type: {structure_analysis.get('document_type', 'unknown')}")
        print(f"  - Processing strategy: {slide_config.get('strategy', 'unknown')}")
        
        return self._build_final_presentation(structure_analysis, slide_config)
    
    def _generate_segment_content(self, segment_info: Dict, segment_pages: List[Dict], structure_analysis: Dict) -> str:
        """Generate content for a single segment"""
        
        # Build segment content
        segment_content = ""
        for page in segment_pages:
            page_text = page.get('text', '')
            segment_content += f"Page {page['page_number']}: {page_text}\n"
        
        document_type = structure_analysis.get('document_type', 'mixed_content')
        
        # Generate focused content for this segment
        content_prompt = f"""
        Create brief presentation content for: {segment_info.get('segment_title', 'Content')}
        
        FOCUS: {segment_info.get('main_topic', 'Content information')}
        DOCUMENT TYPE: {document_type}
        
        Content from specific pages:
        {segment_content}
        
        Requirements:
        - Create concise content (2-3 sentences) about THIS specific topic only
        - Highlight the most important feature or benefit
        - Use the actual product name from the source material
        - Keep it brief since viewers can see the detailed image
        - Focus on what makes this product unique or valuable
        - Adapt tone based on document type: {document_type}
        
        Write as natural, brief speaking content that complements the visual information.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"Create brief presentation content for {document_type} documents. Be concise since viewers can see detailed images."},
                    {"role": "user", "content": content_prompt}
                ],
                max_tokens=100,
                temperature=0.2
            )
            
            generated_content = response.choices[0].message['content']
            
            print(f"✅ GENERATED ADAPTIVE CONTENT:")
            print(f"   📝 Content ({len(generated_content)} chars): {generated_content[:150]}...")
            
            return generated_content
            
        except Exception as e:
            print(f"❌ Error generating segment content: {e}")
            return f"Here we explore {segment_info.get('segment_title', 'important features')} as detailed in our document."
    
    def _create_presentation_segment(self, segment_info: Dict, segment_pages: List[Dict], 
                                   content: str, segment_id: int, slide_info: Dict) -> 'PresentationSegment':
        """Create PresentationSegment object from segment data"""
        
        # Get relevant page images
        images = []
        print(f"🖼️ Loading images for segment: {segment_info.get('segment_title', 'Unknown')}")
        for page in segment_pages:
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
        words = content.split()
        total_duration = max(8, len(words) / 2.5)  # ~150 words per minute, minimum 8 seconds
        
        image_timing = None
        if len(images) > 1:
            # Distribute images evenly throughout the speech
            image_timing = []
            for j in range(len(images)):
                timing = (total_duration / len(images)) * j
                image_timing.append(timing)
            print(f"⏰ Image timing calculated: {[f'{t:.1f}s' for t in image_timing]}")
        
        # Create presentation segment
        from models import PresentationSegment
        segment = PresentationSegment(
            id=segment_id,
            text=content,
            images=images,
            duration_seconds=int(total_duration),
            pdf_page=segment_pages[0].get('page_number') if segment_pages else 0,
            pdf_name=segment_pages[0].get('pdf_name') if segment_pages else 'Unknown',
            category=slide_info.get('category', 'general'),
            image_strategy=slide_info.get('image_strategy', 'show_multiple'),
            image_timing=image_timing
        )
        
        return segment
    
    def _build_final_presentation(self, structure_analysis: Dict, slide_config: Dict) -> Dict[str, Any]:
        """Build final presentation data structure"""
        
        return {
            "title": structure_analysis.get('title', 'Adaptive Presentation'),
            "subtitle": f"{structure_analysis.get('document_type', 'Document').title()} Presentation",
            "total_slides": len(self.segments),
            "processing_strategy": slide_config.get('strategy', 'adaptive'),
            "document_type": structure_analysis.get('document_type', 'mixed_content'),
            "slides": [{
                "slide_number": seg.id + 1,
                "title": f"Segment {seg.id + 1}",
                "content": seg.text,
                "relevant_pages": seg.pdf_page,
                "has_images": len(seg.images) > 0
            } for seg in self.segments]
        }
    
    def create_legacy_presentation(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Legacy method - create presentation using original logic (kept for backward compatibility)"""
        
        # Store pages data for later use
        self.pages_data = pages_data
        
        # Analyze structure using original method
        structure = self.analyze_pdf_structure(pages_data)
        
        print(f"\n🔧 CREATING PRESENTATION SEGMENTS WITH LEGACY SEGMENTATION...")
        
        # Generate presentation segments using original logic
        self.segments = []
        segment_counter = 0
        
        for i, slide_info in enumerate(structure.get('slides', [])):
            print(f"\n📋 Processing slide {i+1}/{len(structure.get('slides', []))} with legacy segmentation")
            
            # Get multiple focused segments for this slide using original method
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