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
        logger.info(f"Starting video processing pipeline for URL: {url}")
        start_time = time.time()
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Download and process video
                    video_path, title = self._download_video(url, temp_dir)
                    logger.info("Video download completed")
                    
                    video_base64 = self._process_video_data(video_path)
                    logger.info("Video data encoding completed")

                    # Create video part for the model
                    video_part = {
                        'mime_type': 'video/mp4',
                        'data': video_base64
                    }
                    logger.info("Video part prepared for model")

                    # Create the prompt for video analysis
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

                    # Generate content
                    response_text = self._generate_content(prompt, video_part)
                    logger.info("Content generation completed")
                    
                    # Store in database
                    session = Session()
                    content = Content(
                        type='youtube',
                        source_url=url,
                        title=title,
                        content=prompt,
                        summary=response_text,
                        key_points=None
                    )
                    session.add(content)
                    session.commit()
                    logger.info("Content saved to database")
                    
                    total_time = time.time() - start_time
                    logger.info(f"Total processing time: {total_time:.2f} seconds")
                    return content
                    
                except Exception as e:
                    logger.error(f"Error during video processing: {str(e)}")
                    st.error(f"Error during video processing: {str(e)}")
                    return None
            
        except Exception as e:
            logger.error(f"Error processing YouTube video: {str(e)}")
            st.error(f"Error processing YouTube video: {str(e)}")
            return None
