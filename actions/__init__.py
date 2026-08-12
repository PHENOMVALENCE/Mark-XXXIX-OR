"""Tool implementations.

Each module exposes one callable with a ``(parameters, ..., player=None)``
signature, invoked by main.py's dispatch chain and by agent/executor.py.

Migrating toward the typed registry described in docs/ARCHITECTURE.md §7,
where a tool declares its own schema, permission level, and timeout.
"""
