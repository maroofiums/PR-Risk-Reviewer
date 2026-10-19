# Security Checks

Use this when the diff touches authentication, authorization, user input, file handling, serialization, secrets, network calls, or when `diff_stats.py` reports content findings of type `auth_bypass_marker`, `possible_hardcoded_secret`, `shell_injection_risk`, `unsafe_deserialization`, `tls_verification_disabled`, or `dynamic_exec`.

Contents: access control, input handling, secrets, transport and crypto, data exposure, how to report.

## Access control
- Was an authentication or authorization check removed, loosened, or moved after the action it protects?
- New endpoint: does it enforce the same auth as its siblings? Compare with neighboring routes.
- Object-level access: does the code verify the requesting user owns or may access the specific record, not just that they are logged in? (Insecure direct object reference.)
- Role checks: are they done server-side, and on every code path including error and fallback branches?
- Default permission changed to a more permissive value?

## Input handling
- SQL built by string concatenation or f-strings instead of parameters.
- User input reaching a shell command, file path (path traversal), template, regex (denial of service), or redirect URL (open redirect).
- Deserialization of untrusted data (pickle, unsafe YAML, marshal).
- Missing size or type limits on uploads and request bodies.
- Validation moved from the server to the client only.

## Secrets
- Hardcoded keys, tokens, passwords, connection strings, private keys.
- Secrets written to logs, error messages, or responses.
- `.env` files or credentials committed.
- Treat any real-looking secret in a diff as compromised: it exists in git history even if removed later. Recommend rotation.

## Transport and cryptography
- TLS verification disabled, certificate checks skipped.
- Home-made crypto, weak hashes for passwords (MD5, SHA1, unsalted), predictable tokens (non-cryptographic random), hardcoded IVs or salts.
- Token expiry lengthened, signature verification skipped (`verify_signature=False`, `alg: none` accepted).

## Data exposure
- New response fields that include sensitive data (emails, tokens, internal IDs, hashed passwords).
- Verbose error messages or stack traces returned to clients.
- Logging of personal data or credentials.
- CORS opened to all origins on an authenticated API; cookies without Secure/HttpOnly/SameSite.

## How to report
- State the concrete attack scenario in one sentence: who can do what they could not before.
- Cite `path:line`.
- If exploitability depends on code outside the diff, say so and mark it "unverified".
- Do not provide working exploit payloads. Describe the weakness and the fix.
- A confirmed exploitable weakness reachable by a low-privilege or unauthenticated user is Critical in the overall verdict.
