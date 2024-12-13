import json
import random
import re
import time
from bs4 import BeautifulSoup
import requests
from stqdm import stqdm
import lxml.etree

def open_json(path: str) -> json:
    with open(path, mode="r") as f:
        file = json.load(f)
    return file


######### MULTIPLE REVIEW #########
# INFATUATION - /guides
# TIMEOUT - /food-and-drink , /restaurants (some subdomains), 
def multi_review_scraper(
    website: str,
    url: str,
    selector_options: json,
    save: bool = False,
) -> list:

    response = requests.get(url=url)
    soup = BeautifulSoup(response.content, features="lxml", from_encoding="utf-8")

    def multi_data_scraper(soup: BeautifulSoup, option_dict: dict) -> list:
        print(f"trying to multi scrape using {option_dict["option_name"]}")

        base_url = option_dict["base_url"]

        venues_selector = option_dict["venues_selector"]
        venues_soup = soup.select(venues_selector)

        if venues_soup == []:
            return None

        if venues_soup:
            all_venue_data = []
            for venue in stqdm(venues_soup):
                time.sleep(random.randint(1,5))

                ### VENUE NAME ###
                try:
                    venue_name_selector = option_dict["venue_name_selector"]
                    venue_name = venue.select_one(venue_name_selector).text
                    venue_name = re.sub(r"\d+.\xa0", "", venue_name)
                except AttributeError as e:
                    venue_name = None

                ### REVIEWS and ADDRESS TIMOUT WEBSITE###
                # save the review from the motor page and the review from the detailed page
                review_text_list = []
                if website == "Timeout":
                    # REVIEW FROM SUMMARY
                    venue_summary_review_selector = option_dict[
                        "venue_summary_review_selector"
                    ]
                    venue_summary_review_list = venue.select(
                        venue_summary_review_selector
                    )
                    summary_review = ""
                    for review_paragraph in venue_summary_review_list:
                        summary_review += review_paragraph.text + "\n"
                    summary_review = summary_review.strip()

                    summary_review = None if summary_review == "" else summary_review

                    if summary_review:
                        review_text_list.append(summary_review)
                    # REVIEW AND ADDRESS FROM DETAILS
                    try:
                        # first we need the url
                        venue_url_selector = option_dict["venue_url_selector"]
                        venue_url = base_url + venue.select_one(venue_url_selector).get(
                            "href"
                        )
                        # detailed review and address using the single venue scrapper function
                        venue_detaill_review, venue_address = single_review_scraper(
                            website=website,
                            url=venue_url,
                            detailed=False,
                            save=False,
                            selector_options=open_json(
                                "selector_options/Timeout/timeout_single_review_selector_options.json"
                            ),
                        )

                    except AttributeError as e:
                        venue_detaill_review = None
                        venue_address = None

                    if venue_detaill_review:
                        review_text_list.append(venue_detaill_review)

                ### REVIEWS and ADDRESS INFATUIATION WEBSITE###
                elif website == "Infatuation":
                    ### VENUE REVIEW ###
                    try:
                        venue_url_selector = "div[data-testid='venue-venueLink'] a"
                        venue_url = base_url + venue.select_one(venue_url_selector).get(
                            "href"
                        )
                        venue_review, _ = single_review_scraper(
                            website=website,
                            url=venue_url,
                            detailed=False,
                            save=False,
                            selector_options=open_json(
                                "selector_options/Infatuation/infatuation_single_review_selector_options.json"
                            ),
                        )
                    except AttributeError as e:
                        venue_review = None

                    if venue_review:
                        review_text_list.append(venue_review)

                    ### VENUE ADDRESS ###
                    try:
                        venue_address_selector = option_dict["venue_address_selector"]
                        venue_address = venue.select_one(venue_address_selector).text
                    except AttributeError as e:
                        venue_address = None

                else:
                    pass

                # create a list with all the reviews got
                venue_reviews = []
                for review in review_text_list:
                    review_dict = {
                        "text": review,
                        "source": website,
                    }
                    venue_reviews.append(review_dict)

                ### DATA STRUCTUR ###
                venue_data = {
                    "Venue": venue_name,
                    "Reviews": venue_reviews,
                    "Address": venue_address,
                }
                # Notify if there is some detailes for the link provided couldent be scraped
                if not (venue_name and venue_reviews != [] and venue_address):
                    # here we can skip the venue of beeing added to the list of all venues if there is any data that is missing
                    print(f"missing information for the url: {url}")

                # if we want to not add a venue that misses data but this apend on an else
                all_venue_data.append(venue_data)

        return all_venue_data

    # create a list with all selector options available
    scraping_options_dict_list = [
        selector_options[key] for key in selector_options.keys()
    ]

    for option_dict in scraping_options_dict_list:
        all_venue_data = multi_data_scraper(soup=soup, option_dict=option_dict)
        if all_venue_data:
            # save data for testing - for simulation of database update
            if save:
                # TODO - save dynamicly
                with open(
                    f"data/{website}/dataMulti.json", mode="w", encoding="utf-8"
                ) as f:
                    json.dump(
                        all_venue_data, f
                    )  # , ensure_ascii=False    --- > parameter to not save unicoded characters
            break
        else:
            continue

    if website == "Timeout" and not all_venue_data:
        # can try the next functions !!!!
        print(
            "No Option Aviliable to scrape data correctly using Multi venue Scraping! Trying to get one review! using single review scrapper"
        )

        single_venue_data = single_review_scraper(
            url=url,
            website=website,
            save=save,
            selector_options=open_json(
                "selector_options/Timeout/timeout_single_review_selector_options.json"
            ),
        )
        if single_venue_data:
            print("manage using single review scrapper!")
            return single_venue_data

    return all_venue_data


