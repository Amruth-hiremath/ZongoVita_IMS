"""Core kernel: what every request and job passes through (LLD section 2).

Tenant context, licence state gate, database routing, authentication, the unit of work with
audit and outbox, idempotency and typed errors. Business modules import the kernel; the kernel
never imports a business module (LD-01).
"""
