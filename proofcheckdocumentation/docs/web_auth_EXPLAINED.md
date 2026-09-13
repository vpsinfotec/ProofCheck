# web_auth — 0.3.0 module note

Passwords use salted PBKDF2; tokens use HMAC and expiry. Token parsing bounds input and handles malformed Unicode. Existing-user lookup protects deleted identities. Usernames are normalized before storage/signing. Cookies are HttpOnly/SameSite=Lax and Secure on HTTPS or when configured. Logout does not revoke copied stateless tokens.

Current references:

- [Architecture](../../docs/ARCHITECTURE.md)
- [API](../../docs/API.md)
- [Configuration](../../docs/CONFIGURATION.md)
- [Audit and regression evidence](../../docs/AUDIT.md)
- [Testing](../../docs/TESTING.md)

The supplied implementation and former explanation remain available in Git baseline
`9c9502c`. The current source is authoritative for exact signatures and behavior.
