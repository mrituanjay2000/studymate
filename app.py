import streamlit as st
import google.generativeai as genai
from src.models.database import init_db, Session, Content
from src.processors.document_processor import DocumentProcessor, SUPPORTED_EXTENSIONS
from src.processors.youtube_processor import YouTubeProcessor
import os
from dotenv import load_dotenv
import tempfile
import logging

# Initialize
load_dotenv()
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
init_db()

st.set_page_config(page_title="StudyMate AI", layout="wide")
st.title("StudyMate AI")

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'context_cache' not in st.session_state:
    st.session_state.context_cache = None

def get_context():
    """Cache and return the context from the database."""
    if st.session_state.context_cache is None:
        session = Session()
        contents = session.query(Content).all()
        if contents:
            context = "\n\n".join([
                f"Content from '{c.title}':\n{c.summary}"
                for c in contents
            ])
        else:
            context = "No study materials available yet."
        st.session_state.context_cache = context
    return st.session_state.context_cache

def process_user_input(user_input):
    """Process user input with cached context."""
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        context = get_context()
        
        prompt = f"""As a helpful study assistant, use the following context and your knowledge to answer the user's question.
        If referencing specific content, mention the source.
        
        Context:
        {context}
        
        User question: {user_input}
        
        Answer concisely and clearly."""
        
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.7,
                "top_k": 40,
                "top_p": 0.8,
                "max_output_tokens": 1024,
            }
        )
        return response.text
    except Exception as e:
        return f"I apologize, but I encountered an error: {str(e)}"

# Sidebar for content upload
with st.sidebar:
    st.header("Add Study Material")
    
    # Clear contents button
    if st.button("Clear All Study Materials", type="secondary"):
        session = Session()
        session.query(Content).delete()
        session.commit()
        st.session_state.context_cache = None
        st.success("All study materials have been cleared!")
        st.rerun()
    
    st.divider()
    
    # YouTube URL input with submit button
    with st.form("youtube_form"):
        youtube_url = st.text_input("YouTube Video URL")
        submit_youtube = st.form_submit_button("Process Video")
        if submit_youtube and youtube_url:
            with st.spinner("Processing YouTube video..."):
                processor = YouTubeProcessor()
                content = processor.process_video(youtube_url)
                if content:
                    st.session_state.context_cache = None
                    st.success("Video processed successfully!")
                else:
                    st.error("Error processing video. Please check the URL and try again.")
    
    # Document upload
    with st.form("document_form"):
        st.write("Supported formats: PDF, Python, JavaScript, HTML, CSS, TXT, Markdown, CSV, XML, RTF")
        uploaded_file = st.file_uploader("Upload Document", type=[ext[1:] for ext in SUPPORTED_EXTENSIONS])
        submit_doc = st.form_submit_button("Process Document")
        if submit_doc and uploaded_file:
            # Create a temporary file and ensure it's properly closed
            temp_dir = tempfile.mkdtemp()
            original_filename = uploaded_file.name
            temp_path = os.path.join(temp_dir, original_filename)
            
            try:
                # Write the uploaded file to the temporary path
                with open(temp_path, 'wb') as f:
                    f.write(uploaded_file.getvalue())
                
                # Process the document
                with st.spinner("Processing document..."):
                    processor = DocumentProcessor()
                    content = processor.process_document(temp_path)
                    if content:
                        st.session_state.context_cache = None
                        st.success("Document processed successfully!")
                    else:
                        st.error("Error processing document. Please try again.")
            except Exception as e:
                st.error(f"Error processing document: {str(e)}")
            finally:
                # Clean up: close file handles and remove temporary directory
                try:
                    os.unlink(temp_path)
                    os.rmdir(temp_dir)
                except Exception as e:
                    logging.error(f"Error cleaning up temporary files: {str(e)}")

# Main chat interface
st.header("Chat with StudyMate")

# Display chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Ask a question about your study materials...")
    submit_chat = st.form_submit_button("Send")
    if submit_chat and user_input:
        # Display user message
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        # Generate and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = process_user_input(user_input)
                st.write(response)
        st.session_state.chat_history.append({"role": "assistant", "content": response})

# Display processed content
st.header("Study Materials")
session = Session()
contents = session.query(Content).all()

for content in contents:
    with st.expander(f"{content.title} ({content.type})"):
        st.write("Summary:")
        st.write(content.summary)
        if content.key_points:
            st.write("Key Points:")
            st.write(content.key_points)
