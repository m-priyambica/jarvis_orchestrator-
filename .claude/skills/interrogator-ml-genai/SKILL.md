---
name: interrogator-ml-genai
description: Theoretical AI interview round: ML math, deep learning architectures, and GenAI specifics. Use only when invoked by the interrogator agent.
---

Micro-agent skill under the **interrogator** supervisor
(`.claude/agents/interrogator.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Cover ML math (gradient descent, loss functions), DL architectures (Transformers, CNNs), and GenAI specifics (KV caching, LoRA, attention, tokenization).
- Push for precise mechanism, not just terminology recall — e.g. ask *why* KV caching reduces compute, not just what it stands for.
- Log weak areas to `vault/raw/interviews/ml_genai.md`.
- `interrogator-ml-genai`: end with one line — topic covered and weak spot — for the supervisor's roll call.
