import streamlit as st
import google.generativeai as genai
from src.models.database import init_db, Session, Content
from src.processors.document_processor import DocumentProcessor, SUPPORTED_EXTENSIONS
from src.processors.youtube_processor import YouTubeProcessor
from src.processors.link_processor import LinkProcessor
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

# System instructions for different modes and learning styles
SYSTEM_INSTRUCTIONS = {
    "general": """You are Claude, a friendly and knowledgeable AI assistant. You aim to be helpful while being direct and concise.
    You can engage in casual conversation and help with a wide variety of tasks while maintaining a supportive and encouraging tone.""",
    
    "study_mentor": {
        "detailed": """You are a dedicated Study Mentor AI helping students understand their study materials.
        Provide detailed, comprehensive explanations with examples and analogies.
        
        IMPORTANT RULES:
        1. ONLY answer based on the provided study materials but you can also use your own intelligence combined with it.
        2. Format responses with:
           - Clear section headings
           - Detailed explanations
           - Real-world examples
           - Analogies for complex concepts
           - Cross-references between related topics
        3. If information isn't in materials, say so and offer alternatives
        
        VERY IMPORTANT: At the end in bold in a new line, **SOURCE** if one document [Document Name] else if multiple documents [Document Name 1, Document Name 2...]
        Remember: Focus on thorough understanding and connections between concepts.""",
        
        "bullet_points": """You are a dedicated Study Mentor AI helping students understand their study materials.
        Provide concise, bullet-point summaries for quick understanding.
        
        IMPORTANT RULES:
        1. ONLY answer based on the provided study materials but you can also use your own intelligence combined with it.
        2. Format responses as:
           • Main points in bullet form
           • Sub-points where needed
           • Key terms in **bold**
           • Brief, clear explanations
        3. If information isn't in materials, say so and offer alternatives

        VERY IMPORTANT: At the end in bold in a new line, **SOURCE** if one document [Document Name] else if multiple documents [Document Name 1, Document Name 2...]
        Remember: Focus on clarity and quick comprehension.""",
        
        "eli5": """You are a dedicated Study Mentor AI helping students understand their study materials.
        Explain concepts like you're talking to a 5-year-old, using simple language and familiar examples.
        
        IMPORTANT RULES:
        1. ONLY answer based on the provided study materials but you can also use your own intelligence combined with it.
        2. Format responses with:
           - Simple, everyday language
           - Familiar examples kids can relate to
           - Fun analogies and comparisons
           - Short, clear sentences
           - Visual descriptions where possible
        3. If information isn't in materials, say so and offer alternatives

        VERY IMPORTANT: At the end in bold in a new line, **SOURCE** if one document [Document Name] else if multiple documents [Document Name 1, Document Name 2...]
        Remember: Make complex ideas simple and relatable."""
    }
}

# Initialize session state variables
if 'show_upload' not in st.session_state:
    st.session_state.show_upload = False
if 'learning_style' not in st.session_state:
    st.session_state.learning_style = "detailed"
if 'context_cache' not in st.session_state:
    st.session_state.context_cache = None
