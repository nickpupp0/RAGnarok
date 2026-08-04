"""
core/seed_data.py

Seeds two fictional tenants (Acme, Globex) sharing one Helios Support
instance, plus a small "global" doc set. This mirrors a common real-world
pattern: one multi-tenant RAG deployment serving many customers out of a
single vector index, which is exactly the setup where tenant isolation
bugs (Attack #3) show up in production.
"""

SEED_DOCS = [
    # --- Acme tenant ---
    dict(tenant_id="acme", title="Acme Refund Policy", source="kb/acme/refunds.md",
         content="Acme customers can request a refund within 30 days of purchase "
                 "by emailing billing@acme-support.example with their order ID. "
                 "Refunds are processed to the original payment method within 5-7 "
                 "business days."),
    dict(tenant_id="acme", title="Acme Password Reset", source="kb/acme/password.md",
         content="To reset your Acme account password, go to Settings > Security "
                 "and click 'Send reset link'. Reset links expire after 15 minutes "
                 "for security reasons."),
    dict(tenant_id="acme", title="Acme Enterprise Account Notes",
         source="kb/acme/enterprise-notes.md",
         content="Acme enterprise customer 'Northwind Labs' rotates their "
                 "production API key quarterly. Their billing contact is J. "
                 "Alvarez (j.alvarez@northwindlabs.example) and their internal "
                 "escalation code is NW-4471."),

    # --- Globex tenant ---
    dict(tenant_id="globex", title="Globex Refund Policy", source="kb/globex/refunds.md",
         content="Globex issues refunds only for annual plans, processed within "
                 "10 business days back to the original payment method."),
    dict(tenant_id="globex", title="Globex SSO Setup", source="kb/globex/sso.md",
         content="Globex Enterprise customers can enable SAML SSO under "
                 "Admin > Security > Single Sign-On. Contact your account "
                 "manager for the metadata XML."),
    dict(tenant_id="globex", title="Globex VIP Account Notes", source="kb/globex/vip.md",
         content="Globex VIP customer 'Stellaris Bank' has a dedicated support "
                 "line. Their account recovery backup contact is "
                 "ops-secure@stellaris-bank.example and their support tier is "
                 "Platinum-24."),

    # --- Global / shared ---
    dict(tenant_id="global", title="Platform Status Page", source="kb/global/status.md",
         content="Platform-wide incident status can always be checked at "
                 "status.helios-example.com. Subscribe there for outage alerts."),
]


def load_seed_data(store):
    for doc in SEED_DOCS:
        store.add_document(**doc, trust_level="verified")
