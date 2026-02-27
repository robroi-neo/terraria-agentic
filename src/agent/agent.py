from src.agent.llm import LLMProvider
from src.agent.agent import RAGAgent
from 

# Initialize dependencies
llm_provider = LLMProvider()
vector_repo = VectorStoreRepository()  # your ingested content
agent_config = AgentConfig()  # load prompts, retriever_k, test cases

# Create the RAG agent
rag_agent = RAGAgent(config=agent_config, repository=vector_repo, llm_provider=llm_provider)

# Run a query
response = rag_agent.run("Explain quantum entanglement.")
print(response.output)