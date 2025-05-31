import json
from datetime import datetime
import uuid
from google.cloud.sql.connector import Connector
import mysql.connector
from gcp_config import DB_CONFIG

class ConversationStore:
    def __init__(self):
        self.connector = Connector()
        self._init_db()

    def _get_connection(self):
        """Get a connection to the Cloud SQL MySQL instance."""
        def getconn():
            conn = self.connector.connect(
                instance_connection_string=DB_CONFIG['instance_connection_name'],
                driver="pymysql",
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'](),
                db=DB_CONFIG['database'],
            )
            return conn
        return getconn()

    def _init_db(self):
        """Initialize the database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Create conversations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    thread_id VARCHAR(255) NOT NULL,
                    db_path VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Create messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    conversation_id INT,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            ''')
            conn.commit()

    def save_message(self, thread_id, role, content, db_path, metadata=None):
        """Save a message to the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Get or create conversation
            cursor.execute('''
                SELECT id FROM conversations 
                WHERE thread_id = %s AND db_path = %s
            ''', (thread_id, db_path))
            result = cursor.fetchone()
            if result:
                conversation_id = result[0]
            else:
                cursor.execute('''
                    INSERT INTO conversations (thread_id, db_path)
                    VALUES (%s, %s)
                ''', (thread_id, db_path))
                conversation_id = cursor.lastrowid
            # Insert message
            cursor.execute('''
                INSERT INTO messages (conversation_id, role, content, metadata)
                VALUES (%s, %s, %s, %s)
            ''', (conversation_id, role, content, json.dumps(metadata) if metadata else None))
            conn.commit()

    def get_conversation_history(self, thread_id, db_path):
        """Get conversation history for a specific thread and database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.role, m.content, m.timestamp, m.metadata
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.thread_id = %s AND c.db_path = %s
                ORDER BY m.timestamp ASC
            ''', (thread_id, db_path))
            rows = cursor.fetchall()
            # Convert the rows into the expected format
            return [{"role": row[0], "content": row[1]} for row in rows]

    def get_all_conversations(self):
        """Get all conversations with their message counts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.thread_id, c.db_path, c.created_at,
                       COUNT(m.id) as message_count,
                       MAX(m.timestamp) as last_message_time
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                GROUP BY c.id, c.thread_id, c.db_path, c.created_at
                ORDER BY last_message_time DESC
            ''')
            return cursor.fetchall()

    def get_popular_questions(self):
        """Get popular questions from the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT question 
                    FROM popular_questions 
                    ORDER BY created_at DESC
                ''')
                questions = cursor.fetchall()
                return [row[0] for row in questions] if questions else []
        except Exception as e:
            print(f"Error fetching popular questions: {e}")
            return []

    def __del__(self):
        self.connector.close() 