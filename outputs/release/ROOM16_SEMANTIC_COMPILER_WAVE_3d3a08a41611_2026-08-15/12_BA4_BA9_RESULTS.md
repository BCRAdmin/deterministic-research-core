# BA4–BA9 Results

| Build section | Result | Primary proof |
| --- | --- | --- |
| BA4 | PASS | all snapshot artifacts parsed; canonical tables hashed |
| BA5 | PASS | all accepted facts typed; unknown IDs fail closed |
| BA6 | PASS | all executable formulas re-evaluated exactly |
| BA7 | PASS | zero Evidence Graph orphan facts |
| BA8 | PASS | zero claims without definition or evidence |
| BA9 | PASS | 3/3 lossless Decision Packet roundtrips |

Pass count: `9`. Pass hash: `f78cac545eeaa9d61407a61cb1f2ada09088b4e7028e5e620a45d4f374f0b1a0`. Side effects: none. Cache: content-addressed. Replay: hash-verified.

Full Research regression: `PASS`. Product verification: `PASS` with only the volatile hardening-age assertion explicitly skipped; the hardening verdict itself was not regenerated. Product TypeScript: `PASS`.
