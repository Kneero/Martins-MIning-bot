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

# Validate environment variables
if not BOT_TOKEN:
    print("❌ BOT_TOKEN not found. Please set it in Secrets tab.")
    exit(1)
if not CHAT_ID:
    print("❌ CHAT_ID not found. Please set it in Secrets tab.")
    exit(1)

print(f"✅ Bot configured with CHAT_ID: {CHAT_ID}")

# Initialize bot
try:
    bot = Bot(token=BOT_TOKEN)
    # Test the bot connection
    bot_info = bot.get_me()
    print(f"✅ Bot connected: @{bot_info.username}")
except Exception as e:
    print(f"❌ Failed to initialize bot: {e}")
    exit(1)

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
        # Add SSL bypass and retry options for snscrape
        command = f"snscrape --jsonl --max-results 5 --retry 2 twitter-search '{query}'"
        env = os.environ.copy()
        env['PYTHONHTTPSVERIFY'] = '0'  # Bypass SSL verification
        output = subprocess.check_output(command, shell=True, text=True, env=env)
        tweets = [json.loads(line) for line in output.strip().split('\n') if line]
        return tweets
    except subprocess.CalledProcessError as e:
        print(f"Error scraping for '{query}': {e}")
        return []
    except Exception as e:
        print(f"Unexpected error scraping for '{query}': {e}")
        return []

def send_to_telegram(tweet):
    try:
        tweet_id = tweet['id']
        username = tweet['user']['username']
        text = html.escape(tweet['content'])
        link = tweet['url']
        message = f"🔔 New tweet by @{username}:\n\n{text}\n\n🔗 {link}"
        bot.send_message(chat_id=CHAT_ID, text=message)
        print(f"✅ Sent tweet {tweet_id} to Telegram")
    except Exception as e:
        print(f"❌ Error sending to Telegram: {e}")

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
