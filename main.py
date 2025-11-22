"""
Marketing Campaign Backend - FastAPI Server
Production-ready with security, logging, and monitoring
"""

import os
import sys
import json
import uuid
import asyncio
import logging
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from collections import defaultdict
import time

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import google.generativeai as genai
import tweepy
from supabase import create_client, Client
from dotenv import load_dotenv

# Sumy for text summarization
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.luhn import LuhnSummarizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

load_dotenv()

# ============================================================
# LOGGING CONFIGURATION
# ============================================================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("nexus-backend")

# ============================================================
# ENVIRONMENT VALIDATION
# ============================================================

def validate_environment():
    """Validate required environment variables"""
    required_vars = ["SUPABASE_URL", "SUPABASE_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Set these in Render Dashboard > Environment > Environment Variables")
        return False

    # Warn about missing API keys
    gemini_keys = [k for k in [os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, 7)] if k]
    exa_keys = [k for k in [os.getenv(f"EXA_API_KEY_{i}") for i in range(1, 7)] if k]

    if not gemini_keys:
        logger.warning("No Gemini API keys configured - AI features will not work")
    if not exa_keys:
        logger.warning("No EXA API keys configured - search features will not work")

    logger.info(f"Environment validated: {len(gemini_keys)} Gemini keys, {len(exa_keys)} EXA keys")
    return True

ENV_VALID = validate_environment()

# ============================================================
# RATE LIMITING
# ============================================================

