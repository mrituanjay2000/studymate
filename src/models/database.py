from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Ensure database directory exists
os.makedirs('database', exist_ok=True)

Base = declarative_base()
engine = create_engine('sqlite:///database/studymate.db', connect_args={'check_same_thread': False})
Session = sessionmaker(bind=engine)

class Content(Base):
    __tablename__ = 'content'
    
    id = Column(Integer, primary_key=True)
    type = Column(String(50))  # youtube, pdf, webpage
    source_url = Column(String(500))
    title = Column(String(200))
    content = Column(Text)
    summary = Column(Text)
    key_points = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserQuery(Base):
    __tablename__ = 'user_queries'
    
    id = Column(Integer, primary_key=True)
    query = Column(Text)
    response = Column(Text)
    content_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(engine)
