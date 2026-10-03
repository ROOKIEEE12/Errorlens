# Adding a rule (≈10 minutes)
1. Save a real failing log in `samples/` (secrets are fine — redaction runs first).
2. In `errorlens/core/rules_extra.py` write a builder `(lines, i, match, ctx) -> RuleResult`:
   root cause, **exactly 3** fix steps, verify commands, `(risk_level, reason)`, confidence, and a stable `key`
   (the part of the error that identifies it — e.g. the module name — NOT paths, ports or hashes).
3. Register `Rule(id, framework, compiled_regex, builder, priority)` in `EXTRA`.
   - Lower priority number wins ties on the same line. The **earliest** matching line always wins (first meaningful failure).
   - Consequence lines (`ELIFECYCLE`, `exited with 1`, …) belong in `CASCADE` in `rules.py`, never as rules.
   - `last_resort=True` rules only fire if nothing else matched (used for the generic Next.js prerender message).
4. Add the sample to `tests/test_rules_pack.py` (parametrized) and run `pytest`.
