import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import time
from stqdm import stqdm
from json import JSONDecodeError

from helper.info import ReservationFinder,MenuFinder, get_google_info
from helper.utils import  check_password

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

google_status = db.collection('status').document('google_data').get().to_dict()
google_last_updated = google_status['updated']
google_last_point = google_status['point']

# Fetch the data from Firestore in a single call
if st.session_state.restaurant_db == None:
    st.session_state.restaurant_db = db.collection("restaurants").get()

# make as dictionary
complete_data = [{i.id.strip() : i.to_dict()} for i in st.session_state.restaurant_db]

### ---- APP ----
st.title('Update Menu & Reservation links')
st.divider()

left, right = st.columns(2)


## LEFT -- MENU
leap_menu = 200
progress_divider_menu = len(complete_data) / 100
progress_val_menu = int(menu_last_point / progress_divider_menu)

left.subheader('Menu', divider="orange")
left.write(f'Last updated: {str(menu_last_updated).split('.')[0]}')
menu_progress_bar = left.progress(progress_val_menu, text= f"{menu_last_point} / {len(complete_data)}")

update_menu = left.button('Update Menu', use_container_width=True)
if update_menu:
    ## decide the range
    if menu_last_point + leap_menu > len(complete_data):
        end_range_menu = len(complete_data)
    else:
        end_range_menu = menu_last_point+leap_menu

    with st.spinner('Updating menu links...'):
        for rests in stqdm(complete_data[menu_last_point: end_range_menu]):
            all_menu_links = []
            key, val = list(rests.items())[0]
            menu_finder = MenuFinder(st.secrets['GOOGLE_API_KEY'], st.secrets['cx'])
            menu_link = menu_finder.get_menu(key, val['Website'])
            # menu_link = menu_finder.get_menu(key, val['Google Data']['website_uri'])

            db.collection("restaurants").document(key.strip().lower()).set({'Menu': menu_link},
                                                                                    merge=True)
            
            menu_last_point += 1
            menu_progress_bar.progress(progress_val_menu, text= f"{menu_last_point} / {len(complete_data)}")

            time.sleep(0.5)

            db.collection('status').document('menu').set({'updated': datetime.now(),
                                                         'point': menu_last_point}, merge=True)

    st.success(f'Menu links updated')

    if menu_last_point == len(complete_data):
        db.collection('status').document('menu').set({'updated': datetime.now(),
                                                         'point': 0}, merge=True)


## RIGHT -- RESERVATION
leap_rsvp = 200
progress_divider_rsvp = len(complete_data) / 100
progress_val_rsvp = int(rsvp_last_point / progress_divider_rsvp)

right.subheader('Reservation', divider="green")
right.write(f'Last updated: {str(rsvp_last_updated).split('.')[0]}')
rsvp_progress_bar = right.progress(progress_val_rsvp, text= f"{rsvp_last_point} / {len(complete_data)}")

update_rsvp = right.button('Update Reservation', use_container_width=True)
if update_rsvp:
    ## decide the range
    if rsvp_last_point + leap_rsvp > len(complete_data):
        end_range_rsvp = len(complete_data)
    else:
        end_range_rsvp = rsvp_last_point+leap_rsvp
    
    with st.spinner('Updating reservation links...'):
        for rests in stqdm(complete_data[rsvp_last_point: end_range_rsvp]):
            key, val = list(rests.items())[0]
            reservation_finder = ReservationFinder(st.secrets['GOOGLE_API_KEY'], st.secrets['cx'])
            reservation_link = reservation_finder.get_reservation(key, val['Website'])
            # reservation_link = reservation_finder.get_reservation(key, val['Google Data']['website_uri'])

            db.collection("restaurants").document(key.strip().lower()).set({'Reservation': reservation_link},
                                                                                    merge=True)
            
            rsvp_last_point += 1
            rsvp_progress_bar.progress(progress_val_rsvp, text= f"{rsvp_last_point} / {len(complete_data)}")

            time.sleep(0.4)

            db.collection('status').document('reservation').set({'updated': datetime.now(),
                                                         'point': rsvp_last_point}, merge=True)

    st.success(f'Reservation links updated')

    if rsvp_last_point == len(complete_data):
        db.collection('status').document('reservation').set({'updated': datetime.now(),
                                                         'point': 0}, merge=True)
        

## LEFT -- GOOGLE DATA
leap_google = 200
progress_divider_google = len(complete_data) / 100
progress_val_google = int(google_last_point / progress_divider_google)

left.subheader('Google Info', divider="red")
left.write(f'Last updated: {str(google_last_updated).split('.')[0]}')
google_progress_bar = left.progress(progress_val_google, text= f"{google_last_point} / {len(complete_data)}")

update_google = left.button('Update Google Data', use_container_width=True)
if update_google:
    ## decide the range
    if google_last_point + leap_google > len(complete_data):
        end_range_google = len(complete_data)
    else:
        end_range_google = google_last_point+leap_google
    
    with st.spinner('Updating Google data...'):
        for rests in stqdm(complete_data[google_last_point: end_range_google]):
            key, val = list(rests.items())[0]
            try:
                google_info = get_google_info(val['Place ID'])
                db.collection('restaurants').document(key.strip().lower()).set({'Website': google_info.pop('website_uri')}, merge=True)
                db.collection('restaurants').document(key.strip().lower()).set({'Google Data': google_info}, merge=True)
            except JSONDecodeError:
                db.collection('restaurants').document(key.strip().lower()).set({'Google Data': 'None'}, merge=True)
            
            google_last_point += 1
            google_progress_bar.progress(progress_val_google, text= f"{google_last_point} / {len(complete_data)}")

            time.sleep(0.7)

            db.collection('status').document('google_data').set({'updated': datetime.now(),
                                                         'point': google_last_point}, merge=True)

    st.success(f'Google data updated')

    if google_last_point == len(complete_data):
        db.collection('status').document('google_data').set({'updated': datetime.now(),
                                                         'point': 0}, merge=True)
