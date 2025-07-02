
import os
import subprocess
import json
import time
import html
from telegram import Bot
from dotenv import load_dotenv
import ssl
import requests
import feedparser
from datetime import datetime, timedelta

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
    print(f"✅ Bot initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize bot: {e}")
    exit(1)

# Mining-related search terms
SEARCH_TERMS = [
    "new mining app",
    "testnet mining", 
    "depin crypto",
    "mobile mining",
    "airdrop mining",
    "crypto testnet",
    "mining opportunities"
]

# News RSS feeds related to crypto/mining
NEWS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://coindesk.com/arc/outboundfeeds/rss/",
    "https://cryptonews.com/news/feed/",
    "https://decrypt.co/feed",
    "https://www.coinbureau.com/feed/"
]

# Reddit subreddits (using JSON feeds)
REDDIT_SOURCES = [
    "https://www.reddit.com/r/CryptoCurrency/new.json?limit=10",
    "https://www.reddit.com/r/defi/new.json?limit=10", 
    "https://www.reddit.com/r/CryptoMoonShots/new.json?limit=10",
    "https://www.reddit.com/r/altcoin/new.json?limit=10",
    "https://www.reddit.com/r/ethereum/new.json?limit=10"
]

# Track seen content
seen_items = {
    'news': set(),
    'reddit': set(),
    'twitter': set()
}

def send_telegram_message(message):
    """Sends a message to the Telegram bot."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Message sent successfully!")
            return True
        else:
            print(f"❌ Failed to send message: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False

def check_keywords(text, keywords):
    """Check if any keywords are present in the text"""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)

def scrape_news_feeds():
    """Scrape RSS news feeds for relevant content"""
    print("🔍 Checking news feeds...")
    found_items = []
    
    for feed_url in NEWS_FEEDS:
        try:
            print(f"  📰 Checking {feed_url}")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:5]:  # Check latest 5 entries
                title = entry.get('title', '')
                description = entry.get('description', '')
                link = entry.get('link', '')
                published = entry.get('published', '')
                
                # Check if content matches our keywords
                content_text = f"{title} {description}"
                if check_keywords(content_text, SEARCH_TERMS):
                    item_id = f"news_{hash(link)}"
                    if item_id not in seen_items['news']:
                        seen_items['news'].add(item_id)
                        found_items.append({
                            'type': 'news',
                            'title': title,
                            'description': description[:200] + '...' if len(description) > 200 else description,
                            'link': link,
                            'source': feed.feed.get('title', 'News'),
                            'published': published
                        })
                        
        except Exception as e:
            print(f"❌ Error checking feed {feed_url}: {e}")
            continue
    
    return found_items

def scrape_reddit():
    """Scrape Reddit for relevant posts"""
    print("🔍 Checking Reddit...")
    found_items = []
    
    headers = {
        'User-Agent': 'python:crypto-mining-bot:v1.0.0 (by /u/cryptobot)'
    }
    
    for reddit_url in REDDIT_SOURCES:
        try:
            subreddit_name = reddit_url.split('/r/')[1].split('/')[0]
            print(f"  🔴 Checking r/{subreddit_name}")
            
            response = requests.get(reddit_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                for post in data['data']['children'][:5]:  # Check latest 5 posts
                    post_data = post['data']
                    title = post_data.get('title', '')
                    selftext = post_data.get('selftext', '')
                    url = f"https://reddit.com{post_data.get('permalink', '')}"
                    score = post_data.get('score', 0)
                    created_utc = post_data.get('created_utc', 0)
                    
                    # Check if content matches our keywords
                    content_text = f"{title} {selftext}"
                    if check_keywords(content_text, SEARCH_TERMS) and score > 5:  # Only posts with some upvotes
                        item_id = f"reddit_{post_data.get('id', '')}"
                        if item_id not in seen_items['reddit']:
                            seen_items['reddit'].add(item_id)
                            found_items.append({
                                'type': 'reddit',
                                'title': title,
                                'text': selftext[:150] + '...' if len(selftext) > 150 else selftext,
                                'link': url,
                                'subreddit': subreddit_name,
                                'score': score,
                                'created': datetime.fromtimestamp(created_utc).strftime('%Y-%m-%d %H:%M')
                            })
                            
        except Exception as e:
            print(f"❌ Error checking Reddit {reddit_url}: {e}")
            continue
    
    return found_items

def scrape_tweets(query):
    """Keep the original Twitter scraping as backup"""
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        command = f"snscrape --jsonl --max-results 3 --retry 1 twitter-search '{query}'"
        env = os.environ.copy()
        env['PYTHONHTTPSVERIFY'] = '0'
        env['SSL_VERIFY'] = 'false'
        output = subprocess.check_output(command, shell=True, text=True, env=env, timeout=20)
        tweets = [json.loads(line) for line in output.strip().split('\n') if line]
        return tweets
    except Exception:
        return []  # Silently fail for Twitter since we have other sources

def send_news_alert(item):
    """Send news alert to Telegram"""
    try:
        if item['type'] == 'news':
            message = f"📰 <b>Crypto News Alert</b>\n\n"
            message += f"<b>{html.escape(item['title'])}</b>\n\n"
            message += f"{html.escape(item['description'])}\n\n"
            message += f"📅 {item['published']}\n"
            message += f"🔗 <a href='{item['link']}'>Read More</a>\n"
            message += f"📡 Source: {item['source']}"
            
        elif item['type'] == 'reddit':
            message = f"🔴 <b>Reddit Alert - r/{item['subreddit']}</b>\n\n"
            message += f"<b>{html.escape(item['title'])}</b>\n\n"
            if item['text']:
                message += f"{html.escape(item['text'])}\n\n"
            message += f"👍 Score: {item['score']} | 📅 {item['created']}\n"
            message += f"🔗 <a href='{item['link']}'>View Post</a>"
            
        elif item['type'] == 'twitter':
            username = item['user']['username']
            text = html.escape(item['content'])
            link = item['url']
            message = f"🔔 <b>Twitter Alert</b>\n\n"
            message += f"<b>@{username}</b>\n\n{text}\n\n🔗 <a href='{link}'>View Tweet</a>"

        if send_telegram_message(message):
            print(f"✅ Sent {item['type']} alert to Telegram")
        else:
            print(f"❌ Failed to send {item['type']} alert")
            
    except Exception as e:
        print(f"❌ Error sending alert: {e}")

def test_bot():
    """Send a test message to verify bot is working"""
    print("🧪 Testing bot connectivity...")
    test_message = """🤖 <b>Multi-Source Crypto Bot Test!</b>

