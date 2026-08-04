# Helios Support (RAGnarok Lab) -- RAG Security Assessment

**Assessment type:** AI/LLM application security review (retrieval-augmented generation)
**Target:** Helios Support multi-tenant chatbot (fictional, self-hosted lab)
**Frameworks referenced:** OWASP Top 10 for LLM Applications (2025), MITRE ATLAS
**Report status:** Sample writeup for portfolio purposes -- findings are from the accompanying RAGnarok lab, not a live system.

---

## 1. Executive Summary

This assessment evaluated the retrieval-augmented generation (RAG)
pipeline behind Helios Support, a multi-tenant SaaS support chatbot.
Testing focused on the trust boundary between externally-influenceable
knowledge-base content and the LLM's context window, and on tenant
isolation within the shared vector index.

Three findings were confirmed, all present in the default ("vulnerable")
configuration and all mitigated when `defense_mode` is enabled:

| ID | Finding | Severity | Status (defended config) |
|----|---------|----------|---------------------------|
| RAG-01 | Indirect prompt injection via unvetted document ingestion | **High** | Mitigated |
| RAG-02 | Retrieval ranking manipulation via keyword stuffing | **Medium** | Mitigated |
| RAG-03 | Cross-tenant data disclosure via shared vector index | **Critical** | Mitigated |

The unifying root cause across all three findings is the same: **the
application treats retrieval as a purely relevance-ranked operation and
enforces trust and tenancy boundaries only at the prompt level (i.e., by
asking the model nicely), rather than as hard controls in the retrieval
and ingestion layers.** This is consistent with OWASP's rationale for
introducing `LLM08:2025 Vector and Embedding Weaknesses` as a dedicated
category: RAG has become the default pattern for grounding LLMs in
proprietary data, and neither vector databases nor LLMs enforce
per-document access control on their own -- the application has to.

---

## 2. Scope & Methodology

**In scope:** the RAG ingestion pipeline, vector retrieval logic, prompt
construction, and generated output for the Helios Support chatbot
(`app.py`, `core/vectorstore.py`, `core/rag_engine.py`).

**Out of scope:** the underlying Claude API/model itself, network/infra
hardening, and authentication to the admin ingestion endpoint (assumed,
for this assessment, to be reachable by a low-trust "content editor"
role -- a realistic assumption for support-KB CMS workflows).

**Methodology:** manual testing plus three repeatable proof-of-concept
scripts (`attacks/attack1_direct_poisoning.py`,
`attack2_semantic_collision.py`, `attack3_cross_tenant_leak.py`), each
run against both the default and `defense_mode`-enabled configurations
to confirm the finding and validate the fix.

---

## 3. Findings

### RAG-01 -- Indirect Prompt Injection via Unvetted Document Ingestion

**Severity:** High
**OWASP:** LLM01:2025 Prompt Injection (indirect); LLM08:2025 Vector and Embedding Weaknesses
**MITRE ATLAS:** AML.T0051 (LLM Prompt Injection), AML.T0020 (Poison Training Data)

