import sqlite3
from datetime import datetime
import json

class ConversationStore:
    def __init__(self, db_path="conversations.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create conversations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    db_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(thread_id)
                )
            ''')
            
            # Create messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            ''')
            
            conn.commit()

    def save_conversation(self, thread_id: str, db_path: str):
        """Save a new conversation or get existing one."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO conversations (thread_id, db_path)
                VALUES (?, ?)
            ''', (thread_id, db_path))
            
            # Get the conversation ID
            cursor.execute('SELECT id FROM conversations WHERE thread_id = ?', (thread_id,))
            conversation_id = cursor.fetchone()[0]
            conn.commit()
            return conversation_id

    def save_message(self, thread_id: str, role: str, content: str, metadata: dict = None):
        """Save a message to the conversation."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get conversation ID
            cursor.execute('SELECT id FROM conversations WHERE thread_id = ?', (thread_id,))
            result = cursor.fetchone()
            if not result:
                raise ValueError(f"No conversation found for thread_id: {thread_id}")
            
            conversation_id = result[0]
            
            # Save message
            cursor.execute('''
                INSERT INTO messages (conversation_id, role, content, metadata)
                VALUES (?, ?, ?, ?)
            ''', (conversation_id, role, content, json.dumps(metadata) if metadata else None))
            
            conn.commit()

    def get_conversation_history(self, thread_id: str, limit: int = None):
        """Retrieve conversation history for a thread."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get conversation ID
            cursor.execute('SELECT id FROM conversations WHERE thread_id = ?', (thread_id,))
            result = cursor.fetchone()
            if not result:
                return []
            
            conversation_id = result[0]
            
            # Get messages
            query = '''
                SELECT role, content, timestamp, metadata
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            '''
            
            if limit:
                query += f' LIMIT {limit}'
            
            cursor.execute(query, (conversation_id,))
            messages = cursor.fetchall()
            
            return [
                {
                    'role': msg[0],
                    'content': msg[1],
                    'timestamp': msg[2],
                    'metadata': json.loads(msg[3]) if msg[3] else None
                }
                for msg in messages
            ]

    def get_all_conversations(self):
        """Get all conversations with their metadata."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.thread_id, c.db_path, c.created_at,
                       COUNT(m.id) as message_count,
                       MAX(m.timestamp) as last_message_time
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                GROUP BY c.id
                ORDER BY last_message_time DESC
            ''')
            return cursor.fetchall()

    def delete_conversation(self, thread_id: str):
        """Delete a conversation and all its messages."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM conversations WHERE thread_id = ?', (thread_id,))
            conn.commit() 