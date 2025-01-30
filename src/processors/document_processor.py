import google.generativeai as genai
from pathlib import Path
from ..models.database import Session, Content
import os
from dotenv import load_dotenv
import logging
import base64
import mimetypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

load_dotenv()
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

# Supported MIME types and their file extensions
SUPPORTED_TYPES = {
    'application/pdf': ['.pdf'],
    'application/x-javascript': ['.js'],
    'text/javascript': ['.js'],
    'application/x-python': ['.py'],
    'text/x-python': ['.py'],
    'text/plain': ['.txt'],
    'text/html': ['.html', '.htm'],
    'text/css': ['.css'],
    'text/markdown': ['.md', '.markdown'],
    'text/csv': ['.csv'],
    'text/xml': ['.xml'],
    'text/rtf': ['.rtf']
}

# Flatten the extensions list for easy lookup
SUPPORTED_EXTENSIONS = [ext for exts in SUPPORTED_TYPES.values() for ext in exts]

class DocumentProcessor:
    def __init__(self):
        self.model = genai.GenerativeModel(GEMINI_MODEL)
    
    def _get_file_mime_type(self, file_path):
        """Get MIME type of the file."""
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            # Try to guess from extension
            ext = Path(file_path).suffix.lower()
            for mime, extensions in SUPPORTED_TYPES.items():
                if ext in extensions:
                    return mime
        return mime_type
    
    def _encode_file(self, file_path):
        """Encode file to base64."""
        with open(file_path, 'rb') as file:
            return base64.b64encode(file.read()).decode('utf-8')
    
    def _get_document_type_prompt(self, file_path):
        """Get document-type specific prompt additions."""
        ext = Path(file_path).suffix.lower()
        
        if ext in ['.py', '.js', '.css']:
            return """
Additional Analysis Points:
- Code structure and organization
- Functions and classes overview
- Dependencies and imports
- Best practices followed
- Potential improvements or optimizations
- Code quality and maintainability
"""
        elif ext in ['.csv']:
            return """
Additional Analysis Points:
- Data structure and columns
- Data types present
- Key statistics or patterns
- Data quality observations
- Potential use cases
"""
        elif ext in ['.html', '.xml']:
            return """
Additional Analysis Points:
- Document structure
- Key elements and attributes
- Layout and organization
- Linked resources
- Accessibility considerations
"""
        return ""  # Default no additional prompts
    
    def process_document(self, file_path):
        """Process document using Gemini's document understanding capabilities."""
        logger.info(f"Starting document processing: {file_path}")
        try:
            # Check if file type is supported
            mime_type = self._get_file_mime_type(file_path)
            if not mime_type or not any(mime_type.startswith(supported) for supported in SUPPORTED_TYPES.keys()):
                raise ValueError(f"Unsupported file type: {mime_type}")
            
            # Prepare the document for Gemini
            encoded_doc = self._encode_file(file_path)
            
            # Create the document part
            document_part = {
                "mime_type": mime_type,
                "data": encoded_doc
            }
            logger.info(f"Document encoded and prepared for analysis. MIME type: {mime_type}")
            
            # Get any additional prompts based on file type
            type_specific_prompt = self._get_document_type_prompt(file_path)
            
            # Create the analysis prompt
            prompt = f"""You are a helpful study assistant analyzing a document. Please analyze this document and provide:

1. Document Overview:
   - Document type and purpose
   - Main topic or subject matter
   - Target audience
   - Structure and organization

2. Content Analysis:
   - Executive summary (2-3 sentences)
   - Main concepts or ideas presented
   - Key points and arguments
   - Important definitions or terminology

3. Detailed Breakdown:
   - Section-by-section analysis
   - Important examples or illustrations
   - References or citations
   - Visual elements description (if any)

4. Study Guide:
   - Essential concepts to understand
   - Common misconceptions to avoid
   - Practical applications
   - Related topics to explore

5. Learning Assessment:
   - 3 multiple choice questions with explanations
   - Key points for review
   - Practice exercises or problems

{type_specific_prompt}

Please format your response with clear headers and bullet points. For any technical terms, provide brief explanations."""

            logger.info("Generating content analysis...")
            response = self.model.generate_content(
                contents=[prompt, document_part],
                generation_config={
                    "temperature": 0.7,
                    "top_k": 40,
                    "top_p": 0.8,
                    "max_output_tokens": 2048,
                }
            )
            logger.info("Content analysis completed")
            
            # Store in database
            session = Session()
            filename = os.path.basename(file_path)
            content = Content(
                type=Path(file_path).suffix[1:],  # File extension without dot
                source_url=file_path,
                title=filename,
                content=prompt,
                summary=response.text,
                key_points=None
            )
            session.add(content)
            session.commit()
            logger.info(f"Content saved to database with title: {filename}")
            
            return content
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return None
