import yt_dlp
import google.generativeai as genai
from ..models.database import Session, Content
import os
from dotenv import load_dotenv
import tempfile
import time
from PIL import Image
import base64
import streamlit as st
import logging

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

class YouTubeProcessor:
    def __init__(self):
        self.model = genai.GenerativeModel(GEMINI_MODEL)
        self.ydl_opts = {
            'format': 'best[ext=mp4]',  # Best quality MP4
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'max_filesize': 20 * 1024 * 1024  # 20MB limit to be safe
        }

    def _download_video(self, url, temp_dir):
        """Download video and return path and title."""
        logger.info(f"Starting video download from: {url}")
        video_path = os.path.join(temp_dir, 'video.mp4')
        self.ydl_opts['outtmpl'] = video_path
        
        with st.spinner("Downloading video..."):
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    logger.info("Extracting video info...")
                    info = ydl.extract_info(url, download=True)
                    title = info.get('title', 'Untitled Video')
                    logger.info(f"Downloaded video: {title}")
                    
                if not os.path.exists(video_path):
                    raise Exception("Failed to download video")
                
                file_size = os.path.getsize(video_path) / (1024 * 1024)  # Size in MB
                logger.info(f"Video file size: {file_size:.2f}MB")
                    
                return video_path, title
            except Exception as e:
                logger.error(f"Error downloading video: {str(e)}")
                raise

    def _process_video_data(self, video_path):
        """Process video data and return base64 encoded data."""
        logger.info("Starting video data processing")
        try:
            with st.spinner("Processing video data..."):
                start_time = time.time()
                with open(video_path, 'rb') as f:
                    video_data = f.read()
                    encoded_data = base64.b64encode(video_data).decode('utf-8')
                    processing_time = time.time() - start_time
                    logger.info(f"Video data processed in {processing_time:.2f} seconds")
                    return encoded_data
        except Exception as e:
            logger.error(f"Error processing video data: {str(e)}")
            raise

    def _generate_content(self, prompt, video_part):
        """Generate content from the model."""
        logger.info("Starting content generation")
        try:
            with st.spinner("Analyzing video content..."):
                start_time = time.time()
                response = self.model.generate_content(
                    contents=[prompt, video_part],
                    generation_config={
                        "temperature": 0.7,
                        "top_k": 40,
                        "top_p": 0.8,
                        "max_output_tokens": 1024,
                    }
                )
                processing_time = time.time() - start_time
                logger.info(f"Content generated in {processing_time:.2f} seconds")
                return response.text
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            raise

    def process_video(self, url):
        """Process a YouTube video and store its content."""
        temp_dir = tempfile.mkdtemp()
        try:
            # Download video and get title
            video_path, title = self._download_video(url, temp_dir)
            
            # Process video content
            content = Content(
                title=title,
                source_type="youtube"  # Set source type here
            )
            
            # Generate summary and key points
            video_base64 = self._process_video_data(video_path)
            video_part = {
                'mime_type': 'video/mp4',
                'data': video_base64
            }
            prompt = f"""Analyze this educational video and provide:

1. Brief Summary:
   - Core topic and main message
   - Key takeaways

2. Main Points:
   - Key concepts covered
   - Important examples shown

3. Learning Assessment:
   - 2 multiple choice questions with answers

Video Title: {title}"""
            summary = self._generate_content(prompt, video_part)
            content.summary = summary
            content.content = f"YouTube Video: {url}\n\nSummary:\n{summary}"
            
            # Store in database
            session = Session()
            session.add(content)
            session.commit()
            logger.info("Content saved to database")
            
            return content
            
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            raise
        finally:
            # Clean up temp files
            if os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    except Exception as e:
                        logger.error(f"Error deleting {file_path}: {str(e)}")
                os.rmdir(temp_dir)
