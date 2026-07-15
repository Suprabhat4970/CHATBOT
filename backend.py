from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
import sqlite3
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.messages import BaseMessage, AIMessage, SystemMessage


import yfinance as yf
import requests
from pypdf import PdfReader
from docx import Document
import pandas as pd
import os
import pytesseract

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

load_dotenv()

# ================= Gemini =================

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0
)
@tool
def calculator(first_num: float, second_num: float, operation: str):
    """
    Supported operations:
    add, sub, mul, div
    """

    if operation == "add":
        return first_num + second_num

    elif operation == "sub":
        return first_num - second_num

    elif operation == "mul":
        return first_num * second_num

    elif operation == "div":
        if second_num == 0:
            return "Division by zero not allowed"

        return first_num / second_num

    return "Invalid operation"

@tool
def get_weather(city: str):
    """
    Get weather of a city
    """

    try:
        data = requests.get(
            f"https://wttr.in/{city}?format=j1"
        ).json()

        return {
            "temperature": data["current_condition"][0]["temp_C"],
            "humidity": data["current_condition"][0]["humidity"],
            "weather": data["current_condition"][0]["weatherDesc"][0]["value"]
        }

    except Exception as e:
        return str(e)


@tool
def stock_price(symbol: str):
    """
    Get latest stock price for a stock symbol.
    """
    stock = yf.Ticker(symbol)
    data = stock.history(period="1d")
    return float(data["Close"].iloc[-1])
@tool
def youtube_search(query: str):
    """
    Search YouTube and return a search URL.
    """
    return (
        "https://www.youtube.com/results?search_query="
        + query.replace(" ", "+")
    )
search_tool = DuckDuckGoSearchRun()

search_tool.description = """
Search the internet for current information.

Use ONLY when:
- latest news
- current events
- today's information
- real-time facts

Do NOT use for:
- definitions
- explanations
- programming
- general knowledge
"""

# ==========================================
# Document Tool
# ==========================================


def read_uploaded_file(file_path):

    if not os.path.exists(file_path):
        return ""

    try:
        if file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        elif file_path.endswith(".pdf"):
            try:
                reader = PdfReader(file_path)

                print("Pages:", len(reader.pages))

                text = ""

                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()

                    print("PAGE", i + 1)
                    print(repr(page_text))

                    if page_text:
                        text += page_text

                print("TOTAL CHARS:", len(text))

                if len(text.strip()) > 50:
                    return text
            except Exception as e:
                print("PyPDF ERROR:", e)

            # OCR fallback
            # try:
            #     from pdf2image import convert_from_path
            #
            #     pages = convert_from_path(file_path)
            #
            #     ocr_text = ""
            #
            #     for page in pages:
            #         ocr_text += pytesseract.image_to_string(page)
            #
            #     print("OCR CHARS:", len(ocr_text))
            #
            #     return ocr_text
            #
            # except Exception as e:
            #     print("OCR ERROR:", e)

        elif file_path.endswith(".docx"):
            doc = Document(file_path)
            return "\n".join(para.text for para in doc.paragraphs)

        elif file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
            return df.to_string()

        elif file_path.endswith(".xlsx"):
            df = pd.read_excel(file_path)
            return df.to_string()

    except Exception as e:
        return f"File Read Error: {str(e)}"

    return ""
@tool
def read_uploaded_document(text: str):
    """
    Read uploaded document content and answer questions from it.
    """
    return text


tools = [
    search_tool,
    calculator,
    get_weather,
    stock_price,
    youtube_search,
    read_uploaded_document
]

llm_with_tools = llm.bind_tools(tools)
# ================= Database Setup =================

def init_db():

    conn = sqlite3.connect("chatbot.db")

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversations(
        thread_id TEXT PRIMARY KEY,
        title TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= Long Term Memory =================

def init_memory_db():

    conn = sqlite3.connect("memory.db")

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS memories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_memory(memory):

    conn = sqlite3.connect("memory.db")

    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO memories(memory) VALUES(?)",
        (memory,)
    )

    conn.commit()
    conn.close()


