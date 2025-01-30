import PyPDF2
import google.generativeai as genai
from ..models.database import Session, Content
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

class PDFProcessor:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-pro')
    
    def process_pdf(self, file_path):
        try:
            # Extract text from PDF
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
            
            # Generate summary using Gemini
            prompt = f"""Analyze this document and provide:
            1. A comprehensive summary
            2. Key points and main ideas (as a bullet list)
            3. Important concepts and definitions
            
            Document text:
            {text[:10000]}"""  # Limiting text length for API constraints
            
            response = self.model.generate_content(prompt)
            
            # Store in database
            session = Session()
            content = Content(
                type='pdf',
                source_url=file_path,
                title=os.path.basename(file_path),
                content=text,
                summary=response.text
            )
            session.add(content)
            session.commit()
            
            return content
            
        except Exception as e:
            print(f"Error processing PDF: {str(e)}")
            return None
