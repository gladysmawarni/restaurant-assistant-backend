import streamlit as st
import time
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
import pandas as pd
import pydeck as pdk
import ast
import json
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore

from swarm import Swarm, Agent

if 'agent_memories' not in st.session_state:
    st.session_state.agent_memories = []
if 'chat_memories' not in st.session_state:
    st.session_state.chat_memories = []
if 'start' not in st.session_state:
    st.session_state.start = False
if 'map_point' not in st.session_state:
    st.session_state.map_point = None
if 'area_info' not in st.session_state:
    st.session_state.area_info = None


# Vector DB
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
pc = Pinecone(st.secrets['PINECONE_API_KEY'])
index = pc.Index('restaurants')
vector_store = PineconeVectorStore(index=index, embedding=embeddings)

# Google Maps API
gmap_api = st.secrets['GOOGLE_API_KEY']

def stream_data(response):
    for word in response.split(" "):
        yield word + " "
        time.sleep(0.04)


def area_bounds(loc):
    model = ChatOpenAI(model="gpt-4o", model_kwargs={"response_format": {"type": "json_object"}}, temperature=0)

    prompt = f"""
    Provide the approximate boundary coordinates (northeast and southwest) for the location: {loc}, UK.

    - If the location is not a specific location, return three distinct location.
    - For each area, provide:
        - The name of the area
        - The northeast boundary coordinates ("lat" and "lon")
        - The southwest boundary coordinates ("lat" and "lon")
    
    - If the user specify one specific location, return only one area with its details.
    - Format latitude and longitude values with exactly 7 decimal places.
    - Return the output as a **valid JSON object**, with no additional text or formatting.
    - The main key of the JSON should be 'locations'
    """


    # Generate the response
    response_text = model.invoke(prompt).content

    # Parse the response as JSON
    response_json = json.loads(response_text)

    # print the area info
    st.session_state.area_info = response_json
    with st.chat_message("assistant"):
        st.write(st.session_state.area_info)

    return response_json


def make_filter(bound):
    # Initialize a list to hold individual filters for each location
    filters = []

    for point in bound.get('locations', []):
        # Combine latitude and longitude filters for the current location
        location_filter = {
            "$and": [
                {"latitude": {"$lte": point['northeast']['lat']}},
                {"latitude": {"$gte": point['southwest']['lat']}},
                {"longitude": {"$lte": point['northeast']['lon']}},
                {"longitude": {"$gte": point['southwest']['lon']}}
            ]
        }
        # Add the location filter to the list of filters
        filters.append(location_filter)

    if len(filters) > 1:
        # Combine all location filters using the $or operator
        combined_filter = {
            "$or": filters
        }

        return combined_filter
    else:
        return location_filter



def get_context(preference:str, location="London") -> dict:
    """Retrieve data from database based on user's preference and location."""
    print(preference, ',' , location)
    
    bounds = area_bounds(location)
    filt = make_filter(bounds)

    results = vector_store.similarity_search_with_relevance_scores(
            preference,
            filter=filt,
            k=1000,
    )

    all_result = [{**i[0].metadata, "reviews": i[0].page_content, "score": i[1]} for i in results]
    top_result = [{**i[0].metadata, "reviews": i[0].page_content, "score": i[1]} for i in results[:20]]
    
    # Convert to a DataFrame
    st.session_state.all_df = pd.DataFrame(all_result)[['score', 'name', 'address', 'reviews', 'review_source', 'website', 'instagram', 'latitude', 'longitude']]
    st.session_state.top_df = pd.DataFrame(top_result)[['score', 'name', 'address', 'reviews', 'review_source', 'website', 'instagram',  'latitude', 'longitude']]

    return top_result


def show_map(df):
    view_state = pdk.ViewState(
        latitude=51.50735,
        longitude=-0.12776,
        zoom=11,  # Adjust zoom level
        pitch=0
        )

    # Define the layer for displaying the data points
    layer = pdk.Layer(
        'ScatterplotLayer',
        data=df,
        get_position='[longitude, latitude]',
        get_radius=50,
        get_color='[200, 30, 160]',
        pickable=True
    )

    # Create the map using pydeck
    map = pdk.Deck(
        initial_view_state=view_state,
        layers=[layer],
        tooltip={"text": "{name}\n{address}"}
    )

    st.pydeck_chart(map)


def assistant_msg(messages):
    if len(messages) <= 1:
        message = messages[0]
        if message["content"]:
            st.session_state.agent_memories.append({"role": "assistant", "content": message["content"]})
            st.session_state.chat_memories.append({"role": "assistant", "content": message["content"]})
            with st.chat_message("assistant"):
                st.write_stream(stream_data(message["content"]))
    else:
        for message in messages:
            if  message['role'] == 'tool' and message['tool_name'] == 'get_context':
                context = ast.literal_eval(message['content'])

                st.subheader('all restaurant in the location')
                st.dataframe(st.session_state.all_df)
                st.subheader('top 20 restaurant based on relevance')
                st.dataframe(st.session_state.top_df)
                show_map(st.session_state.all_df)

                st.session_state.chat_memories.append({"role": "tool", "content": context})
                st.session_state.chat_memories.append({"role": "map", "content": st.session_state.all_df})
                st.session_state.chat_memories.append({"role": "map", "content": st.session_state.top_df})

            elif message["role"] == "assistant":
                if message["content"]:
                    st.session_state.agent_memories.append({"role": "assistant", "content": message["content"]})



### --------- agent -----------
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
    instructions = """
        You are a restaurant critic. Your primary role is to recommend restaurants to users based on the information available in our database. 

        Follow these guidelines:

        1. All recommendations must be sourced exclusively from the database and tailored to the user's preferences, location(s), and any additional details they provide.

        2. If the user does not specify their food or restaurant preferences, ask clarifying questions to gather the necessary details before proceeding.

        3. Strictly use the user's stated preferences without modification.

        4. Do not create or fabricate information that is not present in the database.

        5. Get the context considering all location specified by the user, at once. Do not redundantly get the context multiple times.

    """,

    functions = [transfer_to_get_context])


def transfer_back_to_assistant():
    return assistant_agent

context_agent.functions.append(transfer_back_to_assistant)


## ------- swarm --------
for memory in st.session_state.chat_memories:
    if memory['role'] == 'tool':
        st.data_editor(memory['content'])
    elif memory['role'] == 'map':
        show_map(memory['content'])
    else:
        with st.chat_message(memory["role"]):
            st.write(memory["content"])


client = Swarm()

if st.session_state.start == False:
    response = client.run(
        agent=assistant_agent,
        messages=[{"role": "user", "content": "Hello!"}],
        context_variables={},
    )
    assistant_msg(response.messages)

    st.session_state.start = True

if user_input := st.chat_input("Say Something"):
    st.session_state.input = user_input

    # Add user message to chat history
    st.session_state.chat_memories.append({"role": "user", "content": user_input})
    st.session_state.agent_memories.append({"role": "user", "content": user_input})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.write(user_input)
    
    with st.spinner('Loading..'):
        response = client.run(
            agent=assistant_agent,
            messages=st.session_state.agent_memories,
            context_variables={},
        )

        assistant_msg(response.messages)


