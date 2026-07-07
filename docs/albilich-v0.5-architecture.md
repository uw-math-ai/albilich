# Albilich v0.5 Architecture

Albilich v0.5 is a reset branch. It adds CAS as a direct agent tool, not as a separate research pipeline.

## Core Shape

- The generation runner stays close to upstream `run_example.sh`.
- The verification API stays compatible with upstream `/health` and `/verify`.
- Both agents receive the same CAS lifecycle MCP tools.
- CAS state is process-local to the MCP server and controlled by the agent through `cas_start`, `cas_poll`, and `cas_stop`.

## CAS Tool Interface

- `discover_cas_backends` reports availability for `sage`, `gap`, `macaulay2`, `singular`, and `lean`.
- `cas_start` writes the supplied script to an isolated temporary session directory and starts the backend immediately. If `working_directory` is provided, the backend process runs there, but the generated CAS script still stays in the temporary session directory.
- `cas_poll` returns status, elapsed time, return code, and new stdout/stderr since the previous poll.
- `cas_stop` terminates a running session.

Agents are responsible for deciding whether a run is useful enough to continue. The tool layer does not impose the v1 requested-experiment gate, claim ledger, computation ledger, pattern miner, or experimentalist flow.

## Search And Tool Policy

Search and CAS follow the same policy: they are tools the agents may use when
they are expected to change the next reasoning step. Search is encouraged during
the first few iterations to establish terminology, related results, and known
obstructions, but it is not mandatory for every nontrivial claim. After that
initial window, the runner prompts the agent to prefer memory and independent
reasoning unless there is a specific external fact to check.

The default generation runner settings are:

- `SEARCH_ENCOURAGED_ITERATIONS=2`
- `WEB_SEARCH_AFTER_INITIAL=live`

Set `WEB_SEARCH_AFTER_INITIAL=disabled` for runs that should avoid built-in web
search after the initial exploration window.

## Proof Discipline

CAS can suggest patterns, catch mistakes, and find examples or counterexamples. Non-exhaustive computation is not a proof of a universal theorem. The written blueprint must still contain the mathematical proof accepted by the verifier.

## v1 Quarantine

Do not copy these v1 mechanisms into this branch:

- mandatory first CAS pass;
- nested experimentalist agent;
- requested experiment ledgers;
- claim/conjecture/strategy/computation ledgers;
- verifier CAS-audit bundles;
- broad-status runner logic;
- custom large-log or raw-output runner guardrails.
