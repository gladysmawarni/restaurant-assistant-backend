import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from stqdm import stqdm
import ast

from helper.utils import router, check_password, remove_accents
from helper.info import get_placeid, find_ig, get_lat_lng, get_google_info, MenuFinder, ReservationFinder

### -------- SESSION STATE ---------
if 'new_data' not in st.session_state:
    st.session_state.new_data = []
if 'existing_data' not in st.session_state:
    st.session_state.existing_data = []
if 'not_acceptable_data' not in st.session_state:
    st.session_state.not_acceptable_data = []


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




### ---- APP ----
st.title('Scrape Data')
st.divider()

st.subheader('Acceptable links:')

explanation = """
        - Infatuation  
        `london/guides`, `london/reviews` 

        - Hot Dinners  
        `Features`, `Gastroblog`, `London-restaurants`

        - Timeout  
        `london/food-and-drink`, `london/restaurants`, `london/news`

        - CN Traveller
        """

st.markdown(explanation)

st.divider()

url = st.text_input('input URL')

if st.button('Scrape'):
    with st.spinner('Scraping...'):
        scraped_venue_data = router(url=url, save=False)

        new = []
        existing = []
        for scraped in stqdm(scraped_venue_data):
            venue = scraped['Venue'].lower()
            
            exist = db.collection("restaurants").document(venue).get().to_dict()
            if exist:
                if ("Reviews" in exist):
                    ## if it exist, check if there's new review
                    try:
                        all_venue_reviews = {
                                review["text"] for review in exist["Reviews"]
                            }
                    except TypeError:
                        ## FIX TYPE ERROR
                        exist["Reviews"] = [exist['Reviews']]
                        db.collection("restaurants").document(venue).delete()
                        db.collection("restaurants").document(venue).set(exist)

                        all_venue_reviews = {
                                review["text"] for review in exist["Reviews"]
                            }

                    for review in scraped["Reviews"]:
                        scrapped_review_set = {review["text"]}

                        # if the scrapped reviews is in the database then we should have a empty set in the diference
                        new_reviews_set = scrapped_review_set.difference(all_venue_reviews)

                        # NEW REVIEWS
                        if new_reviews_set != set():
                            temp = {}
                            temp['Restaurant'] = venue
                            temp['Status'] = "NEW REVIEW"
                            temp['Reviews'] = "\n---\n".join([i['text'] for i in scraped['Reviews']])
                            temp['Address'] = scraped['Address']
                            temp['Instagram'] = '-'
                            temp['PlaceID'] = '-'
                            temp['Latitude'], temp['Longitude'] = '-', '-'
                            temp['Source'] = st.session_state.source

                            st.session_state.new_data.append(temp)
                        
                        # EXIST
                        else:
                            temp = {}
                            temp['Restaurant'] = venue
                            temp['Status'] = "EXIST"
                            temp['Reviews'] = "\n---\n".join([i['text'] for i in scraped['Reviews']])
                            temp['Address'] = scraped['Address']

                            st.session_state.existing_data.append(temp)
            
            # NEW VENUE
            else:
                try:
                    temp = {}
                    temp['Restaurant'] = venue
                    temp['Status'] = "NEW VENUE"
                    temp['Reviews'] = "\n---\n".join([i['text'] for i in scraped['Reviews']])
                    temp['Address'] = scraped['Address']
                    temp['Instagram'] = find_ig(venue)
                    temp['PlaceID'] = get_placeid(venue + ' , ' + ", London, UK")
                    temp['Latitude'], temp['Longitude'] = get_lat_lng(scraped['Address'])
                    temp['Source'] = st.session_state.source

                    google_info = get_google_info(temp['PlaceID'])
                    temp['Website'] = google_info.pop('website_uri')
                    temp['GoogleData']  = google_info if type(google_info) == dict else ast.literal_eval(google_info)

                    menu_finder = MenuFinder(st.secrets['GOOGLE_API_KEY'], st.secrets['cx'])
                    temp['Menu'] = menu_finder.get_menu(venue, temp['Website'])
                    # temp['Menu']  = menu_finder.get_menu(venue, temp['Google Data']['website_uri'])

                    reservation_finder = ReservationFinder(st.secrets['GOOGLE_API_KEY'], st.secrets['cx'])
                    temp['Reservation'] = reservation_finder.get_reservation(venue, temp['Website'])
                    # temp['Reservation'] = reservation_finder.get_reservation(venue, temp['Google Data']['website_uri']) 

                    st.session_state.new_data.append(temp)

                except Exception as e:
                    temp = {}
                    temp['Restaurant'] = venue
                    temp['Status'] = "NOT ACCEPTABLE"
                    temp['Address'] = scraped['Address']
                    temp['Error'] = str(e)

                    st.session_state.not_acceptable_data.append(temp)




if len(st.session_state.new_data) > 0:
    st.success('New Venues / Reviews')
   
    new_df = pd.DataFrame(st.session_state.new_data)

    new_df["Add"] = True
    # Make Add be the first column
    new_df = new_df[["Add"] + new_df.columns[:-1].tolist()]

    final_df = st.data_editor(new_df, hide_index=True)

    if st.button('Send to Database'):
        selected_df = final_df[final_df['Add'] == True]
        selected_data = selected_df.to_dict('records')

        with st.spinner():
            for i in selected_data:
                if i['Status'] == 'NEW REVIEW':
                    rest_reviews = db.collection("restaurants").document(i['Restaurant'].strip()).get().to_dict()['Reviews']
                    tmp = {'text': i['Reviews'], 'source': i['Source']}
                    rest_reviews.append(tmp)

                    db.collection("restaurants").document(i['Restaurant'].strip()).set({'Reviews': rest_reviews}, merge=True)
                
                elif i['Status'] == 'NEW VENUE':
                    reviews = [{'text': i['Reviews'], 'source': i['Source']}]
                    venue = remove_accents(i['Restaurant'].lower())
                    db.collection("restaurants").document(venue.strip()).set({'Address': i['Address'],
                                                                              'GoogleData': i['GoogleData'] if type(i['GoogleData']) == dict else ast.literal_eval(i['GoogleData']),
                                                                                'Latitude': i['Latitude'],
                                                                                'Longitude': i['Longitude'],
                                                                                'Reviews': reviews,
                                                                                'PlaceID': i['PlaceID'],
                                                                                'Menu': i['Menu'],
                                                                                'Reservation': i['Reservation'],
                                                                                'Instagram': i['Instagram'],
                                                                                'Website': i['Website']},merge=True)
        
        st.success('Database updated')

if len(st.session_state.existing_data) > 0:
    st.warning('Venue already exist, no new reviews')
    df = pd.DataFrame(st.session_state.existing_data)
    st.data_editor(df, hide_index=True)

if len(st.session_state.not_acceptable_data) > 0:
    st.error('Error')
    df = pd.DataFrame(st.session_state.not_acceptable_data)
    st.data_editor(df, hide_index=True)