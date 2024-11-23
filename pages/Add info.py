import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import time
from stqdm import stqdm

from info import find_reservation
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
menu_last_updated = menu_status['updated']
menu_last_point = menu_status['point']

reservation_status = db.collection('status').document('reservation').get().to_dict()
rsvp_last_updated = reservation_status['updated']
rsvp_last_point = reservation_status['point']

# Fetch the data from Firestore in a single call
if st.session_state.restaurant_db == None:
    st.session_state.restaurant_db = db.collection("restaurants").get()

# make as dictionary
complete_data = [{i.id.strip() : i.to_dict()} for i in st.session_state.restaurant_db]

### ---- APP ----
st.title('Update Menu & Reservation links')
st.divider()

left, right = st.columns(2)
if left.button('Update Menu', use_container_width=True):
    left.write('a')

## RIGHT -- RESERVATION
leap = 100
progress_divider_rsvp = len(complete_data) / 100
progress_val_rsvp = int(rsvp_last_point / progress_divider_rsvp)

right.write(f'Last updated: {str(rsvp_last_updated).split('.')[0]}')
rsvp_progress_bar = right.progress(progress_val_rsvp, text= f"{rsvp_last_point} / {len(complete_data)}")

update_rsvp = right.button('Update Reservation', use_container_width=True)
if update_rsvp:
    ## decide the range
    if rsvp_last_point + leap > len(complete_data):
        end_range = len(complete_data)
    else:
        end_range = rsvp_last_point+leap
    
    with st.spinner('Updating reservation links...'):
        for rests in stqdm(complete_data[rsvp_last_point: end_range]):
            key, val = list(rests.items())[0]
            reserve = find_reservation( f"{val['Website']} reserve book")
            if reserve == 'None':
                reserve = find_reservation(f"sevenrooms reservation {key} london uk")
                if reserve == 'None':
                    reserve = find_reservation(f"opentable reservation {key} london uk")
                    if reserve == 'None':
                        reserve = find_reservation(f"thefork reservation {key} london uk")

            db.collection("restaurants").document(key.strip().lower()).set({'Reservation': reserve},
                                                                                    merge=True)
            
            rsvp_last_point += 1
            rsvp_progress_bar.progress(progress_val_rsvp, text= f"{rsvp_last_point} / {len(complete_data)}")

            time.sleep(0.4)

            db.collection('status').document('reservation').set({'updated': datetime.now(),
                                                         'point': rsvp_last_point}, merge=True)

    st.success(f'Reservation links updated for {leap} restaurants')

    if rsvp_last_point == len(complete_data):
        db.collection('status').document('reservation').set({'updated': datetime.now(),
                                                         'point': 0}, merge=True)