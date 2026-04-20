# LitOrbit — Future Roadmap

## Phase 2 complete

Corpus migrated to Gemini's `task_type="SEMANTIC_SIMILARITY"` embedding space; two deterministic hard-reject filters shipped (title-only negative keywords, abstract-quality guard); admin tuning panel with signal histograms deployed; threshold suggestion script available.

Phase 3 items (only worth doing if you still see leakage after Phase 2 settles):

- **Methods-vs-applications two-track profile** using the `tags` field populated by Phase 1 Chunk 3. A paper passes if it matches *either* your methods anchors OR your applications anchors. Belt-and-braces for cross-disciplinary ML papers. Activate this only if Phase 2's negative keyword layer is still rejecting methods papers you wanted to see.
- **Active-learning surfacing:** when the gate is uncertain (positive ≈ negative, effective_score near threshold ± 0.05), proactively present these papers for rating. Turns borderline cases into training examples.
- **Author-watch list:** for 9–10 rated papers, add an option to monitor future publications by the same authors across the corpus.

---

## Layer 2: Semi-Agentic (6-12 months)

### LangGraph Integration

Add `backend/app/agents/` directory with LangGraph StateGraph agents that observe user behaviour and take autonomous actions:

```python
# agents/research_monitor_agent.py
# LangGraph StateGraph that:
# 1. Observes: user has rated 5+ papers in "battery degradation" category >= 8/10
# 2. Reasons: this user has strong interest in this sub-topic
# 3. Acts: automatically expand Scopus query to include related journals
#    (e.g., Electrochimica Acta, Journal of The Electrochemical Society)
# 4. Notifies user: "I noticed you rate degradation papers highly.
#    I've started monitoring 2 additional journals. Approve?"
```

### Agent Tools (Already Built)

The Layer 2 agent uses existing service functions:

- `ieee_client.search(query, publication_number)` — IEEE discovery
- `scopus_client.search(issn, keywords)` — Scopus discovery
- `rss_client.fetch(url)` — RSS discovery
- `summariser.generate(paper)` — AI summary generation
- `email_digest.send(user, papers)` — Email delivery
- `scorer.score(paper, user_profile)` — Relevance scoring

### Interest Model Upgrade

Replace the simple weight vector with embeddings-based user model:

- Store embeddings in `pgvector` extension in Supabase
- Use Claude to generate paper embeddings from title + abstract
- Cosine similarity for relevance instead of keyword matching
- Continuous learning from ratings feedback

## Layer 3: Full Agentic (12-24 months)

### Natural Language Goal Execution

Open-ended queries processed by a multi-agent system:

**Example queries:**

- *"Find papers that challenge the methodology in my 2023 Applied Energy paper"*
  → Agent reads the user's paper, identifies claims, searches across journals and citation networks, returns a briefing

- *"Prepare a literature review summary for Sahand's thesis chapter on BESS degradation forecasting"*
  → Agent queries across journals, groups by sub-theme, generates structured literature review document

- *"Alert me if any paper cites our FRESNO project results"*
  → Agent sets up persistent citation monitoring via Semantic Scholar or OpenCitations API

### Multi-Agent Framework

AutoGen or CrewAI multi-agent system with specialised roles:

| Agent | Role |
|---|---|
| Research Agent | Discovery + search across APIs and citation networks |
| Analysis Agent | Synthesis + comparison of paper methodologies and findings |
| Writing Agent | Summary generation + literature review drafting |
| Orchestrator Agent | Interprets user goals, delegates to other agents |

### Natural Language Interface

Add `/chat` route to frontend — a text input where admin and researchers type research goals and the agent responds with findings:

```
User: "What's the latest on V2G integration with frequency regulation markets?"
Agent: Found 8 relevant papers from the last 3 months. Here's a summary...
       [structured briefing with citations]
```

### Design Constraint

All agent tools must be the same FastAPI service endpoints already built. The agent framework is purely an orchestration layer on top of existing services. This ensures:

- No architectural changes required
- Agents are testable via the same API
- Existing non-agentic features continue to work independently
- Gradual rollout: agents enhance but don't replace the core pipeline