######### SINGLE REVIEW  #########
# HOTDINNERS -- /Gastroblog/Test-drive, /Gastroblog/Latest-news, /Features (some subdomais), /London-restaurants
# TIMEOUT -- /food-and-drink (some subdomains), /bars-and-pubs /restaurants
# INFATUATION -- /reviews
def single_review_scraper(
    url: str,
    website: str,
    selector_options: json,
    save: bool = False,
    detailed: bool = True,
) -> dict | None:

    response = requests.get(url=url)
    soup = BeautifulSoup(response.content, features="lxml", from_encoding="utf-8")

    # aricle_body_selector = "div[itemprop='articleBody']"
    # aricle_body_soup = soup.select_one(aricle_body_selector)

    def data_scrapper(soup: BeautifulSoup, option_dict: dict) -> list | tuple[str, str]:

        print(
            f"trying single scraper selector {option_dict['option_name']} - to get {"reviews and address" if detailed == False else "all details"}"
        )

        aricle_body_selector = option_dict["aricle_body_selector"]
        aricle_body_soup = soup.select_one(aricle_body_selector)

        if not aricle_body_soup:
            return None
        # Venue Name
        try:
            venue_name_selector = option_dict["venue_name_selector"]
            venue_name = aricle_body_soup.select_one(venue_name_selector).text
            # for hotscope single scraper ?
            venue_name = re.sub("More about ", "", venue_name)
        except AttributeError as error:
            venue_name = None

        # Venue Review
        venue_review_selector = option_dict["venue_review_selector"]
        review_list = aricle_body_soup.select(
            venue_review_selector
        )  # without the titles ==> add :not(:has(strong))
        # review_list = [
        #     review.text for review in review_list if not review.text == "\xa0"
        # ]

        review = ""
        for review_paragraph in review_list:
            if review_paragraph.text != "\xa0":
                review += review_paragraph.text + "\n"
            else:
                continue
        review = review.strip()

        review = None if review == "" else review

        # Venue Address
        if website == "Infatuation":
            # get the adress ussing the href from a anchore tag
            try:
                googleMaps_url_selector = option_dict["googleMaps_url_selector"]
                googleMaps_url = aricle_body_soup.select_one(
                    googleMaps_url_selector
                ).get("href")
                pattern = r"\+.+$"
                venue_address = re.findall(pattern, googleMaps_url)[0][1:]
            except AttributeError as e:
                venue_address = None
        else:
            venue_address_selector = option_dict["venue_address_selector"]
            venue_address_list = aricle_body_soup.select(venue_address_selector)
            venue_address = ""
            for address in venue_address_list:
                address = address.text
                # cleaning the text fot hotdinners
                address = re.sub(r"Where is it\?\xa0|Where is it\? ", "", address)
                # clean the text address for ...
                address = re.sub(r"Address:\u00a0", "", address)
                venue_address += address + " "
            # except AttributeError as error:
            # venue_address = None

            # venue_address is empty string make it None
            venue_address = venue_address.strip()
            venue_address = None if venue_address == "" else venue_address

        # Notify if there is some detailes for the link provided couldent be scraped
        if not (venue_name and review and venue_address) and detailed:
            print(f"missing information for the url: {url}")
            return None

        ### DATA STRUCTURE ###
        venue_data = [
            {
                "Venue": venue_name,
                "Reviews": [
                    {
                        "text": review,
                        "source": website,
                    }
                ],
                "Address": venue_address,
            }
        ]

        if detailed:
            return venue_data
        else:
            return review, venue_address

    scraping_options_dict_list = [
        selector_options[key] for key in selector_options.keys()
    ]

    for option_dict in scraping_options_dict_list:
        venue_data = data_scrapper(soup=soup, option_dict=option_dict)

        if venue_data and detailed:
            if save:
                with open(
                    f"data/{website}/dataSingle.json", mode="w", encoding="utf-8"
                ) as f:
                    json.dump(
                        venue_data, f
                    )  # , ensure_ascii=False    --- > parameter to not save unicoded characters
            break
        elif venue_data:
            break
        else:
            continue

    if detailed:
        return venue_data
    else:
        review, venue_address = venue_data
        return review, venue_address