class RateLimiter:
    """Simple in-memory rate limiter"""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for client"""
        now = time.time()
        minute_ago = now - 60

        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > minute_ago
        ]

        # Check limit
        if len(self.requests[client_id]) >= self.requests_per_minute:
            return False

        self.requests[client_id].append(now)
        return True

    def get_retry_after(self, client_id: str) -> int:
        """Get seconds until next request is allowed"""
        if not self.requests[client_id]:
            return 0
        oldest = min(self.requests[client_id])
        return max(0, int(60 - (time.time() - oldest)))

rate_limiter = RateLimiter(requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "100")))

# ============================================================
# CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Gemini API Keys - Planner uses 1-3, Others use 4-6
GEMINI_PLANNER_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]
GEMINI_OTHER_KEYS = [
    os.getenv("GEMINI_API_KEY_4"),
    os.getenv("GEMINI_API_KEY_5"),
    os.getenv("GEMINI_API_KEY_6"),
]

# EXA Search API Keys
EXA_API_KEYS = [
    os.getenv("EXA_API_KEY_1"),
    os.getenv("EXA_API_KEY_2"),
    os.getenv("EXA_API_KEY_3"),
    os.getenv("EXA_API_KEY_4"),
    os.getenv("EXA_API_KEY_5"),
    os.getenv("EXA_API_KEY_6"),
]

# API key state tracking
api_state = {
    "gemini_planner_index": 0,
    "gemini_other_index": 0,
    "exa_index": 0,
    "gemini_planner_paused_until": None,
    "gemini_other_paused_until": None,
    "exa_paused_until": None,
}

# Initialize Supabase client with error handling
supabase: Optional[Client] = None
try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully")
    else:
        logger.error("Supabase credentials missing - database features disabled")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {e}")

# Cache for tweepy clients (user_id -> client)
tweepy_clients: Dict[str, tweepy.Client] = {}

# ============================================================
# IN-MEMORY STATE
# ============================================================

active_sessions: Dict[str, Dict] = {}
stream_logs: Dict[str, List[Dict]] = {}
background_tasks_running: Dict[str, bool] = {}
scheduler_task = None

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def summarize_text(text: str, sentence_count: int = 5, method: str = "luhn") -> str:
    """
    Summarize text using sumy's statistical methods to extract key points.

    Args:
        text: Input text to summarize
        sentence_count: Number of sentences to extract
        method: 'luhn' for statistical or 'lsa' for semantic analysis

    Returns:
        Summarized text with key points
    """
    if not text or len(text.strip()) < 100:
        return text

    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        stemmer = Stemmer("english")

        if method == "lsa":
            summarizer = LsaSummarizer(stemmer)
        else:
            summarizer = LuhnSummarizer(stemmer)

        summarizer.stop_words = get_stop_words("english")

        summary_sentences = summarizer(parser.document, sentence_count)
        summary = " ".join([str(sentence) for sentence in summary_sentences])

        return summary if summary else text

    except Exception as e:
        print(f"[Sumy] Summarization error: {e}", flush=True)
        return text


def extract_key_points(text: str, num_points: int = 5) -> List[str]:
    """
    Extract key points from text as a list of sentences.

    Args:
        text: Input text
        num_points: Number of key points to extract

    Returns:
        List of key point sentences
    """
    if not text or len(text.strip()) < 100:
        return [text] if text else []

    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        stemmer = Stemmer("english")

        # Use LSA for better semantic understanding
        summarizer = LsaSummarizer(stemmer)
        summarizer.stop_words = get_stop_words("english")

        summary_sentences = summarizer(parser.document, num_points)

        return [str(sentence) for sentence in summary_sentences]

    except Exception as e:
        print(f"[Sumy] Key point extraction error: {e}", flush=True)
        return [text[:500]] if text else []


def log_stream(session_id: str, agent: str, msg_type: str, content: str):
    """Log to stream and print to console"""
    if session_id not in stream_logs:
        stream_logs[session_id] = []

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent": agent,
        "type": msg_type,
        "content": content
    }
    stream_logs[session_id].append(entry)

    # Print with color
    colors = {"thinking": "\033[93m", "action": "\033[94m", "result": "\033[92m", "error": "\033[91m"}
    color = colors.get(msg_type, "")
    reset = "\033[0m"
    print(f"{color}[{agent}] ({msg_type}) {content}{reset}", flush=True)

    # Save to Supabase
    try:
        supabase.table("agent_streams").insert({
            "session_id": session_id,
            "agent_name": agent,
            "chunk_type": msg_type,
            "content": content,
            "sequence_num": len(stream_logs[session_id])
        }).execute()
    except Exception as e:
        logger.debug(f"Failed to save stream log: {e}")

def get_tweepy_client(user_id: str) -> tweepy.Client:
    """Get authenticated tweepy client for user"""
    # Check cache first
    if user_id in tweepy_clients:
        return tweepy_clients[user_id]

    # Get credentials from database
    result = supabase.table("x_credentials").select("*").eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="X credentials not found. Please add your credentials first.")

    creds = result.data[0]

    # Create tweepy client with OAuth 1.0a
    client = tweepy.Client(
        consumer_key=creds.get("consumer_key"),
        consumer_secret=creds.get("consumer_secret"),
        access_token=creds.get("access_token"),
        access_token_secret=creds.get("access_token_secret"),
        wait_on_rate_limit=True
    )

    tweepy_clients[user_id] = client
    return client


async def get_trending_topics(query: str = "trending topics today") -> List[Dict]:
    """
    Get trending topics using EXA search (Internet trends)

    Args:
        query: Search query for trends

    Returns:
        List of trending topics with title, url, etc.
    """
    try:
        print(f"[Trending/Internet] Searching EXA for: {query}", flush=True)

        results = await call_exa_search(query, num_results=20)

        trending_list = []
        for result in results:
            trending_list.append({
                "name": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("text", result.get("snippet", ""))[:200],
                "source": "internet"
            })

        print(f"[Trending/Internet] Found {len(trending_list)} trending topics", flush=True)
        return trending_list

    except Exception as e:
        print(f"[Trending/Internet] Error fetching trends: {e}", flush=True)
        return []


async def get_x_trending(user_id: str, query: str = None) -> List[Dict]:
    """
    Get trending topics from X (Twitter) using recent popular tweets

    Args:
        user_id: User ID to get tweepy client
        query: Optional search query (if None, searches for viral/trending content)

    Returns:
        List of trending X posts with content, metrics, etc.
    """
    try:
        client = get_tweepy_client(user_id)

        # Search queries to find trending content on X
        search_queries = [
            query if query else "viral OR trending",
            "breaking news",
            "what's happening"
        ]

        trending_list = []
        seen_ids = set()

        for search_query in search_queries[:1]:  # Use first query to avoid rate limits
            try:
                print(f"[Trending/X] Searching X for: {search_query}", flush=True)

                # Search recent tweets with high engagement
                tweets = client.search_recent_tweets(
                    query=f"{search_query} -is:retweet lang:en",
                    max_results=20,
                    tweet_fields=["created_at", "public_metrics", "author_id", "text"],
                    expansions=["author_id"],
                    user_fields=["username", "name"]
                )

                if tweets.data:
                    # Build user lookup
                    users = {}
                    if tweets.includes and "users" in tweets.includes:
                        for user in tweets.includes["users"]:
                            users[user.id] = {"username": user.username, "name": user.name}

                    for tweet in tweets.data:
                        if tweet.id in seen_ids:
                            continue
                        seen_ids.add(tweet.id)

                        metrics = tweet.public_metrics or {}
                        user_info = users.get(tweet.author_id, {})

                        # Calculate engagement score
                        engagement = (
                            metrics.get("like_count", 0) +
                            metrics.get("retweet_count", 0) * 2 +
                            metrics.get("reply_count", 0)
                        )

                        trending_list.append({
                            "name": tweet.text[:100] + "..." if len(tweet.text) > 100 else tweet.text,
                            "full_text": tweet.text,
                            "url": f"https://x.com/{user_info.get('username', 'i')}/status/{tweet.id}",
                            "author": user_info.get("name", "Unknown"),
                            "username": user_info.get("username", ""),
                            "likes": metrics.get("like_count", 0),
                            "retweets": metrics.get("retweet_count", 0),
                            "replies": metrics.get("reply_count", 0),
                            "engagement_score": engagement,
                            "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                            "source": "x"
                        })

            except Exception as e:
                print(f"[Trending/X] Error searching X: {e}", flush=True)
                continue

        # Sort by engagement score
        trending_list.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)

        print(f"[Trending/X] Found {len(trending_list)} trending posts from X", flush=True)
        return trending_list[:15]  # Return top 15

    except HTTPException:
        print(f"[Trending/X] X credentials not configured for user", flush=True)
        return []
    except Exception as e:
        print(f"[Trending/X] Error fetching X trends: {e}", flush=True)
        return []

async def call_gemini_planner(prompt: str) -> str:
    """Call Gemini API for planner tasks (uses keys 1-3) with rotation"""
    global api_state

    # Check if paused
    if api_state["gemini_planner_paused_until"]:
        if datetime.utcnow() < api_state["gemini_planner_paused_until"]:
            wait_time = (api_state["gemini_planner_paused_until"] - datetime.utcnow()).seconds
            print(f"[Gemini Planner] Paused for {wait_time}s, waiting...", flush=True)
            await asyncio.sleep(wait_time)
        api_state["gemini_planner_paused_until"] = None
        api_state["gemini_planner_index"] = 0

    attempts = 0
    start_index = api_state["gemini_planner_index"]

    while attempts < len(GEMINI_PLANNER_KEYS):
        key_index = (start_index + attempts) % len(GEMINI_PLANNER_KEYS)
        api_key = GEMINI_PLANNER_KEYS[key_index]

        if not api_key:
            attempts += 1
            continue

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            api_state["gemini_planner_index"] = key_index
            return response.text
        except Exception as e:
            error_str = str(e).lower()
            if "quota" in error_str or "rate" in error_str or "limit" in error_str:
                print(f"[Gemini Planner] Key {key_index + 1} rate limited, trying next...", flush=True)
                attempts += 1
                continue
            else:
                raise e

    # All keys exhausted - pause for 1 hour
    print("[Gemini Planner] All keys exhausted, pausing for 1 hour", flush=True)
    api_state["gemini_planner_paused_until"] = datetime.utcnow() + timedelta(hours=1)
    api_state["gemini_planner_index"] = 0
    await asyncio.sleep(3600)
    return await call_gemini_planner(prompt)

async def call_gemini(prompt: str) -> str:
    """Call Gemini API for general tasks (uses keys 4-6) with rotation"""
    global api_state

    # Check if paused
    if api_state["gemini_other_paused_until"]:
        if datetime.utcnow() < api_state["gemini_other_paused_until"]:
            wait_time = (api_state["gemini_other_paused_until"] - datetime.utcnow()).seconds
            print(f"[Gemini] Paused for {wait_time}s, waiting...", flush=True)
            await asyncio.sleep(wait_time)
        api_state["gemini_other_paused_until"] = None
        api_state["gemini_other_index"] = 0

    attempts = 0
    start_index = api_state["gemini_other_index"]

    while attempts < len(GEMINI_OTHER_KEYS):
        key_index = (start_index + attempts) % len(GEMINI_OTHER_KEYS)
        api_key = GEMINI_OTHER_KEYS[key_index]

        if not api_key:
            attempts += 1
            continue

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            api_state["gemini_other_index"] = key_index
            return response.text
        except Exception as e:
            error_str = str(e).lower()
            if "quota" in error_str or "rate" in error_str or "limit" in error_str:
                print(f"[Gemini] Key {key_index + 4} rate limited, trying next...", flush=True)
                attempts += 1
                continue
            else:
                raise e

    # All keys exhausted - pause for 1 hour
    print("[Gemini] All keys exhausted, pausing for 1 hour", flush=True)
    api_state["gemini_other_paused_until"] = datetime.utcnow() + timedelta(hours=1)
    api_state["gemini_other_index"] = 0
    await asyncio.sleep(3600)
    return await call_gemini(prompt)

async def call_exa_search(query: str, num_results: int = 5) -> List[Dict]:
    """
    Call EXA Search API with key rotation
    1. Search for URLs
    2. Get contents of each URL
    3. Use sumy to extract key insights
    """
    global api_state
    import httpx

    # Check if paused
    if api_state["exa_paused_until"]:
        if datetime.utcnow() < api_state["exa_paused_until"]:
            wait_time = (api_state["exa_paused_until"] - datetime.utcnow()).seconds
            print(f"[EXA] Paused for {wait_time}s, waiting...", flush=True)
            await asyncio.sleep(wait_time)
        api_state["exa_paused_until"] = None
        api_state["exa_index"] = 0

    attempts = 0
    start_index = api_state["exa_index"]

    while attempts < len(EXA_API_KEYS):
        key_index = (start_index + attempts) % len(EXA_API_KEYS)
        api_key = EXA_API_KEYS[key_index]

        if not api_key:
            attempts += 1
            continue

        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Search for URLs
                print(f"[EXA] Searching for: {query}", flush=True)
                search_response = await client.post(
                    "https://api.exa.ai/search",
                    headers={"x-api-key": api_key},
                    json={
                        "query": query,
                        "num_results": num_results,
                        "use_autoprompt": True,
                        "type": "neural"
                    },
                    timeout=30
                )

                if search_response.status_code == 429:
                    print(f"[EXA] Key {key_index + 1} rate limited, trying next...", flush=True)
                    attempts += 1
                    continue
                elif search_response.status_code != 200:
                    print(f"[EXA] Search error {search_response.status_code}: {search_response.text}", flush=True)
                    attempts += 1
                    continue

                search_results = search_response.json().get("results", [])

                if not search_results:
                    api_state["exa_index"] = key_index
                    return []

                # Extract URLs from search results
                urls = [result.get("url") for result in search_results if result.get("url")]
                print(f"[EXA] Found {len(urls)} URLs, fetching contents...", flush=True)

                # Step 2: Get contents of each URL
                contents_response = await client.post(
                    "https://api.exa.ai/contents",
                    headers={"x-api-key": api_key},
                    json={
                        "ids": urls,
                        "text": True
                    },
                    timeout=60
                )

                if contents_response.status_code != 200:
                    print(f"[EXA] Contents error {contents_response.status_code}, using search results", flush=True)
                    # Fall back to search results if contents fails
                    api_state["exa_index"] = key_index
                    return search_results

                contents_data = contents_response.json().get("results", [])
                print(f"[EXA] Got contents for {len(contents_data)} pages", flush=True)

                # Step 3: Use sumy to extract key insights from each result
                enriched_results = []
                for content in contents_data:
                    title = content.get("title", "")
                    url = content.get("url", "")
                    text = content.get("text", "")

                    # Extract key insights using sumy
                    if text and len(text) > 100:
                        key_points = extract_key_points(text, num_points=3)
                        insights = " | ".join(key_points) if key_points else text[:500]
                    else:
                        insights = text[:500] if text else ""

                    enriched_results.append({
                        "title": title,
                        "url": url,
                        "text": insights,
                        "full_text_length": len(text)
                    })

                print(f"[EXA] Extracted key insights from {len(enriched_results)} results", flush=True)
                api_state["exa_index"] = key_index
                return enriched_results

        except Exception as e:
            print(f"[EXA] Key {key_index + 1} error: {e}", flush=True)
            attempts += 1
            continue

    # All keys exhausted - pause for 1 hour
    print("[EXA] All keys exhausted, pausing for 1 hour", flush=True)
    api_state["exa_paused_until"] = datetime.utcnow() + timedelta(hours=1)
    api_state["exa_index"] = 0
    await asyncio.sleep(3600)
    return await call_exa_search(query, num_results)

def parse_json(text: str) -> Any:
    """Extract JSON from text"""
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        start = text.find('[')
        end = text.rfind(']') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"Failed to parse JSON: {e}")
    return {"raw": text}

# ============================================================
# TASK TRACKING & MONITORING
# ============================================================

async def update_task_status(user_id: str, session_id: str, task_name: str,
                            status: str, progress: int = 0, details: str = ""):
    """Update task status in Supabase for monitoring"""
    try:
        supabase.table("task_progress").upsert({
            "user_id": user_id,
            "session_id": session_id,
            "task_name": task_name,
            "status": status,
            "progress": progress,
            "details": details,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"[TaskTracker] Error updating status: {e}", flush=True)

async def log_completed_task(user_id: str, session_id: str, task_name: str,
                            result: Dict, duration_seconds: float):
    """Log completed task to Supabase"""
    try:
        supabase.table("completed_tasks").insert({
            "user_id": user_id,
            "session_id": session_id,
            "task_name": task_name,
            "result": result,
            "duration_seconds": duration_seconds,
            "completed_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"[TaskTracker] Error logging completed task: {e}", flush=True)

# ============================================================
# BACKGROUND SCHEDULER
# ============================================================

async def run_scheduled_campaign(user_id: str, session_id: str):
    """Run campaign tasks based on the strategic plan"""
    global background_tasks_running

    background_tasks_running[session_id] = True

    try:
        session = active_sessions.get(session_id, {})
        plan = session.get("plan", {})
        analysis = session.get("analysis", {})

        if not plan or not analysis:
            print(f"[Scheduler] No plan found for session {session_id}", flush=True)
            return

        # Get weeks from plan
        weeks = plan.get("weeks", [])

        for week in weeks:
            week_num = week.get("week", 1)
            posts = week.get("posts", [])

            await update_task_status(
                user_id, session_id,
                f"Week {week_num}",
                "in_progress",
                0,
                f"Processing {len(posts)} scheduled posts"
            )

            for i, scheduled_post in enumerate(posts):
                if not background_tasks_running.get(session_id, False):
                    print(f"[Scheduler] Task stopped for session {session_id}", flush=True)
                    return

                start_time = datetime.utcnow()

                # Update progress
                progress = int((i / len(posts)) * 100)
                await update_task_status(
                    user_id, session_id,
                    f"Week {week_num} - Post {i+1}",
                    "in_progress",
                    progress,
                    f"Generating: {scheduled_post.get('topic', 'content')}"
                )

                # Run the posting swarm for this scheduled post
                try:
                    posting_swarm = PostingSwarm(session_id, user_id)

                    # Generate and post content based on schedule
                    industry_intel = await posting_swarm.agent_search_industry(analysis)
                    previous_posts = await posting_swarm.agent_scan_previous_posts()
                    posts_content = await posting_swarm.agent_generate_posts(
                        plan, analysis, industry_intel, previous_posts, 1
                    )
                    posted = await posting_swarm.agent_post_content(posts_content)

                    duration = (datetime.utcnow() - start_time).total_seconds()

                    await log_completed_task(
                        user_id, session_id,
                        f"Week {week_num} - Post {i+1}",
                        {"posted": posted, "scheduled": scheduled_post},
                        duration
                    )

                    await update_task_status(
                        user_id, session_id,
                        f"Week {week_num} - Post {i+1}",
                        "completed",
                        100,
                        f"Posted successfully"
                    )

                except Exception as e:
                    await update_task_status(
                        user_id, session_id,
                        f"Week {week_num} - Post {i+1}",
                        "failed",
                        progress,
                        str(e)
                    )

                # Wait between posts (configurable delay)
                await asyncio.sleep(60)  # 1 minute between posts for demo

            await update_task_status(
                user_id, session_id,
                f"Week {week_num}",
                "completed",
                100,
                f"Completed all {len(posts)} posts"
            )

        # Run reply swarm periodically
        reply_swarm = ReplySwarm(session_id, user_id)
        await update_task_status(user_id, session_id, "Reply Engagement", "in_progress", 0, "Finding posts to engage with")

        replies = await reply_swarm.run(analysis)

        await update_task_status(
            user_id, session_id,
            "Reply Engagement",
            "completed",
            100,
            f"Posted {len(replies)} replies"
        )

    except Exception as e:
        print(f"[Scheduler] Error: {e}", flush=True)
        await update_task_status(user_id, session_id, "Campaign", "error", 0, str(e))
    finally:
        background_tasks_running[session_id] = False

async def campaign_scheduler():
    """Main scheduler that runs continuously and checks for approved campaigns"""
    print("[Scheduler] Background scheduler started", flush=True)

    while True:
        try:
            # Check for approved campaigns that need to run
            for session_id, session in active_sessions.items():
                if session.get("status") == "approved" and not background_tasks_running.get(session_id, False):
                    user_id = session.get("user_id")
                    if user_id:
                        print(f"[Scheduler] Starting campaign for session {session_id}", flush=True)
                        asyncio.create_task(run_scheduled_campaign(user_id, session_id))
                        session["status"] = "running"

            # Also load campaigns from database
            try:
                result = supabase.table("campaign_plans").select("*").eq("status", "approved").execute()
                for campaign in result.data:
                    session_id = campaign.get("session_id")
                    if session_id and session_id not in active_sessions:
                        # Restore session from database
                        active_sessions[session_id] = {
                            "user_id": campaign.get("user_id"),
                            "plan": campaign.get("plan"),
                            "analysis": {},
                            "status": "approved"
                        }
                        # Load analysis
                        research = supabase.table("campaign_research").select("*").eq("session_id", session_id).execute()
                        if research.data:
                            active_sessions[session_id]["analysis"] = research.data[0].get("analysis", {})
            except Exception as e:
                logger.debug(f"Failed to load campaigns from database: {e}")

        except Exception as e:
            logger.error(f"Scheduler error in main loop: {e}")

        await asyncio.sleep(30)  # Check every 30 seconds

# ============================================================
# VALIDATOR - Check X Credentials (Twikit)
# ============================================================

class XValidator:
    """Validates X credentials using tweepy"""

    @staticmethod
    async def validate_credentials(user_id: str, consumer_key: str, consumer_secret: str,
                                   access_token: str, access_token_secret: str) -> bool:
        """Validate and store X credentials using tweepy"""
        try:
            # Test credentials by making a simple API call
            client = tweepy.Client(
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                access_token=access_token,
                access_token_secret=access_token_secret,
                wait_on_rate_limit=True
            )

            # Verify credentials by getting authenticated user
            me = client.get_me()
            if not me or not me.data:
                print("[Validator] Could not verify credentials", flush=True)
                return False

            username = me.data.username
            print(f"[Validator] Verified credentials for @{username}", flush=True)

            # Store in Supabase
            supabase.table("x_credentials").upsert({
                "user_id": user_id,
                "consumer_key": consumer_key,
                "consumer_secret": consumer_secret,
                "access_token": access_token,
                "access_token_secret": access_token_secret,
                "username": username,
                "last_verified": datetime.utcnow().isoformat()
            }).execute()

            # Cache the client
            tweepy_clients[user_id] = client

            return True
        except Exception as e:
            print(f"[Validator] Error: {e}", flush=True)
            return False

    @staticmethod
    async def get_credentials(user_id: str) -> Optional[Dict]:
        """Get stored credentials"""
        result = supabase.table("x_credentials").select("*").eq("user_id", user_id).execute()
        return result.data[0] if result.data else None

# ============================================================
# SWARM 1: INTERVIEWER SWARM
# ============================================================

class InterviewerSwarm:
    """Interviews user and investigates X trends"""

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id

    async def agent_interview(self, campaign_info: Dict) -> Dict:
        """Agent 1: Process user's campaign goals"""
        log_stream(self.session_id, "Interviewer", "thinking", "Analyzing campaign goals...")

        prompt = f"""Analyze this marketing campaign brief and extract key information:

Campaign Info:
{json.dumps(campaign_info, indent=2)}

Return JSON with:
{{
    "target_audience": "description of target audience",
    "main_message": "core message to communicate",
    "tone": "tone of voice (professional/casual/etc)",
    "goals": ["list of specific goals"],
    "keywords": ["relevant keywords/hashtags"],
    "content_themes": ["themes to cover"]
}}"""

        log_stream(self.session_id, "Interviewer", "action", "Extracting campaign requirements...")
        result = await call_gemini(prompt)
        parsed = parse_json(result)

        log_stream(self.session_id, "Interviewer", "result", f"Identified {len(parsed.get('keywords', []))} keywords and {len(parsed.get('content_themes', []))} themes")
        return parsed

    async def agent_investigate_x(self, keywords: List[str]) -> List[Dict]:
        """Agent 2: Investigate X for popular posts"""
        log_stream(self.session_id, "XInvestigator", "thinking", "Searching X for trending content...")

        try:
            client = get_tweepy_client(self.user_id)

            all_tweets = []
            for keyword in keywords[:3]:  # Search top 3 keywords
                log_stream(self.session_id, "XInvestigator", "action", f"Searching for: {keyword}")

                # Tweepy v2 search_recent_tweets
                response = client.search_recent_tweets(
                    query=keyword,
                    max_results=10,
                    tweet_fields=["public_metrics", "created_at"],
                    user_fields=["username"],
                    expansions=["author_id"]
                )

                if response.data:
                    # Build user lookup
                    users = {u.id: u for u in (response.includes.get("users", []) or [])}

                    for tweet in response.data[:5]:
                        metrics = tweet.public_metrics or {}
                        user = users.get(tweet.author_id)
                        all_tweets.append({
                            "id": str(tweet.id),
                            "text": tweet.text,
                            "user": user.username if user else "unknown",
                            "likes": metrics.get("like_count", 0),
                            "retweets": metrics.get("retweet_count", 0),
                            "keyword": keyword
                        })

            # Sort by engagement
            all_tweets.sort(key=lambda x: x["likes"] + x["retweets"], reverse=True)
            top_tweets = all_tweets[:15]

            log_stream(self.session_id, "XInvestigator", "result", f"Found {len(top_tweets)} popular posts")
            return top_tweets

        except Exception as e:
            log_stream(self.session_id, "XInvestigator", "error", str(e))
            # Return mock data if API fails
            return await self._mock_investigate(keywords)

    async def _mock_investigate(self, keywords: List[str]) -> List[Dict]:
        """Mock investigation for testing"""
        prompt = f"""Generate 15 example popular tweets about these topics: {', '.join(keywords)}

Return JSON array:
[
    {{"text": "tweet content", "likes": 1000, "retweets": 200, "theme": "theme"}}
]"""
        result = await call_gemini(prompt)
        return parse_json(result) if isinstance(parse_json(result), list) else []

    async def run(self, campaign_info: Dict) -> Dict:
        """Run the full interviewer swarm"""
        print(f"\n{'='*60}\n  INTERVIEWER SWARM STARTING\n{'='*60}\n", flush=True)

        # Agent 1: Interview
        analysis = await self.agent_interview(campaign_info)

        # Agent 2: Investigate X
        keywords = analysis.get("keywords", ["marketing", "tech"])
        trending = await self.agent_investigate_x(keywords)

        result = {
            "analysis": analysis,
            "trending_posts": trending
        }

        # Save to Supabase
        supabase.table("campaign_research").insert({
            "user_id": self.user_id,
            "session_id": self.session_id,
            "analysis": analysis,
            "trending_posts": trending
        }).execute()

        print(f"\n{'='*60}\n  INTERVIEWER SWARM COMPLETE\n{'='*60}\n", flush=True)
        return result

