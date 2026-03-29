from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone, timedelta
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# LLM setup
EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# PROFANITY / SAFETY FILTER (Hard-coded baseline)
# ============================================================
BLOCKED_WORDS = [
    "kill", "murder", "suicide", "die", "dead", "blood", "gun", "weapon",
    "knife", "bomb", "shoot", "stab", "drug", "cocaine", "heroin", "meth",
    "weed", "marijuana", "alcohol", "beer", "wine", "vodka", "cigarette",
    "smoke", "vape", "sex", "porn", "nude", "naked", "ass", "damn",
    "hell", "shit", "fuck", "bitch", "bastard", "crap", "dick", "pussy",
    "slut", "whore", "rape", "abuse", "torture", "hate", "racist",
    "terrorism", "terrorist", "hack", "exploit"
]

RESTRICTED_TOPICS = {
    "violence": ["fight", "hit", "punch", "kick", "hurt", "attack", "war", "battle", "destroy", "weapon", "gun", "knife", "bomb", "kill", "murder", "blood", "shoot", "stab"],
    "privacy": ["address", "phone number", "credit card", "password", "social security", "where do you live", "my name is", "my school", "my teacher", "home address", "bank account"],
    "adult_content": ["sex", "porn", "nude", "naked", "dating", "boyfriend", "girlfriend", "kiss", "love making"],
    "substance": ["drug", "alcohol", "beer", "wine", "smoke", "vape", "cigarette", "weed", "marijuana", "cocaine"],
    "self_harm": ["suicide", "kill myself", "cut myself", "hurt myself", "die", "don't want to live", "end my life"]
}


def check_profanity(text: str) -> dict:
    text_lower = text.lower()
    matched = [w for w in BLOCKED_WORDS if re.search(r'\b' + re.escape(w) + r'\b', text_lower)]
    return {"is_blocked": len(matched) > 0, "matched_words": matched}


def check_restricted_topics(text: str) -> dict:
    text_lower = text.lower()
    flagged = {}
    for category, phrases in RESTRICTED_TOPICS.items():
        matches = [p for p in phrases if p in text_lower]
        if matches:
            flagged[category] = matches
    return flagged


# ============================================================
# PYDANTIC MODELS
# ============================================================
class MessageCreate(BaseModel):
    conversation_id: Optional[str] = None
    text: str
    device_id: Optional[str] = None

class ConversationCreate(BaseModel):
    title: Optional[str] = "New Chat"

class AlertResolve(BaseModel):
    resolved: bool = True

class BrowsingPacket(BaseModel):
    id: str
    timestamp: str
    device_id: str
    tab_type: str = "normal"
    url: str
    domain: str
    title: Optional[str] = ""
    packet_type: str
    search_query: Optional[str] = None
    search_engine: Optional[str] = None

class PacketBatch(BaseModel):
    device_id: str
    packets: List[BrowsingPacket]

class PinVerify(BaseModel):
    device_id: str
    pin: str

# ============================================================
# REACT SYSTEM PROMPT (Enhanced with browsing context)
# ============================================================
REACT_SYSTEM_PROMPT = """You are BuddyBot, a warm, friendly, and safe AI companion for children aged 5-12. You speak in simple, encouraging language.

IMPORTANT: You must ALWAYS follow this ReAct thinking pattern internally before every response:

**THOUGHT**: First, analyze the child's message for safety. Consider:
- Is there any inappropriate content?
- Is the child sharing personal information?
- Is the child expressing distress or unsafe situations?
- What's the emotional tone?
- Consider the child's recent browsing history if provided (they may be exploring topics seen online)

**SAFETY_LEVEL**: Rate as SAFE, CAUTION, or ALERT
- SAFE: Normal, fun, educational conversation
- CAUTION: Borderline topic, needs gentle redirection
- ALERT: Child may be in danger, needs careful response + flagging

**RESPONSE**: Then compose your response following these rules:
1. Always be kind, encouraging, and age-appropriate
2. Use simple words a 5-year-old can understand
3. If asked about restricted topics, gently redirect to fun alternatives
4. If a child seems sad or scared, be comforting and suggest talking to a trusted adult
5. Never provide personal information or encourage sharing personal details
6. Encourage creativity, learning, and positive behavior
7. Keep responses SHORT (2-4 sentences max)
8. Use fun analogies and references kids would enjoy (animals, games, nature)

You MUST format your response EXACTLY like this:
[THOUGHT] Your safety analysis here
[SAFETY] SAFE or CAUTION or ALERT
[RESPONSE] Your child-friendly response here

NEVER deviate from this format. The [THOUGHT] and [SAFETY] sections are hidden from children but visible to parents."""


