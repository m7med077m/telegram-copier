import sqlite3
import json
import logging
from typing import Dict, List, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "bot.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Connect to SQLite database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            # Users table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    is_vip BOOLEAN DEFAULT FALSE,
                    is_owner BOOLEAN DEFAULT FALSE,
                    message_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Sessions table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id INTEGER PRIMARY KEY,
                    session_string TEXT,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Copy jobs table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_jobs (
                    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    source_channel TEXT,
                    target_channel TEXT,
                    start_msg_id INTEGER,
                    end_msg_id INTEGER,
                    status TEXT DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
    
    def add_user(self, user_id: int, username: Optional[str] = None, is_owner: bool = False):
        """Add a new user to the database"""
        try:
            self.cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, is_owner)
                VALUES (?, ?, ?)
            """, (user_id, username, is_owner))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            raise
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user details from database"""
        try:
            self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = self.cursor.fetchone()
            return dict(user) if user else None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    def set_vip_status(self, user_id: int, is_vip: bool):
        """Set user's VIP status"""
        try:
            self.cursor.execute("""
                UPDATE users SET is_vip = ? WHERE user_id = ?
            """, (is_vip, user_id))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error setting VIP status: {e}")
            raise
    
    def get_all_vip_users(self) -> List[Dict]:
        """Get all VIP users"""
        try:
            self.cursor.execute("SELECT * FROM users WHERE is_vip = TRUE")
            users = self.cursor.fetchall()
            return [dict(user) for user in users]
        except Exception as e:
            logger.error(f"Error getting VIP users: {e}")
            return []
    
    def increment_message_count(self, user_id: int):
        """Increment user's message count"""
        try:
            self.cursor.execute("""
                UPDATE users SET message_count = message_count + 1
                WHERE user_id = ?
            """, (user_id,))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error incrementing message count: {e}")
            raise
    
    def reset_message_count(self, user_id: int):
        """Reset user's message count"""
        try:
            self.cursor.execute("""
                UPDATE users SET message_count = 0
                WHERE user_id = ?
            """, (user_id,))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error resetting message count: {e}")
            raise
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics"""
        try:
            self.cursor.execute("""
                SELECT user_id, username, is_vip, is_owner, message_count
                FROM users WHERE user_id = ?
            """, (user_id,))
            user = self.cursor.fetchone()
            
            if not user:
                return {
                    'message_count': 0,
                    'is_vip': False,
                    'is_owner': False
                }
            
            return dict(user)
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {
                'message_count': 0,
                'is_vip': False,
                'is_owner': False
            }
    
    def save_session(self, user_id: int, session_string: str):
        """Save user's session string"""
        try:
            self.cursor.execute("""
                INSERT OR REPLACE INTO sessions (user_id, session_string)
                VALUES (?, ?)
            """, (user_id, session_string))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving session: {e}")
            raise
    
    def get_session(self, user_id: int) -> Optional[str]:
        """Get user's session string"""
        try:
            self.cursor.execute("""
                SELECT session_string FROM sessions WHERE user_id = ?
            """, (user_id,))
            result = self.cursor.fetchone()
            return result['session_string'] if result else None
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    def create_copy_job(self, user_id: int, source_channel: str, target_channel: str,
                       start_msg_id: int, end_msg_id: int) -> int:
        """Create a new copy job"""
        try:
            self.cursor.execute("""
                INSERT INTO copy_jobs (
                    user_id, source_channel, target_channel,
                    start_msg_id, end_msg_id
                ) VALUES (?, ?, ?, ?, ?)
            """, (user_id, source_channel, target_channel, start_msg_id, end_msg_id))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            logger.error(f"Error creating copy job: {e}")
            raise
    
    def update_job_status(self, job_id: int, status: str, progress: int = 0):
        """Update copy job status and progress"""
        try:
            self.cursor.execute("""
                UPDATE copy_jobs SET status = ?, progress = ?
                WHERE job_id = ?
            """, (status, progress, job_id))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error updating job status: {e}")
            raise
    
    def get_job_status(self, job_id: int) -> Optional[Dict]:
        """Get copy job status"""
        try:
            self.cursor.execute("""
                SELECT * FROM copy_jobs WHERE job_id = ?
            """, (job_id,))
            job = self.cursor.fetchone()
            return dict(job) if job else None
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return None
    
    def close(self):
        """Close database connection"""
        try:
            if self.conn:
                self.conn.close()
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
            raise 