import streamlit as st
import time
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
import pandas as pd
import pydeck as pdk
import ast
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
    model = ChatOpenAI(model="gpt-4o")
    prompt = f"""
            Provide the approximate boundary coordinates (northeast and southwest) for the location: {loc}, UK.
            And the center point of the location.
            Format the latitude & longitude response with exactly 7 decimal places.

            Example output:
            northeast: latitude longitude & southwest: latitude longitude // center: latitude longitude

            Only return the coordinates in the specified format, nothing else.
            """

    response_text = model.invoke(prompt).content
    bounds , center = response_text.split(' // ')
    center_point = center.strip('center: ').split()

    return bounds, {'lat': float(center_point[0]), 'lng': float(center_point[1])}

def area_info(loc):
    model = ChatOpenAI(model="gpt-4o")
    prompt = f"""
            Provide the approximate boundary coordinates (northeast and southwest) for the location: {loc}, UK.
            Mention the location first then the coordinates with exactly 7 decimal places.
            """
    response_text = model.invoke(prompt).content
    return response_text


def filter_location(bound):
    parts = bound.split("&")

    # Extract northeast and southwest parts
    northeast = parts[0].split(":")[1].strip()
    southwest = parts[1].split(":")[1].strip()

    # Split into latitude and longitude
    northeast_lat, northeast_lon = map(float, northeast.split())
    southwest_lat, southwest_lon = map(float, southwest.split())

    latitude_filter = {
    "$and": [
        {"latitude": {"$lte": northeast_lat}},
        {"latitude": {"$gte": southwest_lat}}
    ]
    }

    longitude_filter = {
        "$and": [
            {"longitude": {"$lte": northeast_lon}},
            {"longitude": {"$gte": southwest_lon}}
        ]
    }

    # Combine filters using $and operator
    combined_filter = {
        "$and": [
            latitude_filter,
            longitude_filter
        ]
    }

    return combined_filter


def get_context(preference:str, location="London") -> dict:
    """Retrieve data from database based on user's preference and location."""
    print(preference, ',' , location)
    
    bounds, st.session_state.map_point = area_bounds(location)
    filter = filter_location(bounds)

    results = vector_store.similarity_search_with_relevance_scores(
            preference,
            filter=filter,
            k=1000,
    )

    all_result = [{**i[0].metadata, "reviews": i[0].page_content, "score": i[1]} for i in results]
    top_result = [{**i[0].metadata, "reviews": i[0].page_content, "score": i[1]} for i in results[:20]]
    
    # Convert to a DataFrame
    st.session_state.all_df = pd.DataFrame(all_result)[['score', 'name', 'address', 'reviews', 'review_source', 'website', 'instagram', 'latitude', 'longitude']]
    st.session_state.top_df = pd.DataFrame(top_result)[['score', 'name', 'address', 'reviews', 'review_source', 'website', 'instagram',  'latitude', 'longitude']]


    st.session_state.area_info = area_info(location)
    with st.chat_message("assistant"):
        st.write_stream(stream_data(st.session_state.area_info))

    return top_result


def show_map(df):
    view_state = pdk.ViewState(
        latitude=st.session_state.map_point['lat'],  # Latitude 
        longitude=st.session_state.map_point['lng'],  # Longitude
        zoom=12,  # Adjust zoom level
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
    instructions="""You are a restaurant critics, your job is to recommend restaurants to user based on the data we have. 
                    make sure the recommendation is from our database and is retrieved by considering the user preference and location.
                    if the user does not specify their location or their food/restaurant preference, ask until they specify their preference and an area or address in London, UK.
                    Do not made up information not in the database. 
                    Do not call the function unless it is very necessary.
                """,

    functions = [transfer_to_get_context]
)

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