# ============================================================
# SWARM 2: PLANNING SWARM
# ============================================================

class PlanningSwarm:
    """Creates 3-week content timeline"""

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id

    async def fetch_current_trends(self) -> List[Dict]:
        """Fetch current trending topics using EXA search"""
        log_stream(self.session_id, "TrendScanner", "thinking", "Searching EXA for trending topics...")

        try:
            trends = await get_trending_topics("trending topics news today")
            log_stream(self.session_id, "TrendScanner", "result", f"Found {len(trends)} trending topics via EXA")
            return trends
        except Exception as e:
            log_stream(self.session_id, "TrendScanner", "error", f"Failed to fetch trends: {e}")
            return []

    async def compile_and_plan(self, analysis: Dict, trending: List[Dict], strategic_plan: Dict = None) -> Dict:
        """Compile info and create 3-week timeline using trending data and strategic plan"""
        log_stream(self.session_id, "Planner", "thinking", "Compiling research and creating timeline...")

        # Extract strategic context if available
        strategic_context = ""
        if strategic_plan:
            market_research = strategic_plan.get("market_research", {})
            product_feedback = strategic_plan.get("product_feedback", {})
            strategy_table = strategic_plan.get("strategy_table", {})

            strategic_context = f"""
STRATEGIC PLAN CONTEXT:
- Market Position: {market_research.get('positioning_recommendation', 'N/A')}
- Key Opportunities: {', '.join(market_research.get('opportunities', [])[:3])}
- Product Strengths: {', '.join(product_feedback.get('strengths', [])[:3])}
- Success Metrics: {', '.join(product_feedback.get('success_metrics', [])[:5])}
- Strategy Overview: {strategy_table.get('strategy_overview', 'N/A')}
- Current Phase Focus: {strategy_table.get('phase_1_foundation', {}).get('theme', 'Foundation')}
"""
            log_stream(self.session_id, "Planner", "action", "Incorporating strategic plan insights...")

        # Fetch current trending topics from X
        current_trends = await self.fetch_current_trends()
        trends_summary = ""
        if current_trends:
            trends_summary = "\n".join([f"- {t.get('name', '')}" for t in current_trends[:20]])
            log_stream(self.session_id, "Planner", "action", f"Incorporating {len(current_trends)} trending topics into plan...")

        # Summarize trending posts from research using sumy
        trending_texts = " ".join([t.get('text', '') for t in trending[:10]])
        if trending_texts:
            # Use statistical summarization to extract key points
            key_trend_points = extract_key_points(trending_texts, num_points=5)
            trending_summary = "\n".join([f"- {point}" for point in key_trend_points])
            log_stream(self.session_id, "Planner", "action", f"Extracted {len(key_trend_points)} key points from trending content")
        else:
            trending_summary = "No trending content available"

        prompt = f"""Create a 3-week content marketing timeline based on this research:

Campaign Analysis:
{json.dumps(analysis, indent=2)}
{strategic_context}
CURRENT TRENDING TOPICS ON X (use these to make content timely and relevant):
{trends_summary if trends_summary else "No trending data available"}

Popular Content from Research:
{trending_summary}

IMPORTANT:
- Incorporate relevant trending topics into your content plan to maximize engagement and virality.
- Connect trending themes to the campaign goals where possible.
- Align content with the strategic plan's market positioning and success metrics.
- Focus messaging on identified product strengths and opportunities.

Create a detailed 3-week posting schedule with 5 posts per week (Mon-Fri).
Each post should align with the campaign goals and trending themes.

Return JSON:
{{
    "strategy_summary": "brief strategy overview",
    "weeks": [
        {{
            "week": 1,
            "theme": "week theme",
            "posts": [
                {{
                    "day": "Monday",
                    "time": "9:00 AM",
                    "type": "educational/promotional/engagement",
                    "topic": "post topic",
                    "hook": "attention-grabbing opening",
                    "hashtags": ["#tag1", "#tag2"]
                }}
            ]
        }}
    ],
    "engagement_strategy": "how to engage with replies"
}}"""

        log_stream(self.session_id, "Planner", "action", "Generating 3-week content calendar...")
        result = await call_gemini_planner(prompt)
        plan = parse_json(result)

        total_posts = sum(len(w.get("posts", [])) for w in plan.get("weeks", []))
        log_stream(self.session_id, "Planner", "result", f"Created timeline with {total_posts} posts across 3 weeks")

        return plan

    async def run(self, analysis: Dict, trending: List[Dict], strategic_plan: Dict = None) -> Dict:
        """Run the planning swarm with strategic context"""
        print(f"\n{'='*60}\n  PLANNING SWARM STARTING\n{'='*60}\n", flush=True)

        plan = await self.compile_and_plan(analysis, trending, strategic_plan)

        # Save to Supabase
        supabase.table("campaign_plans").insert({
            "user_id": self.user_id,
            "session_id": self.session_id,
            "plan": plan,
            "status": "pending_approval"
        }).execute()

        print(f"\n{'='*60}\n  PLANNING SWARM COMPLETE\n{'='*60}\n", flush=True)
        return plan

