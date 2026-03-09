import asyncio
import concurrent.futures
import streamlit as st
from src.agent.graph import terraria_graph

from main import build_initial_state, DEFAULT_GAMEPLAY_ASSUMPTIONS


def run_graph_sync(state):
    return asyncio.run(terraria_graph.ainvoke(state))
    


st.set_page_config(page_title="Terraria Wiki Assistant")

if "history" not in st.session_state:
    st.session_state.history = []

if "gameplay_assumptions" not in st.session_state:
    st.session_state.gameplay_assumptions = dict(DEFAULT_GAMEPLAY_ASSUMPTIONS)

# --- Chat history ---
st.title("Terraria Boss Progression Assistant")

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):  
        st.markdown(msg["content"])

# st.chat_input sticks to the bottom natively
query = st.chat_input("Ask anything...")

if query:
    with st.chat_message("user"):
        st.markdown(query)

    state = build_initial_state(
        query,
        st.session_state.history,
        st.session_state.gameplay_assumptions,
    )

    with st.spinner("Thinking..."):
        try:
            with concurrent.futures.ThreadPoolExecutor() as ex:
                result = ex.submit(run_graph_sync, state).result()
        except Exception as e:
            st.error(f"Error running assistant: {e}")
            result = {}

    st.session_state.history = result.get("conversation_history", st.session_state.history)
    st.session_state.gameplay_assumptions = result.get(
        "gameplay_assumptions",
        st.session_state.gameplay_assumptions,
    )

    if result.get("clarification_needed"):
        with st.chat_message("assistant"):
            st.info(result.get("clarification_question", ""))
    elif result.get("generation"):
        with st.chat_message("assistant"):
            st.markdown(result["generation"])

    st.rerun()