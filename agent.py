import os
import time
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate # Keep for potential future use
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage # For constructing messages
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver # Added for memory
from database import query_db, get_db_schema
from dotenv import load_dotenv

# Configure logging to output to console/terminal
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # This ensures output goes to console/terminal
    ]
)

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found. Please set it in your .env file or environment.")

# Global checkpointer for storing conversation states
checkpointer = InMemorySaver()

# --- Database Query Tool (as previously defined) --- #
@tool
def database_query_tool(query: str, db_path: str):
    """
    Executes a SQL query against the specified SQLite database and returns the result.
    The query should be a valid SQL SELECT statement.
    Use this tool to answer questions about the data in the database.
    Example query: 'SELECT * FROM customers WHERE country = "USA"';
    """
    db_start_time = time.time()
    print(f"Executing query: {query} on db: {db_path}")
    logging.info(f"🔍 DB Query started: {query[:100]}...")
    
    result = query_db(db_path, query)
    
    db_end_time = time.time()
    db_execution_time = db_end_time - db_start_time
    result_size = len(str(result)) if result else 0
    logging.info(f"📊 DB Query completed in {db_execution_time:.3f}s | Result size: {result_size} chars")
    
    return result

# System prompt template string
SYSTEM_PROMPT_TEMPLATE = (
"""You are a Walmart e-commerce data specialist AI that analyzes seller performance through advertising and sales metrics. Key capabilities:
    
**Walmart Metric Expertise**
- **TACOS** = (Total Ad Spend / Total Net Sales) × 100 (measures advertising efficiency across all sales) [2][3]
- **ROAS** = (Ad Sales / Ad Spend) (measures direct return from advertising) [3][4]
- **Omnichannel ROAS** = Includes both online and in-store attributed sales (+20%\ avg. boost) [1]
- **CTR** = (Ad Clicks/Ad Impressions)
- **Organic Conversion** = (Organic Units Sold/Organic Views)

**Database Analysis Rules**
1. **Schema Navigation**  
   Cross-reference these tables using common keys (SKU, Product Type, Brand):
   Summary (high-level metrics)
├── ByItemIDs (SKU-level details)
├── ByKeywords (search term analysis)
└── Trend - Period (trend analysis over time)


2. **Query Construction**
- Prioritize JOINs on `SKU`, `Product Type`, or `Brand` for cross-table analysis
- Calculate metrics using original formulas when needed
- Filter using Walmart-specific columns: `Walmart Item Page Views`, `EBC Page Views`

3. **Response Protocol**
- Present key metrics first: "ROAS: 4.2 (Ad Sales $84k / Ad Spend $20k)"
- Highlight Walmart-specific insights:  
  "Omnichannel ROAS increases 30% when including in-store sales [1]"
- Use brief bullet points for multi-faceted answers
- Add context: "TACOS <10% is considered healthy for Walmart FMCG brands [3]"

**Execution Flow**
1. Parse query for Walmart metric terms
2. Identify required tables/columns using schema
3. Generate SQLite-compliant query
4. Execute via database_query_tool
5. Return concise interpretation with data highlights

**Example Query Handling**
User: "Show best performing TACOS by brand"
→ JOIN ByBrands & Summary on Brand
→ Calculate: `TACOS = (SUM(Ad Spend)/SUM(Total Net Sales))*100`
→ Return: "Brand A: 8.2% TACOS ($12k spend/$146k sales)"

Use only the tables and columns from the database schema provided.

When the user asks a question, first understand the database schema to identify relevant tables and columns.
Then, formulate a precise SQL query to retrieve the necessary information. Use the 'database_query_tool' to execute your SQL query. Provide the answer based on the query results in a clear and concise manner. If the query is ambiguous or you need more information, ask clarifying questions. Always ensure your SQL queries are valid for SQLite. Focus on e-commerce related queries like sales, customer behavior, product performance, inventory, etc.
Give data in a table format in markdown.

If a user asks a question that is not related to the database or e-commerce, respond with:
I'm sorry, but I can only assist with questions related to the database and e-commerce metrics. Please ask a question related to sales, customer behavior, product performance, or inventory.

If a user asks a follow-up question try to keep printing data in the same table from the previous question if possible.

   """

    "You have access to a SQLite database containing tables from an uploaded Excel file. "
    "When asked a question, first understand the database schema to identify relevant tables and columns. "
    "Then, formulate a precise SQL query to retrieve the necessary information. "
    "Use the 'database_query_tool' to execute your SQL query. "
    "Provide the answer based on the query results in a clear and concise manner. "
    "If the query is ambiguous or you need more information, ask clarifying questions. "
    "Always ensure your SQL queries are valid for SQLite. "
    "Focus on e-commerce related queries like sales, customer behavior, product performance, inventory, etc.\n" # Added newline for clarity
    "Give data in a table format in markdown.\n"
    "Database Schema: {db_schema}"
)

