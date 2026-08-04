"""
core/rag_engine.py

Ties the vector store, defenses, and Claude together into a single
query/response pipeline, emitting step-by-step events for the live UI
(retrieval results, which docs were used, whether output was flagged).
"""

import os
from anthropic import Anthropic

from .defenses import wrap_context_for_prompt, filter_output

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT_BASE = """You are Helios Support, an AI assistant for a SaaS billing platform.
Answer user questions using ONLY the retrieved knowledge-base context provided below.
If the answer isn't in the context, say you don't know and suggest contacting a human agent.
Keep answers concise (2-4 sentences) unless the user asks for detail."""


class RAGEngine:
    def __init__(self, vectorstore, defense_mode: bool = False, emit=None):
        self.store = vectorstore
        self.defense_mode = defense_mode
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.emit = emit or (lambda event, data: None)

    def query(self, user_message: str, tenant_id: str, other_tenant_markers=None):
        other_tenant_markers = other_tenant_markers or []

        results = self.store.search(
            user_message,
            tenant_id=tenant_id,
            top_k=3,
            enforce_tenant_isolation=self.defense_mode,
        )

        self.emit("retrieval", {
            "query": user_message,
            "defense_mode": self.defense_mode,
            "results": [
                {"id": d.id, "title": d.title, "tenant": d.tenant_id,
                 "trust": d.trust_level, "score": round(s, 4)}
                for d, s in results
            ],
        })

        # Quarantined docs never make it into context, in either mode --
        # quarantine only means something if it's actually enforced.
        usable = [(d, s) for d, s in results if d.trust_level != "quarantined"]
        chunks = [d.content for d, _ in usable]

        # PRIMARY leak signal: did a document belonging to a different
        # tenant actually make it into the prompt context at all? This is
        # computed directly from what was retrieved, so it doesn't depend
        # on the LLM happening to quote text verbatim in its answer -- it
        # catches the leak the moment it enters context, which is the
        # real point of failure (OWASP LLM08 / LLM02).
        context_leak = any(
            d.tenant_id not in (tenant_id, "global") for d, _ in usable
        )

        context_block = wrap_context_for_prompt(chunks, self.defense_mode)
        system_prompt = SYSTEM_PROMPT_BASE + "\n\n" + context_block

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        answer = "".join(b.text for b in response.content if b.type == "text")

        # SECONDARY signal: defense-in-depth output scanning for verbatim
        # leaked text, independent of whether context_leak already fired.
        answer, output_leak = filter_output(answer, tenant_id, other_tenant_markers, self.defense_mode)

        flagged = context_leak or output_leak

        self.emit("response", {
            "answer": answer,
            "context_leak": context_leak,
            "output_leak": output_leak,
            "sources": [{"id": d.id, "title": d.title} for d, _ in usable],
        })

        return {
            "answer": answer,
            "retrieved": [
                {"id": d.id, "title": d.title, "tenant": d.tenant_id,
                 "trust": d.trust_level, "score": round(s, 4)}
                for d, s in results
            ],
            "context_leak": context_leak,
            "output_leak": output_leak,
            "cross_tenant_flag": flagged,
        }
