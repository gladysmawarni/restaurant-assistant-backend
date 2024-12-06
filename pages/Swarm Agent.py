import streamlit as st
import time
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
import requests
import pandas as pd
import pydeck as pdk
import ast
import json

from swarm import Swarm, Agent

if 'agent_memories' not in st.session_state:
    st.session_state.agent_memories = []
if 'chat_memories' not in st.session_state:
    st.session_state.chat_memories = []
if 'start' not in st.session_state:
    st.session_state.start = False
if 'map_point' not in st.session_state:
    st.session_state.map_point = None

# Vector DB
embeddings = OpenAIEmbeddings()
faiss_db = FAISS.load_local("faiss_db", embeddings, allow_dangerous_deserialization=True)

gmap_api = st.secrets['GOOGLE_API_KEY']

def stream_data(response):
    for word in response.split(" "):
        yield word + " "
        time.sleep(0.04)

def get_geolocation(area):
    """Get area boundary."""
    geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json?"

    # Define the parameters
    params = {
        "address": area,
        "region": "GB",
        "components": "locality:london|country:GB",
        "key": gmap_api, # Replace with your actual API key
    }
    response = requests.get(geocoding_url, params=params)
    geodata=response.json()

    return geodata['results'][0]['geometry']['bounds'], geodata['results'][0]['geometry']['location']

# def filter_location(bound, db):
#     latitude_filter = {
#     "$and": [
#         {"latitude": {"$lte": bound['northeast']['lat']}},
#         {"latitude": {"$gte": bound['southwest']['lat']}}
#     ]
#     }

#     longitude_filter = {
#         "$and": [
#             {"longitude": {"$lte": bound['northeast']['lng']}},
#             {"longitude": {"$gte": bound['southwest']['lng']}}
#         ]
#     }

#     # Combine filters using $and operator
#     combined_filter = {
#         "$and": [
#             latitude_filter,
#             longitude_filter
#         ]
#     }

#     # Modify the as_retriever method to include the filter in search_kwargs
#     base_retriever = db.as_retriever(search_kwargs={'filter': combined_filter})

#     return base_retriever

# def get_context(food:str, location="London") -> dict:
#     """Retrieve data from database based on user's preference and location."""
#     bounds, st.session_state.map_point = get_geolocation(location)
#     retriever = filter_location(bounds, faiss_db)
#     docs = retriever.invoke(food)

#     merged_result = [{**i.metadata, "reviews": i.page_content} for i in docs]
    
#      # Convert to a DataFrame
#     st.session_state.df = pd.DataFrame(merged_result)

#     return st.session_state.df.to_dict(orient='records')

def get_context(food:str, location="London") -> list:
    """Retrieve data from database based on user's preference and location."""
    preference = food + ', ' + location
    docs_faiss = faiss_db.similarity_search_with_relevance_scores(preference, k=20)

    merged_result = [{**i[0].metadata, "reviews": i[0].page_content, "score": i[1]} for i in docs_faiss]
    # st.session_state.context = result

    # Extract data into a list of dictionaries
    data_for_df = [
        {
            "name": info['name'],
            "address": info['address'],
            "score": info['score'],
            "reviews": info['reviews'],
            "instagram": info['instagram'],
            "website": info['website'],
            "reservation": info['reservation'],
            "menu": info['menu'],
            "latitude": float(info['latitude']),
            "longitude": float(info['longitude']),
            "placeid": info['place_id']
        }
        for info in merged_result
    ]

    # Convert to a DataFrame
    df = pd.DataFrame(data_for_df)

    bounds, st.session_state.map_point = get_geolocation(location)
    # Extract bounds
    min_lat = float(bounds['southwest']['lat'])
    max_lat = float(bounds['northeast']['lat'])
    min_lng = float(bounds['southwest']['lng'])
    max_lng = float(bounds['northeast']['lng'])

    # Filter dataframe
    st.session_state.df = df[
        (df['latitude'] >= min_lat) & 
        (df['latitude'] <= max_lat) & 
        (df['longitude'] >= min_lng) & 
        (df['longitude'] <= max_lng)
    ]

    return st.session_state.df.to_dict(orient='records')



def show_map(df):
    view_state = pdk.ViewState(
        latitude=st.session_state.map_point['lat'],  # Latitude 
        longitude=st.session_state.map_point['lng'],  # Longitude
        zoom=14
        ,  # Adjust zoom level as needed
        pitch=0
        )

    # Define the layer for displaying the data points
    layer = pdk.Layer(
        'ScatterplotLayer',
        data=df,
        get_position='[longitude, latitude]',
        get_radius=30,
        get_color='[200, 30, 0, 160]',
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
                st.dataframe(pd.DataFrame(context))
                show_map(st.session_state.df)

                st.session_state.chat_memories.append({"role": "tool", "content": context})
                st.session_state.chat_memories.append({"role": "map", "content": st.session_state.df})

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

