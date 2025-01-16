import streamlit as st
import requests
from openai import OpenAI
from helper.utils import retry_on_failure

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
        raise f"An error occurred: {str(e)}"

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


### ------ GOOGLE INFO ------
def summarize_reviews(reviews):
    system_message = """
    Summarize the five provided Google reviews into a single concise sentence. Highlight the key positive and negative aspects of the restaurant.
    """
    # Define the assistant's role and set up the messages for the API call
    messages = [
        {
            "role": "system",
            "content": system_message
        },
        {
            "role": "user",
            "content": f"Reviews: {reviews}"
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


def get_google_info(place_id):
    url = f"https://places.googleapis.com/v1/places/{place_id}"

    # Define the headers
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-Goog-FieldMask": "displayName,formattedAddress,internationalPhoneNumber,priceLevel,rating,userRatingCount,reviews,websiteUri,googleMapsUri,regularOpeningHours,servesVegetarianFood,goodForChildren,allowsDogs,goodForGroups,goodForWatchingSports,menuForChildren,servesBreakfast,servesBrunch,servesLunch,servesDinner,outdoorSeating",
    }

    # Define the headers
    params = {
        "key": st.secrets['GOOGLE_API_KEY']
    }
    
    response = requests.get(url, params=params, headers=headers).json()

    restaurant_data = {}
    restaurant_data['restaurant'] = response.get('displayName', {}).get('text', 'N/A')
    restaurant_data['address'] = response.get('formattedAddress', 'N/A')
    restaurant_data['phone_number'] = response.get('internationalPhoneNumber', 'N/A')
    try:
        price_level = response.get('priceLevel', 'N/A')
        restaurant_data['price_level'] = price_level.split('_')[-1]
    except:
        restaurant_data['price_level'] = 'N/A'

    restaurant_data['google_rating'] = response.get('rating', 'N/A')
    restaurant_data['google_rating_count'] = response.get('userRatingCount', 'N/A')
    try:
        reviews = response.get('reviews', 'N/A')
        restaurant_data['google_reviews'] = [{'rating': i['rating'], 'review':i['text']['text'], 'published': i['publishTime'].split('T')[0]} for i in reviews]
        restaurant_data['google_reviews_summary'] = summarize_reviews(restaurant_data['google_reviews'])
        restaurant_data['last5_google_rating'] = sum([float(i['rating']) for i in reviews]) / len(reviews)
    except:
        restaurant_data['google_reviews'] = 'N/A'
        restaurant_data['google_reviews_summary'] = 'N/A'
        restaurant_data['last5_google_rating'] = 'N/A'

    restaurant_data['reservable'] = response.get('reservable', 'N/A')
    restaurant_data['serves_vegetarian'] = response.get('servesVegetarianFood', 'N/A')
    restaurant_data['google_maps_uri'] = response.get('googleMapsUri', 'N/A')
    restaurant_data['opening_hours'] = response.get('regularOpeningHours', {}).get('weekdayDescriptions', 'N/A')
    restaurant_data['website_uri'] = response.get('websiteUri', 'N/A')
    restaurant_data['goodForChildren'] = response.get('goodForChildren', 'N/A')
    restaurant_data['goodForGroups'] = response.get('goodForGroups', 'N/A')
    restaurant_data['allowsDogs'] = response.get('allowsDogs', 'N/A')
    restaurant_data['goodForWatchingSports'] = response.get('goodForWatchingSports', 'N/A')
    restaurant_data['menuForChildren'] = response.get('menuForChildren', 'N/A')
    restaurant_data['servesBreakfast'] = response.get('servesBreakfast', 'N/A')
    restaurant_data['servesBrunch'] = response.get('servesBrunch', 'N/A')
    restaurant_data['servesLunch'] = response.get('servesLunch', 'N/A')
    restaurant_data['servesDinner'] = response.get('servesDinner', 'N/A')
    restaurant_data['outdoorSeating'] = response.get('outdoorSeating', 'N/A')

    
    return restaurant_data


### ----- RESERVATION --------
class ReservationFinder:
    """
    A class to handle the process of identifying and retrieving reservation links for restaurants.
    """

    def __init__(self, google_api_key, search_engine_id):
        """
        Initialize the ReservationFinder with necessary credentials.

        Args:
            google_api_key (str): API key for Google Custom Search.
            search_engine_id (str): Search engine ID for Google Custom Search.
        """
        self.google_api_key = google_api_key
        self.search_engine_id = search_engine_id
        self.system_message = """
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
        
        Output:
        - Return only the selected link as your answer.
        - If no suitable link is found, return 'None'.
        """

    @retry_on_failure(retries=5, delay=3)
    def search_reservation_links(self, query):
        """
        Search for reservation links using Google Custom Search API.

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
            'num': 5
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            links = [item['link'] for item in response.json().get('items', [])]
            return links
        except requests.RequestException as e:
            return []


    def identify_reservation_link(self, links, query):
        """
        Use a system prompt to identify the reservation link from a list of links.

        Args:
            links (list): List of candidate links.
            query (str): User's query.

        Returns:
            str: Identified reservation link or 'None' if no match is found.
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

    def get_reservation(self, restaurant_name, website=None):
        """
        Main method to retrieve the reservation link for a restaurant.

        Args:
            restaurant_name (str): Name of the restaurant.
            website (str, optional): Official website of the restaurant.

        Returns:
            str: The identified reservation link or 'None' if no match is found.
        """
        queries = [
            f"{website} reserve book" if website else f"{restaurant_name} reserve book",
            f"sevenrooms reservation {restaurant_name} london uk",
            f"opentable reservation {restaurant_name} london uk",
            f"thefork reservation {restaurant_name} london uk"
        ]

        for query in queries:
            links = self.search_reservation_links(query)
            reservation_link = self.identify_reservation_link(links, query)
            if reservation_link != 'None':
                return reservation_link

        return 'None'



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

            From the provided list of links, identify and return the one that corresponds to the menu page of a restaurant or food establishment based on the query. Follow these guidelines strictly:

            ---

            1. **Official Website**:
            - If the query specifies the restaurant's **official website**, the selected link must meet **all** the following criteria:
                - Belongs to the restaurant’s **official domain** (base domain matches exactly).
                - Contains the **exact full name** of the restaurant.
                - Includes the word **'menu'** in the URL path.
            - **Do not return** any link from the official website that does not include 'menu'.

            ---

            2. **Third-Party Platforms**:
            - If the query mentions specific platforms like **JustEat** or **Deliveroo**, the selected link must meet **all** the following criteria:
                - The link belongs to the mentioned platform (e.g., JustEat or Deliveroo).
                - The link contains the **exact full name** of the restaurant as specified in the query.
                - Example: For "Arabica Cafe and Kitchen," links such as `https://www.just-eat.co.uk/restaurants-caffe-arabica-bow-e3/menu` should **not** be selected because the name does not match exactly.
                - Example: For "Bang bang oriental foodhall", links such as `https://deliveroo.co.uk/menu/london/colindale/four-seasons-bang-bang` should **not** be selected because the name does not match exactly.
                - Includes the restaurant's **location** (London, UK) when available or required by the platform.

            - **Do not consider**:
                - Links from platforms not explicitly mentioned in the query.
                - Links with similar but not exact names.
            
            - Make sure to be extra careful and only choose a link if you are very certain. I will die if you choose the wrong link. It is better to choose None than to choose wrongly.

            ---

            3. **Location Specificity**:
            - The restaurant must be located in **London, UK**.
            - Avoid links that do not correspond to this location, even if other criteria are met.

            ---

            4. **Handle Uncertainty**:
            - If none of the links clearly match the menu page based on these criteria, return **'None'**.
            - If you are uncertain about the match, return **'None'**.

            ---

            5. **Exclude Provided URL**:
            - Do not consider the exact URL that has already been given as input.
            - Do not consider a link with a different base URL than the input provided.

            ---

            **Output**:
            - Return only the selected link (if it meets all criteria) or **'None'**.

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
            return links
        except requests.RequestException as e:
            return []


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
            f"{restaurant_name} london deliveroo menu",
            f"{restaurant_name} london ubereats menu"
        ]

        for query in queries:
            links = self.search_menu_links(query)
            menu_link = self.identify_menu_link(links, query)
            if menu_link != 'None':
                return menu_link
            

        return 'None'