######### MULTIPLE REVIEW - NO DIVISIONS IN HTML! #########
# when there is no separation between restaurants in the html structure
# bad designed pages

# HOTDINNERS  -- /Features
# TIMEOUT -- /news
def multi_sigle_block_reviews_scraper(
    website: str,
    url: str,
    selector_options: json,
    save: bool = False,
):

    response = requests.get(url=url)
    soup = BeautifulSoup(response.content, features="lxml", from_encoding="utf-8")

    def multi_data_block_scrapper(soup: BeautifulSoup, option_dict: dict) -> list:

        # print(f"trying to scrape using {option_dict["option_name"]}")

        venues_selector = option_dict["venues_selector"]
        venues_soup = soup.select_one(venues_selector)

        if not venues_soup:
            return None

        raw_data_list = []
        # Venue name
        venue_name_selector = option_dict["venue_name_selector"]
        venue_name_list = venues_soup.select(venue_name_selector)
        venue_name_list = [name.text for name in venue_name_list if not ('the best' in name.text.lower() and 'restaurant' in name.text.lower())]
        raw_data_list.append(venue_name_list)

        # Venue Review
        venue_review_selector = option_dict["venue_review_selector"]
        venue_review_list = venues_soup.select(venue_review_selector)
        venue_review_list = [
            review.text.strip()
            for review in venue_review_list
            if (review.text != "\xa0") and (review.text != "")
        ]
        # for option four of the selector - hotdinners multi review
        venue_review_list = [review.split("Why should you care? ")[1] if "Why should you care? " in review else review for review in venue_review_list]
        venue_review_list = [review.split("What We Know:  ")[1] if "What We Know:  " in review else review for review in venue_review_list]
        raw_data_list.append(venue_review_list)

        # Venue address
        venue_address_selector = option_dict[
            "venue_address_selector"
        ]  # the address appeares as the first simbling tag of an h2 tag
        venue_address_list = venues_soup.select(venue_address_selector)
        venue_address_list = [address.text.strip() for address in venue_address_list]
        
        # for option four of the selector - hotdinners multi review
        venue_address_list = [address.split("Why should you care? ")[0] if "Why should you care? " in address else address for address in venue_address_list]
        venue_address_list = [address.split("Where is it? ")[1] if "Where is it? " in address else address for address in venue_address_list]
        venue_address_list = [address.split("Address:  ")[1] if "Address:  " in address else address for address in venue_address_list]

        raw_data_list.append(venue_address_list)

        # Check if data is complete for each venue -- all the lists with information must be same size and not empty
        # Needed because there is no devisions between each restaurante/venue
        if bool(raw_data_list != []) & (
            all(len(li) == len(raw_data_list[0]) for li in raw_data_list)
            & all(li != [] for li in raw_data_list)
        ):

            venue_info_list = zip(*raw_data_list)
            all_venue_data = []
            for venue_name, review, address in venue_info_list:

                ### DATYA STRUCTURE ###
                venue_data = {
                    "Venue": venue_name,
                    "Reviews": [
                        {
                            "text": review,
                            "source": website,
                        }
                    ],
                    "Address": address,
                }

                all_venue_data.append(venue_data)

            return all_venue_data
        else:
            # could get anny review using structrure for multi reviews
            return None

    # create a list with all selector options available
    scraping_options_dict_list = [
        selector_options[key] for key in selector_options.keys()
    ]

    for option_dict in scraping_options_dict_list:
        all_venue_data = multi_data_block_scrapper(soup=soup, option_dict=option_dict)
        if all_venue_data:
            # save data for testing - for simulation of database update
            if save:
                with open(
                    f"data/{website}/dataMultiple.json", mode="w", encoding="utf-8"
                ) as f:
                    json.dump(
                        all_venue_data, f
                    )  # , ensure_ascii=False    --- > parameter to not save unicoded characters

            break
        else:
            continue

    if website == "Hotdinners" and not all_venue_data:
        print(
            "No Option Aviliable to scrape data correctly using Multi venue Scraping! Trying to get one review! using single review scrapper"
        )
        # can try the next functions !!!!
        single_venue_data = single_review_scraper(
            website=website,
            url=url,
            save=save,
            selector_options=open_json(
                "selector_options/Hotdinners/hotdinners_gastrobloger_selector_options.json"
            ),
        )
        if single_venue_data:
            print("manage using single review scrapper!")
            return single_venue_data

    return all_venue_data


