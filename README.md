# RAGnarok

A deliberately vulnerable RAG-backed support chatbot, built as an AI red
team / security research lab.
> ⚠️ Intentionally insecure by default. Run in an isolated environment
> only. Do not point this at real data or expose it publicly.

## Why this exists

Prompt injection gets most of the attention, but a growing share of
real-world LLM incidents happen one layer down, in the retrieval
pipeline: a poisoned document, a crafted embedding, or a missing tenant
filter on a vector store. OWASP added a dedicated category for this in
2025 (`LLM08:2025 Vector and Embedding Weaknesses`) specifically because
RAG has become the default way enterprises ground LLMs in their own
data, and neither vector databases nor LLMs enforce per-document
permissions on their own.

RAGnarok is "Helios Support" -- a fictional multi-tenant SaaS support bot
serving two customers (Acme Corp, Globex Inc) out of one shared
knowledge base, with a `defense_mode` toggle so you can demonstrate the
same three attacks against both a vulnerable and a mitigated
configuration.

## Architecture

```
app.py                Flask + Socket.IO server, live event streaming
core/
  vectorstore.py       TF-IDF retrieval (pluggable -> dense embeddings)
  rag_engine.py         retrieval -> context assembly -> Claude -> output
  defenses.py           toggle-able ingestion / prompt / output mitigations
  seed_data.py           two-tenant fictional knowledge base
attacks/
  attack1_direct_poisoning.py     indirect prompt injection via a doc
  attack2_semantic_collision.py   keyword-stuffing to hijack retrieval
  attack3_cross_tenant_leak.py    shared-index data leakage across tenants
templates/, static/     terminal-style UI: chat, live pipeline log, admin panel
findings/
  FINDINGS_REPORT.md    sample assessment writeup, framework-mapped
```

Retrieval defaults to TF-IDF (`scikit-learn`) so the lab runs fully
offline with zero model downloads. Set `EMBEDDING_BACKEND=sentence-transformers`
in `.env` to swap in real dense embeddings (`all-MiniLM-L6-v2`) with no
other code changes -- useful if you want to also demonstrate that
semantic-collision attacks aren't a TF-IDF-specific quirk.

## Setup

```bash
git clone <this repo>
cd ragnarok
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
python app.py
```

Open `http://localhost:5000`. The left panel is the customer-facing
chat; the middle panel streams every retrieval/response/ingest event
live; the right panel is the "attacker/admin" surface -- document
ingestion, one-click attack scripts, and a KB browser.

Attacks can also be run headless against any running instance:

```bash
python attacks/attack1_direct_poisoning.py --target http://localhost:5000
python attacks/attack2_semantic_collision.py
python attacks/attack3_cross_tenant_leak.py
```

## The three attacks

| # | Attack | What it shows | Toggle to fix |
|---|--------|----------------|----------------|
| 1 | Direct RAG poisoning | An attacker with low-trust "content editor" access plants a document with hidden instructions. Retrieved into context later, the bot follows them instead of its real policy. | `defense_mode` ON quarantines the doc at ingest (pattern-based screening) and structurally separates retrieved content from instructions in the prompt. |
| 2 | Semantic collision | A keyword-stuffed document ranks in the top-k for queries it has nothing to do with, smuggling injected content into unrelated conversations. | Same ingestion screening catches the injected payload; the collision itself is a retrieval-design problem worth discussing separately (see findings report). |
| 3 | Cross-tenant leak | Acme and Globex share one vector index. Without a hard tenant filter at the retrieval layer, an Acme user's query can pull back Globex's private account notes. | `defense_mode` ON enforces `tenant_id` as a hard filter in `vectorstore.search()`, not just a prompt-level suggestion. |

Toggle `defense_mode` in the top-right of the UI and re-run any attack
to see the before/after -- that comparison is the actual portfolio
artifact; screenshot or screen-record both states.

## Framework mapping

| Attack | OWASP Top 10 for LLM Apps (2025) | MITRE ATLAS |
|---|---|---|
| 1. Direct poisoning | LLM01:2025 Prompt Injection (indirect); LLM08:2025 Vector and Embedding Weaknesses | AML.T0051 LLM Prompt Injection; AML.T0020 Poison Training Data |
| 2. Semantic collision | LLM08:2025 Vector and Embedding Weaknesses (similarity attacks) | AML.T0051 LLM Prompt Injection |
| 3. Cross-tenant leak | LLM02:2025 Sensitive Information Disclosure; LLM08:2025 Vector and Embedding Weaknesses | AML.T0060 Data from AI Services (RAG database retrieval) |

Full writeup with severity ratings and remediation in
[`findings/FINDINGS_REPORT.md`](findings/FINDINGS_REPORT.md).

## Extending this

- Swap in `sentence-transformers` and re-run Attack #2 to show semantic
  collision holds against dense embeddings too, not just TF-IDF.
- Add a fourth tenant and a role-based ingestion permission model, then
  attack *that* instead of the flat trust levels here.
- Wire in an actual moderation/classifier API in `defenses.py` in place
  of the regex-based `scan_for_injection` to discuss detection quality
  and evasion (encoding tricks, unicode homoglyphs, translation).
