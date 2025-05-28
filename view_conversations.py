import sqlite3
import json
from datetime import datetime
from tabulate import tabulate

def view_conversations():
    # Connect to the conversations database
    conn = sqlite3.connect('conversations.db')
    cursor = conn.cursor()
    
    # Get all conversations
    cursor.execute('''
        SELECT c.id, c.thread_id, c.db_path, c.created_at,
               COUNT(m.id) as message_count,
               MAX(m.timestamp) as last_message_time
        FROM conversations c
        LEFT JOIN messages m ON c.id = m.conversation_id
        GROUP BY c.id
        ORDER BY last_message_time DESC
    ''')
    conversations = cursor.fetchall()
    
    print("\n=== All Conversations ===")
    headers = ["ID", "Thread ID", "Database", "Created At", "Messages", "Last Message"]
    print(tabulate(conversations, headers=headers, tablefmt="grid"))
    
    # For each conversation, show detailed messages
    for conv in conversations:
        conv_id, thread_id, db_path, created_at, msg_count, last_msg = conv
        print(f"\n{'='*80}")
        print(f"CONVERSATION #{conv_id}")
        print(f"Thread ID: {thread_id}")
        print(f"Database: {db_path}")
        print(f"Started: {created_at}")
        print(f"Total Messages: {msg_count}")
        print(f"Last Message: {last_msg}")
        print(f"{'='*80}")
        
        # Get all messages for this conversation
        cursor.execute('''
            SELECT m.id, m.role, m.content, m.timestamp, m.metadata
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.thread_id = ?
            ORDER BY m.timestamp ASC
        ''', (thread_id,))
        messages = cursor.fetchall()
        
        print("\nMessages in this conversation:")
        for msg in messages:
            msg_id, role, content, timestamp, metadata = msg
            print(f"\nMessage #{msg_id}")
            print(f"Time: {timestamp}")
            print(f"Role: {role.upper()}")
            print(f"Content: {content}")
            if metadata:
                print(f"Metadata: {json.loads(metadata)}")
            print("-" * 80)

if __name__ == "__main__":
    view_conversations() 