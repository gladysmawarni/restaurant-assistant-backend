from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from openai import OpenAI
import json
import pandas as pd

import streamlit as st


# Vector DB
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
pc = Pinecone(st.secrets['PINECONE_API_KEY'])

index_all = pc.Index('testrestaurantsall')
vector_all = PineconeVectorStore(index=index_all, embedding=embeddings)

index_cuisine = pc.Index('testrestaurantscuisine')
vector_cuisine = PineconeVectorStore(index=index_cuisine, embedding=embeddings)

index_dishes = pc.Index('testrestaurantscuisinedishes')
vector_dishes = PineconeVectorStore(index=index_dishes, embedding=embeddings)

index_desc = pc.Index('testrestaurantsdesc')
vector_desc = PineconeVectorStore(index=index_desc, embedding=embeddings)


# OpenAI
client = OpenAI()

# Grok
grok_client = OpenAI(
  api_key=st.secrets['GROK_API_KEY'],
  base_url="https://api.x.ai/v1",
)

if 'memories' not in st.session_state:
    st.session_state.memories = []


##### ----- FUNCTIONS ----- #####
def make_filter(bound):
    # Initialize a list to hold individual filters for each location
    filters = []

    for point in bound.get('locations', []):
        # Combine latitude and longitude filters for the current location
        location_filter = {
            "$and": [
                {"latitude": {"$lte": float(point['northeast']['lat'])}},
                {"latitude": {"$gte": float(point['southwest']['lat'])}},
                {"longitude": {"$lte": float(point['northeast']['lon'])}},
                {"longitude": {"$gte": float(point['southwest']['lon'])}}
            ]
        }
        # Add the location filter to the list of filters
        filters.append(location_filter)

    if len(filters) > 1:
        # Combine all location filters using the $or operator
        combined_filter = {
            "$or": filters
        }

        return combined_filter
    else:
        return location_filter
    
def area_bounds(loc):
    # prompt = f"""
    # Provide the exact boundary coordinates (northeast and southwest) for the given location.

    # 1. If the location is ambiguous (e.g., "Halfway between Willesden Green and Stratford"), return details for at least **three distinct areas**. For each area, include:
    # - The name of the area
    # - Northeast coordinates ("lat" and "lon")
    # - Southwest coordinates ("lat" and "lon")

    # 2. If the location is specific, return details for only that area.

    # 3. If the word 'near' is included along with an area, return details for the area and the surroundings. If the area is big, simply extend the latitude and longitude to cover an extra mile around.

    # - Ensure latitude and longitude values are formatted with exactly **7 decimal places**.
    # - Return the response as a JSON with no additional text or formatting. 
    # - The JSON object must use 'locations' as the main key.
    # """

    prompt = """
    For a prompt you are finding Meeting points in London: 
    1 - For between/midpoint of two places, plot the journey on a tfl tube map and work out the total journey time. Once calculated, halve the journey time and then suggest suitable locations that are the same journey time to within +/- 5 minutes for both people. Please suggest as many areas as possible 
    2 - Specific location: return area, expand by 0.25 sq miles if <0.25 sq miles. 
    3 - 'Near/around/close to': include area + surroundings within 0.3 miles. 
    List each area: name, northeast coords ("lat", "lon"), southwest coords ("lat", "lon". Return JSON, no text/format, 'locations' key.
    """


    completion = grok_client.chat.completions.create(
    model="grok-2-latest",
    messages=[
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": loc
        }
    ],
    temperature=0.7,
    response_format={ "type": "json_object" }
    )

    bound = json.loads(completion.choices[0].message.content)
    # with open('data.json', 'w', encoding='utf-8') as f:
    #     json.dump(bound, f, ensure_ascii=False, indent=4)

    st.header('Area')
    for i in bound['locations']:
        st.write(f'**{i['name']}**: Northeast: {i['northeast']['lat']}, {i['northeast']['lon']}, Southwest: {i['southwest']['lat']}, {i['southwest']['lon']}')

    area_filter = make_filter(bound)

    return area_filter

def add_more_filter(dining: str = "None", vegetarian: bool = False, vegan: bool = False, price_level: str = "None"):
    key_map = {
        'breakfast': 'servesBreakfast',
        'lunch': 'servesLunch',
        'brunch': 'servesBrunch',
        'dinner': 'servesDinner',
        'vegetarian': 'serves_vegetarian',
        'vegan': 'serves_vegan',
    }

    final_filter = {}
    filters_to_add = []

    if dining != "None":
        filters_to_add.append({key_map[dining]: True})
    if vegetarian == True:
        filters_to_add.append({key_map['vegetarian']: True})
    if vegan == True:
        filters_to_add.append({key_map['vegan']: True})
    if price_level != "None":
        filters_to_add.append({'price_level': price_level})
    
    if filters_to_add:
        # if '$or' in area:
        #     for loc in area['$or']:
        #         loc['$and'].extend(filters_to_add)
        # else:
            final_filter.setdefault('$and', []).extend(filters_to_add)
    
    return final_filter


