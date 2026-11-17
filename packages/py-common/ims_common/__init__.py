"""Runtime helpers shared by Core, Workers, the Platform Service and the database pipeline.

Unlike ``ims_contracts`` (pure wire models), this package holds small pieces of behaviour that
every deployable needs and that must not drift between them: ID generation, the secrets-store
and object-store ports, Ed25519 token signing, problem-details error handling and logging.
"""
