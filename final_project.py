import requests
from yelp_secrets import YELP_KEY
from z_secrets import Z_KEY
import json
import time
import plotly.graph_objects as go
import sqlite3

CACHE_FILE_NAME = 'cache.json'
CACHE_DICT = {}

def load_cache():
    ''' Opens the cache file if it exists and loads the JSON into
    the CACHE_DICT dictionary.
    if the cache file doesn't exist, creates a new cache dictionary
    
    Parameters
    ----------
    None
    
    Returns
    -------
    The opened cache: dict
    '''
    try:
        cache_file = open(CACHE_FILE_NAME, 'r')
        cache_file_contents = cache_file.read()
        cache = json.loads(cache_file_contents)
        cache_file.close()
    except:
        cache = {}
    return cache

def save_cache(cache):
    ''' Saves the current state of the cache to disk

    Parameters
    ----------
    cache: dict
        The dictionary to save

    Returns
    -------
    None
    '''
    cache_file = open(CACHE_FILE_NAME, 'w')
    contents_to_write = json.dumps(cache)
    cache_file.write(contents_to_write)
    cache_file.close()

def make_url_request_using_cache(url, params, headers, cache):
    '''Make a request to the Web API using the baseurl and cache
    
    Parameters
    ----------
    baseurl: string
        The URL for the API endpoint
    cache: dictionary
        A dictionary of cached data
    
    Returns
    -------
    str
        the data returned from making the request in a string
    '''
    if (url in cache.keys()): # the url is our unique key
        print("Using cache")
        return cache[url]
    else:
        print("Fetching")
        time.sleep(1)
        response = requests.get(url, params=params, headers=headers)
        cache[url] = response.text
        save_cache(cache)
        return cache[url]

# ## Load the cache, save in global variable
CACHE_DICT = load_cache()

def get_yelp(terms, location, num_results):
    yelp_url = 'https://api.yelp.com/v3/businesses/search'
    yelp_headers = {'Authorization': 'Bearer %s' % YELP_KEY}
    yelp_param = {'term': terms, 'location': location, 'limit':num_results, 'sort_by': 'review_count'}
    yelp_req = requests.get(yelp_url, params=yelp_param, headers=yelp_headers).json()
    yelp_cache_url = requests.get(yelp_url,params=yelp_param, headers=yelp_headers).url
    yelp_cache = make_url_request_using_cache(yelp_cache_url, params=yelp_param,headers=yelp_headers, cache=CACHE_DICT)
    return yelp_req

def get_zomato(terms, location):
    zomato_url = 'https://developers.zomato.com/api/v2.1/locations'
    next_zomato_url = 'https://developers.zomato.com/api/v2.1/location_details'
    zomato_headers = {'user-key': Z_KEY}
    zomato_param = {'query': location}
    zomato_req = requests.get(zomato_url, params=zomato_param, headers=zomato_headers).json()
    zomato_req_url = requests.get(zomato_url, params=zomato_param, headers=zomato_headers).url
    zomato_req_cache = make_url_request_using_cache(zomato_req_url,params=zomato_param, headers=zomato_headers, cache=CACHE_DICT)
    entity_id = zomato_req['location_suggestions'][0]['entity_id']
    entity_type = zomato_req['location_suggestions'][0]['entity_type']
    next_param = {'entity_id': entity_id, 'entity_type': entity_type}
    find_zomato = requests.get(next_zomato_url, params=next_param, headers=zomato_headers).json()
    find_zomato_url = requests.get(next_zomato_url, params=next_param, headers=zomato_headers).url
    find_zomato_cache = make_url_request_using_cache(find_zomato_url,params=next_param, headers=zomato_headers, cache=CACHE_DICT)
    return find_zomato

def create_db():
    conn = sqlite3.connect('restaurants.sqlite')
    cur = conn.cursor()

    # drop_yelp = 'DROP TABLE IF EXISTS "Yelp"'
    # drop_zomato = 'DROP TABLE IF EXISTS "Zomato"'
    
    create_yelp = '''
        CREATE TABLE IF NOT EXISTS "Yelp" (
            "Id" INTEGER PRIMARY KEY AUTOINCREMENT, 
            "Name" TEXT NOT NULL,
            "Address" TEXT NOT NULL,
            "Reviews" INTEGER NOT NULL,
            "Ratings" FLOAT NOT NULL,
            "Price" TEXT NOT NULL,
            "Latitude" FLOAT NOT NULL,
            "Longitude" FLOAT NOT NULL
        )
    '''
    create_zomato = '''
        CREATE TABLE IF NOT EXISTS 'Zomato'(
            "Id" INTEGER PRIMARY KEY AUTOINCREMENT, 
            "Name" TEXT NOT NULL,
            "Address" TEXT NOT NULL,
            "Reviews" INTEGER NOT NULL,
            "Ratings" FLOAT NOT NULL,
            "Price" TEXT NOT NULL,
            "Latitude" FLOAT NOT NULL,
            "Longitude" FLOAT NOT NULL
        )
    '''
    # cur.execute(drop_zomato)
    # cur.execute(drop_yelp)
    cur.execute(create_yelp)
    cur.execute(create_zomato)
    conn.commit()
    conn.close()

