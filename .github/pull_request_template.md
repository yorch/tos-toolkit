## What this changes

<!-- One or two sentences. -->

## Why

<!-- The failure it prevents, or the use case it serves. -->

## Layer check

- [ ] If this adds a lint rule: it is in the correct layer. Layer 1 = true of
      ThinkScript anywhere (always on). Layer 2 = house convention
      (profile-gated). Unsure counts as Layer 2.

## Verification

<!-- Tick what applies. Be honest — "not verified" is acceptable and expected. -->

- [ ] `python -m pytest -q` passes
- [ ] New or changed rules have a fixture in `tests/test_checks.py`
- [ ] No thinkorswim code, decompiled output, or reconstructed grammar was added
      (see `docs/adr/0004`)
- [ ] Any platform behaviour claim is either verified by a paste-test or marked
      unverified

## Reviewer

<!-- If you ran the adversarial gate, paste the verdict line. -->

```text
VERDICT:
```
