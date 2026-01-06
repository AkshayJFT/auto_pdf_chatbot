import fitz
import os
from PIL import Image
import io
import json
from typing import List, Dict, Any

class PDFProcessor:
    def __init__(self, output_dir: str = "processed_pdfs"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def extract_page_content(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extract text and render full page image from each page of a PDF"""
        doc = fitz.open(pdf_path)
        pages_data = []
        
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        pdf_output_dir = os.path.join(self.output_dir, pdf_name)
        os.makedirs(pdf_output_dir, exist_ok=True)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Extract text
            text = page.get_text()
            
            # Render full page as image
            matrix = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
            pix = page.get_pixmap(matrix=matrix)
            page_img_name = f"page_{page_num}_full.png"
            page_img_path = os.path.join(pdf_output_dir, page_img_name)
            pix.save(page_img_path)
            pix = None
            
            # Extract individual images (optional, for backup)
            image_list = page.get_images()
            extracted_images = []
            
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        img_data = pix.tobytes("png")
                        img_name = f"page_{page_num}_img_{img_index}.png"
                        img_path = os.path.join(pdf_output_dir, img_name)
                        
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                        
                        extracted_images.append({
                            "image_path": img_path,
                            "image_name": img_name
                        })
                    
                    pix = None
                except Exception as e:
                    print(f"Error extracting image {img_index} from page {page_num}: {e}")
            
            # Store page data with full page image
            page_data = {
                "pdf_name": pdf_name,
                "page_number": page_num,
                "text": text.strip(),
                "full_page_image": page_img_path,
                "images": extracted_images,  # Keep individual images as backup
                "page_id": f"{pdf_name}_page_{page_num}"
            }
            
            pages_data.append(page_data)
        
        doc.close()
        return pages_data
    
    def process_multiple_pdfs(self, pdf_paths: List[str]) -> List[Dict[str, Any]]:
        """Process multiple PDFs and return all page data"""
        all_pages = []
        
        for pdf_path in pdf_paths:
            try:
                pages = self.extract_page_content(pdf_path)
                all_pages.extend(pages)
                print(f"Processed {len(pages)} pages from {pdf_path}")
            except Exception as e:
                print(f"Error processing {pdf_path}: {e}")
        
        return all_pages
    
    def save_processed_data(self, pages_data: List[Dict[str, Any]], filename: str = "pages_data.json"):
        """Save processed data to JSON file"""
        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(pages_data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved processed data to {output_path}")
        return output_path


