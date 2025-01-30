# StudyMate AI

StudyMate AI is an intelligent, chat-based study assistant that helps students understand educational content from multiple sources using Google's Gemini AI.

## Features

- Process YouTube lecture videos with summaries and key points
- Analyze PDFs and web pages for content extraction
- Multi-source data fusion for cross-referencing concepts
- Interactive chat interface with contextual answers
- Multiple summarization styles
- Flashcard generation
- Google Search integration

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the root directory with your Google API key:
```
GOOGLE_API_KEY=your_api_key_here
```

3. Run the application:
```bash
streamlit run app.py
```

## Project Structure

- `app.py`: Main Streamlit application
- `src/`
  - `processors/`: Content processing modules
  - `models/`: Database models
  - `utils/`: Utility functions
  - `services/`: Core services (Gemini AI, Celery tasks)
- `database/`: SQLite database files
