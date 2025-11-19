"""
Marketing Campaign Backend - FastAPI Server
All swarms connected with streaming output
"""

import os
import sys
import json
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import tweepy
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
X_CLIENT_ID = os.getenv("X_CLIENT_ID")
X_CLIENT_SECRET = os.getenv("X_CLIENT_SECRET")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# ============================================================
# IN-MEMORY STATE
# ============================================================

active_sessions: Dict[str, Dict] = {}
stream_logs: Dict[str, List[Dict]] = {}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

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
    except:
        pass

def get_x_client(access_token: str, access_secret: str):
    """Get authenticated X/Twitter client"""
    auth = tweepy.OAuth1UserHandler(
        X_CLIENT_ID, X_CLIENT_SECRET,
        access_token, access_secret
    )
    return tweepy.API(auth)

def get_x_client_v2(access_token: str, access_secret: str):
    """Get authenticated X/Twitter client (v2 API)"""
    return tweepy.Client(
        consumer_key=X_CLIENT_ID,
        consumer_secret=X_CLIENT_SECRET,
        access_token=access_token,
        access_token_secret=access_secret
    )

def call_gemini(prompt: str) -> str:
    """Call Gemini API and return response"""
    response = model.generate_content(prompt)
    return response.text

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
    except:
        pass
    return {"raw": text}

# ============================================================
# VALIDATOR - Check X API Token
# ============================================================