# ============================================================
# SWARM 3: REPLY SWARM
# ============================================================

class ReplySwarm:
    """Finds and replies to relevant posts"""

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id

    async def agent_find_posts(self, keywords: List[str]) -> List[Dict]:
        """Agent 1: Find technical/related posts to reply to"""
        log_stream(self.session_id, "PostFinder", "thinking", "Searching for posts to engage with...")

        try:
            client = get_tweepy_client(self.user_id)

            posts = []
            for keyword in keywords[:2]:
                log_stream(self.session_id, "PostFinder", "action", f"Finding posts about: {keyword}")

                # Tweepy v2 search_recent_tweets
                response = client.search_recent_tweets(
                    query=keyword,
                    max_results=20,
                    tweet_fields=["public_metrics", "created_at"],
                    user_fields=["username"],
                    expansions=["author_id"]
                )

                if response.data:
                    # Build user lookup
                    users = {u.id: u for u in (response.includes.get("users", []) or [])}

                    for tweet in response.data[:10]:
                        metrics = tweet.public_metrics or {}
                        likes = metrics.get("like_count", 0)
                        if likes > 10:  # Only engage with somewhat popular posts
                            user = users.get(tweet.author_id)
                            posts.append({
                                "id": str(tweet.id),
                                "text": tweet.text,
                                "user": user.username if user else "unknown",
                                "likes": likes
                            })

            # Take top 4
            posts.sort(key=lambda x: x["likes"], reverse=True)
            selected = posts[:4]

            log_stream(self.session_id, "PostFinder", "result", f"Selected {len(selected)} posts for engagement")
            return selected

        except Exception as e:
            log_stream(self.session_id, "PostFinder", "error", str(e))
            return []

    async def agent_reply(self, posts: List[Dict], analysis: Dict) -> List[Dict]:
        """Agent 2: Generate and post valuable replies"""
        log_stream(self.session_id, "Replier", "thinking", "Generating valuable replies...")

        client = get_tweepy_client(self.user_id)
        replies_made = []

        for post in posts:
            # Generate reply
            prompt = f"""Generate a valuable, insightful reply to this tweet that adds to the conversation.
Keep it under 280 characters. Be helpful, not promotional.

Tweet: {post['text']}

Campaign context: {analysis.get('main_message', '')}

Return just the reply text, nothing else."""

            reply_text = (await call_gemini(prompt)).strip().strip('"')

            log_stream(self.session_id, "Replier", "action", f"Replying to @{post['user']}: {reply_text[:50]}...")

            # Post reply using tweepy v2
            try:
                response = client.create_tweet(
                    text=f"@{post['user']} {reply_text}",
                    in_reply_to_tweet_id=post['id']
                )
                reply_id = str(response.data['id']) if response and response.data else f"mock_{uuid.uuid4().hex[:8]}"
            except Exception as e:
                log_stream(self.session_id, "Replier", "error", f"Failed to post: {e}")
                reply_id = f"error_{uuid.uuid4().hex[:8]}"

            replies_made.append({
                "original_post": post,
                "reply_text": reply_text,
                "reply_id": reply_id,
                "timestamp": datetime.utcnow().isoformat()
            })

        # Record in Supabase
        supabase.table("engagement_log").insert({
            "user_id": self.user_id,
            "session_id": self.session_id,
            "type": "replies",
            "data": replies_made
        }).execute()

        log_stream(self.session_id, "Replier", "result", f"Posted {len(replies_made)} valuable replies")
        return replies_made

    async def run(self, analysis: Dict) -> List[Dict]:
        """Run the reply swarm"""
        print(f"\n{'='*60}\n  REPLY SWARM STARTING\n{'='*60}\n", flush=True)

        keywords = analysis.get("keywords", ["tech"])

        # Agent 1: Find posts
        posts = await self.agent_find_posts(keywords)

        # Agent 2: Reply
        replies = []
        if posts:
            replies = await self.agent_reply(posts, analysis)

        print(f"\n{'='*60}\n  REPLY SWARM COMPLETE\n{'='*60}\n", flush=True)
        return replies

# ============================================================
# SWARM 4: POSTING SWARM
# ============================================================

