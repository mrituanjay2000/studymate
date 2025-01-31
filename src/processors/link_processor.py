import os
import tempfile
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from .document_processor import DocumentProcessor
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class LinkProcessor:
    def __init__(self):
        self.document_processor = DocumentProcessor()
        # Configure session with retries and timeouts
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def process_link(self, url):
        """
        Process a website link:
        1. Fetch the HTML content
        2. Clean and parse it
        3. Save to temporary HTML file
        4. Process using DocumentProcessor
        
        Returns:
            tuple: (content_object, title, url) or (None, None, None) if processing fails
        """
        temp_path = None
        try:
            # Validate URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValueError("Invalid URL format. Please include http:// or https://")

            # Fetch content with timeout
            response = self.session.get(
                url,
                timeout=(5, 30),  # (connect timeout, read timeout)
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            response.raise_for_status()
            html_content = response.text

            # Parse and clean HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Get the title early
            title = soup.title.string if soup.title else url
            
            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'nav', 'footer', 'iframe', 'meta', 'link']):
                element.decompose()

            # Try to find main content
            main_content = None
            for selector in ['main', 'article', 'div[role="main"]', '.main-content', '#main-content']:
                main_content = soup.select_one(selector)
                if main_content:
                    break

            if not main_content:
                # Fallback to body if no main content found
                main_content = soup.find('body')
                if not main_content:
                    main_content = soup

            # Clean the content
            cleaned_html = f"""
            <html>
            <head>
                <title>{title}</title>
            </head>
            <body>
                <h1>{title}</h1>
                {str(main_content)}
            </body>
            </html>
            """

            # Create temporary HTML file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(cleaned_html)
                temp_path = temp_file.name

            # Process the HTML file using DocumentProcessor
            content = self.document_processor.process_document(temp_path)
            if content:
                # Let the caller handle the database operations
                return content, title, url
            return None, None, None

        except requests.Timeout:
            raise Exception("Website took too long to respond. Please try again later.")
        except requests.RequestException as e:
            raise Exception(f"Error accessing website: {str(e)}")
        except Exception as e:
            logging.error(f"Error processing website content: {str(e)}")
            raise Exception(f"Error processing website content: {str(e)}")
        finally:
            # Clean up temporary file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    logging.error(f"Error removing temporary file: {str(e)}")