### CNtraveller Scraper
def cntraveller_scraper(url):
    final = []
    source = 'CN Traveller'
    review_2 = ''

    headers = {
    'Cookie': 'CN_geo_country_code=EG',
    'accept-language': 'en-US,en;q=0.9,ar;q=0.8',
    'priority': 'u=0, i',
    'referer': 'https://www.cntraveller.com/topic/eating-drinking',
    'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/244.178.44.111 Safari/537.36 Edg/131.0.16299.15'
    }

    response = requests.request("GET", url, headers=headers)
    dom = lxml.etree.HTML(response.text)
    containers = dom.xpath('//div[@class="body__inner-container"]')
    if len(containers) == 0:
        containers = dom.xpath('//div[@data-testid="BodyWrapper"]')
    elements = dom.xpath('//div[@class="body__inner-container"]/h2 | //div[@class="body__inner-container"]/p')
    if len(elements) == 0:
        elements = dom.xpath('//div[@data-testid="BodyWrapper"]/div/h2 | //div[@data-testid="BodyWrapper"]/div/p')
    if len(elements) < 7:
        elements = dom.xpath('//div[@class="GallerySlideFigCaption-dOeyTg gWbVWR"]//h2 | //div[@class="GallerySlideFigCaption-dOeyTg gWbVWR"]//p')
    if len(elements) == 7:
        elements = dom.xpath('//figure//h2 | //figure//p')


    for element in elements:
        address = ''
        # try: 
        if element.tag == 'h2':
            title = ''.join(element.xpath('.//text()'))
            # clean title
            pattern = r"^\d+\.\s*|,\s.*$"
            title = re.sub(pattern, "", title).strip()
            if 'The best' in title or 'Best new' in title or 'How we' in title or len(title) < 1:
                continue
            #  need the next element in the list elements
            next_element = elements[elements.index(element) + 1]
            if next_element.tag == 'p':
                review_1 = ''.join(next_element.xpath('.//text()'))
            
            try:
                next_element = elements[elements.index(element) + 2]
                if next_element.tag == 'p':
                    if 'Address' in ''.join(next_element.xpath('.//text()')):
                        address = ''.join(next_element.xpath(".//strong[contains(text(),'Address')]//following-sibling::text()[1]")[:1]).replace(':', '').strip()
                    if 'Website' not in ''.join(next_element.xpath('.//text()')):
                        review_2 = ''.join(next_element.xpath('.//text()'))
                
                    if address == '':
                        address = ''.join(next_element.xpath(".//strong[contains(text(),'Address')]//following-sibling::a/text()[1]")[:1])
            except:
                pass
            try:
                next_element = elements[elements.index(element) + 3]
                if next_element.tag == 'p' and address == '':
                    address = ''.join(next_element.xpath(".//strong[contains(text(),'Address')]//following-sibling::text()[1]")[:1]).replace(':', '').strip()
                    if address == '':
                        address = ''.join(next_element.xpath(".//strong[contains(text(),'Address')]//following-sibling::a/text()[1]")[:1])
    
            except:
                pass
            try:
                next_element = elements[elements.index(element) + 4]
                if next_element.tag == 'p' and address == '':
                    address = ''.join(next_element.xpath(".//strong[contains(text(),'Address')]//following-sibling::text()[1]")[:1]).replace(':', '').strip()
                    if address == '':
                        address = ''.join(next_element.xpath(".//strong[contains(text(),'Address')]//following-sibling::a/text()[1]")[:1])

            except:
                pass
            try:
                next_element = elements[elements.index(element) + 5]
                if next_element.tag == 'p' and address == '':
                    address = ''.join(next_element.xpath(".//strong[contains(text(),'Address')]//following-sibling::text()[1]")[:1]).replace(':', '').strip()
                    if address == '':
                        address = ''.join(next_element.xpath(".//strong[contains(text(),'Address')]//following-sibling::a/text()[1]")[:1])
            except:
                pass
            try:
                next_element = elements[elements.index(element) + 6]
                if next_element.tag == 'p' and address == '':
                    address = ''.join(next_element.xpath(".//strong[contains(text(),'Address')]//following-sibling::text()[1]")[:1]).replace(':', '').strip()
                    if address == '':
                        address = ''.join(next_element.xpath(".//strong[contains(text(),'Address')]//following-sibling::a/text()[1]")[:1])
            except:
                pass
            if title == '':
                continue

            if title in address:
                address = address.strip(title).strip(', ')

            if address != '':
                final.append({
                    "Venue": title,
                    "Reviews": [{'text': (review_1 + '\n' + review_2).strip(),
                                'source': source}],
                    "Address": address
                })
    

    if len(final) < 2:
        elemnts = dom.xpath('//div[@class="GallerySlideCaptionDek-cXnbPe blsCCS"]/div')
        for element in elemnts:
            title = ''.join(element.xpath('./p[1]//text()'))
            pattern = r"^\d+\.\s*|,\s.*$"
            title = re.sub(pattern, "", title).strip()
            review_1 = ''.join(element.xpath('./p[2]//text()'))
            review_2 = ''.join(element.xpath('./p[3]//text()'))
            address = ''.join(element.xpath(".//strong[contains(text(),'Address')]//following-sibling::text()[1]")[:1]).replace(':', '').strip()
            if address == '':
                address = ''.join(element.xpath(".//strong[contains(text(),'Address')]//following-sibling::a/text()[1]")[:1])

            if address != '':
                final.append({
                        "Venue": title,
                        "Reviews": [{'text': (review_1 + '\n' + review_2).strip(),
                                    'source': source}],
                        "Address": address
                    })
    
    return final