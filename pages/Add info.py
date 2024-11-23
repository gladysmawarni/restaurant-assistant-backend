import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

from utils import  check_password

### -------- SESSION STATE ---------
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


### STATUS
menu_status = db.collection('status').document('menu').get().to_dict()
print(menu_status)
menu_last_updated = menu_status['updated']
menu_last_point = menu_status['point']

reservation_status = db.collection('status').document('reservation').get().to_dict()
print(reservation_status)
reserv_last_updated = reservation_status['updated']
reserv_last_point = reservation_status['point']

# Fetch the data from Firestore in a single call
if st.session_state.restaurant_db == None:
    st.session_state.restaurant_db = db.collection("restaurants").get()

rests = [i.id.strip() for i in st.session_state.restaurant_db]

### ---- APP ----
st.title('Update Menu & Reservation links')
st.divider()

left, right = st.columns(2)
if left.button('Menu', use_container_width=True):
    left.write('a')
if right.button('Reservation', use_container_width=True):
    right.write('b')

# db.collection('status').document('reservation').set({'last': datetime.now()}, merge=True)