# Stage 3b — Grounded Writing and Client Narratives

## Context Pack Contract

Each client can have multiple immutable content versions. An Account Manager creates the next version; existing versions remain available for audit and draft provenance. Each version stores brand voice, audience segments, offers, approved fact candidates, prohibited wording, and compliance notes.

Fact records contain an ID, exact text, source reference, expiry date, approving client user, and approval timestamp. New versions reset approvals. A separate client fact-review view supports explicit approval; the approved-facts view returns only facts approved by that user.

## Generation Interface

`CopyProvider.generate(pack, campaign, fact_ids, format)` returns a brief, cited copy, claim references, and review flags. The default implementation is `TemplateProvider`. No network provider is configured or called.

The template combines approved fact variables with controlled non-factual framing. Brand voice, audience, objective, channel, and compliance notes are included in the brief for review. Offers do not become promotional claims unless represented by approved facts.

Starter formats: Headline, Primary Text, CTA, TV Script, Outdoor Script. Character limits are project defaults, not claims about vendor platform limits. Future adapters should supply current channel-specific constraints through explicit configuration.

## Claim Review

- Every factual passage must match an approved fact and include `[fact:id]`.
- Unknown, inconsistent, or missing references are flagged.
- Expired facts and facts lacking client approval are flagged.
- Prohibited wording is detected case-insensitively.
- Unsupported text and format overflow are flagged.
- Generated content enters Creative Review as **Draft — Generated**.
- Flagged drafts cannot be submitted. Approval rechecks expiry and claims.
- Generated copy and brief edits require regeneration; ordinary untraced manual drafts remain a separate operational workflow.

Prohibited wording detection is literal matching, not a semantic compliance classifier. The limited template engine is not a guarantee of legal compliance.

## Narrative Contract

Reports are generated from a campaign's stored metrics and a Context Pack version. A snapshot preserves amounts, counts, derived ratios, date range, currency, source, timezone, attribution, and capture timestamp. No user-supplied numeric prose is accepted.

Context facts containing numeric characters are omitted from narrative fact paragraphs. Numerical performance claims come only from the metric snapshot; source references, version numbers, and expiry dates remain provenance metadata.

The first-release narrative uses fixed, cautious interpretation and recommendation templates. Reports render approved fact text with source and expiry metadata, followed by:

1. **Results (facts)**
2. **Interpretation**
3. **Recommendations**
4. **Open questions**

Approval sequence: **Draft → Account Approved → Client Approved**. A changes request ends that version's approval path; prepare a revised report. Clients cannot access draft reports or draft PDFs. Later changes to campaign metrics require a new report and approval cycle.

The first release supports in-app review and PDF export. Slide-deck export and explicitly configured LLM adapters are future work. Reports and drafts are never automatically published.