def get_data(
        location: str,
        cuisine_specification: str,
        other_specification: str,
        dining_preference: str = "None",
        vegetarian: bool = False,
        vegan: bool = False,
        price_level: str = "None",
        k: int = 100
    ) -> list:

    info = {}
    info['cuisine'] = cuisine_specification
    info['details'] = other_specification
    info['location'] = location
    info['dining time'] = dining_preference
    info['vegetarian'] = vegetarian
    info['vegan'] = vegan
    info['price level'] = price_level
    st.header('Prompt')
    st.dataframe(pd.DataFrame.from_dict([info]), hide_index=True)
    st.divider()


    area_filter = area_bounds(location)
    all_filter = add_more_filter(dining_preference, vegetarian, vegan, price_level)
    # print(all_filter)
    
    st.divider()
    st.header('Data')
    cuisine = vector_cuisine.similarity_search_with_score(cuisine_specification, k=k)

    # can be optimized??
    new_results = []
    REST_NAMES = []
    for i in cuisine:
        if i[1] > 0.4:
            result_dict = {}
            result_dict['restaurant_name'] = i[0].metadata.get('restaurant')
            REST_NAMES.append(i[0].metadata.get('restaurant'))
            result_dict['review'] = i[0].page_content
            result_dict['dining time'] = i[0].metadata.get('restaurant')
            result_dict['vegetarian'] = i[0].metadata.get('serves_vegetarian')
            result_dict['vegan'] = i[0].metadata.get('serves_vegan')
            result_dict['price_level'] = i[0].metadata.get('price_level')
            result_dict['score'] = i[1]
        
            new_results.append(result_dict)
    

    new_results2 = []
    if other_specification != "":
        others = vector_all.similarity_search_with_score(other_specification, k=k)
        for i in others:
            if (i[1] > 0.3) & (i[0].metadata.get('restaurant') in REST_NAMES):
                result_dict2 = {}
                result_dict2['restaurant_name'] = i[0].metadata.get('restaurant')
                result_dict2['vegetarian'] = i[0].metadata.get('serves_vegetarian')
                result_dict2['vegan'] = i[0].metadata.get('serves_vegan')
                result_dict2['price_level'] = i[0].metadata.get('price_level')
                result_dict2['review'] = i[0].page_content
                result_dict2['score'] = i[1]
            
                new_results2.append(result_dict2)
    
    
    def add_filter(li):
        filtered_results = []

        for i in li:
            keep = True

            if vegan != False:
                vegan_pref = i['vegan']
                if vegan_pref is False:
                    keep = False
            
            if vegetarian != False:
                vegetarian_pref = i['vegetarian']
                if vegetarian_pref is False:
                    keep = False
            
            # Check price level
            if price_level != "None":
                item_price_level = i['price_level']
                if item_price_level != price_level:
                    keep = False


            if keep == True:
                filtered_results.append(i)
        
        return filtered_results


    if len(new_results2) > 3:
        filtered = add_filter(new_results2)


    else:
        filtered = []


    # results = vector_all.similarity_search_with_score(f"{cuisine_specification}, {other_specification}", filter=all_filter, k=k)
    # results2 = vector_cuisine.similarity_search_with_score(cuisine_specification, filter=all_filter, k=k)
    # results3 = vector_dishes.similarity_search_with_score(cuisine_specification, filter=all_filter, k=k)
    # results4 = vector_desc.similarity_search_with_score(other_specification, filter=all_filter, k=k)

    # st.write('Total restaurant in the area: ', len(results)+1)

    

    
    # new_results3 = []
    # for i in results3[:10]:
    #     result_dict3 = {}
    #     result_dict3['restaurant_name'] = i[0].metadata.get('restaurant')
    #     result_dict3['review'] = i[0].page_content
    #     result_dict3['score'] = i[1]
    
    #     new_results3.append(result_dict3)

    # new_results4 = []
    # for i in results4[:10]:
    #     result_dict4 = {}
    #     result_dict4['restaurant_name'] = i[0].metadata.get('restaurant')
    #     result_dict4['review'] = i[0].page_content
    #     result_dict4['score'] = i[1]
    
    #     new_results4.append(result_dict4)


    return new_results, new_results2, filtered





