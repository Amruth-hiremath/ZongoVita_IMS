"""Event types the identity module writes to the outbox (AD-51).

These are internal: Workers consume ``iam.user.created`` to activate the Login Directory entry
(LLD 6.3). They are not in the published event catalogue (LLD section 13).
"""

USER_CREATED = "iam.user.created"
API_CLIENT_CREATED = "iam.api_client.created"
