"""Database pipeline: the only executor of provisioning DDL, schema migrations and partition
maintenance (AD-13, AD-29, LD-85).

It runs in CI/CD under a non-human identity, which is the only identity able to read migration
credentials. No service imports this package at runtime: the Platform Service triggers and
records runs but holds no DDL or data credentials.
"""
