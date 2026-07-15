from backend import read_uploaded_file
import subprocess
import importlib.util
import streamlit as st
from backend import (
    chatbot,
    generate_title,
    save_conversation,
    load_conversations,
    read_uploaded_file
)
from langchain_core.messages import HumanMessage, AIMessage
import uuid
import os

st.title("Environment Check")

packages = [
    "streamlit",
    "langgraph",
    "langchain",
    "langchain_core",
    "langchain_community",
    "langchain_google_genai",
    "langgraph_checkpoint_sqlite",
    "dotenv",
    "pypdf",
    "docx",
    "pandas",
    "openpyxl",
    "requests",
    "yfinance",
    "duckduckgo_search",
    "pytesseract",
    "pdf2image"
]


for package in packages:
    installed = importlib.util.find_spec(package) is not None
    st.write(package, "✅ Installed" if installed else "❌ Missing")


st.subheader("pip list from Streamlit VM")

result = subprocess.run(
    ["pip", "list"],
    capture_output=True,
    text=True
)

st.text(result.stdout)

# **************************************** utility functions *************************

def generate_thread_id():
    return str(uuid.uuid4())

def reset_chat():
    st.session_state['thread_id'] = generate_thread_id()
    st.session_state['message_history'] = []
    st.rerun()

def add_thread(thread_id, title="New Chat"):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'][thread_id] = title

def load_conversation(thread_id):
    state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
    # Check if messages key exists in state values, return empty list if not
    return state.values.get('messages', [])


# **************************************** Session Setup ******************************
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()

if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = load_conversations()

if "uploaded_text" not in st.session_state:
    st.session_state["uploaded_text"] = ""


# **************************************** Sidebar UI *********************************
st.sidebar.image("logo.png", width=220)

col1, col2, col3 = st.columns([1,2,1])

with col2:

    if len(st.session_state["message_history"]) == 0:
        st.image("chatgenius_name_logo.png", width=350)

    else:
        st.image("chatgenius_name_logo.png", width=350)
st.sidebar.markdown("""
<style>
.new-chat {
    font-size:18px;
    padding:10px 0;
    cursor:pointer;
    color:white;
}
.new-chat:hover {
    color:#10A37F;
}
</style>
""", unsafe_allow_html=True)
new_chat = st.sidebar.button(
    "✏️  New Chat",
    use_container_width=True
)

if new_chat:
    reset_chat()

# ================= FILE UPLOAD =================

import os

st.sidebar.markdown("---")
st.sidebar.subheader("📄 Upload Document")

uploaded_file = st.sidebar.file_uploader(
    "Choose File",
    type=["pdf", "docx", "txt", "csv", "xlsx"]
)

if uploaded_file:

    os.makedirs("uploads", exist_ok=True)

    file_path = os.path.join(
        "uploads",
        uploaded_file.name
    )

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.session_state["file_path"] = file_path

    # READ DOCUMENT
    file_content = read_uploaded_file(file_path)
    print(file_content[:500])

    st.session_state["file_content"] = file_content

    st.sidebar.success(f"✅ {uploaded_file.name}")

    st.sidebar.write(
        f"Loaded {len(file_content)} characters"
    )

    st.sidebar.write(
        f"Loaded {len(file_content)} characters"
    )

# ==============================================

st.sidebar.header('My Conversations')

for thread_id, title in st.session_state['chat_threads'].items():

    if st.sidebar.button(
        f"💬 {title}",
        key=thread_id,
        use_container_width=True
    ):

        st.session_state['thread_id'] = thread_id

        messages = load_conversation(thread_id)

        temp_messages = []

        for msg in messages:

            if isinstance(msg, HumanMessage):
                role = "user"
                content = msg.content

            else:
                role = "assistant"

                if isinstance(msg.content, str):
                    content = msg.content

                elif isinstance(msg.content, list):

                    text = ""

                    for item in msg.content:

                        if (
                            isinstance(item, dict)
                            and item.get("type") == "text"
                        ):
                            text += item.get("text", "")

                    content = text

                else:
                    content = str(msg.content)

            temp_messages.append(
                {
                    "role": role,
                    "content": content
                }
            )

        st.session_state["message_history"] = temp_messages
        st.rerun()
# **************************************** Main UI ************************************
for i, message in enumerate(st.session_state["message_history"]):

    if message["role"] == "user":

        with st.chat_message("user"):
            st.markdown(message["content"])

    else:

        with st.chat_message("assistant"):
            st.markdown(message["content"])

# ******************************** Chat Input ********************************

user_input = st.chat_input("Type here")

if user_input:
    if user_input.lower().startswith("remember"):
        from backend import save_memory

        save_memory(user_input)

        st.success("Memory Saved!")

    if len(st.session_state['message_history']) == 0:

        title = generate_title(user_input)

        add_thread(
            st.session_state['thread_id'],
            title
        )

        save_conversation(
            st.session_state['thread_id'],
            title
        )

        st.session_state['chat_threads'] = load_conversations()

    st.session_state['message_history'].append(
        {
            'role': 'user',
            'content': user_input
        }
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    CONFIG = {
        "configurable": {
            "thread_id": st.session_state["thread_id"]
        }
    }

    document_context = ""

    if st.session_state["uploaded_text"]:
        document_context = f"""
Uploaded Document:

{st.session_state['uploaded_text']}

User Question:
{user_input}
"""

    else:
        document_context = user_input

    result = chatbot.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],
            "file_content": st.session_state.get(
                "file_content",
                ""
            )
        },
        config=CONFIG
    )

    last_message = result["messages"][-1]

    if isinstance(last_message.content, str):
        ai_message = last_message.content

    elif isinstance(last_message.content, list):

        ai_message = ""

        for item in last_message.content:

            if (
                isinstance(item, dict)
                and item.get("type") == "text"
            ):
                ai_message += item.get("text", "")

    else:
        ai_message = str(last_message.content)

    with st.chat_message("assistant"):
        st.markdown(ai_message)

    st.session_state['message_history'].append(
        {
            "role": "assistant",
            "content": ai_message
        }
    )
   