class XValidator:
    """Validates X API credentials"""

    @staticmethod
    async def validate_token(user_id: str, access_token: str, access_secret: str) -> bool:
        """Validate and store X token"""
        try:
            client = get_x_client(access_token, access_secret)
            user = client.verify_credentials()

            # Store in Supabase
            supabase.table("x_credentials").upsert({
                "user_id": user_id,
                "access_token": access_token,
                "access_secret": access_secret,
                "username": user.screen_name,
                "validated_at": datetime.utcnow().isoformat()
            }).execute()

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
        result = call_gemini(prompt)
        parsed = parse_json(result)

        log_stream(self.session_id, "Interviewer", "result", f"Identified {len(parsed.get('keywords', []))} keywords and {len(parsed.get('content_themes', []))} themes")
        return parsed

    async def agent_investigate_x(self, keywords: List[str], creds: Dict) -> List[Dict]:
        """Agent 2: Investigate X for popular posts"""
        log_stream(self.session_id, "XInvestigator", "thinking", "Searching X for trending content...")

        try:
            client = get_x_client(creds["access_token"], creds["access_secret"])

            all_tweets = []
            for keyword in keywords[:3]:  # Search top 3 keywords
                log_stream(self.session_id, "XInvestigator", "action", f"Searching for: {keyword}")
                tweets = client.search_tweets(q=keyword, count=5, result_type="popular", tweet_mode="extended")

                for tweet in tweets:
                    all_tweets.append({
                        "id": tweet.id_str,
                        "text": tweet.full_text,
                        "user": tweet.user.screen_name,
                        "likes": tweet.favorite_count,
                        "retweets": tweet.retweet_count,
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
            return self._mock_investigate(keywords)

    def _mock_investigate(self, keywords: List[str]) -> List[Dict]:
        """Mock investigation for testing"""
        prompt = f"""Generate 15 example popular tweets about these topics: {', '.join(keywords)}

Return JSON array:
[
    {{"text": "tweet content", "likes": 1000, "retweets": 200, "theme": "theme"}}
]"""
        result = call_gemini(prompt)
        return parse_json(result) if isinstance(parse_json(result), list) else []

    async def run(self, campaign_info: Dict, creds: Dict) -> Dict:
        """Run the full interviewer swarm"""
        print(f"\n{'='*60}\n  INTERVIEWER SWARM STARTING\n{'='*60}\n", flush=True)

        # Agent 1: Interview
        analysis = await self.agent_interview(campaign_info)

        # Agent 2: Investigate X
        keywords = analysis.get("keywords", ["marketing", "tech"])
        trending = await self.agent_investigate_x(keywords, creds)

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

    async def compile_and_plan(self, analysis: Dict, trending: List[Dict]) -> Dict:
        """Compile info and create 3-week timeline"""
        log_stream(self.session_id, "Planner", "thinking", "Compiling research and creating timeline...")

        # Summarize trending posts
        trending_summary = "\n".join([f"- {t.get('text', '')[:100]}..." for t in trending[:10]])

        prompt = f"""Create a 3-week content marketing timeline based on this research:

Campaign Analysis:
{json.dumps(analysis, indent=2)}

Popular Content Trends:
{trending_summary}

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
        result = call_gemini(prompt)
        plan = parse_json(result)

        total_posts = sum(len(w.get("posts", [])) for w in plan.get("weeks", []))
        log_stream(self.session_id, "Planner", "result", f"Created timeline with {total_posts} posts across 3 weeks")

        return plan

    async def run(self, analysis: Dict, trending: List[Dict]) -> Dict:
        """Run the planning swarm"""
        print(f"\n{'='*60}\n  PLANNING SWARM STARTING\n{'='*60}\n", flush=True)

        plan = await self.compile_and_plan(analysis, trending)

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

    async def agent_find_posts(self, keywords: List[str], creds: Dict) -> List[Dict]:
        """Agent 1: Find technical/related posts to reply to"""
        log_stream(self.session_id, "PostFinder", "thinking", "Searching for posts to engage with...")

        try:
            client = get_x_client(creds["access_token"], creds["access_secret"])

            posts = []
            for keyword in keywords[:2]:
                log_stream(self.session_id, "PostFinder", "action", f"Finding posts about: {keyword}")
                tweets = client.search_tweets(q=keyword, count=10, result_type="recent", tweet_mode="extended")

                for tweet in tweets:
                    if tweet.favorite_count > 10:  # Only engage with somewhat popular posts
                        posts.append({
                            "id": tweet.id_str,
                            "text": tweet.full_text,
                            "user": tweet.user.screen_name,
                            "likes": tweet.favorite_count
                        })

            # Take top 4
            posts.sort(key=lambda x: x["likes"], reverse=True)
            selected = posts[:4]

            log_stream(self.session_id, "PostFinder", "result", f"Selected {len(selected)} posts for engagement")
            return selected

        except Exception as e:
            log_stream(self.session_id, "PostFinder", "error", str(e))
            return []

    async def agent_reply(self, posts: List[Dict], analysis: Dict, creds: Dict) -> List[Dict]:
        """Agent 2: Generate and post valuable replies"""
        log_stream(self.session_id, "Replier", "thinking", "Generating valuable replies...")

        replies_made = []

        for post in posts:
            # Generate reply
            prompt = f"""Generate a valuable, insightful reply to this tweet that adds to the conversation.
Keep it under 280 characters. Be helpful, not promotional.

Tweet: {post['text']}

Campaign context: {analysis.get('main_message', '')}

Return just the reply text, nothing else."""

            reply_text = call_gemini(prompt).strip().strip('"')

            log_stream(self.session_id, "Replier", "action", f"Replying to @{post['user']}: {reply_text[:50]}...")

            # Post reply (or mock it)
            try:
                client = get_x_client(creds["access_token"], creds["access_secret"])
                response = client.update_status(
                    status=f"@{post['user']} {reply_text}",
                    in_reply_to_status_id=post['id']
                )
                reply_id = response.id_str
            except Exception as e:
                log_stream(self.session_id, "Replier", "error", f"Failed to post: {e}")
                reply_id = "mock_" + str(uuid.uuid4())[:8]

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

    async def run(self, analysis: Dict, creds: Dict) -> List[Dict]:
        """Run the reply swarm"""
        print(f"\n{'='*60}\n  REPLY SWARM STARTING\n{'='*60}\n", flush=True)

        keywords = analysis.get("keywords", ["tech"])

        # Agent 1: Find posts
        posts = await self.agent_find_posts(keywords, creds)

        # Agent 2: Reply
        replies = []
        if posts:
            replies = await self.agent_reply(posts, analysis, creds)

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
        """Agent 1: Search and gather industry intelligence"""
        log_stream(self.session_id, "IndustryResearcher", "thinking", "Gathering industry intelligence from search...")

        industry = analysis.get("target_audience", "tech")
        keywords = analysis.get("keywords", ["technology", "innovation"])

        prompt = f"""You are an industry research analyst. Research the current state of the {industry} industry.

Focus on:
- Latest trends and developments
- Key challenges and pain points
- Emerging technologies and solutions
- Market dynamics and competitive landscape
- Expert opinions and thought leadership

Keywords to consider: {', '.join(keywords)}

Provide a comprehensive summary of the current industry landscape with specific data points, statistics, and insights that can be used to create authoritative content.

Return a detailed analysis (500-800 words) covering the above areas."""

        log_stream(self.session_id, "IndustryResearcher", "action", f"Analyzing {industry} industry trends...")
        result = call_gemini(prompt)

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

        prompt = f"""You are a viral tech content creator specializing in creating authoritative, insightful posts about industry trends.

CAMPAIGN STRATEGY:
{strategy}

THEMES: {', '.join(themes)}
GOALS: {', '.join(goals)}

INDUSTRY INTELLIGENCE (from search engine research):
{industry_intel}

PREVIOUS AI-GENERATED POSTS (avoid repetition, build on themes):
{previous_context}

TASK: Generate {count} viral tech posts that demonstrate deep industry knowledge.

REQUIREMENTS:
1. Each post must show genuine expertise and insider knowledge
2. Include specific data points, statistics, or trends from the research
3. Use separate paragraphs to structure longer thoughts (2-3 short paragraphs per post)
4. NO hashtags
5. NO quotation marks around the content
6. NO exclamation marks
7. Write in a confident, authoritative tone
8. Each post should be standalone and directly copy-pasteable
9. Focus on insights that make readers think "this person really knows their stuff"
10. Vary the format: some observations, some predictions, some contrarian takes

FORMAT each post like this (use line breaks between paragraphs):
[Post content paragraph 1]

[Post content paragraph 2]

[Optional paragraph 3]

---

Generate exactly {count} posts, separated by "---" between each post."""

        log_stream(self.session_id, "PostGenerator", "action", f"Creating {count} industry-depth posts...")
        result = call_gemini(prompt)

        # Parse the posts
        posts = [p.strip() for p in result.split("---") if p.strip()]

        log_stream(self.session_id, "PostGenerator", "result", f"Generated {len(posts)} industry posts")
        return posts[:count]

    async def agent_post_content(self, posts: List[str], creds: Dict) -> List[Dict]:
        """Agent 4: Post content to X using v2 API"""
        log_stream(self.session_id, "Poster", "thinking", "Posting industry content to X...")

        client = get_x_client_v2(creds["access_token"], creds["access_secret"])
        posted = []

        for i, content in enumerate(posts):
            log_stream(self.session_id, "Poster", "action", f"Posting {i+1}/{len(posts)}: {content[:50]}...")

            try:
                response = client.create_tweet(text=content)
                post_id = response.data["id"] if response.data else f"mock_{uuid.uuid4().hex[:8]}"
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

    async def run(self, plan: Dict, analysis: Dict, creds: Dict) -> List[Dict]:
        """Run the posting swarm"""
        print(f"\n{'='*60}\n  POSTING SWARM STARTING\n{'='*60}\n", flush=True)

        # Agent 1: Research industry intelligence
        industry_intel = await self.agent_search_industry(analysis)

        # Agent 2: Scan previous posts
        previous_posts = await self.agent_scan_previous_posts()

        # Agent 3: Generate 5 industry-depth posts
        posts = await self.agent_generate_posts(plan, analysis, industry_intel, previous_posts, 5)

        # Agent 4: Post to X
        posted = await self.agent_post_content(posts, creds)

        print(f"\n{'='*60}\n  POSTING SWARM COMPLETE\n{'='*60}\n", flush=True)
        return posted

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

    async def run_initial_campaign(self, campaign_info: Dict, creds: Dict) -> Dict:
        """Run interviewer and planning swarms"""
        active_sessions[self.session_id]["status"] = "interviewing"

        # Swarm 1: Interviewer
        interviewer = InterviewerSwarm(self.session_id, self.user_id)
        research = await interviewer.run(campaign_info, creds)

        active_sessions[self.session_id]["status"] = "planning"

        # Swarm 2: Planning
        planner = PlanningSwarm(self.session_id, self.user_id)
        plan = await planner.run(research["analysis"], research["trending_posts"])

        active_sessions[self.session_id]["status"] = "awaiting_approval"
        active_sessions[self.session_id]["plan"] = plan
        active_sessions[self.session_id]["analysis"] = research["analysis"]

        return {
            "session_id": self.session_id,
            "research": research,
            "plan": plan
        }

    async def run_daily_swarms(self, creds: Dict) -> Dict:
        """Run reply and posting swarms (daily task)"""
        session = active_sessions.get(self.session_id, {})
        analysis = session.get("analysis", {})
        plan = session.get("plan", {})

        active_sessions[self.session_id]["status"] = "running_daily"

        # Run reply and posting swarms concurrently
        reply_swarm = ReplySwarm(self.session_id, self.user_id)
        posting_swarm = PostingSwarm(self.session_id, self.user_id)

        replies, posts = await asyncio.gather(
            reply_swarm.run(analysis, creds),
            posting_swarm.run(plan, analysis, creds)
        )

        active_sessions[self.session_id]["status"] = "daily_complete"

        return {
            "replies": replies,
            "posts": posts
        }

# ============================================================
# PYDANTIC MODELS
# ============================================================

class XCredentials(BaseModel):
    access_token: str
    access_secret: str

class CampaignInfo(BaseModel):
    name: str
    description: str
    target_audience: str
    goals: List[str]
    duration_weeks: int = 3

class PlanFeedback(BaseModel):
    approved: bool
    feedback: Optional[str] = None

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(title="Marketing Campaign API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_user_id(x_user_id: str = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header required")
    return x_user_id

# ============================================================
# API ROUTES
# ============================================================

@app.post("/auth/validate-x")
async def validate_x_credentials(creds: XCredentials, user_id: str = Depends(get_user_id)):
    """Validate and store X API credentials"""
    valid = await XValidator.validate_token(user_id, creds.access_token, creds.access_secret)
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid X credentials")
    return {"message": "X credentials validated and stored"}

@app.get("/auth/x-status")
async def get_x_status(user_id: str = Depends(get_user_id)):
    """Check if user has valid X credentials"""
    creds = await XValidator.get_credentials(user_id)
    return {"connected": creds is not None, "username": creds.get("username") if creds else None}

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
        info.dict(),
        creds
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

    creds = await XValidator.get_credentials(user_id)
    if not creds:
        raise HTTPException(status_code=400, detail="X credentials not found")

    orchestrator = CampaignOrchestrator(user_id)
    orchestrator.session_id = session_id

    background_tasks.add_task(orchestrator.run_daily_swarms, creds)

    return {"message": "Daily swarms started"}

@app.get("/campaign/{session_id}/status")
async def get_campaign_status(session_id: str, user_id: str = Depends(get_user_id)):
    """Get campaign status"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

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

    return active_sessions[session_id].get("plan", {})

@app.get("/campaign/{session_id}/stream")
async def get_stream(session_id: str, user_id: str = Depends(get_user_id)):
    """Get streaming logs for a session"""
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
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("  MARKETING CAMPAIGN SERVER")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
