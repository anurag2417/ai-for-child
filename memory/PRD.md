# BuddyBot - Children's AI Chatbot PRD

## Problem Statement
Build a Chatbot/AI Assistant with a conversational UI specifically designed for children. It should feel like a friendly companion but have a "hidden" moderation layer using ReAct pattern for safety analysis.

## Architecture
- **Frontend**: React + Tailwind CSS (Nunito/Quicksand fonts, pastel theme)
- **Backend**: FastAPI + MongoDB + emergentintegrations (OpenAI gpt-4.1-mini)
- **Database**: MongoDB (test_database) - collections: conversations, messages, alerts

## User Personas
1. **Child (5-12 years)**: Primary user of chat interface
2. **Parent/Guardian**: Uses dashboard to monitor conversations and safety

## Core Requirements
- [x] Child-friendly chat interface with playful design
- [x] AI companion (BuddyBot) using ReAct safety thinking pattern
- [x] Hard-coded profanity/safety filter middleware
- [x] Restricted topic detection (violence, privacy, adult content, substance, self-harm)
- [x] Parent Dashboard with stats, alerts, and conversation logs
- [x] AI "Thoughts" visible only in parent dashboard
- [x] Alert system with severity levels (high/medium) and resolve capability
- [x] Conversation persistence in MongoDB
- [x] Navigation state persistence via localStorage

## What's Been Implemented (March 28, 2026)
1. **Chat Page** (`/`): Sidebar with conversations, new chat, message input, typing indicator
2. **AI Engine**: ReAct pattern with [THOUGHT], [SAFETY], [RESPONSE] parsing
3. **Safety Layer**: Profanity filter (60+ blocked words), restricted topic detection (5 categories)
4. **Parent Dashboard** (`/parent`): Stats cards, alerts tab, conversations tab, resolve alerts
5. **Conversation Detail** (`/parent/conversation/:id`): Full message thread with AI thoughts, safety badges, alert history
6. **LLM Integration**: OpenAI gpt-4.1-mini via emergentintegrations library with Emergent LLM key

## API Endpoints
- POST /api/chat/send - Send message & get AI response
- POST /api/chat/conversations - Create conversation
- GET /api/chat/conversations - List conversations
- GET /api/chat/conversations/:id - Get conversation detail
- GET /api/parent/dashboard - Dashboard stats + recent alerts
- GET /api/parent/alerts - All alerts (filterable by resolved status)
- PUT /api/parent/alerts/:id/resolve - Resolve an alert
- GET /api/parent/conversations - Parent conversation list
- GET /api/parent/conversations/:id - Detailed view with thoughts

## Backlog
### P1 (Next)
- Real-time notifications (WebSocket) when new alerts occur
- Export conversation logs as PDF
- Multiple child profiles support

### P2
- Daily/weekly safety report emails to parents
- Adjustable safety sensitivity levels
- Chat topics suggestion chips for kids
- Time-based usage limits

### P3
- Voice input/output for younger children
- Achievement/reward system for positive interactions
- Dark mode toggle
- Multi-language support
