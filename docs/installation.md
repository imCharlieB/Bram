# Installing

BRAM is not ready for general use. The current version only watches and logs; see [BRAM Server](server.md). The HA App is not built yet. This is the plan.

1. **BRAM integration**, through HACS. Needs Home Assistant 2026.8 or later.
2. **BRAM Server**, one of:
   - **HA App**: for Home Assistant OS or Supervised. Simplest, but it cannot report that the Home Assistant machine has failed.
   - **Docker Compose**: any always-on machine. Required for Home Assistant Container.
3. **A model**, such as one in Ollama. See [Testing your model](benchmark.md).

No separate database is needed. Memory is optional; see [Design](../SPEC.md).