if 'messages' not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! How can I help you with your studies today?"}
    ]

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
    """Process user input with appropriate system instruction based on context and learning style."""
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
            
            # Get appropriate system instruction based on learning style
            style = st.session_state.learning_style
            system_message = (
                f"{SYSTEM_INSTRUCTIONS['study_mentor'][style]}\n\n"
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

def delete_source(source_id):
    """Delete a source from the database."""
    with Session() as session:
        content = session.query(Content).filter(Content.id == source_id).first()
        if content:
            session.delete(content)
            session.commit()
            st.session_state.context_cache = None

def clear_all_sources():
    """Clear all sources from the database."""
    with Session() as session:
        session.query(Content).delete()
        session.commit()
        st.session_state.context_cache = None

def get_source_icon(title, source_type=None):
    """Get the appropriate icon based on source title/type."""
    # Check source type first
    if source_type == "youtube":
        return "🎬"  # Video icon
    
    # Then check file extensions
    lower_title = title.lower()
    if lower_title.endswith('.pdf'):
        return "📑"  # PDF icon
    elif lower_title.endswith('.html'):
        return "🌐"  # HTML icon
    elif lower_title.endswith('.py'):
        return "🐍"  # Python icon
    elif lower_title.endswith('.js'):
        return "📱"  # JavaScript icon
    elif lower_title.endswith('.css'):
        return "🎨"  # CSS icon
    elif lower_title.endswith('.txt'):
        return "📝"  # Text file icon
    elif lower_title.endswith('.md'):
        return "📋"  # Markdown icon
    elif lower_title.endswith('.csv'):
        return "📊"  # CSV/Spreadsheet icon
    elif lower_title.endswith('.xml'):
        return "🔧"  # XML icon
    elif lower_title.endswith('.json'):
        return "📦"  # JSON icon
    else:
        return "📄"  # Default document icon

# Left sidebar with tabs for Sources and Settings
with st.sidebar:
    sources_tab, settings_tab = st.tabs(["📚 Sources", "⚙️ Settings"])
    
    # Sources Tab
    with sources_tab:
        st.title("Sources")
        
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button("Add Source"):
                st.session_state.show_upload = True
                st.rerun()
        with col2:
            if st.button("Clear All"):
                st.session_state.show_clear_confirm = True
                st.rerun()
        
        # Show clear all confirmation
        if st.session_state.get('show_clear_confirm', False):
            st.warning("Are you sure you want to delete all sources?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Yes", key="clear_yes"):
                    clear_all_sources()
                    st.session_state.show_clear_confirm = False
                    st.rerun()
            with col2:
                if st.button("No", key="clear_no"):
                    st.session_state.show_clear_confirm = False
                    st.rerun()
        
        # Show upload section when Add Source is clicked
        if st.session_state.get('show_upload', False):
            st.write("### Upload Study Materials")
            upload_tab = st.radio("Select Source Type:", ["Document", "YouTube", "Website Link"], horizontal=True)
            
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
            
            elif upload_tab == "YouTube":  # YouTube tab
                youtube_url = st.text_input("Enter YouTube URL")
                if youtube_url:
                    try:
                        with st.spinner("Processing video..."):
                            processor = YouTubeProcessor()
                            # Create new session for processing
                            with Session() as session:
                                content = processor.process_video(youtube_url)
                                if content:
                                    # Update source type within the same session
                                    content.source_type = "youtube"
                                    session.add(content)
                                    session.commit()
                                    session.refresh(content)
                                    
                                    st.success("Successfully processed video")
                                    st.session_state.context_cache = None
                                    st.session_state.show_upload = False
                                    st.rerun()
                                else:
                                    st.error("Failed to process video")
                    except Exception as e:
                        st.error(f"Error processing video: {str(e)}")
            
            else:  # Website Link tab
                st.write("Enter a website URL to process its content")
                st.write("Note: Processing may take a few moments depending on the website size")
                website_url = st.text_input("Enter Website URL (include http:// or https://)")
                
                if website_url:
                    try:
                        progress_placeholder = st.empty()
                        with st.spinner("Processing website content..."):
                            progress_placeholder.info("Fetching website content...")
                            processor = LinkProcessor()
                            
                            # Process the link first
                            progress_placeholder.info("Analyzing content...")
                            content, title, url = processor.process_link(website_url)
                            
                            if content and title and url:
                                # Create new session for database operations
                                with Session() as session:
                                    progress_placeholder.info("Saving processed content...")
                                    
                                    # Update content properties
                                    content.title = title
                                    content.source_type = "website"
                                    content.url = url
                                    
                                    # Add and commit within the same session
                                    session.add(content)
                                    session.commit()
                                    
                                    progress_placeholder.success("Successfully processed website content")
                                    st.session_state.context_cache = None
                                    st.session_state.show_upload = False
                                    st.rerun()
                            else:
                                progress_placeholder.error("Failed to process website content. The content might be too complex or not accessible.")
                    except ValueError as e:
                        st.error(str(e))
                    except Exception as e:
                        error_msg = str(e)
                        if "took too long to respond" in error_msg:
                            st.error("⏱️ " + error_msg)
                        elif "Error accessing website" in error_msg:
                            st.error("🌐 " + error_msg + "\nPlease check if the URL is correct and the website is accessible.")
                        else:
                            st.error("❌ " + error_msg)
            
            # Hide upload section button
            if st.button("❌ Cancel"):
                st.session_state.show_upload = False
                st.rerun()
        
        # Get all sources
        with Session() as session:
            sources = session.query(Content).all()
            
            if not sources:
                st.info("No sources added yet. Click 'Add Source' to get started!")
            else:
                for source in sources:
                    cols = st.columns([12, 1.5])
                    with cols[0]:
                        source_icon = get_source_icon(source.title, getattr(source, 'source_type', None))
                        with st.expander(f"{source_icon} {source.title}", expanded=False):
                            if source.summary:
                                st.write("**Summary:** " + source.summary)
                            if source.key_points:
                                st.write("**Key Points:** " + source.key_points)
                    with cols[1]:
                        if st.button("❌", key=f"delete_{source.id}", help="Delete this source", use_container_width=True):
                            st.session_state[f'confirm_delete_{source.id}'] = True
                            st.rerun()
                    
                    # Show delete confirmation below the source
                    if st.session_state.get(f'confirm_delete_{source.id}', False):
                        st.warning(f"Are you sure you want to delete '{source.title}'?")
                        conf_col1, conf_col2 = st.columns(2)
                        with conf_col1:
                            if st.button("Yes", key=f"yes_{source.id}"):
                                delete_source(source.id)
                                st.session_state.pop(f'confirm_delete_{source.id}')
                                st.rerun()
                        with conf_col2:
                            if st.button("No", key=f"no_{source.id}"):
                                st.session_state.pop(f'confirm_delete_{source.id}')
                                st.rerun()
                    
    # Settings Tab
    with settings_tab:
        st.title("Settings")
        
        # Learning Style
        st.write("### Learning Style")
        learning_style = st.selectbox(
            "Choose how you want information presented:",
            options=["detailed", "bullet_points", "eli5"],
            format_func=lambda x: {
                "detailed": "Detailed Explanations",
                "bullet_points": "Bullet Point Summaries",
                "eli5": "Explain Like I'm 5"
            }[x],
            key="learning_style_select"
        )
        
        if learning_style != st.session_state.learning_style:
            st.session_state.learning_style = learning_style
            st.success(f"Learning style updated to: {learning_style}")
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