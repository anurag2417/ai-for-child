from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# PROFANITY / SAFETY FILTER (Hard-coded middleware)
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
    """Returns dict with is_blocked and matched words."""
    text_lower = text.lower()
    matched = [w for w in BLOCKED_WORDS if re.search(r'\b' + re.escape(w) + r'\b', text_lower)]
    return {"is_blocked": len(matched) > 0, "matched_words": matched}


def check_restricted_topics(text: str) -> dict:
    """Check for restricted topics, return categories and matched phrases."""
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

class ConversationCreate(BaseModel):
    title: Optional[str] = "New Chat"

class AlertResolve(BaseModel):
    resolved: bool = True

# ============================================================
# REACT SYSTEM PROMPT
# ============================================================
REACT_SYSTEM_PROMPT = """You are BuddyBot, a warm, friendly, and safe AI companion for children aged 5-12. You speak in simple, encouraging language.

IMPORTANT: You must ALWAYS follow this ReAct thinking pattern internally before every response:

**THOUGHT**: First, analyze the child's message for safety. Consider:
- Is there any inappropriate content?
- Is the child sharing personal information?
- Is the child expressing distress or unsafe situations?
- What's the emotional tone?

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
    """Parse the ReAct formatted response from the LLM."""
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

    # Fallback if parsing fails
    if not response:
        response = raw_response.strip()
        thought = "Unable to parse structured response"
        safety_level = "CAUTION"

    return {
        "thought": thought,
        "safety_level": safety_level,
        "response": response
    }


# ============================================================
# CHAT ENDPOINTS
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
        # Store the blocked message
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

        # Create alert
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

        # Bot blocked response
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

    # Step 4: Get conversation history for context
    history = await db.messages.find(
        {"conversation_id": conversation_id, "role": {"$in": ["user", "assistant"]}, "blocked": {"$ne": True}},
        {"_id": 0}
    ).sort("created_at", 1).to_list(20)

    # Build context string for LLM
    context_parts = []
    for msg in history[:-1]:  # exclude current message since we'll send it
        if msg["role"] == "user":
            context_parts.append(f"Child: {msg['text']}")
        else:
            context_parts.append(f"BuddyBot: {msg['text']}")

    context_str = "\n".join(context_parts[-10:])  # last 10 messages
    
    extra_context = ""
    if restricted:
        extra_context = f"\n\n[SYSTEM NOTE: The child's message touches on restricted topics: {restricted}. Be extra careful and redirect gently.]"

    full_prompt = ""
    if context_str:
        full_prompt = f"Previous conversation:\n{context_str}\n\nChild's new message: {data.text}{extra_context}"
    else:
        full_prompt = f"Child's message: {data.text}{extra_context}"

    # Step 5: Call LLM with ReAct pattern
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"buddy-{conversation_id}-{uuid.uuid4().hex[:8]}",
            system_message=REACT_SYSTEM_PROMPT
        )
        chat.with_model("openai", "gpt-4.1-mini")

        user_message = UserMessage(text=full_prompt)
        raw_response = await chat.send_message(user_message)
        parsed = parse_react_response(raw_response)
    except Exception as e:
        logger.error(f"LLM error: {e}")
        parsed = {
            "thought": f"LLM call failed: {str(e)}",
            "safety_level": "CAUTION",
            "response": "Oops! My brain got a little fuzzy for a second. Can you say that again?"
        }

    # Step 6: Create alert if needed
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

    # Step 7: Store bot message
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

    # Recent alerts
    recent_alerts = await db.alerts.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).to_list(10)

    return {
        "stats": {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_alerts": total_alerts,
            "unresolved_alerts": unresolved_alerts,
            "flagged_conversations": flagged_conversations
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


# Health check
@api_router.get("/")
async def root():
    return {"message": "BuddyBot API is running"}


# Include router & middleware
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
