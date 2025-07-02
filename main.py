import os
import subprocess
import json
import time
import html
from telegram import Bot
from dotenv import load_dotenv

# Load secrets from .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Initialize bot
bot = Bot(token=BOT_TOKEN)

# Mining-related search terms
SEARCH_TERMS = [
    "new mining app",
    "testnet mining",
    "depin crypto",
    "mobile mining"
]

# Track seen tweets
seen_tweet_ids = set()

def scrape_tweets(query):
    try:
        command = f"snscrape --jsonl --max-results 5 twitter-search '{query}'"
        output = subprocess.check_output(command, shell=True, text=True)
        tweets = [json.loads(line) for line in output.strip().split('\n') if line]
        return tweets
    except subprocess.CalledProcessError as e:
        print(f"Error scraping for '{query}': {e}")
        return []

def send_to_telegram(tweet):
    tweet_id = tweet['id']
    username = tweet['user']['username']
    text = html.escape(tweet['content'])
    link = tweet['url']
    message = f"🔔 New tweet by @{username}:\n\n{text}\n\n🔗 {link}"
    bot.send_message(chat_id=CHAT_ID, text=message)

def run_bot():
    while True:
        for term in SEARCH_TERMS:
            print(f"Checking for: {term}")
            tweets = scrape_tweets(term)
            for tweet in tweets:
                if tweet['id'] not in seen_tweet_ids:
                    seen_tweet_ids.add(tweet['id'])
                    send_to_telegram(tweet)
        time.sleep(300)  # Wait 5 minutes before next check

# Run the bot
run_bot()