##### ------ TOOLS ----- #####
tools = [{
    "type": "function",
    "function": {
        "name": "get_data",
        "description": "Get current temperature for a given location.",
        "parameters": {
            "type": "object",
             "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City or location or areas in London, England. e.g 'Near Wimbledon', 'Central London'"
                },
                "cuisine_specification": {
                    "type": "string",
                    "description": "Cuisine preference e.g asian food"
                },
                "other_specification": {
                    "type": "string",
                    "description": "Restaurant or other preferences preference, or any specific cuisine e.g hidden gems restaurant, chicken curry"
                },
                "dining_preference": {
                    "type": "string",
                    "description": "Dining type, if not specified then it is 'None'",
                    "enum": ['breakfast', 'brunch', 'lunch', 'dinner', 'None']
                },
                "vegetarian": {
                    "type": "boolean",
                    "description": "If the user specified vegetarian preference, if not mentioned then it is False, differentiate from vegan.",
                    "enum": [True, False]
                },
                "vegan": {
                    "type": "boolean",
                    "description": "If the user specified vegan preference, if not mentioned then it is False, differentiate from vegetarian.",
                    "enum": [True, False]
                },
                "price_level": {
                    "type": "string",
                    "description": "The specified price level; if no price or budget is mentioned, it is recorded as 'None'. Interpret related terms into price levels (e.g., 'luxury' corresponds to 'EXPENSIVE').",
                    "enum": ['INEXPENSIVE', 'MODERATE', 'EXPENSIVE', "None"]
                }
            },
            "required": [
                "location", "cuisine_specification", "other_specification", "dining_preference", "vegetarian", "vegan", "price_level"
            ],
            "additionalProperties": False
        },
        "strict": True
    }
}]

##### ----- SYSTEM PROMPT ----- #####
system_prompt = """
    You are a restaurant critic. Your job is to recommend restaurants strictly based on the available database. Follow these guidelines:

    1. Use Database Information Only: All recommendations must come exclusively from the database and align with the user's stated preferences, location (including phrases like "near" or "around"), or any additional details they provide.

    2. Respect User Input:
    - If the user provides a location or food/restaurant preference, proceed with recommendations immediately without asking for further clarification.
    - Only request additional details if their input is too vague (e.g., "good food" or "anywhere").
    
    3. Handling Location Input:
    - If the user does not specify a location, ask for one once.
    - If they still do not provide one, default to London as the location.
    
    4. Preserve User Wording (with Minor Corrections): Do not alter, exclude, or reinterpret any part of the user’s location or cuisine/restaurant input, including descriptors such as "near" or "around." However, correct minor typos while keeping the original meaning intact.

    5. No Fabrication: Never create or infer information that is not available in the database. If no matching results exist, inform the user honestly.

    6. Maintain Accuracy: Provide recommendations exactly as per the user’s request, ensuring their preferences are fully considered. If a typo correction is necessary, apply the most reasonable fix based on context. Do not exclude any restaurant/cuisine specification.

    Database Querying: When retrieving data from the database, do not inform the user that you are checking or confirming information. Simply call the function to get the data and present the recommendations promptly. Avoid making the user wait or stating that you need to check.
"""



### ----------- APP -------------
# for memory in st.session_state.memories:
#     with st.chat_message(memory["role"]):
#         st.write(memory["content"])


if user_input := st.chat_input("Say Something"):
    st.session_state.input = user_input
    # Add user message to chat history
    st.session_state.memories.append({"role": "user", "content": user_input})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.write(user_input)
    
    with st.spinner('Loading...'):
        results = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "developer", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"""
                                Chat history:
                                {st.session_state.memories},

                                User query:
                                {user_input}
                                """
                }
            ],
            tools=tools
        )

    if not results:
        with st.chat_message("assistant"):
            st.write("no result")

    if results.choices[0].message.content:
        st.session_state.memories.append({"role": "user", "content": results.choices[0].message.content})
        with st.chat_message("assistant"):
            st.write(results.choices[0].message.content)
    
    # Check if there are tool calls
    tool_calls = results.choices[0].message.tool_calls
    if tool_calls and tool_calls[0].function.name == 'get_data':
        # Parse the tool call arguments
        raw_args = tool_calls[0].function.arguments
        args = json.loads(raw_args)

        # try:
         # Fetch data based on arguments
        result1, result2, result3 = get_data(
            location=args['location'],
            cuisine_specification=args['cuisine_specification'],
            other_specification=args['other_specification'],
            dining_preference=args['dining_preference'],
            vegetarian=args['vegetarian'],
            vegan=args['vegan'],
            price_level= args['price_level']
        )

        # st.write('Top 10 (full database) - prompt: cuisine + details')
        # st.dataframe(pd.DataFrame.from_dict(data),  hide_index=True)

        st.write('cuisine database - prompt: cuisine')
        st.dataframe(pd.DataFrame.from_dict(result1),  hide_index=True)

        # st.write('Top 10 (cuisine-dishes database) - prompt: cuisine')
        # st.dataframe(pd.DataFrame.from_dict(data3),  hide_index=True)

        st.write('other description database - prompt: details')
        st.dataframe(pd.DataFrame.from_dict(result2),  hide_index=True)

        st.write('filtered (dining time, vegetarian, vegan, price level)')
        st.dataframe(pd.DataFrame.from_dict(result3),  hide_index=True)


        # except Exception as e:
        #     with st.chat_message("assistant"):
        #         st.write(f"error: {e}")
