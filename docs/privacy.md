# Data handling, disconnect and operator policy

This document describes the software. It is not a blanket privacy policy for every operator who self-hosts it. A hosted operator must identify themselves, their hosting region, contact, retention/deletion procedures and selected assistant recipients in their own policy and authorization disclosure.

## Data flow

The user authorizes a particular assistant connection and selects Google Health read permissions. The MCP server uses that user's Google authorization to read the requested records, normalizes them in memory and returns results to that assistant. The assistant/AI provider receives those requested health results; its own privacy, retention and training settings apply independently.

The software stores encrypted Google access/refresh credentials, MCP credential mappings, client registrations and temporary OAuth state in its persistent authorization volume. It does not persist health measurements or create a health-result cache. Encryption does not prevent the operating server from reading records needed to answer a request.

Do not log authorization URLs, tokens, request/response bodies or health values. Readiness probes do not access Google records. All repository fixtures and examples are synthetic.

## Disconnect

1. Remove or disconnect the MCP connector in the assistant.
2. Revoke the operator application's access through your [Google Account third-party connections](https://myaccount.google.com/connections).
3. Contact the operator to request deletion of remaining encrypted authorization references and applicable backups. Revoking at Google and deleting stored references are separate actions.

The current server does not advertise an RFC 7009 revocation endpoint, automatically revoke a Google grant when an assistant disconnects, or expose a per-user account-deletion UI. Stored references have expiration times; operator-managed cleanup and backup retention still matter. An operator must provide an appropriate deletion procedure before running a public shared service.

## Google Limited Use

Use of information received from Google Health API must adhere to the [Google Health API Developer and User Data Policy](https://developers.google.com/health/policies/health-api-developer-user-data-policy), including its Limited Use requirements. Operators must make their own accurate disclosure and obtain consent before transferring health results to an assistant or another third party for the disclosed health/fitness features.

Google requires prominent disclosure during authorization, not only a link to a privacy policy. Self-hosting or using an MIT-licensed server does not remove Google's access, use, verification or security-assessment requirements.