def load_memory():

    conn = sqlite3.connect("memory.db")

    cursor = conn.cursor()

    cursor.execute(
        "SELECT memory FROM memories"
    )

    rows = cursor.fetchall()

    conn.close()

    return "\n".join(
        row[0]
        for row in rows
    )


init_memory_db()
# ================= Conversation Functions =================

def save_conversation(thread_id, title):

    conn = sqlite3.connect("chatbot.db")

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO conversations
        (thread_id, title)
        VALUES (?, ?)
        """,
        (thread_id, title)
    )

    conn.commit()
    conn.close()


def load_conversations():

    conn = sqlite3.connect("chatbot.db")

    cursor = conn.cursor()

    cursor.execute("""
    SELECT thread_id, title
    FROM conversations
    ORDER BY rowid DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return {
        row[0]: row[1]
        for row in rows
    }

# ================= Title Generator =================

def generate_title(user_message):

    try:

        prompt = f"""
Create a short chat title.
Maximum 5 words.

User Message:
{user_message}

Return only the title.
"""

        response = llm.invoke(prompt)

        return response.content.strip()

    except Exception:

        return (
            user_message[:40] + "..."
            if len(user_message) > 40
            else user_message
        )

# ================= LangGraph State =================

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    file_content: str


def needs_tools(query: str):
    query = query.lower()

    calculator_keywords = [
        "+", "-", "*", "/", "calculate",
        "multiply", "divide", "subtract", "add"
    ]

    weather_keywords = [
        "weather",
        "temperature",
        "forecast",
        "rain"
    ]

    news_keywords = [
        "latest",
        "today",
        "news",
        "current",
        "breaking"
    ]

    stock_keywords = [
        "stock",
        "share",
        "price",
        "nse",
        "bse"
    ]

    youtube_keywords = [
        "youtube",
        "video"
    ]

    if any(k in query for k in calculator_keywords):
        return True

    if any(k in query for k in weather_keywords):
        return True

    if any(k in query for k in news_keywords):
        return True

    if any(k in query for k in stock_keywords):
        return True

    if any(k in query for k in youtube_keywords):
        return True

    return False
# ================= Chat Node =================
def chat_node(state: ChatState):

    messages = state["messages"]

    try:

        file_content = state.get(
            "file_content",
            ""
        )
        long_term_memory = load_memory()
        print("FILE CONTENT LENGTH:", len(file_content))
        
        system_prompt = SystemMessage(
            content=f"""
You are a helpful AI assistant.

LONG TERM MEMORY:

{long_term_memory}

IMPORTANT:
- Use long-term memory when relevant.
- If user asks about themselves, check memory first.
- Use document information if available.

DOCUMENT CONTENT:

{file_content[:15000]}
"""
        )
        query = messages[-1].content

        print("USER:", query)
        print("TOOLS:", needs_tools(query))
        if needs_tools(messages[-1].content):
            response = llm_with_tools.invoke(
                [system_prompt] + messages
            )
        else:
            response = llm.invoke(
                [system_prompt] + messages
            )

        return {
            "messages": [response]
        }

    except Exception as e:

        print("ERROR:", e)

        return {
            "messages": [
                AIMessage(
                    content=f"ERROR: {str(e)}"
                )
            ]
        }

tool_node = ToolNode(tools)
# ================= LangGraph =================

checkpoint_conn = sqlite3.connect(
    "chatbot_memory.db",
    check_same_thread=False
)

checkpointer = SqliteSaver(checkpoint_conn)

graph = StateGraph(ChatState)

graph.add_node(
    "chat_node",
    chat_node
)

graph.add_node(
    "tools",
    tool_node
)

graph.add_edge(
    START,
    "chat_node"
)

graph.add_conditional_edges(
    "chat_node",
    tools_condition
)

graph.add_edge(
    "tools",
    "chat_node"
)
chatbot = graph.compile(
    checkpointer=checkpointer
)

print("Backend Loaded Successfully")