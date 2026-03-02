'''
This is just a TypedDict that acts as the single source of truth passed between every node in the graph.
Every node reads from it and writes back to it. 
'''
from typing import List, Dict, Any, Literal, Optional
from typing_extensions import TypedDict 

class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str

class AgentState(TypedDict):
    # Set at start
    query: str                  # original user question

    # filled if progressively
    rewritten_query: str        # cleaned up version for retrieval
    retrieved_chunks: List[Dict]  # raw ChromaDB hits
    graded_chunks: List[Dict]     # filtered relevant chunks
    generation: str               # final answer

    # control fields
    retry_count: int              # loop guard
    route: Literal["rag", "direct"]

    # clarification_fields
    clarification_needed: bool          # only set if clarify_query runs
    clarification_question: str | None  # only set if query is insufficient
    
    # records convo history 
    conversation_history: List[Message] 