✅ <b>Your bot is now monitoring:</b>
📰 News feeds (CoinTelegraph, CoinDesk, etc.)
🔴 Reddit (r/CryptoCurrency, r/defi, etc.)  
🐦 Twitter (when available)

🎯 <b>Searching for:</b>
• New mining apps
• Testnet opportunities  
• DePIN projects
• Mobile mining
• Airdrops & more

If you received this, your multi-source setup is working perfectly! 🚀"""

    if send_telegram_message(test_message):
        print("✅ Test message sent! Check your Telegram.")
        return True
    else:
        print("❌ Test message failed!")
        return False

def run_multi_source_bot():
    """Main bot function with multiple data sources"""
    if not test_bot():
        print("❌ Bot test failed. Exiting.")
        return

    print("🔄 Starting multi-source monitoring...")

    while True:
        try:
            # Check news feeds
            news_items = scrape_news_feeds()
            for item in news_items:
                send_news_alert(item)
                time.sleep(2)  # Small delay between messages

            # Check Reddit
            reddit_items = scrape_reddit()
            for item in reddit_items:
                send_news_alert(item)
                time.sleep(2)

            # Try Twitter as backup (might fail silently)
            print("🔍 Checking Twitter (backup)...")
            for term in SEARCH_TERMS[:2]:  # Just check 2 terms to save time
                tweets = scrape_tweets(term)
                for tweet in tweets:
                    tweet_id = tweet['id']
                    if tweet_id not in seen_items['twitter']:
                        seen_items['twitter'].add(tweet_id)
                        tweet['type'] = 'twitter'
                        send_news_alert(tweet)
                        time.sleep(2)

            print(f"⏳ Cycle complete. Found {len(news_items)} news items and {len(reddit_items)} Reddit posts.")
            print("⏳ Waiting 10 minutes before next check...")
            time.sleep(600)  # Wait 10 minutes

        except KeyboardInterrupt:
            print("🛑 Bot stopped by user")
            break
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            time.sleep(60)  # Wait 1 minute before retrying

# Run the multi-source bot
run_multi_source_bot()
