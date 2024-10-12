import streamlit as st
import os
from firebase_admin import firestore
import pandas as pd
import time
import pydeck as pdk

env = 'DEV'

if env == 'PROD':
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = st.secrets["GOOGLE_CREDENTIALS"] 
elif env == 'DEV':
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "secrets/credentials.json"

import os
import time
from google.cloud import firestore
import pandas as pd
import streamlit as st

# Specify the folder path
folder_path = 'data'
# Get the current time
current_time = time.time()
# Define a time threshold (24 hours = 86400 seconds)
time_threshold = 24 * 60 * 60

# Initialize Firestore client
db = firestore.Client()

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
            
            # Display the DataFrame in Streamlit
            st.dataframe(df[['Restaurant Name', 'Address', 'Appears on']])
        
        else:
            # Read the latest CSV file from the folder
            csv_path = os.path.join(folder_path, filename)
            df = pd.read_csv(csv_path)


# Display the DataFrame in Streamlit
st.dataframe(df[['Restaurant', 'Address', 'Appears on']])