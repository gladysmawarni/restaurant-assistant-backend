import streamlit as st
import os
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import time
import pydeck as pdk
# import folium
# from streamlit_folium import st_folium


env = 'PROD'

if env == 'PROD':
    # Load credentials from Streamlit secrets and verify the content structure
    try:
        cred = credentials.Certificate(dict(st.secrets["GOOGLE_CREDENTIALS"]))
    except Exception as e:
        st.error(f"Error loading credentials: {e}")

    # Initialize the Firebase app with the credentials
    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Error initializing Firebase app: {e}")
            st.stop()  # Stop the Streamlit script if there's an issue with initialization

    # Now you can use Firestore
    try:
        db = firestore.client()
    except Exception as e:
        st.error(f"Error creating Firestore client: {e}")
        st.stop()  # Stop the script if there's an issue with the Firestore client

elif env == 'DEV':
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "secrets/credentials.json"
    # Initialize Firestore client
    db = firestore.Client()

# Specify the folder path
folder_path = 'data'
# Get the current time
current_time = time.time()
# Define a time threshold (24 hours = 86400 seconds)
time_threshold = 24 * 60 * 60

# Iterate over the files in the folder
for filename in os.listdir(folder_path):
    file_path = os.path.join(folder_path, filename)
    
    # Check if the path is a file (not a directory)
    if os.path.isfile(file_path):
        # Get the file's modification time
        file_mod_time = os.path.getmtime(file_path)
        
        # Check if the file is older than 24 hours
        if current_time - file_mod_time > time_threshold:
            # Fetch the data from Firestore
            rests = [i.id.strip() for i in db.collection("restaurants").get()][:10]
            addresses = [i.to_dict()['Address'] for i in db.collection("restaurants").get()][:10]
            reviews = [i.to_dict()["Reviews"] for i in db.collection("restaurants").get()][:10]
            lat_long = [[i.to_dict()["Latitude"], i.to_dict()['Longitude']] for i in db.collection("restaurants").get()][:10]
            
            # Extract review sources
            reviews_sources = []
            for i in reviews:
                src = set([x['source'] for x in i])
                reviews_sources.append(', '.join(list(src)))

            # Create a DataFrame and save it to a CSV file
            data_dict = {'Restaurant Name': rests, 'Address': addresses, 'Appears on': reviews_sources, 'Lat_lng': lat_long}
            df = pd.DataFrame(data_dict)
            csv_filename = str(int(time.time())) + '.csv'
            df.to_csv(os.path.join(folder_path, csv_filename), index=False)
            
        
        else:
            # Read the latest CSV file from the folder
            csv_path = os.path.join(folder_path, filename)
            df = pd.read_csv(csv_path)


### ---MAP---           
# Set initial view state for the map with a specified zoom level
view_state = pdk.ViewState(
    latitude=51.5074,  # Latitude for London
    longitude=-0.1278,  # Longitude for London
    zoom=12,  # Adjust zoom level as needed
    pitch=0
)

# Define the layer for displaying the data points
layer = pdk.Layer(
    'ScatterplotLayer',
    data=df,
    get_position='[longitude, latitude]',
    get_radius=50,
    get_color='[200, 30, 0, 160]',
    pickable=True
)

# Create the map using pydeck
map = pdk.Deck(
    initial_view_state=view_state,
    layers=[layer],
    tooltip={"text": "{Restaurant}\n{Address}"}
)

st.pydeck_chart(map)
 


# df_map = pd.DataFrame(data_map)

# def create_map():
#     # Create the map with Google Maps
#     map_obj = folium.Map(tiles=None)
#     folium.TileLayer("https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", 
#                      attr="google", 
#                      name="Google Maps", 
#                      overlay=True, 
#                      control=True, 
#                      subdomains=["mt0", "mt1", "mt2", "mt3"]).add_to(map_obj)
#     return map_obj

# def add_markers(map_obj, locations, popup_list=None):
#     if popup_list is  None:
#         # Add markers for each location in the DataFrame
#         for lat, lon in locations:
#             folium.Marker([lat, lon]).add_to(map_obj)
#     else:
#         for i in range(len(locations)):
#             lat, lon = locations[i]
#             popup = popup_list[i]
#             folium.Marker([lat, lon], popup=popup).add_to(map_obj)

#     # Fit the map bounds to include all markers
#     south_west = [min(lat for lat, _ in locations) - 0.02, min(lon for _, lon in locations) - 0.02]
#     north_east = [max(lat for lat, _ in locations) + 0.02, max(lon for _, lon in locations) + 0.02]
#     map_bounds = [south_west, north_east]
#     map_obj.fit_bounds(map_bounds)

#     return map_obj


# m = create_map()
# m = add_markers(m, df_map['lat_lng'], df_map['name'])
# st_folium(m)