class PostingSwarm:
    """Generates and posts industry-focused content with depth"""

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id

    async def agent_search_industry(self, analysis: Dict) -> str:
        """Agent 1: Search and gather industry intelligence using EXA Search"""
        log_stream(self.session_id, "IndustryResearcher", "thinking", "Gathering industry intelligence from search...")

        industry = analysis.get("target_audience", "tech")
        keywords = analysis.get("keywords", ["technology", "innovation"])

        # Use EXA Search for real internet search
        search_results = []
        for keyword in keywords[:3]:
            log_stream(self.session_id, "IndustryResearcher", "action", f"Searching for: {keyword} {industry}")
            query = f"{keyword} {industry} latest trends news 2024 2025"
            results = await call_exa_search(query, num_results=5)
            search_results.extend(results)

        # Format search results for analysis
        search_content = ""
        for i, result in enumerate(search_results[:15]):
            title = result.get("title", "")
            url = result.get("url", "")
            text = result.get("text", result.get("snippet", ""))[:500]
            search_content += f"\n{i+1}. {title}\n   URL: {url}\n   Content: {text}\n"

        log_stream(self.session_id, "IndustryResearcher", "action", f"Analyzing {len(search_results)} search results...")

        # Use sumy to extract key points from search content before sending to AI
        if search_content:
            key_points = extract_key_points(search_content, num_points=10)
            summarized_content = "\n".join([f"{i+1}. {point}" for i, point in enumerate(key_points)])
            log_stream(self.session_id, "IndustryResearcher", "action", f"Extracted {len(key_points)} key points using statistical analysis")
        else:
            summarized_content = search_content

        # Use Gemini to analyze the summarized search results
        prompt = f"""You are an industry research analyst. Analyze these key points extracted from search results about the {industry} industry and synthesize them into actionable intelligence.

KEY POINTS FROM SEARCH (extracted using statistical analysis):
{summarized_content}

Based on these results, provide:
- Latest trends and developments (with specific examples from search)
- Key challenges and pain points
- Emerging technologies and solutions
- Market dynamics and competitive landscape
- Expert opinions and thought leadership

Keywords context: {', '.join(keywords)}

Provide a comprehensive summary of the current industry landscape with specific data points, statistics, and insights that can be used to create authoritative content.

Return a detailed analysis (500-800 words) covering the above areas."""

        result = await call_gemini(prompt)

        log_stream(self.session_id, "IndustryResearcher", "result", f"Gathered industry intelligence ({len(result)} chars)")
        return result

    async def agent_scan_previous_posts(self) -> List[str]:
        """Agent 2: Scan previous AI-generated posts for context"""
        log_stream(self.session_id, "PostScanner", "thinking", "Scanning previous posts for context...")

        try:
            result = supabase.table("post_history").select("posts").order("created_at", desc=True).limit(5).execute()
            previous_posts = []
            for record in result.data:
                if record.get("posts"):
                    for post in record["posts"]:
                        content = post.get("content", "")
                        if content:
                            previous_posts.append(content)

            log_stream(self.session_id, "PostScanner", "result", f"Found {len(previous_posts)} previous posts")
            return previous_posts[:10]
        except Exception as e:
            log_stream(self.session_id, "PostScanner", "error", f"Failed to scan posts: {e}")
            return []

    async def agent_generate_posts(self, plan: Dict, analysis: Dict, industry_intel: str, previous_posts: List[str], count: int) -> List[str]:
        """Agent 3: Generate industry-focused posts with depth"""
        log_stream(self.session_id, "PostGenerator", "thinking", f"Generating {count} industry-depth posts...")

        strategy = plan.get("strategy_summary", "")
        themes = analysis.get("content_themes", [])
        goals = analysis.get("goals", [])

        previous_context = "\n".join([f"- {p[:100]}..." for p in previous_posts]) if previous_posts else "No previous posts available"

        # Summarize industry intel using sumy for more focused content generation
        if industry_intel and len(industry_intel) > 500:
            intel_key_points = extract_key_points(industry_intel, num_points=8)
            summarized_intel = "\n".join([f"- {point}" for point in intel_key_points])
            log_stream(self.session_id, "PostGenerator", "action", f"Condensed industry intel to {len(intel_key_points)} key points")
        else:
            summarized_intel = industry_intel

        prompt = f"""You are a world-class tech industry thought leader creating deeply insightful, nuanced content for techncial and intellectual people.

STRATEGIC CONTEXT:
- Campaign Strategy: {strategy}
- Core Themes: {', '.join(themes)}
- Campaign Goals: {', '.join(goals)}

KEY INDUSTRY INSIGHTS (statistically extracted):
{summarized_intel}

PREVIOUS CONTENT CONTEXT:
{previous_context}

ADVANCED POST GENERATION REQUIREMENTS:
1. Each post must demonstrate profound industry understanding
2. Structure posts in a compelling narrative arc:
   - Opening insight/provocation
   - Supporting evidence and analysis
   - Forward-looking perspective or actionable takeaway
3. Incorporate:
   - Specific data points and research findings
   - Expert perspectives and emerging trends
   - Nuanced, contrarian, or unexpected insights
4. Writing style:
   - Authoritative and confident
   - Intellectually rigorous
   - Clear, concise language
   - No hashtags, quotes, or exclamation marks
5. Target audience: Sophisticated technical and intellectual individuals seeking deep understanding

TECHNICAL POST GENERATION INSTRUCTIONS:
Generate {count} posts that each:
- Are 3-4 paragraphs long
- Provide substantial value beyond surface-level observations
- Offer unique perspectives informed by research and strategic goals
- Can stand alone as thought leadership content

FORMAT each post with clear paragraph breaks, focusing on depth, insight, and intellectual engagement.

CRITICAL DIRECTIVE: Each post must make the reader think more deeply about the industry, challenge existing assumptions, and provide actionable strategic insights."""

        log_stream(self.session_id, "PostGenerator", "action", f"Creating {count} industry-depth posts...")
        result = await call_gemini(prompt)

        # Parse the posts
        posts = [p.strip() for p in result.split("---") if p.strip()]

        log_stream(self.session_id, "PostGenerator", "result", f"Generated {len(posts)} industry posts")
        return posts[:count]

    async def agent_post_content(self, posts: List[str]) -> List[Dict]:
        """Agent 4: Post content to X using tweepy"""
        log_stream(self.session_id, "Poster", "thinking", "Posting industry content to X...")

        client = get_tweepy_client(self.user_id)
        posted = []

        for i, content in enumerate(posts):
            log_stream(self.session_id, "Poster", "action", f"Posting {i+1}/{len(posts)}: {content[:50]}...")

            try:
                # Create tweet using tweepy v2
                response = client.create_tweet(text=content)
                post_id = str(response.data['id']) if response and response.data else f"mock_{uuid.uuid4().hex[:8]}"
                status = "posted"
            except Exception as e:
                log_stream(self.session_id, "Poster", "error", f"Failed: {e}")
                post_id = f"error_{uuid.uuid4().hex[:8]}"
                status = "failed"

            posted.append({
                "content": content,
                "post_id": post_id,
                "status": status,
                "posted_at": datetime.utcnow().isoformat()
            })

            # Delay between posts
            if i < len(posts) - 1:
                await asyncio.sleep(2)

        # Record in Supabase
        try:
            supabase.table("post_history").insert({
                "user_id": self.user_id,
                "session_id": self.session_id,
                "posts": posted,
                "post_type": "industry_depth"
            }).execute()
        except Exception as e:
            log_stream(self.session_id, "Poster", "error", f"Failed to save to DB: {e}")

        successful = len([p for p in posted if p["status"] == "posted"])
        log_stream(self.session_id, "Poster", "result", f"Posted {successful}/{len(posted)} industry posts")
        return posted

    async def run(self, plan: Dict, analysis: Dict) -> List[Dict]:
        """Run the posting swarm"""
        print(f"\n{'='*60}\n  POSTING SWARM STARTING\n{'='*60}\n", flush=True)

        # Agent 1: Research industry intelligence
        industry_intel = await self.agent_search_industry(analysis)

        # Agent 2: Scan previous posts
        previous_posts = await self.agent_scan_previous_posts()

        # Agent 3: Generate 5 industry-depth posts
        posts = await self.agent_generate_posts(plan, analysis, industry_intel, previous_posts, 5)

        # Agent 4: Post to X
        posted = await self.agent_post_content(posts)

        print(f"\n{'='*60}\n  POSTING SWARM COMPLETE\n{'='*60}\n", flush=True)
        return posted

# ============================================================
# SWARM 5: STRATEGIC SWARM
# ============================================================

