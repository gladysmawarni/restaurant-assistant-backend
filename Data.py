import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

import pydeck as pdk
from utils import check_password
# import folium
# from streamlit_folium import st_folium

st.set_page_config(page_title="Backend")
st.title('Data')

if 'restaurant_db' not in st.session_state:
    st.session_state.restaurant_db = None


### ---DATA---
# Check password in prod, continue if password is correct
if not check_password():
    st.stop() 

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


# Fetch the data from Firestore in a single call
if st.session_state.restaurant_db == None:
    st.session_state.restaurant_db = db.collection("restaurants").get()

# Process the data locally
rests = [i.id.strip() for i in st.session_state.restaurant_db]
addresses = [i.to_dict().get('Address') for i in st.session_state.restaurant_db]
reviews = [i.to_dict().get("Reviews") for i in st.session_state.restaurant_db]
latitude = [i.to_dict().get("Latitude") for i in st.session_state.restaurant_db]
longitude = [i.to_dict().get("Longitude") for i in st.session_state.restaurant_db]
instagram = [i.to_dict().get("Instagram") for i in st.session_state.restaurant_db]
menu = [i.to_dict().get("Menu") for i in st.session_state.restaurant_db]
rsvp = [i.to_dict().get("Reservation") for i in st.session_state.restaurant_db]


# Extract review sources
reviews_sources = []
for i in reviews:
    try:
        src = set([x['source'] for x in i])
        reviews_sources.append(', '.join(list(src)))
    except:
        reviews_sources.append('None')

reviews_content = []
for i in reviews:
    try:
        cntn = set([x['text'] for x in i])
        reviews_content.append('\n---\n'.join(list(cntn)))
    except:
        reviews_content.append('None')

# Create a DataFrame and save it to a CSV file
data_dict = {'Restaurant': rests, 'Address': addresses, 
             'Appears on': reviews_sources, 'Reviews': reviews_content,
             'Instagram': instagram,
             'latitude': latitude, 'longitude': longitude}
df = pd.DataFrame(data_dict)


### ---DATA---
df['Restaurant'] = df['Restaurant'].str.strip()
st.dataframe(df[['Restaurant', 'Address', 'Appears on', 'Reviews', 'Instagram']], hide_index=True)
st.write(f'Total restaurant in database: {len(df)}')

### Null counts
st.write(f"Instagram null count: {instagram.count('None')}")
st.write(f"Menu null count: {menu.count('None')}")
st.write(f"Reservation null count: {rsvp.count('None')}")


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