# Local Demonstration

## Operations

1. Sign in as the administrator with your configured demo password.
2. Open **Clients** and add a synthetic organization with a contact and follow-up date.
3. Open **Orders**, select the client, and add deliverables, budget, channel, and deadline.
4. Edit the order through Draft → Confirmed → In Progress.
5. Open **Tasks**, assign a team member, and link the order ID.
6. Create a creative draft, then change its status to Submitted.
7. Use the client workspace to approve the deliverable or request changes.
8. Enter a campaign's reporting-period metrics or import a CSV exported from the campaign table.
9. Review the dashboard's comparable groups and export a filtered campaign CSV.

## Grounded Context

1. Sign out and sign in as `manager@example.test`.
2. Open **Context & reports** and create a Context Pack for the seeded client.
3. Enter brand voice, audience segments, offers, prohibited wording, and compliance notes.
4. Use a fact JSON array such as the following, replacing the source with an appropriate synthetic reference:

```json
[{"id":"service_area","text":"Service is available in Lahore.","source":"Synthetic service register, section 1","expires":"2099-12-31"}]
```

5. Sign in as `client@example.test` and approve the fact in **Fact approval requests**.
6. Verify it appears in **Facts you approved**.
7. Return as the Account Manager, choose the pack and campaign, and generate Primary Text using `service_area`.
8. Open **Creative review**. The generated draft has exact claim references and the status **Draft — Generated**.
9. Review the draft, submit it, and complete the normal client approval flow.
10. Prepare a Monthly Report. Review the numbers and provenance in the in-app view.
11. Approve as the Account Manager, then approve as the client.
12. Export the PDF. It contains the same stored metric snapshot and separate interpretation, recommendations, and open questions.

Use only synthetic information for this walkthrough. Nothing is sent or published externally.
