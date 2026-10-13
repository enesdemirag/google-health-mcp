# Data handling

This page describes the software. Each hosted operator needs their own privacy policy with their identity, hosting region, contact details, retention and deletion rules, and assistant recipients.

## What the server reads and stores

You authorize an assistant connection and choose Google Health read permissions. The server reads your requested records, converts them in memory and sends the results to that assistant. The assistant's privacy, retention and training settings apply separately.

The server encrypts Google access and refresh credentials, MCP credential mappings, client registrations and temporary OAuth state in its authorization volume. It stores no health measurements or result cache. The running server can still read the records needed to answer a request.

Operators should not log authorization URLs, tokens, health values or request and response bodies. Readiness checks do not call Google. Repository fixtures and examples use synthetic data.

## Disconnect

1. Remove the MCP connector from your assistant.
2. Revoke the application's access in [Google Account connections](https://myaccount.google.com/connections).
3. Ask the operator to delete remaining authorization references and applicable backups.

Removing a connector does not revoke the Google grant. The server has no per-user deletion UI or RFC 7009 revocation endpoint. References expire, but operators must handle storage cleanup and backup deletion. A public service needs a per-user deletion process.

## Google Limited Use

Operators must follow the [Google Health API Developer and User Data Policy](https://developers.google.com/health/policies/health-api-developer-user-data-policy), including Limited Use requirements. Explain the health or fitness purpose and obtain consent before sending records to an assistant or another third party.

Google requires a visible disclosure during authorization, beyond the privacy policy link. Self-hosting and the MIT license do not remove Google's verification or security-assessment requirements.
