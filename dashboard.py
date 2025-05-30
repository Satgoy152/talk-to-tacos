from dotenv import load_dotenv
load_dotenv()
import streamlit as st
import pandas as pd
from database import create_db_from_excel, query_db
from agent import get_agent_response
from conversation_store import ConversationStore
import os
import uuid

# Initialize conversation store
conversation_store = ConversationStore()

# Title for the app
st.title("SQL AI Agent for E-commerce Data")

# File uploader
uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])

# Check if a file has been uploaded
if 'file_uploaded' not in st.session_state:
    st.session_state.file_uploaded = False

if uploaded_file is not None:
    # Save the uploaded file temporarily
    with open("temp_excel.xlsx", "wb") as f:
        f.write(uploaded_file.getbuffer())

    db_path = "temp_db.sqlite"

    try:
        if st.session_state.file_uploaded == False:
            create_db_from_excel("temp_excel.xlsx", db_path)
            st.success(f"Database created successfully at {db_path}!")
            st.session_state.file_uploaded = True

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Initialize a new thread_id for a new file upload/session
        if "thread_id" not in st.session_state:
            st.session_state.thread_id = str(uuid.uuid4())
            print(f"Initialized new thread_id for new DB: {st.session_state.thread_id}")
            
            # Save the new conversation
            conversation_store.save_message(
                st.session_state.thread_id,
                "system",
                "Conversation started.",
                db_path
            )
            
            # Load any existing conversation history
            history = conversation_store.get_conversation_history(st.session_state.thread_id, db_path)
            if history:
                st.session_state.messages = history

        # Display chat messages from history on app rerun
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # React to user input
        if prompt := st.chat_input("Ask a question about your data:"):
            # Display user message in chat message container
            st.chat_message("user").markdown(prompt)
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Save user message to conversation store
            conversation_store.save_message(
                st.session_state.thread_id,
                "user",
                prompt,
                db_path,
                metadata={"db_path": db_path}
            )

            # Get agent response
            try:
                response = get_agent_response(db_path, prompt, st.session_state.thread_id)
                # Display assistant response in chat message container
                with st.chat_message("assistant"):
                    st.markdown(response)
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # Save assistant response to conversation store
                conversation_store.save_message(
                    st.session_state.thread_id,
                    "assistant",
                    response,
                    db_path,
                    metadata={"db_path": db_path}
                )
            except Exception as e:
                st.error(f"Error getting response from agent: {e}")

        # Add a section to view conversation history
        with st.sidebar:
            st.header("Conversation History")
            conversations = conversation_store.get_all_conversations()
            if conversations:
                st.write("Recent conversations:")
                for conv in conversations:
                    thread_id, db_path, created_at, msg_count, last_msg = conv
                    st.write(f"Thread: {thread_id[:8]}...")
                    st.write(f"Messages: {msg_count}")
                    st.write(f"Last message: {last_msg}")
                    st.write("---")
            else:
                st.write("No conversation history yet.")

    except Exception as e:
        st.error(f"Error processing Excel file: {e}")
    finally:
        # Clean up temporary files
        if os.path.exists("temp_excel.xlsx"):
            os.remove("temp_excel.xlsx")
        # if os.path.exists(db_path): # Keep the DB for the session or remove if not needed
        #     os.remove(db_path)
else:
    st.info("Please upload an Excel file to begin.")
    
    st.session_state.file_uploaded = False