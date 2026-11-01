# pyai

A small, **purely logic-based** Python assistant. It uses explicit rules, a symbolic per-request purpose seed, a pre-execution safety gate, deterministic skills, and post-task operational scoring. It does not use an LLM, neural network, embeddings, external services, or model training.

## Run

Requires Python 3.10+; there are no third-party dependencies.

```bash
python -m pyai "what is 17 * (8 + 2)?"
python -m pyai --json "convert 5 km to miles"
python -m pyai                 # interactive mode
python -m unittest discover -s tests -v
```

Supported skills: arithmetic (`+`, `-`, `*`, `/`, `//`, `%`, `**`, parentheses), a small set of metric/imperial conversions, and simple ordered plans (for example, `make a plan to organize my desk`). Other requests get an honest explanation of the supported capabilities rather than a fabricated answer.

## Request lifecycle

1. **Dynamic seed:** the request is normalized into a one-use symbolic purpose (goal, constraints, task type, and target delta).
2. **Justification gate:** explicit, auditable rules check the request and a bounded skill execution plan *before* the skill runs. A denied request gets no partial task output.
3. **Anchored execution:** only a validated deterministic skill runs, and its response is kept on the requested goal.
4. **Operational evaluation:** completion, accuracy checks, and efficiency are scored after execution. Scores are diagnostics only; the rule base is not silently trained or changed.

The safety rules are intentionally modest and transparent, not a claim of human-level moral judgment. This toy system is not a substitute for expert review or a security boundary. Run `python -m pyai --help` for CLI options.