**Description**
The knowledge-base ingestion endpoint accepts documents from a low-trust
role (content editor / public submission form) with no screening of
their content before they become eligible for retrieval. A document
containing an embedded instruction ("SYSTEM OVERRIDE: ignore previous
instructions...") is treated identically to legitimate support content.
When later retrieved into a user-facing conversation, the model followed
the embedded instruction rather than its actual policy, in this case
soliciting a customer's card number and CVV under the guise of "refund
verification."

**Impact**
An attacker who can influence any document that ends up in the
knowledge base -- a compromised CMS account, a public feedback form the
bot ingests from, a scraped external page -- can steer the bot's
behavior for every user who asks a related question, without ever
interacting with the chat interface directly. This is a stored,
persistent attack, not a one-off prompt.

**Reproduction:** `python attacks/attack1_direct_poisoning.py`

**Remediation**
- Screen documents at ingest time for injection-style phrasing before
  they're eligible for retrieval (implemented in `defenses.sanitize_on_ingest`).
- Structurally separate retrieved content from instructions in the
  system prompt (explicit untrusted-data delimiters plus an instruction
  to treat retrieved text as data, not commands) -- raises the bar even
  against payloads that evade pattern-based screening.
- Require human review before high-privilege KB changes (e.g. refund
  policy) go live, regardless of automated screening results.

---

### RAG-02 -- Retrieval Ranking Manipulation via Keyword Stuffing

**Severity:** Medium
**OWASP:** LLM08:2025 Vector and Embedding Weaknesses (similarity attacks)
**MITRE ATLAS:** AML.T0051 (LLM Prompt Injection)

**Description**
A document does not need to be topically relevant to the query it gets
retrieved for. A document stuffed with terms spanning many unrelated
support topics ranked in the top-3 results for 4/4 unrelated test
queries (password reset, cancellation, refund, billing), pulling an
injected third-party product recommendation into conversations that had
nothing to do with the document's ostensible subject.

**Impact**
This is a lower-severity variant of RAG-01 in terms of payload (a
recommendation, not a data-exfiltration attempt), but it demonstrates
that relevance-only ranking is trivially gameable independent of the
injection-screening fix for RAG-01 -- the same technique could deliver a
more damaging payload. It also generalizes beyond TF-IDF: dense
embedding models are similarly vulnerable to paraphrase/near-duplicate
phrasing that lands close in vector space, so switching retrieval
backends alone does not close this gap.

**Reproduction:** `python attacks/attack2_semantic_collision.py`

**Remediation**
- Same ingestion screening as RAG-01 catches this specific payload.
- Independent of screening: consider a relevance-score floor or
  provenance/trust weighting in ranking, so documents don't compete
  purely on similarity score regardless of source trust level.
- Log and periodically review documents that get retrieved across an
  unusually broad range of unrelated queries -- that pattern is itself
  a detection signal.

---

### RAG-03 -- Cross-Tenant Data Disclosure via Shared Vector Index

**Severity:** Critical
**OWASP:** LLM02:2025 Sensitive Information Disclosure; LLM08:2025 Vector and Embedding Weaknesses
**MITRE ATLAS:** AML.T0060 (Data from AI Services -- RAG database retrieval)

**Description**
Acme and Globex are served from one shared vector index. Tenant scoping
was enforced only via a system-prompt instruction, not as a hard filter
at the retrieval layer. A query from an Acme session ("Do you have any
notes on Stellaris Bank's account?") retrieved Globex's private VIP
account notes -- including a support contact email and internal support
tier -- directly into the Acme session's context.

**Impact**
This is the most severe finding: it is a direct customer-data breach
across tenant boundaries in a production-shaped multi-tenant SaaS
pattern, requiring no injection payload or malicious document at all --
just a normally-phrased question that happens to semantically overlap
with another tenant's content. OWASP calls this out explicitly:
neither vector databases nor LLMs natively enforce per-tenant
permissions, so anything embedded into a shared index is reachable by
any tenant's queries unless the application enforces isolation itself.

**Reproduction:** `python attacks/attack3_cross_tenant_leak.py`

**Remediation**
- Enforce `tenant_id` as a hard filter at the retrieval layer itself
  (implemented in `vectorstore.search(enforce_tenant_isolation=True)`),
  not as a prompt-level instruction the model is trusted to follow.
- Prefer per-tenant index partitioning (separate collections/namespaces)
  over a single shared index with a metadata filter, where the vector
  DB supports it -- removes an entire class of "forgot to apply the
  filter" bugs.
- Add output-side scanning as defense-in-depth for any content that
  still reaches generation despite retrieval-layer controls (implemented
  in `defenses.filter_output`, though this assessment's primary fix is
  upstream at retrieval).

---

## 4. Summary of Remediation Status

All three findings were re-tested with `defense_mode` enabled and
confirmed mitigated: ingestion-time screening quarantines injected
documents before they're retrievable, retrieved content is structurally
separated from instructions in the prompt, and tenant isolation is
enforced as a hard filter at the retrieval layer rather than a
prompt-level suggestion.

## 5. Notes on Methodology Limitations

The ingestion-screening mitigation is pattern-based and will not catch
obfuscated payloads (encoding tricks, unicode homoglyphs, translation,
or instructions phrased without the specific trigger words tested here).
It should be treated as one layer in a defense-in-depth strategy, not a
complete solution -- the structural prompt-separation and retrieval-layer
tenant enforcement are the more durable fixes of the three, since they
don't depend on anticipating every possible injection phrasing.
