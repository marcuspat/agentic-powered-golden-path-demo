"""Infrastructure adapters and ACLs.

This layer implements domain ports against concrete external systems
(GitHub, OpenRouter, kubectl, the local filesystem, …). It is the only
place foreign types appear; see ``docs/ddd/11-anti-corruption-layers.md``.
"""
