import streamlit as st
import requests
from openai import OpenAI
from utils import retry_on_failure

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

## --- WEBSITE ---
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
    
    try:
        response = requests.get(url, params=params, headers=headers).json()
        website = response.get('websiteUri', 'N/A')
    except:
        website = 'N/A'

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


# --- Reservation --- 
def check_reservation(data, query):
    system_message = """
        Task: Select the most appropriate link for a restaurant booking or reservation from a provided list of links. Follow these criteria to determine the correct link:

        Criteria for Selection:

        1. Official Website:
        - If the query specifies the restaurant's official website, the link must include 'bookings' or 'reservation' in the URL.
        - Do not select the official website if these terms are missing.
        
        2. Third-Party Platforms:
        - If the query mentions platforms like 'opentable', 'sevenrooms', or 'the fork', ensure the link contains the name of the restaurant and corresponds to the platform mentioned.
        
        3. Location Specificity:
        - The restaurant is located in London, UK. Avoid links that do not correspond to this location.
        
        Additional Rules:
        - Exclusions: Do not return any link that does not include the name of the restaurant.
        - Uncertainty: If none of the provided links match the criteria or you are unsure, return 'None'.
        - No Fabrication: Use only the links provided. Do not create or infer new links.
        - DO NOT return the link if you are unsure. Remember the name of the restaurant should match exactly with the url 
        
        Example what not to get:
        - brothers cafe -> https://www.thefork.com/restaurant/brothers-marcus is not the same
        - bono -> https://www.thefork.com/restaurant/bonoo is not the same
        
        Output:
        - Return only the selected link as your answer.
        - If no suitable link is found, return 'None'.
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
        client = OpenAI()
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
    

@retry_on_failure(retries=5, delay=3)
def find_reservation(query):
    url = 'https://www.googleapis.com/customsearch/v1'
    params = {
        'key': st.secrets['GOOGLE_API_KEY'],
        'cx': '663fe7e803e114294',
        # 'q': f"opentable reservation {rest}",
        # 'q': f"{website} reserve book",
        'q': query,
        'num': 5,
    }

    try:
        x = requests.get(url, params=params)
        menu_links = [i['link'] for i in x.json()['items']]
        menu_links_cleaned = [i.split('p/')[0] if 'p/' in i else i.split('reel/')[0] if 'reel/' in i else i for i in menu_links]
    except:
        return 'None'

    response = check_reservation(menu_links_cleaned, params['q'])
    
    return response