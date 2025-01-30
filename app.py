import streamlit as st
import google.generativeai as genai
from src.models.database import init_db, Session, Content
from src.processors.document_processor import DocumentProcessor, SUPPORTED_EXTENSIONS
from src.processors.youtube_processor import YouTubeProcessor
import os
import tempfile
import logging
from dotenv import load_dotenv
from pathlib import Path

# Page config must be the first Streamlit command
st.set_page_config(
    page_title="StudyMate AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load external CSS
with open('static/css/style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Initialize
load_dotenv()
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
init_db()

# Initialize session state variables
if 'show_upload' not in st.session_state:
    st.session_state.show_upload = False
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False
if 'notifications' not in st.session_state:
    st.session_state.notifications = False
if 'context_cache' not in st.session_state:
    st.session_state.context_cache = None
if 'messages' not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! How can I help you with your studies today?"}
    ]

# Set up the main container
st.markdown("""
    <style>
    .stApp {
        max-width: 100%;
        padding: 1rem;
    }
    .main .block-container {
        max-width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    section[data-testid="stSidebar"] {
        width: 250px !important;
    }
    </style>
""", unsafe_allow_html=True)

# System instructions for different modes
SYSTEM_INSTRUCTIONS = {
    "general": """You are Claude, a friendly and knowledgeable AI assistant. 
    Format your responses using markdown for better readability:
    - Use **bold** for emphasis
    - Use `code` for technical terms
    - Use bullet points and numbered lists appropriately
    - Keep responses concise and well-structured""",
    
    "study_mentor": """You are a dedicated Study Mentor AI helping students understand their study materials.
    
    IMPORTANT RULES:
    1. ONLY answer based on the provided study materials
    2. Format ALL responses using markdown:
       - Start with the source: **Source:** [Document Name]
       - Use **bold** for key terms and concepts
       - Use bullet points for lists
       - Use `code` for technical terms/equations
       - Use > for important quotes from the material
       
    3. If information isn't in the materials, respond with:
       "I don't see this in your current study materials. Would you like to:
       - Search other sections of your materials
       - Explore related topics from your materials
       - Add new study materials about this topic"
       
    4. When citing multiple sources:
       - Clearly indicate which source contains what information
       - Use headings to separate information from different sources
       - Cross-reference related information between sources
       
    5. Keep responses:
       - Concise and well-structured
       - Focused on the materials
       - Easy to read with proper markdown formatting
    
    Remember: You are helping students understand THEIR materials, not providing general knowledge."""
}

def get_context():
    """Cache and return the context from the database."""
    if st.session_state.context_cache is None:
        session = Session()
        contents = session.query(Content).all()
        context = []
        for content in contents:
            source = {
                "title": content.title,
                "summary": content.summary,
                "key_points": content.key_points if content.key_points else "",
                "type": content.type if hasattr(content, 'type') else "document"
            }
            context.append(source)
        st.session_state.context_cache = context
    return st.session_state.context_cache

def process_user_input(user_input):
    """Process user input with appropriate system instruction based on context."""
    context = get_context()
    
    try:
        # Base model configuration
        generation_config = genai.types.GenerationConfig(
            temperature=0.7,
            top_k=40,
            top_p=0.8,
            max_output_tokens=1024,
        )
        
        if not context:
            # Use general mode when no study materials are present
            model = genai.GenerativeModel(GEMINI_MODEL)
            chat = model.start_chat(history=[])
            chat.send_message(SYSTEM_INSTRUCTIONS["general"])
        else:
            # Format context for study mentor mode
            formatted_context = "\n### YOUR STUDY MATERIALS:\n\n"
            for idx, source in enumerate(context, 1):
                formatted_context += f"#### {source['title']}\n\n"
                formatted_context += f"**Content Summary:**\n{source['summary']}\n\n"
                if source['key_points']:
                    formatted_context += f"**Key Points:**\n{source['key_points']}\n\n"
                formatted_context += "---\n\n"
            
            # Create full system message with instructions and context
            system_message = (
                f"{SYSTEM_INSTRUCTIONS['study_mentor']}\n\n"
                "IMPORTANT: The following are the ONLY materials you should use to answer questions:\n\n"
                f"{formatted_context}\n"
                "Remember: ONLY use the information from these materials to answer questions. "
                "If the answer isn't in these materials, say so and offer to help find related information."
            )
            
            # Initialize model with context
            model = genai.GenerativeModel(GEMINI_MODEL)
            chat = model.start_chat(history=[])
            chat.send_message(system_message)
        
        # Send user's question
        response = chat.send_message(user_input, generation_config=generation_config)
        return response.text
        
    except Exception as e:
        logging.error(f"Error in process_user_input: {str(e)}")
        return "I apologize, but I encountered an error. Please try again or rephrase your question."

# Left sidebar with tabs for Sources and Settings
with st.sidebar:
    sources_tab, settings_tab = st.tabs(["📚 Sources", "⚙️ Settings"])
    
    # Sources Tab
    with sources_tab:
        st.title("Sources")
        
        # Add source and Clear buttons in same row
        col1, col2 = st.columns([3, 2])
        with col1:
            if st.button("📄 Add Source", key="add_source"):
                st.session_state.show_upload = not st.session_state.show_upload
        with col2:
            if st.button("🗑️ Clear All", key="clear_sources", type="secondary"):
                session = Session()
                session.query(Content).delete()
                session.commit()
                st.session_state.context_cache = None
                st.success("All sources cleared!")
                st.rerun()
        
        # Show upload section when Add Source is clicked
        if st.session_state.show_upload:
            st.write("### Upload Study Materials")
            upload_tab = st.radio("Select Source Type:", ["Document", "YouTube"], horizontal=True)
            
            if upload_tab == "Document":
                st.write("Supported formats: PDF, Python, JavaScript, HTML, CSS, TXT, Markdown, CSV, XML, RTF")
                uploaded_file = st.file_uploader("Upload Document", type=[ext[1:] for ext in SUPPORTED_EXTENSIONS])
                if uploaded_file:
                    temp_dir = tempfile.mkdtemp()
                    temp_path = os.path.join(temp_dir, uploaded_file.name)
                    
                    try:
                        with open(temp_path, 'wb') as f:
                            f.write(uploaded_file.getvalue())
                        
                        with st.spinner("Processing document..."):
                            processor = DocumentProcessor()
                            content = processor.process_document(temp_path)
                            
                            if content:
                                st.success(f"Successfully processed {uploaded_file.name}")
                                st.session_state.context_cache = None
                                st.session_state.show_upload = False
                                st.rerun()
                            else:
                                st.error("Failed to process document")
                    except Exception as e:
                        st.error(f"Error processing document: {str(e)}")
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        if os.path.exists(temp_dir):
                            os.rmdir(temp_dir)
            
            else:  # YouTube tab
                youtube_url = st.text_input("Enter YouTube URL")
                if youtube_url:
                    try:
                        with st.spinner("Processing video..."):
                            processor = YouTubeProcessor()
                            content = processor.process_video(youtube_url)
                            
                            if content:
                                st.success("Successfully processed video")
                                st.session_state.context_cache = None
                                st.session_state.show_upload = False
                                st.rerun()
                            else:
                                st.error("Failed to process video")
                    except Exception as e:
                        st.error(f"Error processing video: {str(e)}")

            # Hide upload section button
            if st.button("❌ Cancel", key="hide_upload"):
                st.session_state.show_upload = False
                st.rerun()
        
        # Show divider before existing sources
        st.write("---")
        
        # Show existing sources
        session = Session()
        contents = session.query(Content).all()
        
        if contents:
            st.write("### Existing Sources")
            for content in contents:
                with st.expander(f"📚 {content.title}"):
                    st.write(f"**Summary:** {content.summary}")
                    if content.key_points:
                        st.write(f"**Key Points:** {content.key_points}")

    # Settings Tab
    with settings_tab:
        st.title("Settings")
        
        st.subheader("Appearance")
        dark_mode = st.checkbox("Dark Mode", value=st.session_state.dark_mode)
        if dark_mode != st.session_state.dark_mode:
            st.session_state.dark_mode = dark_mode
            st.rerun()
        
        st.subheader("Notifications")
        notifications = st.checkbox("Enable Notifications", value=st.session_state.notifications)
        if notifications != st.session_state.notifications:
            st.session_state.notifications = notifications
            st.rerun()

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("Ask about your study materials..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = process_user_input(prompt)
            st.markdown(response)
            
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})
