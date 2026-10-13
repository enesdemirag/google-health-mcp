# Security

Report vulnerabilities privately at:

https://github.com/enesdemirag/google-health-mcp/security/advisories/new

Do not include health records, working tokens or client secrets in a report. Provide a synthetic reproduction, affected version and expected impact. Do not open a public issue for a vulnerability that could expose credentials or another user's records.

Operators must keep dependencies updated, serve public traffic over HTTPS, restrict OAuth callback hosts, protect encryption/signing keys and authorization backups, and apply rate limits to public authorization endpoints. Google verification and security assessment are separate from this repository's tests.

The current persistent OAuth storage supports one application process on one host. Do not scale it across workers or hosts without a shared transactional design and concurrency validation.
