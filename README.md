# pyai

A small, **logic-first** Python assistant. Its default mode uses explicit rules, a symbolic per-request purpose seed, a pre-execution safety gate, deterministic skills, and post-task operational scoring. It does not require an LLM, neural network, embeddings, external services, or model training. An optional simulated-agent demo exercises a bounded planner–critic–synthesizer workflow without making model calls.

## Run

Requires Python 3.10+; there are no third-party dependencies.

```bash
python -m pyai "what is 17 * (8 + 2)?"
python -m pyai --json "convert 5 km to miles"
python -m pyai --mode simulated-agents "make a plan to organize my desk"
python -m pyai                 # interactive logic-only mode
python -m unittest discover -s tests -v
```

Supported logic-mode skills: arithmetic (`+`, `-`, `*`, `/`, `//`, `%`, `**`, parentheses), a small set of metric/imperial conversions, and simple ordered plans. Other requests get an honest explanation of supported capabilities rather than a fabricated answer.

`--mode simulated-agents` runs a fixed three-role workflow (planner, critic, synthesizer) using deterministic stand-ins. It is an offline orchestration demo, **not** a live LLM. PyAI creates one symbolic purpose seed before the safety gate and passes the same immutable seed—including success criteria, constraints, non-goals, and exploration guidance—to every role. It gates every agent result, imposes a call limit, and never gives agents direct tool execution access. Logic-only mode remains the default.

## Request lifecycle

1. **Dynamic seed:** the request becomes a one-use symbolic purpose with a goal, success criteria, constraints, non-goals, and guidance to explore relevant alternatives without forcing tangents.
2. **Justification gate:** explicit, auditable rules check the request and purpose before any skill or simulated agent runs. A denied request gets no partial task output.
3. **Anchored execution:** only a validated deterministic skill runs, and its response is kept on the requested goal.
4. **Operational evaluation:** completion, accuracy checks, and efficiency are scored after execution. Scores are diagnostics only; the rule base is not silently trained or changed.

The safety rules are intentionally modest and transparent, not a claim of human-level moral judgment. This toy system is not a substitute for expert review or a security boundary. Run `python -m pyai --help` for CLI options.
