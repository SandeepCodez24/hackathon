# Government Scheme Recommendation System
## via WhatsApp AI Chatbot — Project Documentation v2.0

> **Meet 530 Million Indians Where They Already Are**

| Field | Detail |
|---|---|
| Problem ID | #9 – Government Schemes Eligibility Assistant |
| Interface | WhatsApp Business API + Web Fallback |
| AI Stack | LLM + Decision Tree + Eligibility Rule Engine |
| Reach | 530M+ WhatsApp users — zero app install needed |
| Version | 2.0 — Final (includes WhatsApp layer) |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [WhatsApp Integration Architecture](#2-whatsapp-integration-architecture)
3. [Full System Architecture](#3-full-system-architecture)
4. [Complete User Journey](#4-complete-user-journey)
5. [Technology Stack](#5-technology-stack)
6. [Data Models](#6-data-models)
7. [Layer-Wise Implementation Phases](#7-layer-wise-implementation-phases)
8. [Project Folder Structure](#8-project-folder-structure)
9. [API Reference](#9-api-reference)
10. [Scheme Catalogue](#10-scheme-catalogue-75-schemes)
11. [Security & Privacy Architecture](#11-security--privacy-architecture)
12. [Demo Presentation Plan](#12-demo-presentation-plan-for-judge)
13. [Competitive Advantage](#13-competitive-advantage)
14. [Risk Register & Mitigation](#14-risk-register--mitigation)
15. [Success Metrics](#15-success-metrics)
16. [Conclusion](#16-conclusion)

---

## 1. Executive Summary

India has over 500 central and state government welfare schemes — yet billions of rupees go unclaimed every year because eligible citizens simply don't know they qualify. The Government Scheme Recommendation System solves this with a **WhatsApp-first AI chatbot** that meets citizens where they already are.

A citizen sends a WhatsApp message to an official number. Within **3 minutes and fewer than 10 adaptive questions**, they receive a ranked list of every scheme they are eligible for — complete with benefit details, document checklists, and direct apply-now links to official portals.

> **Why WhatsApp changes everything**
>
> 530 million Indians use WhatsApp daily. They trust it, understand it, and it works on 2G networks and ₹5,000 Android phones. No app install, no login, no new interface to learn. A farmer in rural Bihar gets scheme guidance in Hindi, via voice note if needed, in the same app he uses to talk to family.

### What the Citizen Gets
- Scheme recommendations in under 3 minutes
- Fewer than 10 smart adaptive questions
- Works in 10+ regional languages
- Voice note input for low-literacy users
- Official portal links + step-by-step apply guide
- Forward results to family via WhatsApp instantly

### What the Government Gets
- Massive increase in scheme utilisation
- Zero new app infrastructure needed
- Built-in fraud detection layer
- Anonymised analytics on welfare gaps
- Scalable to 1M+ conversations/month
- Verified WhatsApp Business badge = citizen trust

---

## 2. WhatsApp Integration Architecture

The WhatsApp layer sits on top of the existing AI engine as a **thin communication adapter**. The AI engine itself is completely unchanged — it simply receives text from WhatsApp instead of a web form, and returns text back through WhatsApp instead of rendering HTML.

### 2.1 End-to-End Message Flow

| Step | Actor | Action | Technology |
|---|---|---|---|
| 1 | Citizen | Sends 'Hi' to official WhatsApp number | WhatsApp on their phone |
| 2 | Meta Cloud API | Receives message, fires HTTP webhook | Meta WhatsApp Business Cloud API |
| 3 | API Gateway | Authenticates webhook, parses payload | FastAPI + signature verification |
| 4 | Session Manager | Loads or creates citizen session | Redis (ephemeral, 24hr TTL) |
| 5 | NLP Parser | Understands the message (text or voice) | LLM + Whisper (voice-to-text) |
| 6 | Question Engine | Selects best next question (info gain) | Decision Tree + Bayesian pruning |
| 7 | Fraud Detector | Silently validates profile consistency | Isolation Forest ML model |
| 8 | Eligibility Engine | Scores all 100+ schemes against profile | Rule engine + ML ranking |
| 9 | Response Builder | Formats results as WhatsApp message | Template engine + LLM |
| 10 | Meta Cloud API | Delivers message back to citizen's phone | WhatsApp Business API |

### 2.2 WhatsApp Message Types Used

| Message Type | When Used | Max Options | Example |
|---|---|---|---|
| Quick Reply Buttons | Occupation, income range, yes/no questions | 3 buttons | Farmer \| Student \| Self-employed |
| List Message | Selecting state, category, scheme | 10 items | [Dropdown: Select your state] |
| Text + Bold/Italic | Questions and explanations | Unlimited | *What is your annual income?* |
| Document (PDF) | Application checklist per scheme | 1 file | PM-KISAN_Checklist.pdf |
| Deep-link Button | Apply now CTA | 1 URL | Apply → pmkisan.gov.in |
| Voice Note (inbound) | Low-literacy user input | N/A | Audio transcribed by Whisper API |

### 2.3 Webhook Integration Code

The entire WhatsApp integration is a **single FastAPI endpoint**. Your existing AI engine requires zero modification:

```python
# whatsapp_webhook.py — The ONLY new file needed for WhatsApp

from fastapi import FastAPI, Request
from app.core.session_manager   import SessionManager
from app.core.adaptive_engine   import AdaptiveQuestionEngine
from app.core.whatsapp_client   import WhatsAppClient
from app.core.voice_transcriber import transcribe_voice

@app.post('/webhook/whatsapp')
async def whatsapp_webhook(request: Request):
    payload = await request.json()
    msg     = payload['entry'][0]['changes'][0]['value']['messages'][0]

    phone   = msg['from']                          # Citizen's number
    if msg['type'] == 'text':
        text = msg['text']['body']
    elif msg['type'] == 'audio':                   # Voice note!
        text = await transcribe_voice(msg['audio']['id'])
    elif msg['type'] == 'interactive':             # Button tap
        text = msg['interactive']['button_reply']['title']

    session  = await SessionManager.get_or_create(phone)
    response = await AdaptiveQuestionEngine.process(session, text)

    await WhatsAppClient.send(phone, response)     # Done!
    return {'status': 'ok'}
```

---

## 3. Full System Architecture

### 3.1 Layer-by-Layer Architecture

| Layer | Components | Technology | Responsibility |
|---|---|---|---|
| Channel Layer | WhatsApp Business API, Web PWA (fallback) | Meta Cloud API, React.js | User-facing entry points |
| API Gateway | Request router, auth, rate limiter | FastAPI + Nginx | Webhook verification, DDoS protection |
| Session Layer | Session manager, context store | Redis (24hr TTL) | Maintain conversation state per phone |
| Conversation Engine | Adaptive Q engine, question bank | Python + LangChain | Orchestrate question flow |
| AI/ML Layer | NLP parser, decision tree, LLM, voice | GPT-4 / Claude API, Whisper, scikit-learn | Understand input, select next question |
| Eligibility Engine | Rule matcher, scoring, ranking | Python + NumPy | Score schemes, compute confidence % |
| Fraud Layer | Anomaly detector, consistency checker | Isolation Forest + rules | Silently flag suspicious profiles |
| Data Layer | Scheme DB, session store, metadata | PostgreSQL + Redis | Persist scheme rules, ephemeral sessions |
| Privacy Layer | Encryption, ZKP vault, PII hasher | PyNaCl, AES-256 | No raw PII persisted after session ends |
| Admin Layer | Scheme CMS, analytics dashboard | React Admin + Grafana | Manage schemes, monitor usage |

### 3.2 AI Engine — Core Components

#### Component 1: Adaptive Question Engine

The brain of the system. Uses **information-theoretic question selection** — at each step it picks the question that maximally reduces the number of candidate schemes (highest entropy reduction). Like a game of 20 Questions, but optimised by an algorithm.

- Starts with all 100+ schemes as candidates
- Calculates information gain for every possible next question
- Selects the single highest-gain question
- After each answer, prunes the candidate set (Bayesian update)
- Stops when fewer than 5 candidates remain OR confidence > 90%
- **Average questions to recommendation: 6–8 (never more than 12)**

#### Component 2: LLM Response Layer

The AI engine generates raw eligibility results. The LLM layer converts them into human, conversational WhatsApp messages in the user's language.

- **Receives:** scheme list + confidence scores + user profile
- **Generates:** friendly WhatsApp message with ranked results
- **Handles:** follow-up questions like "what documents do I need?"
- **Languages:** Hindi, Tamil, Telugu, Kannada, Bengali, Marathi, Gujarati + English

#### Component 3: Voice Transcription

For low-literacy and rural users, voice notes are first-class citizens.

- User sends voice note in any Indian language
- OpenAI Whisper API transcribes with high accuracy for Indian accents
- Transcription sent to NLP parser — same pipeline as text
- Significantly expands accessibility to 200M+ semi-literate users

---

## 4. Complete User Journey

The following table shows the complete end-to-end conversation for a farmer using the WhatsApp bot. The **entire journey takes under 3 minutes with 7 questions**.

| Turn | Who | Message | System Action |
|---|---|---|---|
| 1 | Citizen | Hi | Creates new session, sends welcome + occupation buttons |
| 2 | Bot | *Welcome!* What is your occupation? [Farmer] [Student] [Self-employed] | Sends WhatsApp quick-reply buttons |
| 3 | Citizen | Taps: Farmer | Sets occupation=Farmer, prunes to ~40 schemes, asks income |
| 4 | Bot | What is your annual family income? [Below 2L] [2L–5L] [Above 5L] | Sends quick-reply buttons |
| 5 | Citizen | Taps: Below 2L | Prunes to ~18 schemes. Next highest-gain Q: land ownership |
| 6 | Bot | Do you own agricultural land? [Yes] [No, I'm a tenant] | Quick reply |
| 7 | Citizen | Yes | Prunes to ~10 schemes. Asks land area |
| 8 | Bot | How many acres do you own? [Less than 2] [2–5 acres] [More than 5] | Quick reply |
| 9 | Citizen | 2–5 acres | Prunes to 6 schemes. Asks Aadhaar linkage |
| 10 | Bot | Is your bank account linked to Aadhaar? [Yes] [No] | Quick reply |
| 11 | Citizen | Yes | Confidence > 90%. Engine terminates. Runs scoring. |
| 12 | Bot | Your top 4 schemes — ranked results | Ranked result message sent |
| 13 | Citizen | 1 | Step-by-step apply guide for PM-KISAN + PDF checklist sent |

### 4.1 WhatsApp Result Message Format

```
✅ Based on your profile, you qualify for 4 schemes:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🥇 *PM-KISAN*  — 98% match
   ₹6,000/year direct to your bank account
   👉 pmkisan.gov.in

🥈 *PM Fasal Bima Yojana*  — 91% match
   Crop insurance at just 2% premium
   👉 pmfby.gov.in

🥉 *Kisan Credit Card*  — 87% match
   Low-interest loan up to ₹3 lakh
   👉 kisan.nabard.org

4️⃣  *Soil Health Card*  — 79% match
   Free soil testing + recommendations
   👉 soilhealth.dac.gov.in
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Reply *1, 2, 3 or 4* for step-by-step apply guide 📋
Reply *HELP* anytime to restart
```

---

## 5. Technology Stack

| Layer | Technology | Purpose | Why This Choice |
|---|---|---|---|
| WhatsApp | Meta Business Cloud API | Receive/send WhatsApp messages | Official, free tier, 1000 convos/month, scalable |
| Voice | OpenAI Whisper API | Voice note transcription | Best accuracy for Indian languages/accents |
| Backend | Python FastAPI | REST API + webhook server | Async, fast, type-safe, great for AI pipelines |
| Conversation | LangChain | LLM prompt orchestration | Handles context, chains, memory management |
| LLM | Claude API / GPT-4 | Natural language generation | Human-quality adaptive questions and responses |
| ML | scikit-learn | Decision tree + anomaly detection | Lightweight, interpretable, production-ready |
| Database | PostgreSQL | Scheme rules and metadata | Reliable, supports JSONB for eligibility rules |
| Sessions | Redis (TTL 24hr) | Ephemeral conversation state | Fast, auto-expires — no permanent PII storage |
| Encryption | PyNaCl + AES-256 | PII protection in transit | Industry-standard, IT Act compliant |
| Web Fallback | React.js + Vite | Browser-based alternative | For users without WhatsApp |
| Voice Alt | Bhashini API (GoI) | Indian language support | Government-approved, free, 22 languages |
| Deployment | Docker + AWS/Azure | Containerised cloud deploy | Scalable, Gov-compliant infrastructure |
| Monitoring | Grafana + Prometheus | Uptime and usage analytics | Real-time alerts, anonymised dashboards |
| CI/CD | GitHub Actions | Automated test and deploy | Quality gate before every release |

### 5.1 Meta WhatsApp Business API — Key Facts

| | Free Tier (Hackathon) | Production Tier |
|---|---|---|
| Conversations | 1,000 free/month | Unlimited (pay-per-conversation ~₹0.50) |
| Setup | No credit card needed | Business verification required |
| Test number | Available immediately | Verified green badge |
| Approval time | Sandbox: instant | Production: 2–3 days |
| Who uses it | Demo and MVP | SBI, Paytm, HDFC Bank already use it |

---

## 6. Data Models

### 6.1 Citizen Session Object (Redis — auto-deleted after 24hr)

```json
{
  "session_id":    "wa_+91XXXXXXXXXX",
  "language":      "hi",
  "created_at":    "2025-01-15T10:00Z",
  "profile": {
    "age":           35,
    "gender":        "Male",
    "state":         "Maharashtra",
    "occupation":    "Farmer",
    "annual_income": 180000,
    "land_acres":    2.5,
    "ration_card":   "Yellow",
    "aadhaar_linked": true,
    "family_size":   4,
    "caste":         "OBC"
  },
  "candidates":    ["101 scheme IDs — pruned with each answer"],
  "questions_asked": ["q_occupation", "q_income", "q_land"],
  "state":         "questioning"
}
```

### 6.2 Scheme Record (PostgreSQL / MongoDB)

```json
{
  "id":         "PM-KISAN-001",
  "name":       "PM-KISAN",
  "ministry":   "Ministry of Agriculture",
  "benefits":   "Rs. 6000/year Direct Benefit Transfer",
  "portal_url": "https://pmkisan.gov.in",
  "eligibility": {
    "occupation":       ["Farmer"],
    "max_income":       200000,
    "min_land_acres":   0,
    "requires_aadhaar": true,
    "states":           "ALL",
    "min_age":          18,
    "max_age":          null
  },
  "documents": ["Aadhaar", "Land Record / Khatian", "Bank Passbook"],
  "apply_steps": [
    "Visit pmkisan.gov.in and click Farmer Corner",
    "Click New Farmer Registration",
    "Enter Aadhaar number and captcha",
    "Fill personal and bank details",
    "Submit — money credited within 4 weeks"
  ],
  "information_gain_params": {
    "key_discriminators": ["occupation", "income", "land_owned"]
  }
}
```

---

## 7. Layer-Wise Implementation Phases

### Phase 01 — Foundation & Data Layer *(Week 1–2)*
- Set up monorepo: FastAPI backend, PostgreSQL/MongoDB, Redis
- Design scheme document schema with JSONB eligibility rules
- Seed database with 75+ government schemes
- Build Scheme Catalogue REST API (CRUD, filters)
- Design citizen session model with Redis TTL
- Create question bank (40+ questions tied to scheme discriminators)
- Write unit-tested eligibility rule engine
- Docker Compose dev environment

**Deliverables:** Running DB with 75+ schemes · Rule engine >80% test coverage · Docker one-command startup

---

### Phase 02 — Core Eligibility & Scoring Engine *(Week 3–4)*
- Build weighted scoring: hard rules (binary) + soft preferences (weighted)
- Implement confidence score: `matched_criteria / total_criteria × 100`
- Scheme ranking (sort by confidence, tie-break by benefit value)
- Candidate set pruning after each answer
- Information gain calculator for question selection
- Decision tree question selector (entropy-based ordering)
- REST APIs: `POST /session/start` · `POST /session/answer` · `GET /session/recommend`
- 10+ simulated full conversation E2E tests

**Deliverables:** Scoring engine >95% accuracy · 3 core session APIs passing

---

### Phase 03 — WhatsApp Integration Layer *(Week 5–6)*
- Register Meta WhatsApp Business account + test number
- Webhook endpoint with Meta signature verification
- Message type handlers: text, buttons, list, audio, document
- WhatsApp response formatter (AI output → WA message format)
- Quick-reply button generator from question options
- OpenAI Whisper API for voice note transcription
- PDF document generator for application checklists
- Full conversation flow: greeting → questions → results → apply guide → HELP
- End-to-end test on real phone

**Deliverables:** Live WhatsApp bot (demo-ready) · Voice pipeline · PDF checklists

---

### Phase 04 — AI Intelligence & Multi-Language *(Week 7–8)*
- LLM API integration (Claude / GPT-4) for natural language question generation
- Context-aware follow-up logic
- Bayesian candidate pruning
- LLM explanation layer ("why recommended")
- Language detection from first message
- Bhashini API integration (10 Indian languages)
- Personalised apply guide generator
- Question path optimisation to <10 average

**Deliverables:** LLM-enhanced engine · 10-language support · <10 avg questions confirmed

---

### Phase 05 — Security, Fraud & Privacy *(Week 9)*
- AES-256 encryption for all profile data
- PII hasher: phone/Aadhaar as SHA-256 only
- Redis auto-expiry: 24hr session TTL
- Isolation Forest anomaly detector
- Consistency checker (implausible combinations flagged)
- Rate limiting: 100 messages/phone/day
- Webhook replay attack prevention (timestamp + nonce)
- Anonymous audit log for analytics

**Deliverables:** Full encryption · Fraud model >88% precision · Security audit report

---

### Phase 06 — Scale, Polish & Launch Readiness *(Week 10–12)*
- Cloud deployment (AWS/Azure) with load balancer + auto-scaling
- Prometheus + Grafana monitoring
- CI/CD with GitHub Actions
- Admin dashboard for scheme CRUD (no-code)
- Bulk notification: alert users of new matching schemes
- Load testing: 10,000 concurrent conversations
- User acceptance testing: 50 real citizens, 5 states
- Web PWA fallback

**Deliverables:** Production live URL · Admin dashboard · Load test passing · UAT report

---

## 8. Project Folder Structure

```
govscheme-whatsapp/
├── backend/                           # Python FastAPI
│   ├── app/
│   │   ├── api/
│   │   │   ├── webhook_whatsapp.py    # ← WhatsApp entry point
│   │   │   ├── webhook_web.py         # ← Web fallback entry point
│   │   │   ├── schemes.py             # Scheme catalogue API
│   │   │   └── admin.py               # Admin scheme management
│   │   ├── core/
│   │   │   ├── adaptive_engine.py     # Question selection (info gain)
│   │   │   ├── eligibility_engine.py  # Rule matching + scoring
│   │   │   ├── fraud_detector.py      # Isolation Forest model
│   │   │   ├── session_manager.py     # Redis session CRUD
│   │   │   ├── whatsapp_client.py     # Meta API wrapper
│   │   │   ├── voice_transcriber.py   # Whisper integration
│   │   │   ├── language_handler.py    # Bhashini API wrapper
│   │   │   └── llm_client.py          # Claude/GPT-4 wrapper
│   │   ├── models/
│   │   │   ├── session.py             # Pydantic session schema
│   │   │   └── scheme.py              # Pydantic scheme schema
│   │   └── db/
│   │       ├── database.py            # SQLAlchemy / PyMongo setup
│   │       └── scheme_orm.py          # ORM/ODM models
│   ├── data/
│   │   ├── schemes/                   # JSON files: one per scheme (75+)
│   │   ├── questions/
│   │   │   └── question_bank.yaml     # All 40+ questions
│   │   └── seed_db.py                 # DB seeder script
│   └── tests/
│       ├── test_eligibility.py
│       ├── test_decision_tree.py
│       └── test_whatsapp_flow.py
├── frontend/                          # React.js (web fallback)
│   └── src/
│       ├── components/ChatWidget/
│       ├── components/SchemeCard/
│       └── pages/Home/
├── ml/
│   ├── train_fraud_model.py
│   └── optimise_question_order.py
├── infra/
│   ├── docker-compose.yml
│   ├── nginx.conf
│   └── .github/workflows/deploy.yml
└── docs/
    ├── PROJECT_IDEA_DOCUMENT.md       # ← This file
    ├── API_Reference.md
    └── WhatsApp_Setup_Guide.md
```

---

## 9. API Reference

| Method | Endpoint | Description | Input / Output |
|---|---|---|---|
| POST | `/webhook/whatsapp` | WhatsApp message handler | Meta webhook payload → sends WA reply |
| POST | `/api/session/start` | Start eligibility session | `{ language, state }` → `{ session_id, first_question }` |
| POST | `/api/session/answer` | Submit answer, get next Q or results | `{ session_id, question_id, answer }` → `{ question \| recommendations }` |
| GET | `/api/schemes` | List all schemes with filters | `?state=MH&category=farmer` → `[schemes]` |
| GET | `/api/schemes/:id` | Full scheme detail | `scheme_id` → `{ full record + steps }` |
| GET | `/api/schemes/:id/checklist` | Download PDF checklist | `scheme_id` → PDF file |
| POST | `/api/eligibility/direct` | Skip questions, direct match | `{ full_profile }` → `{ ranked_schemes }` |
| GET | `/api/admin/analytics` | Usage stats (anonymised) | → `{ sessions, top_schemes, avg_questions }` |
| POST | `/api/admin/schemes` | Add or update a scheme | `{ scheme_record }` → `{ success }` |

---

## 10. Scheme Catalogue (75+ Schemes)

| Category | Count | Key Schemes Covered |
|---|---|---|
| Agriculture & Farmers | 16 | PM-KISAN, Fasal Bima (PMFBY), Kisan Credit Card, Soil Health Card, PM Krishi Sinchai, e-NAM, NFSM |
| Women & Girl Child | 13 | Sukanya Samriddhi, Beti Bachao Beti Padhao, Mahila Shakti Kendra, SWADHAR, Ujjwala Yojana, PMMVY |
| Education & Scholarships | 11 | NSP Scholarships (SC/ST/OBC/Minority), Vidya Lakshmi, Central Sector, Post-Matric, Pre-Matric, NMMS |
| Healthcare | 8 | Ayushman Bharat PMJAY, Janani Suraksha, JSSK, PM Jan Arogya (70+), Rashtriya Bal Swasthya |
| Housing | 7 | PMAY-Gramin, PMAY-Urban, CLSS, SVAMITVA |
| Employment & Enterprise | 10 | PM Mudra, PMEGP, Startup India, PMKVY, Stand Up India, MGNREGS, PM SVANidhi, e-Shram |
| Social Security & Pension | 8 | Atal Pension Yojana, PMJJBY, PMSBY, NSAP (IGNOAPS/IGNWPS/IGNDPS), NPS-Lite |
| SC/ST & Minority Welfare | 7 | Pre-Matric SC/ST, Post-Matric SC/ST, Dr Ambedkar Foundation, Nai Roshni, Seekho aur Kamao |
| Digital & Infrastructure | 5 | PM Gramin Digital Saksharta, BharatNet, JJM, Namami Gange, AMRUT |

> Full eligibility details for all 52 base schemes available in `schemes_eligibility.json`

---

## 11. Security & Privacy Architecture

### Privacy Protections
- **No permanent PII storage** — all session data deleted after 24 hours via Redis TTL
- **No account required** — citizens identified only by hashed phone number (SHA-256)
- **AES-256 encryption** for all data in transit (TLS 1.3) and at rest
- Optional **ZKP (Zero-Knowledge Proof) layer**: prove eligibility without revealing raw values
- **Data minimisation**: collect only fields needed for eligibility assessment
- Indian **IT Act 2000 and PDPB 2023** compliant data handling

### Fraud Detection
- **Isolation Forest ML model** detects statistically anomalous income-asset combinations
- **Consistency rules**: farmer with no land, senior claiming student status — flagged silently
- **Rate limiting**: max 100 messages/phone/day
- **Webhook replay attack prevention** via timestamp + nonce validation
- **Session fingerprinting**: identical probing from multiple numbers flagged
- **Audit trail**: all recommendations logged anonymously for post-hoc review

---

## 12. Demo Presentation Plan for Judge

Structure the **5-minute demo** as a live phone walkthrough on projected screen.

| Time | Segment | What to Show |
|---|---|---|
| 0:00–0:40 | Problem Hook | Show myscheme.gov.in — 500 schemes, complex English forms. "This is what citizens face today." |
| 0:40–1:00 | The Solution | Hold up phone — "What if they could just WhatsApp a number?" Send 'Hi' to bot live. |
| 1:00–2:30 | Farmer Live Demo | Walk through 7-question adaptive flow. Button taps. Reach PM-KISAN 98% in 90 seconds. |
| 2:30–3:00 | Results Deep-Dive | Show ranked results. Tap PM-KISAN → apply guide arrives. Tap link → official portal opens. |
| 3:00–3:20 | Voice Note Demo | Send Hindi voice note. Show transcription working. "Works for users who can't type." |
| 3:20–3:45 | Student Profile | Different answers → completely different scheme set. "Same system, different citizen." |
| 3:45–4:10 | Privacy & Fraud | Show Redis TTL auto-delete in terminal. Show fraud flag on implausible profile. |
| 4:10–5:00 | Architecture Close | Show system diagram. "530M Indians, zero new app, 6 questions, <3 minutes." |

> **Key judge quote:**
> *"We didn't build a new app and ask 530 million Indians to download it. We plugged into an app they already trust. A farmer in rural Bihar, with a ₹5,000 phone on 2G, gets personalised government scheme guidance in Hindi — by voice — in under 3 minutes."*

---

## 13. Competitive Advantage

| Dimension | myscheme.gov.in (Existing) | This System |
|---|---|---|
| Interface | Website form, English-heavy | WhatsApp — 530M users, all languages |
| Questions | 30+ fields shown at once | 6–8 adaptive questions, button taps |
| Languages | English + Hindi only | 10+ regional languages + voice |
| Device requirement | Smartphone + decent internet | Any phone with WhatsApp — works on 2G |
| Recommendations | Binary eligible/not eligible | Ranked with % confidence scores |
| Apply guidance | Redirect link only | In-chat step-by-step + PDF checklist |
| Voice input | Not available | Native WhatsApp voice notes |
| Fraud detection | None | ML anomaly detection layer |
| Privacy | Data stored on server | Session-only, auto-deleted, ZKP layer |

---

## 14. Risk Register & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Meta API approval delay | Low | High | Use sandbox test number for demo |
| LLM API downtime | Low | High | Pre-built rule-based fallback without LLM |
| Scheme data outdated | Medium | Medium | Monthly scraper + admin CMS for updates |
| User submits false data | High | Medium | Fraud detection + advisory disclaimer |
| Regional language accuracy | Medium | Low | Bhashini API (GoI official, 22 languages) |
| Scale: 1M+ users | Medium | Medium | Redis + horizontal FastAPI scaling |

---

## 15. Success Metrics

### Technical KPIs
| Metric | Target |
|---|---|
| Average questions to recommendation | < 8 |
| Eligibility accuracy vs expert review | > 95% |
| API response latency per turn | < 600ms |
| Voice transcription accuracy | > 90% |
| Fraud detection precision | > 88% |
| System uptime | 99.5% |
| Schemes covered at launch | 75+ |

### Business KPIs
| Metric | Target |
|---|---|
| Conversations completed (not abandoned) | > 70% |
| Languages used beyond English/Hindi | > 30% of sessions |
| Voice note users | > 15% |
| Daily active conversations (post-launch) | 10,000 |

---

## 16. Conclusion

The Government Scheme Recommendation System via WhatsApp is a genuinely deployable, scalable solution to one of India's most persistent welfare access problems.

The bottleneck to welfare access is not the schemes — it is **discovery and navigation**. Citizens don't know what they qualify for, and even when they do, the application process defeats them. This system removes both barriers in a single 3-minute WhatsApp conversation.

> **The vision in one sentence**
>
> Every eligible Indian citizen — farmer, student, widow, entrepreneur — discovers and applies for every government scheme they deserve, from the same WhatsApp app they use to talk to their family, in their own language, in under 3 minutes.

---

*GovScheme Assistant — WhatsApp AI Platform | Project Documentation v2.0 | Smart Governance Initiative*
