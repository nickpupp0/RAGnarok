# Running the RAGnarok Attacks

A quick walkthrough for setting up the lab and demoing each of the three
attacks, defended vs. undefended.

## 1. Install and configure

Unzip the project, then install dependencies:

```bash
cd ragnarok
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Copy the env template and add your key:

```bash
cp .env.example .env
# then edit .env and set ANTHROPIC_API_KEY=your_key_here
```

## 2. Start the server

```bash
python app.py
```

Open `http://localhost:5000`. The knowledge base seeds itself
automatically with fictional Acme and Globex support docs -- no extra
setup needed.

## 3. Pick an attack surface

In the right-hand panel of the UI, click the **Attacks** tab. Each
button runs the matching script from `attacks/` against the live
instance and streams its output into the **Live pipeline log** panel in
the middle of the screen.

## 4. Run Attack 1 -- Direct RAG Poisoning

Click **Attack 1 — Direct RAG Poisoning**. This ingests a document
containing a hidden instruction, then asks the bot a normal refund
question as a simulated customer.

Watch the log for:
- the poisoned document being retrieved into context
- the bot's answer soliciting a card number and CVV instead of following the real refund policy

## 5. Run Attack 2 -- Semantic Collision

Click **Attack 2 — Semantic Collision**. This ingests a keyword-stuffed
document, then fires four unrelated queries (password reset,
cancellation, refund, billing) at the bot.

Watch for the stuffed document showing up in the top-3 retrieved results
for queries it has nothing to do with, and the injected product
recommendation leaking into the bot's answers.

## 6. Run Attack 3 -- Cross-Tenant Leak

Click **Attack 3 — Cross-Tenant Leak**. This asks a series of questions
from an Acme session that are semantically close to Globex's private
account notes.

Watch for the `context_leak` flag firing in the log -- that means a
Globex-tenant document was retrieved into an Acme-tenant conversation.

## 7. Toggle defense_mode and re-run

Flip the switch in the top-right corner from **VULNERABLE** to
**DEFENDED**, then re-run any of the three attacks above.

What changes:
- **Attack 1**: the poisoned doc gets quarantined at ingest and never reaches retrieval
- **Attack 2**: the same ingestion screening catches the stuffed payload
- **Attack 3**: tenant isolation is enforced as a hard filter at the retrieval layer, so the cross-tenant doc is never retrieved in the first place

This before/after comparison is the actual demo -- screenshot or
screen-record both states for a portfolio piece or interview walkthrough.

## 8. Run headless from a terminal (optional)

With the server running, each attack can also be driven from the
command line instead of the UI -- useful for a scripted demo or a
repeatable CI-style check:

```bash
python attacks/attack1_direct_poisoning.py
python attacks/attack2_semantic_collision.py
python attacks/attack3_cross_tenant_leak.py
```

Add `--target http://host:port` if the server isn't running on the
default `http://localhost:5000`.

## Where to go next

- `README.md` -- architecture overview and framework mapping
- `findings/FINDINGS_REPORT.md` -- full assessment writeup with severity ratings, impact, and remediation for all three findings
