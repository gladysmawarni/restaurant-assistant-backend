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


# ----- GET RESERVATION ----- 
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
        - DO NOT return the link if you are unsure. Remember the name of the restaurant should match exactly the same in the URL.
        - It's not enough for the link to partially match the restaurant name. The full name of the restaurant should be in the URL. 
        
        Example what not to get:
        - 'brothers cafe' and 'link/brothers-marcus' is not correct
        - 'bono' and 'link/bonoo' is not correct
        - 'k kitchen' and 'link/tamarind-kitchen' is not correct
        
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


class MenuFinder:
    """
    A class to handle the process of identifying and retrieving menu links for restaurants.
    """

    def __init__(self, google_api_key, search_engine_id):
        """
        Initialize the MenuFinder with necessary credentials.
        """
        self.google_api_key = google_api_key
        self.search_engine_id = search_engine_id
        self.system_message = """
        Task: Identify the Menu Page of a Restaurant

        From the provided list of links, identify and return the one that corresponds to the menu page of a restaurant or food establishment based on the query. Follow these guidelines carefully:

        1. Official Website:
        - If the query specifies the restaurant's name, the link must have the name of the restaurant (official website).
        - The link should have 'menu' in it.
        - Do not return the website without 'menu'
        
        2. Third-Party Platforms:
        - If the query mentions platforms like 'justeat', or 'deliveroo' ensure the link contains the name of the restaurant and corresponds to the platform mentioned.
        
        3. Location Specificity:
        - The restaurant is located in London, UK. Avoid links that do not correspond to this location.
        
        4. Exclude Product-Specific Links:
        Avoid links that lead to pages focused on a single product or item rather than the full menu.

        Handle Uncertainty:
        - If none of the links clearly match the menu page, return 'None'.
        - If you are uncertain about the match, return 'None'.

        Exclude Provided URL:
        - Do not consider the exact URL that has already been given as input.
        - Do not consider a different base URL that is given as an input.

        Output:
        Return only the selected link (if it meets all criteria) or 'None'.
        """

    @retry_on_failure(retries=5, delay=3)
    def search_menu_links(self, query):
        """
        Search for menu links using Google Custom Search API.

        Args:
            query (str): Search query for Google Custom Search API.

        Returns:
            list: A cleaned list of links retrieved from the API.
        """
        url = 'https://www.googleapis.com/customsearch/v1'
        params = {
            'key': self.google_api_key,
            'cx': self.search_engine_id,
            'q': query,
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            links = [item['link'] for item in response.json().get('items', [])]
            return self._clean_links(links)
        except requests.RequestException as e:
            return []

    def _clean_links(self, links):
        """
        Clean links by removing unnecessary parts like "p/" or "reel/".

        Args:
            links (list): List of URLs.

        Returns:
            list: Cleaned URLs.
        """
        
        return links

    def identify_menu_link(self, links, query):
        """
        Use a system prompt to identify the menu link from a list of links.

        Args:
            links (list): List of candidate links.
            query (str): User's query.

        Returns:
            str: Identified menu link or 'None' if no match is found.
        """
        messages = [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": f"query: {query}, links: {links}"}
        ]

        try:
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.5
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return 'None'

    def get_menu(self, restaurant_name, website=None):
        """
        Main method to retrieve the menu link for a restaurant.

        Args:
            restaurant_name (str): Name of the restaurant.
            website (str, optional): Official website of the restaurant.

        Returns:
            str: The identified menu link or 'None' if no match is found.
        """
        queries = [
            f"{website} menu" if website else f"{restaurant_name} menu",
            f"{restaurant_name} london restaurant menu",
            f"{restaurant_name} london justeat menu",
            f"{restaurant_name} london deliveroo menu"
        ]

        for query in queries:
            links = self.search_menu_links(query)
            menu_link = self.identify_menu_link(links, query)
            if menu_link != 'None':
                return menu_link

        return 'None'
