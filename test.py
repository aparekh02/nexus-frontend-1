# import argparse
# import os
# from dotenv import load_dotenv
# import tweepy
# import google.generativeai as genai

# load_dotenv()

# def main(args):
#     print(f"Number: {args.n}")
#     n = args.n

#     api_key_secret = os.getenv("X_CLIENT_SECRET")
#     api_key = os.getenv("X_CLIENT_ID")
#     access_token = os.getenv("X_ACCESS_TOKEN")
#     access_token_secret= os.getenv("X_SECRET_ACCESS_TOKEN")

#     Client = tweepy.Client(consumer_key=api_key,consumer_secret=api_key_secret,access_token=access_token,access_token_secret=access_token_secret)
    
#     for i in range(n):
#         prompt = "You're a viral tweet generator which returns a viral tech tweet without hastags, quotes or exclamation mark. The reply should only be tweet which can be directly copy-pasted."
#         tweet = chat(prompt)
#         print(tweet)
#         Client.create_tweet(text=tweet)


# def chat(user_message):
#     genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
#     model = genai.GenerativeModel('gemini-2.5-flash')

#     try:
#         response = model.generate_content(user_message)
#         reply = response.text
#         return(reply)
#     except Exception as e:
#         print(f"Error: {e}")
#         return 'Abort'

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Process some parameters.")
#     parser.add_argument('--n', type=int, required=True, help='Number of tweets')

#     args = parser.parse_args()
#     main(args)

import tweepy
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Retrieve Twitter API keys from .env
consumer_key = os.getenv("X_CLIENT_ID")
consumer_secret = os.getenv("X_CLIENT_SECRET")
access_token = os.getenv("X_ACCESS_TOKEN")
access_token_secret = os.getenv("X_SECRET_ACCESS_TOKEN")

#Pass in our twitter API authentication key
auth = tweepy.OAuth1UserHandler(
    consumer_key, consumer_secret,
    access_token, access_token_secret
)

#Instantiate the tweepy API
api = tweepy.API(auth, wait_on_rate_limit=True)


search_query = "'ref''world cup'-filter:retweets AND -filter:replies AND -filter:links"
no_of_tweets = 100

try:
    #The number of tweets we want to retrieved from the search
    tweets = api.search_tweets(q=search_query, lang="en", count=no_of_tweets, tweet_mode ='extended')
    
    #Pulling Some attributes from the tweet
    attributes_container = [[tweet.user.name, tweet.created_at, tweet.favorite_count, tweet.source, tweet.full_text] for tweet in tweets]

    #Creation of column list to rename the columns in the dataframe
    columns = ["User", "Date Created", "Number of Likes", "Source of Tweet", "Tweet"]
    
    #Creation of Dataframe
    tweets_df = pd.DataFrame(attributes_container, columns=columns)
except BaseException as e:
    print('Status Failed On,',str(e))
     