import streamlit as st
import pandas as pd
from database import create_db_from_excel, query_db
from agent import get_agent_response
import os
import uuid  # Added for generating unique thread IDs

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
        # This ensures memory is fresh for a new database.
        # If you want memory to persist across different DBs for the same user session,
        # you might initialize thread_id less frequently (e.g., once per browser tab session).
        if "thread_id" not in st.session_state:
            st.session_state.thread_id = str(uuid.uuid4())
            print(f"Initialized new thread_id for new DB: {st.session_state.thread_id}")
        

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

            # Get agent response
            try:
                # Ensure thread_id is available (it should be set above)
                if "thread_id" not in st.session_state:
                    # Fallback, though ideally it's always set when db is ready
                    st.session_state.thread_id = str(uuid.uuid4())
                    print(f"Fallback: Initialized new thread_id in chat input: {st.session_state.thread_id}")

                # Display assistant response in chat message container
                with st.chat_message("assistant"):
                    response = st.write_stream(get_agent_response(db_path, prompt, st.session_state.thread_id))
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                st.error(f"Error getting response from agent: {e}")

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