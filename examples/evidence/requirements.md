# Synthetic requirements

1. The parser must preserve an escaped delimiter inside a field.
2. Existing unescaped delimiter behavior must remain unchanged.
3. The change must include deterministic unit and regression coverage.
4. The workflow must not introduce a runtime dependency or network call.
5. A human must approve each gated stage in the sample path.
