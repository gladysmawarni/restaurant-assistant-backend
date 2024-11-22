import json
from scrapers import (
    muilti_review_scraper,
    multi_sigle_block_reviews_scraper,
    single_review_scraper,
)
import streamlit as st
import hmac
import requests
from openai import OpenAI

if 'source' not in st.session_state:
    st.session_state.source = None

def open_json(path: str) -> json:
    with open(path, mode="r") as f:
        file = json.load(f)
    return file

### ---PASSWORD---
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False

def router(url: str, **kwargs) -> None:
    if kwargs["save"] == True:
        save = True
    else:
        save = False

    def timeout_routes():
        website = "Timeout"
        if (
            ("/food-and-drink/" in url)
            | ("/bars-and-pubs/" in url)
            | ("/restaurants/" in url)
        ):
            return muilti_review_scraper(
                website=website,
                url=url,
                save=save,
                selector_options=open_json(
                    "selector_options/Timeout/timeout_multi_review_selector_options.json"
                ),
            )
        # elif ("/bars-and-pubs/" in url) | ("/restaurants/" in url):
        #     print("bars-and-pubs or restaurants route")
        #     return timeout_muilti_review_scraper(url=url, save=save)
        elif "/news/" in url:
            return multi_sigle_block_reviews_scraper(
                website=website,
                url=url,
                save=save,
                selector_options=open_json(
                    "selector_options/Timeout/timeout_news_selector_options.json"
                ),
            )
        else:
            return "There is no information for that url"

    def infatuation_routes():
        website = "Infatuation"

        if "/guides/" in url:
            return muilti_review_scraper(
                website=website,
                url=url,
                save=save,
                selector_options=open_json(
                    "selector_options/Infatuation/infatuation_multi_review_selector_options.json"
                ),
            )

        elif "/reviews/" in url:
            return single_review_scraper(
                website=website,
                url=url,
                save=save,
                selector_options=open_json(
                    "selector_options/Infatuation/infatuation_single_review_selector_options.json"
                ),
            )

        else:
            return "There is no information for that url"

    def hotdinners_routes():
        website = "Hotdinners"
        if "/Features/" in url:
            return multi_sigle_block_reviews_scraper(
                website=website,
                url=url,
                save=save,
                selector_options=open_json(
                    "selector_options/Hotdinners/hotdinners_multi_review_selector_options.json"
                ),
            )
        elif "/Gastroblog/" in url:
            return single_review_scraper(
                website=website,
                url=url,
                save=save,
                selector_options=open_json(
                    "selector_options/Hotdinners/hotdinners_gastrobloger_selector_options.json"
                ),
            )
        elif "/London-restaurants/" in url:
            return single_review_scraper(
                website=website,
                url=url,
                save=save,
                selector_options=open_json(
                    "selector_options/Hotdinners/hotdinners_london_restaurants_selector_options.json"
                ),
            )
        else:
            return "There is no information for that url"

    base_url_dict = {
        "https://www.theinfatuation.com": infatuation_routes,
        "https://www.timeout.com": timeout_routes,
        "https://www.hot-dinners.com": hotdinners_routes,
    }

    # select the website that is the root of the link to access the speccific routes to scrape
    base_url = list(filter(lambda x: x in url, base_url_dict.keys()))[0]
    st.session_state.source = "Infatuation" if base_url=="https://www.theinfatuation.com" else "Timeout" if base_url=="https://www.timeout.com" else "Hot Dinners"

    list_of_venues_scrapped = base_url_dict[base_url]()

    return list_of_venues_scrapped


### ----- PLACE ID -------
def get_placeid(query):
    # Define the URL
    url = "https://places.googleapis.com/v1/places:searchText"

    # Define the headers
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": st.secrets['GOOGLE_API_KEY'],  
        "X-Goog-FieldMask": "places.id"
    }

    # Define the data payload
    data = {
        "textQuery": query
    }

    # Make the POST request
    try:
        response = requests.post(url, headers=headers, json=data)
        placeid = response.json()['places'][0]['id']
    except:
        placeid = 'N/A'
    
    return placeid


def get_website(place_id):
    url = f"https://places.googleapis.com/v1/places/{place_id}"

    # Define the headers
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-Goog-FieldMask": "websiteUri",
    }

    # Define the headers
    params = {
        "key": st.secrets['GOOGLE_API_KEY']
    }

    response = requests.get(url, params=params, headers=headers).json()

    website = response.get('websiteUri', 'N/A')

    return website


### ---- CHECK IG ----
def check(data, query):
    system_message = """
    From the provided tuple of links and brief description, select the link that best matches the query as the correct answer and return just the link.
    Consider that the link should be a restautant / food establishment account, not personal account or food review account.
    The selected link should be a valid Instagram profile link in the format: 'https://www.instagram.com/username/'.
    If none of the links match the query as an Instagram profile link, return 'None'.
    If you are not sure, retun 'None'.
    """


    # Define the assistant's role and set up the messages for the API call
    messages = [
        {
            "role": "system",
            "content": system_message
        },
        {
            "role": "user",
            "content": f"query: {query}, links: {data}"
        }
    ]

    try:
        # Call the OpenAI API
        client = OpenAI(api_key=st.secrets['OPENAI_API_KEY'])
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages, 
            temperature=0.5
        )

        # Extract content from the response
        assistant_message = response.choices[0].message.content
        
        return assistant_message

    except Exception as e:
        return f"An error occurred: {str(e)}"

### ---- FIND IG ----
def find_ig(name):
    url = 'https://www.googleapis.com/customsearch/v1'
    params = {
        'key': st.secrets['GOOGLE_API_KEY'],
        'cx': st.secrets['cx'],
        'q': f"{name} restaurant uk / london instagram user site:instagram.com",
    }

    try:
        x = requests.get(url, params=params)
        ig_links = [i['link'] for i in x.json()['items']]
        ig_links_cleaned = [i.split('p/')[0] if 'p/' in i else i.split('reel/')[0] if 'reel/' in i else i for i in ig_links]
    except:
        return 'None'

    ig_titles = []
    for i in x.json()['items']:
        try:
            ig_titles.append(i['pagemap']['metatags'][0]['og:title'].split(':')[0])
        except:
            ig_titles.append(i['snippet'])
    
    data = [(links, titles) for links, titles in list(zip(ig_links_cleaned, ig_titles))]
    response = check(data, params['q'])
    
    return response

### ---- GET LONG & LAT ----
def get_lat_lng(address):
    geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json?"

    # Define the parameters
    params = {
        "address": address,
        "key": st.secrets['GOOGLE_API_KEY'],
    }

    response = requests.get(geocoding_url, params=params)
    geodata=response.json()
    lat= geodata['results'][0]['geometry']['location']['lat']
    lng = geodata['results'][0]['geometry']['location']['lng']

    return lat, lng


import unicodedata

def remove_accents(input_str):
    # Normalize the string to 'NFD' (Normalization Form Decomposed)
    normalized_str = unicodedata.normalize('NFD', input_str)
    # Filter out characters with the 'Mn' (Mark, Nonspacing) unicode category
    return ''.join(char for char in normalized_str if unicodedata.category(char) != 'Mn')