def parse_react_response(raw_response: str) -> dict:
    thought = ""
    safety_level = "SAFE"
    response = ""

    thought_match = re.search(r'\[THOUGHT\]\s*(.*?)(?=\[SAFETY\])', raw_response, re.DOTALL)
    safety_match = re.search(r'\[SAFETY\]\s*(SAFE|CAUTION|ALERT)', raw_response, re.DOTALL)
    response_match = re.search(r'\[RESPONSE\]\s*(.*?)$', raw_response, re.DOTALL)

    if thought_match:
        thought = thought_match.group(1).strip()
    if safety_match:
        safety_level = safety_match.group(1).strip()
    if response_match:
        response = response_match.group(1).strip()

    if not response:
        response = raw_response.strip()
        thought = "Unable to parse structured response"
        safety_level = "CAUTION"

    return {"thought": thought, "safety_level": safety_level, "response": response}


# ============================================================
# BROWSING CONTEXT BUILDER
# ============================================================
async def get_browsing_context(device_id: str = None) -> str:
    """Get recent browsing history to provide context to the AI."""
    if not device_id:
        # Get the most recent device
        latest = await db.browsing_packets.find_one(
            {}, {"_id": 0, "device_id": 1},
            sort=[("timestamp", -1)]
        )
        if latest:
            device_id = latest["device_id"]
        else:
            return ""

    # Get last 20 search queries
    recent_searches = await db.browsing_packets.find(
        {"device_id": device_id, "packet_type": "search_query"},
        {"_id": 0, "search_query": 1, "search_engine": 1, "timestamp": 1, "tab_type": 1}
    ).sort("timestamp", -1).to_list(20)

    # Get last 10 visited domains
    recent_visits = await db.browsing_packets.find(
        {"device_id": device_id, "packet_type": "url_visit"},
        {"_id": 0, "domain": 1, "title": 1, "timestamp": 1, "tab_type": 1}
    ).sort("timestamp", -1).to_list(10)

    if not recent_searches and not recent_visits:
        return ""

    context_parts = ["\n[BROWSING CONTEXT - Recent child activity from browser extension]:"]
    if recent_searches:
        context_parts.append("Recent searches:")
        for s in recent_searches[:10]:
            mode = " (INCOGNITO)" if s.get("tab_type") == "incognito" else ""
            context_parts.append(f"  - \"{s['search_query']}\" on {s.get('search_engine', 'unknown')}{mode}")

    if recent_visits:
        context_parts.append("Recent sites visited:")
        for v in recent_visits[:5]:
            mode = " (INCOGNITO)" if v.get("tab_type") == "incognito" else ""
            context_parts.append(f"  - {v.get('title', v['domain'])} ({v['domain']}){mode}")

    return "\n".join(context_parts)


