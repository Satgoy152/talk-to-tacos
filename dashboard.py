from dotenv import load_dotenv
import os
load_dotenv()
import streamlit as st

# Set custom page config and favicon
st.set_page_config(
    page_title="Optiwise Tacos AI Agent",
    page_icon="img/optiwise.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Improved logo and title alignment with public logo URL
st.markdown("""
    <div style="display: flex; align-items: center; gap: 2.5rem; margin-bottom: 1.5rem;">
        <div style="background-color: white; padding: 0.75rem; border-radius: 12px; box-shadow: 0 2px 8px #0002;">
            <img src="https://www.optiwise.ai/wp-content/uploads/2022/10/optiwise_logo_Color.png" alt="Optiwise Logo" style="height: 90px; display: block;">
        </div>
        <div>
            <h1 style='margin-bottom:0; color:#FFFFFF; font-size:2.6rem; font-weight:800; letter-spacing:-1px;'>Optiwise Tacos AI Agent</h1>
            <p style='font-size:1.25rem; color:#FFFFFF; margin-top:0.5rem;'>Get deep insights and answers about your <b>Tacos report</b> with our smart AI agent.</p>
        </div>
    </div>
""", unsafe_allow_html=True)

# Handle Google credentials
# if "GOOGLE_APPLICATION_CREDENTIALS_JSON" in st.secrets:
#     with open("gcp_creds.json", "w") as f:
#         f.write(st.secrets["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
#     os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp_creds.json"

import pandas as pd
from database import create_db_from_excel, query_db
from agent import get_agent_response
from conversation_store import ConversationStore
import uuid

# Initialize conversation store
conversation_store = ConversationStore()

# File uploader
st.markdown("""
    <div style='margin-top: 1.5rem; margin-bottom: 1.2rem;'>
        <b style='color:#FFFFFF;'>Upload your Tacos Excel report:</b>
    </div>
""", unsafe_allow_html=True)
uploaded_file = st.file_uploader("", type=["xlsx"], label_visibility="collapsed")

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
            if message["role"] == "assistant":
                with st.chat_message("assistant", avatar="https://app.optiwise.ai/assets/olivia-IF0pvoa5.png"):
                    st.markdown(message["content"])
            else:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # React to user input
        if prompt := st.chat_input("Ask anything about your Tacos report:"):
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
                with st.chat_message("assistant", avatar="https://app.optiwise.ai/assets/olivia-IF0pvoa5.png"):
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
            st.header(":blue[Conversation History]")
            conversations = conversation_store.get_all_conversations()
            if conversations:
                st.write(":green[Recent conversations:]")
                for conv in conversations:
                    thread_id, db_path, created_at, msg_count, last_msg = conv
                    st.write(f"**Thread:** `{thread_id[:8]}...`  ")
                    st.write(f"Messages: {msg_count}")
                    st.write(f"Last message: {last_msg}")
                    st.write("---")
            else:
                st.write(":gray[No conversation history yet.]")

    except Exception as e:
        st.error(f"Error processing Excel file: {e}")
    finally:
        # Clean up temporary files
        if os.path.exists("temp_excel.xlsx"):
            os.remove("temp_excel.xlsx")
        # if os.path.exists(db_path): # Keep the DB for the session or remove if not needed
        #     os.remove(db_path)
else:
    st.markdown("""
        <div style='background: #dbeafe; color: #111; padding: 1.2rem 1.5rem; border-radius: 16px; font-size: 1.18rem; font-weight: 500;'>
            Please upload a Tacos Excel report to begin.
        </div>
    """, unsafe_allow_html=True)
    
    st.session_state.file_uploaded = False