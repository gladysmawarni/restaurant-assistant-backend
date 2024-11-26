import streamlit as st
import time
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from swarm import Swarm, Agent

if 'memories' not in st.session_state:
    st.session_state.memories = []


# Vector DB
embeddings = OpenAIEmbeddings()
faiss_db = FAISS.load_local("faiss_db", embeddings, allow_dangerous_deserialization=True)

def stream_data(response):
    for word in response.split(" "):
        yield word + " "
        time.sleep(0.04)

def get_context(preference):
    # print(preference)
    docs_faiss = faiss_db.similarity_search_with_relevance_scores(preference, k=15)
    return docs_faiss

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
                    make sure the recommendation is from our database and is retrieved by considering the user preference and location.
                    if the user does not specify their location or their food/restaurant preference, ask until they specify their preference and an area or address in London, UK.
                    Do not made up information not in the database.
                """,
    functions = [transfer_to_get_context]
)

def transfer_back_to_assistant():
    return assistant_agent

context_agent.functions.append(transfer_back_to_assistant)

def assistant_msg(messages):
     for message in response.messages:
        if message["role"] != "assistant":
          continue

        if message["content"]:
            st.session_state.memories.append({"role": "assistant", "content": message["content"]})
            with st.chat_message("assistant"):
                st.write_stream(stream_data(message["content"]))


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
    
    response = client.run(
      agent=assistant_agent,
      messages=st.session_state.memories,
      context_variables={},
  )
    assistant_msg(response.messages)