class StrategicSwarm:
    """Creates comprehensive 9-week strategy for marketing, operations, and product feedback"""

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id

    async def agent_market_research(self, campaign_info: Dict) -> Dict:
        """Agent 1: Research market and competitors"""
        log_stream(self.session_id, "MarketResearcher", "thinking", "Researching market landscape and competitors...")

        industry = campaign_info.get("target_audience", "technology")
        description = campaign_info.get("description", "")

        # Search for market intelligence
        log_stream(self.session_id, "MarketResearcher", "action", "Gathering market intelligence via EXA...")
        market_results = await call_exa_search(f"{industry} market trends competitors 2024 2025", num_results=5)

        market_intel = "\n".join([f"- {r.get('title', '')}: {r.get('text', '')[:200]}" for r in market_results])

        prompt = f"""Analyze this market research and provide strategic insights:

Product/Service: {description}
Target Market: {industry}

Market Intelligence:
{market_intel}

Return JSON with:
{{
    "market_size": "estimated market size and growth",
    "key_trends": ["top 5 market trends"],
    "competitors": ["main competitors and their strengths"],
    "opportunities": ["3-5 market opportunities"],
    "threats": ["potential market threats"],
    "positioning_recommendation": "how to position in the market"
}}"""

        result = await call_gemini(prompt)
        parsed = parse_json(result)

        log_stream(self.session_id, "MarketResearcher", "result", f"Identified {len(parsed.get('opportunities', []))} opportunities and {len(parsed.get('threats', []))} threats")
        return parsed

    async def agent_product_feedback(self, campaign_info: Dict, market_research: Dict) -> Dict:
        """Agent 2: Analyze product idea and provide feedback"""
        log_stream(self.session_id, "ProductAnalyst", "thinking", "Analyzing product idea and providing feedback...")

        prompt = f"""You are a startup advisor. Analyze this product idea and provide constructive feedback:

Product Description: {campaign_info.get('description', '')}
Target Users: {campaign_info.get('target_audience', '')}
Goals: {', '.join(campaign_info.get('goals', []))}

Market Context:
- Opportunities: {', '.join(market_research.get('opportunities', []))}
- Threats: {', '.join(market_research.get('threats', []))}
- Competitors: {', '.join(market_research.get('competitors', []))}

Provide comprehensive feedback in JSON:
{{
    "overall_score": "1-10 score",
    "strengths": ["product strengths"],
    "weaknesses": ["areas needing improvement"],
    "product_market_fit": "assessment of PMF potential",
    "differentiation": "what makes this unique",
    "risks": ["key risks to address"],
    "recommendations": ["actionable recommendations"],
    "pivot_considerations": ["potential pivots if needed"],
    "success_metrics": ["KPIs to track"]
}}"""

        log_stream(self.session_id, "ProductAnalyst", "action", "Evaluating product-market fit...")
        result = await call_gemini(prompt)
        parsed = parse_json(result)

        log_stream(self.session_id, "ProductAnalyst", "result", f"Product score: {parsed.get('overall_score', 'N/A')}/10 with {len(parsed.get('recommendations', []))} recommendations")
        return parsed

    async def agent_create_strategy_table(self, campaign_info: Dict, market_research: Dict, product_feedback: Dict) -> Dict:
        """Agent 3: Create comprehensive 9-week strategy table"""
        log_stream(self.session_id, "StrategyPlanner", "thinking", "Creating 9-week comprehensive strategy...")

        prompt = f"""Create a detailed 9-week strategic roadmap for this startup. The roadmap must cover three parallel tracks:
1. MARKETING - user acquisition, brand building, content
2. OPERATIONS - product development, team, processes
3. FEEDBACK - user research, metrics, iteration

Context:
- Product: {campaign_info.get('description', '')}
- Target: {campaign_info.get('target_audience', '')}
- Goals: {', '.join(campaign_info.get('goals', []))}
- Market Position: {market_research.get('positioning_recommendation', '')}
- Key Opportunities: {', '.join(market_research.get('opportunities', [])[:3])}
- Product Strengths: {', '.join(product_feedback.get('strengths', [])[:3])}
- Areas to Improve: {', '.join(product_feedback.get('weaknesses', [])[:3])}
- Success Metrics: {', '.join(product_feedback.get('success_metrics', [])[:5])}

Create a JSON strategy table with the following structure:
{{
    "strategy_overview": "executive summary of the 9-week plan",
    "phase_1_foundation": {{
        "weeks": "1-3",
        "theme": "Foundation & Validation",
        "marketing": [
            {{"week": 1, "task": "task description", "deliverable": "specific output", "metric": "how to measure"}},
            {{"week": 2, "task": "...", "deliverable": "...", "metric": "..."}},
            {{"week": 3, "task": "...", "deliverable": "...", "metric": "..."}}
        ],
        "operations": [
            {{"week": 1, "task": "...", "deliverable": "...", "metric": "..."}},
            {{"week": 2, "task": "...", "deliverable": "...", "metric": "..."}},
            {{"week": 3, "task": "...", "deliverable": "...", "metric": "..."}}
        ],
        "feedback": [
            {{"week": 1, "task": "...", "deliverable": "...", "metric": "..."}},
            {{"week": 2, "task": "...", "deliverable": "...", "metric": "..."}},
            {{"week": 3, "task": "...", "deliverable": "...", "metric": "..."}}
        ]
    }},
    "phase_2_growth": {{
        "weeks": "4-6",
        "theme": "Growth & Optimization",
        "marketing": [...],
        "operations": [...],
        "feedback": [...]
    }},
    "phase_3_scale": {{
        "weeks": "7-9",
        "theme": "Scale & Iterate",
        "marketing": [...],
        "operations": [...],
        "feedback": [...]
    }},
    "key_milestones": [
        {{"week": 3, "milestone": "milestone description"}},
        {{"week": 6, "milestone": "..."}},
        {{"week": 9, "milestone": "..."}}
    ],
    "budget_allocation": {{
        "marketing": "percentage and focus",
        "operations": "percentage and focus",
        "feedback": "percentage and focus"
    }},
    "risk_mitigation": [
        {{"risk": "risk description", "mitigation": "how to address"}}
    ]
}}

Make tasks specific, actionable, and measurable. Each week should build on the previous."""

        log_stream(self.session_id, "StrategyPlanner", "action", "Generating 9-week roadmap across all tracks...")
        result = await call_gemini_planner(prompt)
        parsed = parse_json(result)

        # Count total tasks
        total_tasks = 0
        for phase in ["phase_1_foundation", "phase_2_growth", "phase_3_scale"]:
            if phase in parsed:
                for track in ["marketing", "operations", "feedback"]:
                    if track in parsed[phase]:
                        total_tasks += len(parsed[phase][track])

        log_stream(self.session_id, "StrategyPlanner", "result", f"Created 9-week strategy with {total_tasks} tasks across 3 phases")
        return parsed

    async def run(self, campaign_info: Dict) -> Dict:
        """Run the full strategic swarm"""
        print(f"\n{'='*60}\n  STRATEGIC SWARM STARTING\n{'='*60}\n", flush=True)

        # Agent 1: Market Research
        market_research = await self.agent_market_research(campaign_info)

        # Agent 2: Product Feedback
        product_feedback = await self.agent_product_feedback(campaign_info, market_research)

        # Agent 3: Create Strategy Table
        strategy_table = await self.agent_create_strategy_table(campaign_info, market_research, product_feedback)

        result = {
            "market_research": market_research,
            "product_feedback": product_feedback,
            "strategy_table": strategy_table
        }

        # Save to Supabase
        try:
            supabase.table("strategic_plans").insert({
                "user_id": self.user_id,
                "session_id": self.session_id,
                "market_research": market_research,
                "product_feedback": product_feedback,
                "strategy_table": strategy_table,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            log_stream(self.session_id, "StrategicSwarm", "error", f"Failed to save to DB: {e}")

        print(f"\n{'='*60}\n  STRATEGIC SWARM COMPLETE\n{'='*60}\n", flush=True)
        return result

# ============================================================
# CAMPAIGN ORCHESTRATOR
# ============================================================

class CampaignOrchestrator:
    """Orchestrates all swarms"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.session_id = str(uuid.uuid4())
        active_sessions[self.session_id] = {
            "user_id": user_id,
            "status": "starting",
            "started_at": datetime.utcnow().isoformat()
        }

    async def get_or_create_strategic_plan(self, campaign_info: Dict) -> Dict:
        """Get existing strategic plan or create one for the user"""
        # Check for existing strategic plan
        result = supabase.table("strategic_plans").select("*").eq("user_id", self.user_id).order("created_at", desc=True).limit(1).execute()

        if result.data:
            log_stream(self.session_id, "Orchestrator", "action", "Found existing strategic plan")
            return result.data[0]

        # No strategic plan exists - create one
        log_stream(self.session_id, "Orchestrator", "thinking", "No strategic plan found, creating one...")

        strategic_swarm = StrategicSwarm(self.session_id, self.user_id)
        strategy_result = await strategic_swarm.run(campaign_info)

        return {
            "market_research": strategy_result.get("market_research", {}),
            "product_feedback": strategy_result.get("product_feedback", {}),
            "strategy_table": strategy_result.get("strategy_table", {})
        }

    async def run_initial_campaign(self, campaign_info: Dict) -> Dict:
        """Run interviewer and planning swarms with strategic context"""

        # First, get or create strategic plan
        active_sessions[self.session_id]["status"] = "strategic_planning"
        strategic_plan = await self.get_or_create_strategic_plan(campaign_info)
        active_sessions[self.session_id]["strategic_plan"] = strategic_plan

        active_sessions[self.session_id]["status"] = "interviewing"

        # Swarm 1: Interviewer
        interviewer = InterviewerSwarm(self.session_id, self.user_id)
        research = await interviewer.run(campaign_info)

        active_sessions[self.session_id]["status"] = "planning"

        # Swarm 2: Planning (now with strategic context)
        planner = PlanningSwarm(self.session_id, self.user_id)
        plan = await planner.run(research["analysis"], research["trending_posts"], strategic_plan)

        active_sessions[self.session_id]["status"] = "awaiting_approval"
        active_sessions[self.session_id]["plan"] = plan
        active_sessions[self.session_id]["analysis"] = research["analysis"]

        return {
            "session_id": self.session_id,
            "research": research,
            "plan": plan
        }

    async def run_daily_swarms(self) -> Dict:
        """Run reply and posting swarms (daily task)"""
        session = active_sessions.get(self.session_id, {})
        analysis = session.get("analysis", {})
        plan = session.get("plan", {})

        active_sessions[self.session_id]["status"] = "running_daily"

        # Run reply and posting swarms concurrently
        reply_swarm = ReplySwarm(self.session_id, self.user_id)
        posting_swarm = PostingSwarm(self.session_id, self.user_id)

        replies, posts = await asyncio.gather(
            reply_swarm.run(analysis),
            posting_swarm.run(plan, analysis)
        )

        active_sessions[self.session_id]["status"] = "daily_complete"

        return {
            "replies": replies,
            "posts": posts
        }

# ============================================================
# PYDANTIC MODELS
# ============================================================

class UserSignup(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)

    @validator('email')
    def validate_email(cls, v):
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError('Invalid email format')
        return v.lower().strip()

    @validator('username')
    def validate_username(cls, v):
        return v.strip()

class UserLogin(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

    @validator('email')
    def validate_email(cls, v):
        return v.lower().strip()

class XCredentials(BaseModel):
    consumer_key: str = Field(..., min_length=10, max_length=100)
    consumer_secret: str = Field(..., min_length=10, max_length=100)
    access_token: str = Field(..., min_length=10, max_length=100)
    access_token_secret: str = Field(..., min_length=10, max_length=100)

class CampaignInfo(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    target_audience: str = Field(..., min_length=1, max_length=500)
    goals: List[str] = Field(..., min_items=1, max_items=20)
    duration_weeks: int = Field(default=3, ge=1, le=52)

    @validator('name', 'description', 'target_audience')
    def strip_strings(cls, v):
        return v.strip()

    @validator('goals')
    def validate_goals(cls, v):
        return [goal.strip() for goal in v if goal.strip()]

class PlanFeedback(BaseModel):
    approved: bool
    feedback: Optional[str] = Field(None, max_length=2000)

# Password hashing functions
def hash_password(password: str) -> str:
    """Hash password with salt using PBKDF2"""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{hash_obj.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash"""
    try:
        salt, hash_value = stored_hash.split(':')
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hash_obj.hex() == hash_value
    except (ValueError, AttributeError):
        return False

def generate_token() -> str:
    """Generate a secure session token"""
    return secrets.token_urlsafe(32)

# ============================================================
# FASTAPI APP
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global scheduler_task
    # Start the background scheduler
    scheduler_task = asyncio.create_task(campaign_scheduler())
    print("[Server] Background scheduler initialized", flush=True)
    yield
    # Cleanup on shutdown
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
    print("[Server] Scheduler stopped", flush=True)

app = FastAPI(
    title="Nexus Marketing Campaign API",
    description="Production-ready marketing campaign automation API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration - restrict in production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=3600,
)

# Security middleware
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Add security headers and rate limiting"""
    start_time = time.time()

    # Get client identifier for rate limiting
    client_ip = request.client.host if request.client else "unknown"
    client_id = request.headers.get("Authorization", client_ip)

    # Check rate limit
    if not rate_limiter.is_allowed(client_id):
        retry_after = rate_limiter.get_retry_after(client_id)
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests"},
            headers={"Retry-After": str(retry_after)}
        )

    # Process request
    response = await call_next(request)

    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Log request
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")

    return response

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# ============================================================
# HEALTH CHECK ENDPOINTS
# ============================================================

@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with dependency status"""
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "dependencies": {}
    }

    # Check Supabase connection
    try:
        result = supabase.table("users").select("id").limit(1).execute()
        health["dependencies"]["database"] = "healthy"
    except Exception as e:
        health["dependencies"]["database"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"

    # Check API keys availability
    gemini_available = sum(1 for k in GEMINI_PLANNER_KEYS + GEMINI_OTHER_KEYS if k)
    exa_available = sum(1 for k in EXA_API_KEYS if k)

    health["dependencies"]["gemini_keys"] = f"{gemini_available} available"
    health["dependencies"]["exa_keys"] = f"{exa_available} available"

    if gemini_available == 0:
        health["status"] = "degraded"
    if exa_available == 0:
        health["status"] = "degraded"

    # Active sessions count
    health["metrics"] = {
        "active_sessions": len(active_sessions),
        "background_tasks": sum(1 for v in background_tasks_running.values() if v)
    }

    return health

def get_user_id(authorization: str = Header(None)):
    """Validate session token and return user_id"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Extract token from "Bearer <token>" format
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]

    # Validate token against sessions table
    try:
        result = supabase.table("sessions").select("user_id, expires_at").eq("token", token).execute()

        if not result.data:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        session = result.data[0]

        # Check if token is expired
        expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
        if expires_at.replace(tzinfo=None) < datetime.utcnow():
            # Delete expired session
            supabase.table("sessions").delete().eq("token", token).execute()
            raise HTTPException(status_code=401, detail="Token expired. Please login again.")

        return session["user_id"]

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] Token validation error: {e}", flush=True)
        raise HTTPException(status_code=401, detail="Authentication failed")

def validate_session_ownership(session_id: str, user_id: str) -> bool:
    """Validate that a session belongs to the user"""
    # Check active sessions
    if session_id in active_sessions:
        return active_sessions[session_id].get("user_id") == user_id

    # Check database for campaign sessions
    result = supabase.table("campaign_sessions").select("user_id").eq("session_id", session_id).execute()
    if result.data:
        return result.data[0].get("user_id") == user_id

    # Check strategic plans
    result = supabase.table("strategic_plans").select("user_id").eq("session_id", session_id).execute()
    if result.data:
        return result.data[0].get("user_id") == user_id

    return False

def require_session_ownership(session_id: str, user_id: str):
    """Raise 403 if user doesn't own the session"""
    if not validate_session_ownership(session_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied. This session belongs to another user.")

# ============================================================
# API ROUTES
# ============================================================

@app.post("/auth/signup")
async def signup(user: UserSignup):
    """Create a new user account"""
    try:
        # Check if email already exists
        existing = supabase.table("users").select("id").eq("email", user.email).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Check if username already exists
        existing_username = supabase.table("users").select("id").eq("username", user.username).execute()
        if existing_username.data:
            raise HTTPException(status_code=400, detail="Username already taken")

        # Hash password and create user
        password_hash = hash_password(user.password)
        user_id = str(uuid.uuid4())

        supabase.table("users").insert({
            "id": user_id,
            "username": user.username,
            "email": user.email,
            "password_hash": password_hash,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        # Create session token
        token = generate_token()
        expires_at = datetime.utcnow() + timedelta(days=7)

        supabase.table("sessions").insert({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "token": token,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        print(f"[Auth] New user created: {user.username} ({user.email})", flush=True)

        return {
            "message": "Account created successfully",
            "user_id": user_id,
            "username": user.username,
            "token": token,
            "expires_at": expires_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] Signup error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Failed to create account")

@app.post("/auth/login")
async def login(user: UserLogin):
    """Login with email and password"""
    try:
        # Find user by email
        result = supabase.table("users").select("*").eq("email", user.email).execute()
        if not result.data:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user_data = result.data[0]

        # Check if account is active
        if not user_data.get("is_active", True):
            raise HTTPException(status_code=401, detail="Account is disabled")

        # Verify password
        if not verify_password(user.password, user_data.get("password_hash", "")):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Create new session token
        token = generate_token()
        expires_at = datetime.utcnow() + timedelta(days=7)

        supabase.table("sessions").insert({
            "id": str(uuid.uuid4()),
            "user_id": user_data["id"],
            "token": token,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        # Update last login
        supabase.table("users").update({
            "last_login": datetime.utcnow().isoformat()
        }).eq("id", user_data["id"]).execute()

        print(f"[Auth] User logged in: {user_data.get('username')} ({user.email})", flush=True)

        return {
            "message": "Login successful",
            "user_id": user_data["id"],
            "username": user_data.get("username"),
            "token": token,
            "expires_at": expires_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] Login error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Login failed")

@app.post("/auth/logout")
async def logout(user_id: str = Depends(get_user_id)):
    """Logout and invalidate current session"""
    try:
        # Delete all sessions for this user (or just the current one)
        # For now, delete all sessions to force re-login
        supabase.table("sessions").delete().eq("user_id", user_id).execute()

        # Clear tweepy client cache
        if user_id in tweepy_clients:
            del tweepy_clients[user_id]

        print(f"[Auth] User logged out: {user_id}", flush=True)

        return {"message": "Logged out successfully"}

    except Exception as e:
        print(f"[Auth] Logout error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Logout failed")

@app.get("/auth/me")
async def get_current_user(user_id: str = Depends(get_user_id)):
    """Get current user info"""
    try:
        result = supabase.table("users").select("id, username, email, created_at, last_login").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] Get user error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Failed to get user info")

@app.post("/auth/validate-x")
async def validate_x_credentials(creds: XCredentials, user_id: str = Depends(get_user_id)):
    """Validate and store X credentials using tweepy"""
    valid = await XValidator.validate_credentials(
        user_id=user_id,
        consumer_key=creds.consumer_key,
        consumer_secret=creds.consumer_secret,
        access_token=creds.access_token,
        access_token_secret=creds.access_token_secret
    )
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid X credentials")
    return {"message": "X credentials validated and stored"}

@app.get("/auth/x-status")
async def get_x_status(user_id: str = Depends(get_user_id)):
    """Check if user has valid X credentials"""
    creds = await XValidator.get_credentials(user_id)
    return {
        "connected": creds is not None,
        "username": creds.get("username") if creds else None,
        "email": creds.get("email") if creds else None
    }

@app.get("/trending")
async def get_trending(query: str = "trending topics today", user_id: str = Depends(get_user_id)):
    """Get current trending topics from both X (Twitter) and Internet (EXA search)"""

    # Fetch both sources in parallel
    x_trends, internet_trends = await asyncio.gather(
        get_x_trending(user_id, query),
        get_trending_topics(query),
        return_exceptions=True
    )

    # Handle exceptions
    if isinstance(x_trends, Exception):
        print(f"[Trending] X trends error: {x_trends}", flush=True)
        x_trends = []
    if isinstance(internet_trends, Exception):
        print(f"[Trending] Internet trends error: {internet_trends}", flush=True)
        internet_trends = []

    return {
        "message": "Trending topics fetched from X and Internet",
        "x_trends": {
            "source": "X (Twitter)",
            "description": "Popular and viral posts from X",
            "trends": x_trends,
            "count": len(x_trends)
        },
        "internet_trends": {
            "source": "Internet (EXA Search)",
            "description": "Trending topics from across the web",
            "trends": internet_trends,
            "count": len(internet_trends)
        },
        "total_count": len(x_trends) + len(internet_trends),
        "fetched_at": datetime.utcnow().isoformat()
    }

@app.post("/strategy/create")
async def create_strategy(
    info: CampaignInfo,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id)
):
    """Create a comprehensive 9-week strategy - runs strategic swarm"""
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        "user_id": user_id,
        "status": "creating_strategy",
        "started_at": datetime.utcnow().isoformat()
    }

    async def run_strategic_swarm():
        strategic_swarm = StrategicSwarm(session_id, user_id)
        result = await strategic_swarm.run(info.dict())
        active_sessions[session_id]["status"] = "strategy_complete"
        active_sessions[session_id]["strategy"] = result

    background_tasks.add_task(run_strategic_swarm)

    return {
        "message": "Strategic planning started",
        "session_id": session_id
    }

@app.get("/strategy/{session_id}")
async def get_strategy(session_id: str, user_id: str = Depends(get_user_id)):
    """Get the generated strategic plan"""
    # Validate ownership
    require_session_ownership(session_id, user_id)

    # Try active sessions first
    if session_id in active_sessions:
        session = active_sessions[session_id]
        return {
            "session_id": session_id,
            "status": session.get("status"),
            "strategy": session.get("strategy", {})
        }

    # Try database - filter by user_id for extra security
    result = supabase.table("strategic_plans").select("*").eq("session_id", session_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Strategy not found")

    plan = result.data[0]
    return {
        "session_id": session_id,
        "status": "strategy_complete",
        "market_research": plan.get("market_research", {}),
        "product_feedback": plan.get("product_feedback", {}),
        "strategy_table": plan.get("strategy_table", {}),
        "created_at": plan.get("created_at")
    }

@app.get("/strategy/{session_id}/table")
async def get_strategy_table(session_id: str, user_id: str = Depends(get_user_id)):
    """Get just the 9-week strategy table in a formatted view"""
    # Validate ownership
    require_session_ownership(session_id, user_id)

    # Try active sessions first
    strategy = None
    if session_id in active_sessions:
        strategy = active_sessions[session_id].get("strategy", {}).get("strategy_table", {})
    else:
        result = supabase.table("strategic_plans").select("strategy_table").eq("session_id", session_id).eq("user_id", user_id).execute()
        if result.data:
            strategy = result.data[0].get("strategy_table", {})

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy table not found")

    return {
        "session_id": session_id,
        "overview": strategy.get("strategy_overview", ""),
        "phases": {
            "foundation": strategy.get("phase_1_foundation", {}),
            "growth": strategy.get("phase_2_growth", {}),
            "scale": strategy.get("phase_3_scale", {})
        },
        "milestones": strategy.get("key_milestones", []),
        "budget": strategy.get("budget_allocation", {}),
        "risks": strategy.get("risk_mitigation", [])
    }

@app.post("/campaign/create")
async def create_campaign(
    info: CampaignInfo,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id)
):
    """Create a new marketing campaign - runs interviewer and planning swarms"""
    creds = await XValidator.get_credentials(user_id)
    if not creds:
        raise HTTPException(status_code=400, detail="X credentials not found. Please validate first.")

    orchestrator = CampaignOrchestrator(user_id)

    # Run in background
    background_tasks.add_task(
        orchestrator.run_initial_campaign,
        info.dict()
    )

    return {
        "message": "Campaign creation started",
        "session_id": orchestrator.session_id
    }

@app.post("/campaign/{session_id}/approve")
async def approve_plan(
    session_id: str,
    feedback: PlanFeedback,
    user_id: str = Depends(get_user_id)
):
    """Approve or request changes to the plan"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate ownership
    require_session_ownership(session_id, user_id)

    session = active_sessions[session_id]

    if feedback.approved:
        session["status"] = "approved"

        # Update in Supabase
        supabase.table("campaign_plans").update({
            "status": "approved"
        }).eq("session_id", session_id).execute()

        return {"message": "Plan approved! Daily swarms will now run."}
    else:
        session["status"] = "revision_needed"
        return {"message": "Feedback received. Please create a new campaign with adjustments."}

@app.post("/campaign/{session_id}/run-daily")
async def run_daily_tasks(
    session_id: str,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_user_id)
):
    """Manually trigger daily reply and posting swarms"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate ownership
    require_session_ownership(session_id, user_id)

    creds = await XValidator.get_credentials(user_id)
    if not creds:
        raise HTTPException(status_code=400, detail="X credentials not found")

    orchestrator = CampaignOrchestrator(user_id)
    orchestrator.session_id = session_id

    background_tasks.add_task(orchestrator.run_daily_swarms)

    return {"message": "Daily swarms started"}

@app.get("/campaign/{session_id}/status")
async def get_campaign_status(session_id: str, user_id: str = Depends(get_user_id)):
    """Get campaign status"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate ownership
    require_session_ownership(session_id, user_id)

    session = active_sessions[session_id]
    return {
        "session_id": session_id,
        "status": session.get("status"),
        "started_at": session.get("started_at")
    }

@app.get("/campaign/{session_id}/plan")
async def get_campaign_plan(session_id: str, user_id: str = Depends(get_user_id)):
    """Get the generated plan"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate ownership
    require_session_ownership(session_id, user_id)

    return active_sessions[session_id].get("plan", {})

@app.get("/campaign/{session_id}/stream")
async def get_stream(session_id: str, user_id: str = Depends(get_user_id)):
    """Get streaming logs for a session"""
    # Validate ownership
    require_session_ownership(session_id, user_id)

    logs = stream_logs.get(session_id, [])
    status = active_sessions.get(session_id, {}).get("status", "unknown")

    return {
        "session_id": session_id,
        "status": status,
        "logs": logs,
        "count": len(logs)
    }

@app.get("/campaigns")
async def list_campaigns(user_id: str = Depends(get_user_id)):
    """List all campaigns for user"""
    user_sessions = [
        {"session_id": sid, **data}
        for sid, data in active_sessions.items()
        if data.get("user_id") == user_id
    ]
    return {"campaigns": user_sessions}

# ============================================================
# MONITORING ENDPOINTS
# ============================================================

@app.get("/monitor/{session_id}")
async def monitor_campaign(session_id: str, user_id: str = Depends(get_user_id)):
    """Get full monitoring view of campaign progress"""
    # Validate ownership
    require_session_ownership(session_id, user_id)

    # Get task progress
    progress_result = supabase.table("task_progress").select("*").eq("session_id", session_id).order("updated_at", desc=True).execute()

    # Get completed tasks
    completed_result = supabase.table("completed_tasks").select("*").eq("session_id", session_id).order("completed_at", desc=True).execute()

    # Get stream logs
    logs = stream_logs.get(session_id, [])

    # Get session status
    session = active_sessions.get(session_id, {})

    return {
        "session_id": session_id,
        "status": session.get("status", "unknown"),
        "is_running": background_tasks_running.get(session_id, False),
        "task_progress": progress_result.data,
        "completed_tasks": completed_result.data,
        "recent_logs": logs[-50:] if logs else [],
        "total_logs": len(logs)
    }

@app.get("/monitor/{session_id}/progress")
async def get_task_progress(session_id: str, user_id: str = Depends(get_user_id)):
    """Get current task progress for a campaign"""
    result = supabase.table("task_progress").select("*").eq("session_id", session_id).order("updated_at", desc=True).execute()

    # Group by status
    in_progress = [t for t in result.data if t.get("status") == "in_progress"]
    completed = [t for t in result.data if t.get("status") == "completed"]
    failed = [t for t in result.data if t.get("status") == "failed"]

    return {
        "session_id": session_id,
        "in_progress": in_progress,
        "completed": completed,
        "failed": failed,
        "total_tasks": len(result.data),
        "completion_rate": len(completed) / len(result.data) * 100 if result.data else 0
    }

@app.get("/monitor/{session_id}/completed")
async def get_completed_tasks(session_id: str, user_id: str = Depends(get_user_id)):
    """Get all completed tasks with results"""
    result = supabase.table("completed_tasks").select("*").eq("session_id", session_id).order("completed_at", desc=True).execute()

    total_duration = sum(t.get("duration_seconds", 0) for t in result.data)

    return {
        "session_id": session_id,
        "tasks": result.data,
        "total_completed": len(result.data),
        "total_duration_seconds": total_duration
    }

@app.get("/monitor/{session_id}/live")
async def get_live_activity(session_id: str, user_id: str = Depends(get_user_id)):
    """Get live streaming activity"""
    logs = stream_logs.get(session_id, [])
    session = active_sessions.get(session_id, {})

    # Get only recent logs (last 100)
    recent = logs[-100:] if logs else []

    return {
        "session_id": session_id,
        "status": session.get("status", "unknown"),
        "is_running": background_tasks_running.get(session_id, False),
        "logs": recent,
        "total_entries": len(logs)
    }

@app.post("/monitor/{session_id}/stop")
async def stop_campaign(session_id: str, user_id: str = Depends(get_user_id)):
    """Stop a running campaign"""
    # Validate ownership
    require_session_ownership(session_id, user_id)

    if session_id in background_tasks_running:
        background_tasks_running[session_id] = False
        if session_id in active_sessions:
            active_sessions[session_id]["status"] = "stopped"
        return {"message": "Campaign stop signal sent", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Campaign not found or not running")

@app.post("/monitor/{session_id}/resume")
async def resume_campaign(session_id: str, user_id: str = Depends(get_user_id)):
    """Resume a stopped campaign"""
    # Validate ownership
    require_session_ownership(session_id, user_id)

    if session_id in active_sessions:
        session = active_sessions[session_id]
        if session.get("status") in ["stopped", "approved"]:
            session["status"] = "approved"  # Will be picked up by scheduler
            return {"message": "Campaign will resume shortly", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Campaign not found")

@app.get("/monitor/{session_id}/strategic-map")
async def get_strategic_map(session_id: str, user_id: str = Depends(get_user_id)):
    """Get the full strategic plan with current progress overlay"""
    # Validate ownership
    require_session_ownership(session_id, user_id)

    # Get session data
    session = active_sessions.get(session_id)

    # If not in memory, try to load from database
    if not session:
        plan_result = supabase.table("campaign_plans").select("*").eq("session_id", session_id).execute()
        research_result = supabase.table("campaign_research").select("*").eq("session_id", session_id).execute()

        if not plan_result.data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        plan = plan_result.data[0].get("plan", {})
        analysis = research_result.data[0].get("analysis", {}) if research_result.data else {}
        status = plan_result.data[0].get("status", "unknown")
    else:
        plan = session.get("plan", {})
        analysis = session.get("analysis", {})
        status = session.get("status", "unknown")

    # Get task progress from database
    progress_result = supabase.table("task_progress").select("*").eq("session_id", session_id).execute()
    completed_result = supabase.table("completed_tasks").select("*").eq("session_id", session_id).execute()

    # Create progress lookup
    task_status = {}
    for task in progress_result.data:
        task_status[task.get("task_name")] = {
            "status": task.get("status"),
            "progress": task.get("progress"),
            "details": task.get("details"),
            "updated_at": task.get("updated_at")
        }

    # Build strategic map with progress
    weeks = plan.get("weeks", [])
    strategic_map = []

    total_posts = 0
    completed_posts = 0
    in_progress_posts = 0

    for week in weeks:
        week_num = week.get("week", 1)
        posts = week.get("posts", [])
        theme = week.get("theme", "")

        week_data = {
            "week": week_num,
            "theme": theme,
            "total_posts": len(posts),
            "status": task_status.get(f"Week {week_num}", {}).get("status", "pending"),
            "posts": []
        }

        for i, post in enumerate(posts):
            post_key = f"Week {week_num} - Post {i+1}"
            post_status = task_status.get(post_key, {})

            post_data = {
                "index": i + 1,
                "day": post.get("day", ""),
                "time": post.get("time", ""),
                "type": post.get("type", ""),
                "topic": post.get("topic", ""),
                "hook": post.get("hook", ""),
                "hashtags": post.get("hashtags", []),
                "status": post_status.get("status", "pending"),
                "progress": post_status.get("progress", 0),
                "details": post_status.get("details", ""),
                "updated_at": post_status.get("updated_at")
            }

            total_posts += 1
            if post_data["status"] == "completed":
                completed_posts += 1
            elif post_data["status"] == "in_progress":
                in_progress_posts += 1

            week_data["posts"].append(post_data)

        # Calculate week completion
        week_completed = len([p for p in week_data["posts"] if p["status"] == "completed"])
        week_data["completion_percentage"] = (week_completed / len(posts) * 100) if posts else 0

        strategic_map.append(week_data)

    # Get current position
    current_week = None
    current_post = None
    for week_data in strategic_map:
        for post in week_data["posts"]:
            if post["status"] == "in_progress":
                current_week = week_data["week"]
                current_post = post["index"]
                break
        if current_week:
            break

    # If nothing in progress, find next pending
    if not current_week:
        for week_data in strategic_map:
            for post in week_data["posts"]:
                if post["status"] == "pending":
                    current_week = week_data["week"]
                    current_post = post["index"]
                    break
            if current_week:
                break

    return {
        "session_id": session_id,
        "campaign_status": status,
        "is_running": background_tasks_running.get(session_id, False),

        # Campaign info
        "strategy_summary": plan.get("strategy_summary", ""),
        "engagement_strategy": plan.get("engagement_strategy", ""),
        "target_audience": analysis.get("target_audience", ""),
        "main_message": analysis.get("main_message", ""),
        "tone": analysis.get("tone", ""),
        "keywords": analysis.get("keywords", []),
        "content_themes": analysis.get("content_themes", []),

        # Progress overview
        "progress": {
            "total_posts": total_posts,
            "completed": completed_posts,
            "in_progress": in_progress_posts,
            "pending": total_posts - completed_posts - in_progress_posts,
            "completion_percentage": (completed_posts / total_posts * 100) if total_posts else 0
        },

        # Current position
        "current_position": {
            "week": current_week,
            "post": current_post,
            "description": f"Week {current_week}, Post {current_post}" if current_week else "Not started"
        },

        # Full strategic map with progress
        "strategic_map": strategic_map,

        # Completed tasks log
        "completed_tasks_count": len(completed_result.data)
    }

@app.get("/monitor/{session_id}/timeline-view")
async def get_timeline_view(session_id: str, user_id: str = Depends(get_user_id)):
    """Get a simplified timeline view for quick progress check"""
    # Get strategic map data
    map_data = await get_strategic_map(session_id, user_id)

    # Create simplified timeline
    timeline = []

    for week in map_data["strategic_map"]:
        week_entry = {
            "week": week["week"],
            "theme": week["theme"],
            "status": week["status"],
            "completion": f"{week['completion_percentage']:.0f}%",
            "posts_summary": []
        }

        for post in week["posts"]:
            status_icon = "✓" if post["status"] == "completed" else "◐" if post["status"] == "in_progress" else "○"
            week_entry["posts_summary"].append({
                "index": post["index"],
                "status": status_icon,
                "topic": post["topic"][:50] + "..." if len(post.get("topic", "")) > 50 else post.get("topic", "")
            })

        timeline.append(week_entry)

    return {
        "session_id": session_id,
        "campaign_status": map_data["campaign_status"],
        "overall_progress": f"{map_data['progress']['completion_percentage']:.0f}%",
        "current_position": map_data["current_position"]["description"],
        "timeline": timeline
    }

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    # Server configuration from environment
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    WORKERS = int(os.getenv("WORKERS", "1"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    logger.info("=" * 60)
    logger.info("  NEXUS MARKETING CAMPAIGN SERVER")
    logger.info("=" * 60)
    logger.info(f"  Host: {HOST}")
    logger.info(f"  Port: {PORT}")
    logger.info(f"  Debug: {DEBUG}")
    logger.info("=" * 60)

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info" if not DEBUG else "debug",
        access_log=True
    )