def load_yelp(locations):
    insert_yelp_sql = '''
        INSERT INTO Yelp
        VALUES (NULL,?,?,?,?,?,?,?)
    '''
    conn = sqlite3.connect('restaurants.sqlite')
    cur = conn.cursor()
    for item in locations:
        name = item['name']
        review = item['review_count']
        rating = item['rating']
        price = item['price']
        address = item['location']['address1']
        city = item['location']['city']
        state = item['location']['state']
        country = item['location']['country']
        zip_code = item['location']['zip_code']
        latitude= item['coordinates']['latitude']
        longitude = item['coordinates']['longitude']
        full_add = f"{address} {city}, {state} {zip_code} {country}"
        cur.execute(insert_yelp_sql,
            [
                name,
                full_add,
                review,
                rating,
                price,
                latitude,
                longitude
            ]
        )
    conn.commit()
    conn.close()

def load_zomato(call_zomato):
    insert_zomato_sql = '''
        INSERT INTO Zomato
        VALUES (NULL,?,?,?,?,?,?,?)
    '''
    conn = sqlite3.connect('restaurants.sqlite')
    cur = conn.cursor()
    for item in call_zomato['best_rated_restaurant']:
        name = item['restaurant']['name']
        review = item['restaurant']['all_reviews_count']
        rating = item['restaurant']['user_rating']['aggregate_rating']
        if type(rating) != float:
            rating = float(rating)
        price_amount = item['restaurant']['price_range']
        if price_amount == 1:
            price = '$'
        if price_amount == 2:
            price = '$$'
        if price_amount == 3:
            price = '$$$'
        if price_amount == 4:
            price = '$$$$'
        address = item['restaurant']['location']['address']
        latitude = item['restaurant']['location']['latitude']
        longitude = item['restaurant']['location']['longitude']

        cur.execute(insert_zomato_sql,
            [
                name,
                address,
                review,
                rating,
                price,
                latitude,
                longitude
            ]
        )
    conn.commit()
    conn.close()

def scatter_1(graph_reviews, graph_ratings, graph_names):
    # number of reviews vs average reviews
    scatter_data = go.Figure(go.Scatter(x=graph_reviews, y=graph_ratings, mode='markers', marker_color = graph_ratings, marker=dict(size=12, line=dict(width=2,
    color='Grey')), text=graph_names))

    scatter_data.update_layout(title={'text':'Comparison of reviews and ratings','y':0.9, 
    'x':0.5, 'xanchor': 'center', 'yanchor': 'top'}, xaxis_title="Number of Reviews", yaxis_title="Average Rating (out of 5 stars)")
    scatter_data.show()

def scatter_2(graph_price, graph_ratings, graph_names):
    fig = go.Figure(go.Scatter(x=graph_price, y=graph_ratings, mode='markers', marker_color = graph_ratings, marker=dict(size=12, line=dict(width=2,
    color='Grey')), text=graph_names))

    fig.update_layout(title={'text':'Comparison of price and ratings','y':0.9, 
    'x':0.5, 'xanchor': 'center', 'yanchor': 'top'}, xaxis_title="Average Price", yaxis_title="Average Rating (out of 5 stars)")
    
    fig.show()

def bar_1(rating_amt, count_rating):
    fig = go.Figure(data=[go.Pie(labels= rating_amt, values=count_rating, hole=.3)])
    fig.update_layout(title={'text':'Comparison of Restaurants by Average Price','y':0.9, 
    'x':0.5, 'xanchor': 'center', 'yanchor': 'top'})
    fig.show()

def map(graph_latitude, graph_longitude, graph_names, city, cuisine):
    mapbox_access_token = 'pk.eyJ1Ijoia3NhbXUiLCJhIjoiY2s4amcyYnRiMGdteDNtcWlrcWV3Y2RnZyJ9.EHGmNlZ6XDht6ZrRcNMz6A'
    fig = go.Figure(go.Scattermapbox(
    lat=graph_latitude,
    lon=graph_longitude,
    mode='markers',marker=go.scattermapbox.Marker(size=14, color='rgb(46, 166, 163)'),
    text=graph_names))

    fig.update_layout(title={'text':f"{city}'s top restaurants and {cuisine} restaurants",'y':0.9, 
    'x':0.5, 'xanchor': 'center', 'yanchor': 'top'},
        autosize=True,
        hovermode='closest',
        mapbox=dict(
            accesstoken=mapbox_access_token,
            bearing=0,
            center=go.layout.mapbox.Center(lat=graph_latitude[0],lon=graph_longitude[0]),
            pitch=0,
            zoom=5
        )
    )

    fig.show()