async def analyze_browsing_patterns(device_id: str) -> dict:
    """AI-powered analysis of browsing patterns for safety."""
    recent_searches = await db.browsing_packets.find(
        {"device_id": device_id, "packet_type": "search_query"},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(50)

    recent_visits = await db.browsing_packets.find(
        {"device_id": device_id, "packet_type": "url_visit"},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(30)

    if not recent_searches and not recent_visits:
        return {"safety_level": "SAFE", "analysis": "No browsing data available", "concerns": []}

    # Check searches against restricted topics
    concerns = []
    for search in recent_searches:
        query = search.get("search_query", "")
        topics = check_restricted_topics(query)
        profanity = check_profanity(query)
        if topics or profanity["is_blocked"]:
            concerns.append({
                "query": query,
                "topics": topics,
                "profanity": profanity["matched_words"],
                "tab_type": search.get("tab_type", "normal"),
                "timestamp": search.get("timestamp"),
                "search_engine": search.get("search_engine")
            })

    # Build analysis prompt for AI
    search_list = [s.get("search_query", "") for s in recent_searches[:30] if s.get("search_query")]
    domain_list = [v.get("domain", "") for v in recent_visits[:20]]

    analysis_prompt = f"""Analyze this child's browsing activity for safety concerns. Be concise.

Recent searches: {search_list[:20]}
Recent domains visited: {list(set(domain_list[:15]))}
Incognito searches: {[s.get('search_query') for s in recent_searches if s.get('tab_type') == 'incognito'][:10]}

Provide:
1. Overall safety assessment (SAFE/CAUTION/ALERT)
2. Any concerning patterns (2-3 sentences max)
3. Positive patterns noticed (1 sentence)

Format:
[SAFETY] SAFE or CAUTION or ALERT
[CONCERNS] Your concern analysis
[POSITIVE] Positive observations"""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"analysis-{device_id}-{uuid.uuid4().hex[:8]}",
            system_message="You are a child safety analyst. Analyze browsing patterns and flag concerns. Be concise and factual."
        )
        chat.with_model("openai", "gpt-4.1-mini")
        raw = await chat.send_message(UserMessage(text=analysis_prompt))

        safety_match = re.search(r'\[SAFETY\]\s*(SAFE|CAUTION|ALERT)', raw)
        concerns_match = re.search(r'\[CONCERNS\]\s*(.*?)(?=\[POSITIVE\])', raw, re.DOTALL)
        positive_match = re.search(r'\[POSITIVE\]\s*(.*?)$', raw, re.DOTALL)

        return {
            "safety_level": safety_match.group(1) if safety_match else "SAFE",
            "analysis": concerns_match.group(1).strip() if concerns_match else "No concerns detected",
            "positive": positive_match.group(1).strip() if positive_match else "",
            "flagged_searches": concerns,
            "total_searches": len(recent_searches),
            "total_visits": len(recent_visits),
            "incognito_count": len([s for s in recent_searches if s.get("tab_type") == "incognito"])
        }
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return {
            "safety_level": "CAUTION" if concerns else "SAFE",
            "analysis": f"AI analysis unavailable. {len(concerns)} keyword-flagged searches found." if concerns else "No keyword-based concerns detected.",
            "positive": "",
            "flagged_searches": concerns,
            "total_searches": len(recent_searches),
            "total_visits": len(recent_visits),
            "incognito_count": len([s for s in recent_searches if s.get("tab_type") == "incognito"])
        }


# ============================================================
# EXTENSION ENDPOINTS
# ============================================================
@api_router.post("/extension/packets")
async def receive_packets(batch: PacketBatch):
    """Receive browsing data packets from the Chrome extension."""
    if not batch.packets:
        return {"status": "ok", "received": 0}

    docs = []
    alerts_to_create = []

    for packet in batch.packets:
        doc = packet.model_dump()
        doc["synced_at"] = datetime.now(timezone.utc).isoformat()

        # Analyze each search query for safety
        if packet.packet_type == "search_query" and packet.search_query:
            profanity = check_profanity(packet.search_query)
            restricted = check_restricted_topics(packet.search_query)
            doc["profanity_flagged"] = profanity["is_blocked"]
            doc["profanity_words"] = profanity["matched_words"]
            doc["restricted_topics"] = restricted if restricted else None

            # Create alert for flagged searches
            if profanity["is_blocked"] or restricted:
                severity = "high" if profanity["is_blocked"] else "medium"
                alert = {
                    "id": str(uuid.uuid4()),
                    "type": "browsing_alert",
                    "severity": severity,
                    "device_id": batch.device_id,
                    "details": f"Flagged search: \"{packet.search_query}\" on {packet.search_engine or 'browser'}",
                    "child_message": packet.search_query,
                    "tab_type": packet.tab_type,
                    "url": packet.url,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "resolved": False,
                    "source": "extension"
                }
                if restricted:
                    alert["details"] += f" | Topics: {list(restricted.keys())}"
                if profanity["is_blocked"]:
                    alert["details"] += f" | Blocked words: {profanity['matched_words']}"
                alerts_to_create.append(alert)

        docs.append(doc)

    # Batch insert packets
    if docs:
        await db.browsing_packets.insert_many(docs)

    # Create alerts
    if alerts_to_create:
        await db.alerts.insert_many(alerts_to_create)

    return {
        "status": "ok",
        "received": len(docs),
        "alerts_created": len(alerts_to_create)
    }


@api_router.get("/extension/status/{device_id}")
async def extension_status(device_id: str):
    """Get status for a specific device."""
    packet_count = await db.browsing_packets.count_documents({"device_id": device_id})
    last_packet = await db.browsing_packets.find_one(
        {"device_id": device_id}, {"_id": 0, "timestamp": 1},
        sort=[("timestamp", -1)]
    )
    alert_count = await db.alerts.count_documents({"device_id": device_id, "source": "extension"})

    return {
        "device_id": device_id,
        "total_packets": packet_count,
        "last_activity": last_packet["timestamp"] if last_packet else None,
        "total_alerts": alert_count
    }


# ============================================================
# BROWSING DATA ENDPOINTS (Parent Dashboard)
# ============================================================
@api_router.get("/parent/browsing/stats")
async def browsing_stats():
    """Get browsing statistics for parent dashboard."""
    total_packets = await db.browsing_packets.count_documents({})
    search_count = await db.browsing_packets.count_documents({"packet_type": "search_query"})
    visit_count = await db.browsing_packets.count_documents({"packet_type": "url_visit"})
    incognito_count = await db.browsing_packets.count_documents({"tab_type": "incognito"})
    flagged_searches = await db.browsing_packets.count_documents({"profanity_flagged": True})
    browsing_alerts = await db.alerts.count_documents({"source": "extension"})

    # Get unique devices
    devices = await db.browsing_packets.distinct("device_id")

    return {
        "total_packets": total_packets,
        "search_count": search_count,
        "visit_count": visit_count,
        "incognito_count": incognito_count,
        "flagged_searches": flagged_searches,
        "browsing_alerts": browsing_alerts,
        "devices": devices
    }


@api_router.get("/parent/browsing/searches")
async def browsing_searches(device_id: Optional[str] = None, limit: int = 50):
    """Get recent search queries."""
    query = {"packet_type": "search_query"}
    if device_id:
        query["device_id"] = device_id
    searches = await db.browsing_packets.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).to_list(limit)
    return searches


