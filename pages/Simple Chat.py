import streamlit as st
import time
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore

from swarm import Swarm, Agent

if 'memories' not in st.session_state:
    st.session_state.memories = []


# Vector DB
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
pc = Pinecone(st.secrets['PINECONE_API_KEY'])
index = pc.Index('restaurants')
vector_store = PineconeVectorStore(index=index, embedding=embeddings)

def stream_data(response):
    for word in response.split(" "):
        yield word + " "
        time.sleep(0.04)

def get_context(preference):
    print(preference)
    docs = vector_store.similarity_search_with_relevance_scores(preference, k=15)
    return docs

context_agent = Agent(
    name="Context Agent",
    instructions="Get the restaurant data based on user's preference.",
    functions=[get_context],
)

def transfer_to_get_context():
    return context_agent

# Main Agent
assistant_agent = Agent(
    name="Assistant Agent",
    instructions="""You are a restaurant critics, your job is to recommend restaurants to user based on the data we have. 
                    make sure the data is retrieved by considering the user preference and location.
                    if the user does not specify their location, ask until they specify an area or address in London, UK.
                    Only recommend restaurants available in the database, and do not recommend the same restaurant twice.
                """,
    functions = [transfer_to_get_context]
)

def transfer_back_to_assistant():
    return assistant_agent

context_agent.functions.append(transfer_back_to_assistant)

def assistant_msg(messages):
     for message in messages:
        if message["role"] != "assistant":
          continue

        if message["content"]:
            st.session_state.memories.append({"role": "assistant", "content": message["content"]})
            with st.chat_message("assistant"):
                st.write(message["content"])


### ----------- APP -------------
for memory in st.session_state.memories:
    with st.chat_message(memory["role"]):
        st.write(memory["content"])


client = Swarm()

if user_input := st.chat_input("Say Something"):
    st.session_state.input = user_input
    # Add user message to chat history
    st.session_state.memories.append({"role": "user", "content": user_input})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.write(user_input)
    
    with st.spinner('Loading...'):
        response = client.run(
        agent=assistant_agent,
        messages=st.session_state.memories,
        context_variables={})

        
    assistant_msg(response.messages)