# Cache for initialized agent executors to avoid re-creation for the same db_path
_agent_executors_cache = {}

def get_or_create_agent_executor(db_path: str):
    """
    Retrieves a cached agent executor for the given db_path or creates a new one.
    """
    if db_path in _agent_executors_cache:
        return _agent_executors_cache[db_path]

    # LLM configuration
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro-preview-03-25", temperature=0.5)

    # Tool specifically bound to the db_path for this agent instance
    @tool
    def specific_database_query_tool(query: str):
        """
        Executes a SQL query against the database for this session and returns the result.
        The query should be a valid SQL SELECT statement.
        """
        return database_query_tool.func(query=query, db_path=db_path)

    tools_for_agent = [specific_database_query_tool]

    db_schema = get_db_schema(db_path)
    formatted_schema = "\n".join([f"Table: {table}\nColumns: {', '.join(columns)}" for table, columns in db_schema.items()])
    
    # Format the system prompt with the dynamic schema
    formatted_system_prompt = SYSTEM_PROMPT_TEMPLATE.format(db_schema=formatted_schema)
    # print(f"Formatted system prompt: {formatted_system_prompt}")  # Debugging line

    agent_executor = create_react_agent(
        llm,
        tools=tools_for_agent,
        prompt=formatted_system_prompt, # Pass the formatted system prompt
        checkpointer=checkpointer # Add the checkpointer for memory
    )
    
    _agent_executors_cache[db_path] = agent_executor
    return agent_executor

def get_agent_response(db_path: str, user_query: str, thread_id: str): # Added thread_id
    """
    Gets a response from the Langgraph ReAct agent, maintaining conversation history.
    """
    start_time = time.time()
    
    try:
        logging.info(f"🚀 Starting agent response | Query: '{user_query[:50]}...' | Thread: {thread_id[:8]}")
        
        agent_executor = get_or_create_agent_executor(db_path)

        # Configuration for invoking the agent with a specific thread_id for memory
        config = {"configurable": {"thread_id": thread_id}}

        # Invoke the agent. The input is a list of messages.
        agent_invoke_start = time.time()
        logging.info(f"🤖 Starting Gemini agent processing...")
        
        response_messages = agent_executor.invoke(
            {"messages": [HumanMessage(content=user_query)]}, # Use HumanMessage
            config
        )
        
        agent_invoke_end = time.time()
        agent_processing_time = agent_invoke_end - agent_invoke_start
        logging.info(f"🧠 Gemini agent processing completed in {agent_processing_time:.3f}s")

        for message in response_messages["messages"]:
            message.pretty_print()
            print("\n")

        
        # The agent's response is the last message in the list of messages
        if response_messages and "messages" in response_messages and response_messages["messages"]:
            last_message = response_messages["messages"][-1]
            # Ensure it's an AI response and has content
            if hasattr(last_message, 'role') and (last_message.role.lower() == 'ai' or last_message.role.lower() == 'assistant') and hasattr(last_message, 'content'):
                response_content = last_message.content
            elif isinstance(last_message, dict) and last_message.get("role", "").lower() in ['ai', 'assistant'] and "content" in last_message: # If it's a dict
                response_content = last_message["content"]
            # Fallback if the last message isn't structured as expected but has content
            elif hasattr(last_message, 'content'):
                response_content = last_message.content
            else:
                response_content = "Sorry, I couldn't get a valid response from the agent."
        else:
            response_content = "Sorry, I couldn't get a valid response from the agent."
            
        end_time = time.time()
        total_time = end_time - start_time
        
        # Detailed timing breakdown
        logging.info(f"Gemini: {agent_processing_time:.3f}s | Response: {len(response_content)} chars | Thread: {thread_id[:8]}")
        logging.info("========================================================================================")
        
        return response_content
        
    except Exception as e:
        end_time = time.time()
        total_time = end_time - start_time
        logging.error(f"❌ Agent error after {total_time:.3f}s | Query: '{user_query[:50]}...' | Error: {str(e)}")
        raise e

# (Keep the __main__ block commented out or remove if not needed for direct testing of this file)
# if __name__ == '__main__':
# ... (your test code) ...