@api_router.get("/parent/browsing/visits")
async def browsing_visits(device_id: Optional[str] = None, limit: int = 50):
    """Get recent URL visits."""
    query = {"packet_type": "url_visit"}
    if device_id:
        query["device_id"] = device_id
    visits = await db.browsing_packets.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).to_list(limit)
    return visits


@api_router.get("/parent/browsing/analysis")
async def browsing_analysis(device_id: Optional[str] = None):
    """AI-powered browsing pattern analysis."""
    if not device_id:
        latest = await db.browsing_packets.find_one(
            {}, {"_id": 0, "device_id": 1}, sort=[("timestamp", -1)]
        )
        if latest:
            device_id = latest["device_id"]
        else:
            return {"safety_level": "SAFE", "analysis": "No browsing data available", "concerns": []}

    return await analyze_browsing_patterns(device_id)


# ============================================================
# CHAT ENDPOINTS (Enhanced with browsing context)
# ============================================================
@api_router.post("/chat/conversations")
async def create_conversation(data: ConversationCreate):
    conv_id = str(uuid.uuid4())
    doc = {
        "id": conv_id,
        "title": data.title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "message_count": 0,
        "has_flags": False,
        "flag_count": 0
    }
    await db.conversations.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.get("/chat/conversations")
async def list_conversations():
    convs = await db.conversations.find({}, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return convs


@api_router.get("/chat/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    conv = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await db.messages.find(
        {"conversation_id": conversation_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(1000)
    return {"conversation": conv, "messages": messages}


@api_router.post("/chat/send")
async def send_message(data: MessageCreate):
    # Create conversation if needed
    if not data.conversation_id:
        conv_id = str(uuid.uuid4())
        title = data.text[:40] + ("..." if len(data.text) > 40 else "")
        conv_doc = {
            "id": conv_id,
            "title": title,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "message_count": 0,
            "has_flags": False,
            "flag_count": 0
        }
        await db.conversations.insert_one(conv_doc)
        data.conversation_id = conv_id

    conversation_id = data.conversation_id

    # Step 1: Profanity check
    profanity_result = check_profanity(data.text)
    if profanity_result["is_blocked"]:
        user_msg = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "role": "user",
            "text": data.text,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "blocked": True,
            "blocked_words": profanity_result["matched_words"]
        }
        await db.messages.insert_one(user_msg)
        user_msg.pop("_id", None)

        alert_doc = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "message_id": user_msg["id"],
            "type": "profanity",
            "severity": "high",
            "details": f"Blocked words detected: {', '.join(profanity_result['matched_words'])}",
            "child_message": data.text,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "resolved": False
        }
        await db.alerts.insert_one(alert_doc)
        alert_doc.pop("_id", None)

        await db.conversations.update_one(
            {"id": conversation_id},
            {"$set": {"has_flags": True, "updated_at": datetime.now(timezone.utc).isoformat()},
             "$inc": {"message_count": 1, "flag_count": 1}}
        )

        bot_msg = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "role": "assistant",
            "text": "Hmm, let's use kind and friendly words! How about we talk about something fun instead? What's your favorite animal?",
            "thought": "Profanity filter triggered. Blocked words detected in child's message. Redirecting to safe topic.",
            "safety_level": "ALERT",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.messages.insert_one(bot_msg)
        bot_msg.pop("_id", None)

        await db.conversations.update_one(
            {"id": conversation_id},
            {"$inc": {"message_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
        )

        return {
            "conversation_id": conversation_id,
            "user_message": user_msg,
            "bot_message": bot_msg,
            "blocked": True,
            "alert": alert_doc
        }

    # Step 2: Check restricted topics
    restricted = check_restricted_topics(data.text)

    # Step 3: Store user message
    user_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "role": "user",
        "text": data.text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blocked": False,
        "flagged_topics": restricted if restricted else None
    }
    await db.messages.insert_one(user_msg)
    user_msg.pop("_id", None)

    # Step 4: Get conversation history
    history = await db.messages.find(
        {"conversation_id": conversation_id, "role": {"$in": ["user", "assistant"]}, "blocked": {"$ne": True}},
        {"_id": 0}
    ).sort("created_at", 1).to_list(20)

    context_parts = []
    for msg in history[:-1]:
        if msg["role"] == "user":
            context_parts.append(f"Child: {msg['text']}")
        else:
            context_parts.append(f"BuddyBot: {msg['text']}")

    context_str = "\n".join(context_parts[-10:])

    # Step 5: Get browsing context from extension
    browsing_context = await get_browsing_context(data.device_id)

    extra_context = ""
    if restricted:
        extra_context = f"\n\n[SYSTEM NOTE: The child's message touches on restricted topics: {restricted}. Be extra careful and redirect gently.]"

    full_prompt = ""
    if context_str:
        full_prompt = f"Previous conversation:\n{context_str}\n\nChild's new message: {data.text}{extra_context}{browsing_context}"
    else:
        full_prompt = f"Child's message: {data.text}{extra_context}{browsing_context}"

    # Step 6: Call LLM
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"buddy-{conversation_id}-{uuid.uuid4().hex[:8]}",
            system_message=REACT_SYSTEM_PROMPT
        )
        chat.with_model("openai", "gpt-4.1-mini")
        raw_response = await chat.send_message(UserMessage(text=full_prompt))
        parsed = parse_react_response(raw_response)
    except Exception as e:
        logger.error(f"LLM error: {e}")
        parsed = {
            "thought": f"LLM call failed: {str(e)}",
            "safety_level": "CAUTION",
            "response": "Oops! My brain got a little fuzzy for a second. Can you say that again?"
        }

    # Step 7: Create alert if needed
    if parsed["safety_level"] == "ALERT" or restricted:
        severity = "high" if parsed["safety_level"] == "ALERT" else "medium"
        alert_doc = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "message_id": user_msg["id"],
            "type": "restricted_topic",
            "severity": severity,
            "details": f"Safety Level: {parsed['safety_level']}. Topics: {restricted if restricted else 'AI flagged'}. AI Thought: {parsed['thought'][:200]}",
            "child_message": data.text,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "resolved": False
        }
        await db.alerts.insert_one(alert_doc)
        alert_doc.pop("_id", None)

        await db.conversations.update_one(
            {"id": conversation_id},
            {"$set": {"has_flags": True, "updated_at": datetime.now(timezone.utc).isoformat()},
             "$inc": {"flag_count": 1}}
        )

    # Step 8: Store bot message
    bot_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "role": "assistant",
        "text": parsed["response"],
        "thought": parsed["thought"],
        "safety_level": parsed["safety_level"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.messages.insert_one(bot_msg)
    bot_msg.pop("_id", None)

    await db.conversations.update_one(
        {"id": conversation_id},
        {"$inc": {"message_count": 2}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    return {
        "conversation_id": conversation_id,
        "user_message": user_msg,
        "bot_message": bot_msg,
        "blocked": False,
    }


# ============================================================
# PARENT DASHBOARD ENDPOINTS
# ============================================================
@api_router.get("/parent/dashboard")
async def parent_dashboard():
    total_conversations = await db.conversations.count_documents({})
    total_messages = await db.messages.count_documents({})
    total_alerts = await db.alerts.count_documents({})
    unresolved_alerts = await db.alerts.count_documents({"resolved": False})
    flagged_conversations = await db.conversations.count_documents({"has_flags": True})

    # Browsing stats
    total_packets = await db.browsing_packets.count_documents({})
    browsing_alerts = await db.alerts.count_documents({"source": "extension"})
    incognito_count = await db.browsing_packets.count_documents({"tab_type": "incognito"})

    recent_alerts = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(10)

    return {
        "stats": {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_alerts": total_alerts,
            "unresolved_alerts": unresolved_alerts,
            "flagged_conversations": flagged_conversations,
            "total_packets": total_packets,
            "browsing_alerts": browsing_alerts,
            "incognito_searches": incognito_count
        },
        "recent_alerts": recent_alerts
    }


@api_router.get("/parent/alerts")
async def get_alerts(resolved: Optional[bool] = None):
    query = {}
    if resolved is not None:
        query["resolved"] = resolved
    alerts = await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return alerts


@api_router.put("/parent/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    result = await db.alerts.update_one(
        {"id": alert_id},
        {"$set": {"resolved": True, "resolved_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "resolved", "alert_id": alert_id}


@api_router.get("/parent/conversations")
async def parent_conversations():
    convs = await db.conversations.find({}, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return convs


@api_router.get("/parent/conversations/{conversation_id}")
async def parent_conversation_detail(conversation_id: str):
    conv = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await db.messages.find(
        {"conversation_id": conversation_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(1000)
    alerts = await db.alerts.find(
        {"conversation_id": conversation_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"conversation": conv, "messages": messages, "alerts": alerts}


@api_router.get("/")
async def root():
    return {"message": "BuddyBot API is running"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
