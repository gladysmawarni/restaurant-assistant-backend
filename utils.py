import json
from scrapers import (
    muilti_review_scraper,
    multi_sigle_block_reviews_scraper,
    single_review_scraper,
)
import streamlit as st
import hmac
import time
import unicodedata
from functools import wraps


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


def remove_accents(input_str):
    # Normalize the string to 'NFD' (Normalization Form Decomposed)
    normalized_str = unicodedata.normalize('NFD', input_str)
    # Filter out characters with the 'Mn' (Mark, Nonspacing) unicode category
    return ''.join(char for char in normalized_str if unicodedata.category(char) != 'Mn')


def retry_on_failure(retries=5, delay=1):
    """
    Decorator that retries a function call up to a specified number of times if it fails.
    
    Parameters:
        retries (int): The number of retry attempts. Default is 5.
        delay (int): Delay (in seconds) between retry attempts. Default is 1 second.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries):
                try:
                    # Try to execute the function
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    print(f"Attempt {attempt + 1} failed: {e}")
                    time.sleep(delay)  # Wait before retrying
            # Raise the last exception if all retries failed
            raise last_exception
        return wrapper
    return decorator