if __name__ == "__main__":
    while True:
        city_input = input("Enter a city (and state pairing) or exit: ")
        city = city_input.strip().lower()
        if city == 'exit':
            break
        cuisine_input = input("Enter a type of cuisine or exit: ")
        cuisine = cuisine_input.strip().lower()
        if cuisine == 'exit':
            break
        num_results = input("Enter number of restaurants you want to return (max 50) or exit: ")
        num_results = num_results.strip().lower()
        if num_results == 'exit':
            break
        num_results = int(num_results)
        if num_results > 50:
            print("Sorry. Your number is too high. Try again.")
            continue
        if num_results < 1:
            print("Sorry. Your number is too low. Try again.")
            continue
        try:
            call_yelp = get_yelp(terms=cuisine, location=city, num_results=num_results)
            locations = call_yelp['businesses']
            i = 1
            graph_names = []
            graph_reviews = []
            graph_ratings = []
            places = []
            graph_price = []
            graph_latitude = []
            graph_longitude = []
            for item in locations:
                name = item['name']
                graph_names.append(name)
                review = item['review_count']
                graph_reviews.append(review)
                total_reviews = f"{review} reviews"
                rating = item['rating']
                graph_ratings.append(rating)
                total_ratings = f"{rating}/5 stars"
                price = item['price']
                graph_price.append(price)
                address = item['location']['address1']
                city = item['location']['city']
                state = item['location']['state']
                country = item['location']['country']
                zip_code = item['location']['zip_code']
                latitude= item['coordinates']['latitude']
                longitude = item['coordinates']['longitude']
                graph_longitude.append(longitude)
                graph_latitude.append(latitude)
                full_add = f"{address} {city}, {state} {zip_code} {country}"
                item_info = f"[{i}] {total_ratings} ({total_reviews}): {name} [{price}] - {full_add}"
                i+=1
                places.append(item_info)
            
            # print("-------------------------------")
            # print(f"YELP'S {cuisine} RESTAURANTS IN {city}:")
            # print("-------------------------------")
            # for info in places:
            #     print(info)   
            
            
            zomato = []
            call_zomato = get_zomato(terms=cuisine, location=city)
            top_cuisines =  call_zomato['top_cuisines']
            print(top_cuisines)
            num_rest = call_zomato['num_restaurant']
            print(num_rest)
            print("\n-------------------------------")
            print(f"ZOMATO'S BEST RESTAURANTS IN {city}:")
            print(f"there are {num_rest} restaurants in {city}")
            print(f"the top cuisines in {city} are {top_cuisines}")
            print("-------------------------------")
            for item in call_zomato['best_rated_restaurant']:
                name = item['restaurant']['name']
                graph_names.append(name)
                review = item['restaurant']['all_reviews_count']
                graph_reviews.append(review)
                total_reviews = f"{review} reviews"
                rating = item['restaurant']['user_rating']['aggregate_rating']
                if type(rating) != float:
                    rating = float(rating)
                graph_ratings.append(rating)
                total_ratings = f"{rating}/5 stars"
                price_amount = item['restaurant']['price_range']
                if price_amount == 1:
                    price = '$'
                if price_amount == 2:
                    price = '$$'
                if price_amount == 3:
                    price = '$$$'
                if price_amount == 4:
                    price = '$$$$'
                graph_price.append(price)
                address = item['restaurant']['location']['address']
                latitude = item['restaurant']['location']['latitude']
                longitude = item['restaurant']['location']['longitude']
                graph_latitude.append(latitude)
                graph_longitude.append(longitude)
                item_info = f"[{i}] {total_ratings} ({total_reviews}): {name} [{price}] - {address}"
                i+=1
                places.append(item_info)
                zomato.append(item_info)
            
            for info in zomato:
                print(info)
            

            rating3 = 0
            rating3_5 = 0
            rating4 = 0
            rating4_5 = 0
            rating5 = 0
            count_rating = []
            for item in graph_ratings:
                if item == 5:
                    rating5+=1
                if item < 5 and item >= 4.5:
                    rating4_5+=1
                if item <4.5 and item >= 4:
                    rating4 +=1
                if item <4 and item >=3.5:
                    rating3_5 +=1
                if item <3.5 and item >=3:
                    rating3 +=1
            count_rating.append(rating3)
            count_rating.append(rating3_5)
            count_rating.append(rating4)
            count_rating.append(rating4_5)
            count_rating.append(rating5)
            rating_amt = ['3-3.5 stars', '3.5-4 stars', '4-4.5 stars', '4.5-5 stars', '5 stars']

            
            print("\nVisualizations: ")
            print(f"[1] Map of top restaurants in {city} and of {cuisine} cuisine")
            print("[2] Scatterplot of the number of reviews compared to the number of ratings")
            print("[3] Scatterplot comparing average price to average rating")
            print("[4] Pie chart showing percentage of restaurants in each price range")

            while True:
                show_vis = input("\nEnter the number for the visualization you would like to see or exit: ")
                if show_vis == 'exit':
                    break
                show_vis = int(show_vis)
                if show_vis == 1:
                    map(graph_latitude, graph_longitude, graph_names, city, cuisine)
                if show_vis == 2:
                    scatter_1(graph_reviews, graph_ratings, graph_names)
                if show_vis == 3:
                    scatter_2(graph_price, graph_ratings, graph_names)
                if show_vis == 4:
                    bar_1(rating_amt, count_rating)
                else:
                    print("Sorry, invalid input.")  

            create_db()
            load_yelp(locations)
            load_zomato(call_zomato)
      
        except:
            print("")