# Permissions

| Capability | Administrator | Account Manager | Campaign Specialist | Creative | Client |
| --- | --- | --- | --- | --- | --- |
| Client/order creation and editing | Yes | Yes | No | No | No |
| Employee information | Yes | Yes | No | No | No |
| Campaign editing and CSV import | Yes | Yes | Yes | No | No |
| Task editing | Yes | Yes | Yes | Yes | No |
| Creative editing | Yes | Yes | No | Yes | No |
| Creative approval | Yes | Yes | No | No | Own client |
| Context Pack editing | No | **Yes** | No | No | No |
| Template copy generation | No | Yes | No | Yes | No |
| Fact approval | No | No | No | No | Own client |
| Approved-facts client view | No | No | No | No | Facts that user approved |
| Prepare report | No | Yes | Yes | No | No |
| Account approval | No | **Yes** | No | No | No |
| Client report approval | No | No | No | No | Own client, after Account approval |

Internal staff may read context/report content in their own agency except where employee restrictions apply. Clients cannot browse the Context Pack itself; they receive distinct fact approval requests and a filtered approved-facts view.

Every record reference is checked against agency scope. Client access also checks client scope and review status. Hiding a button is a convenience; the API performs authorization independently.
