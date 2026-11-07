# PatchRoom

**Hackathon:** Flip the Switch 2026 · Best Business Workflow

- [Public demo on Texmed Google Cloud](https://patchroom-demo-412542191970.asia-south1.run.app/)
- [Gemini-narrated evidence film (2:27)](https://patchroom-demo-412542191970.asia-south1.run.app/gemini-walkthrough.mp4)
- [Public source](https://github.com/gowtham66867/patchroom)
- [Sanitized live evidence](evidence/live-run/README.md)
- [Website source](website/) and narrated evidence walkthrough

The website presents archived results. The Python CLI and coding agents execute
locally through Switch Console. Authenticated human approval remains blocked on
the installed Switch 0.31.0 server; this limitation is disclosed throughout.

Turn a bug reported in team chat into a reproduced failure, a proposed patch,
independent verification, and an identifiable human review in a Switch room.

The workflow has three agents: **triager → engineer → verifier → human reviewer**.
Switch Console provides live agent sessions and room handoffs. PatchRoom supplies
the durable case state, repository snapshots, execution tools and review evidence.

## Quick start: local replay

Requires Python 3.9+ on macOS or Linux. No Python runtime packages or API keys are
needed for the local CLI. This runner uses POSIX process and pipe APIs.

```sh
cd patchroom
python3 -m patchroom demo --case-id my-demo
python3 -m patchroom status my-demo
python3 -m patchroom timeline my-demo
python3 -m unittest discover -s tests -v
```

The replay starts with a faulty checkout: exactly $100 attracts $5 shipping. It
runs six checks, creates a **scripted** example correction, and independently
rechecks the baseline and candidate. It exports `work/my-demo/review.md` and
`work/my-demo/proposals/p001/`. Use a new case ID for each replay.

**This is not an AI run, a live Switch demonstration, or human approval.**
Follow [the live setup guide](docs/LIVE-DEMO.md) for actual agent collaboration.

## Case and proposal workflow

```sh
python3 -m patchroom init shipping-001 --report 'Exactly $100 incorrectly incurs $5 shipping.' \
  --expected 'Free shipping at $100 or more' --observed '$5 charged'
python3 -m patchroom reproduce shipping-001 --event-id shipping-001:report-1
# Engineer authors work/shipping-001/proposed.py.
python3 -m patchroom propose shipping-001 --source work/shipping-001/proposed.py \
  --explanation 'Include the $100 boundary.' --event-id shipping-001:verify-1
python3 -m patchroom export shipping-001
python3 -m patchroom prepare-pr shipping-001
```

Use `--report-file PATH` instead of embedding arbitrary report text in shell
commands. Every CLI command supports `--help`. Put `--work PATH` before the
subcommand to choose a different state directory.

Cases follow explicit states: reported, needs_information, reproducing,
reproduced, not_reproduced, reproduction_error, patching, verifying,
awaiting_human_review, accepted and rejected. `information` records questions and
responses. `recover` handles orphaned workers after a process exits; it refuses
recovery while the recorded worker PID is alive.

The SQLite database `work/patchroom.sqlite3` is canonical. JSON, text, diffs and
Markdown under each case are regenerated exports. Every attempt has a separate
proposal ID and preserved source, baseline recheck, candidate result and diff.
There are at most three baseline runs and three proposals per case. Replacement
proposals invalidate earlier decisions. Duplicate completed execution requests
with the same `--event-id` return their stored result; conflicting payloads fail.
Interrupted requests need recovery and a new event ID.

Legacy replay folders created before the SQLite implementation remain untouched;
create a fresh case ID rather than reusing those folders. There is no automatic
migration of old JSON-only evidence.

## Configured local Python repository

The second example is a tax-rounding bug:

```sh
python3 -m patchroom init tax-001 --adapter examples/local-python/adapter.json \
  --report 'Tax calculation rounds a half cent down instead of up.'
python3 -m patchroom reproduce tax-001
# Author a fixed tax.py, then verify with --source /path/to/fixed_tax.py.
```

[adapter.json](examples/local-python/adapter.json) is the configuration reference.
Set `root`, `source_files`, protected `test_files`, the exact failing
`reproduction_test` ID, minimum test count, timeout and output limit. Paths are
relative to the config file and repository root. For multiple source files use
`propose --candidate-dir PATH` with the same relative source paths.

This adapter supports **stdlib unittest Python projects with explicit text-file
allowlists**. It does not install dependencies or run arbitrary shell commands.
For an installed dependency, run PatchRoom with that environment's Python.
Add new regression tests to the reviewed adapter before creating a case; agents
cannot change the saved test contract during a proposal. Unlisted resources,
package layouts unsupported by unittest discovery, binaries and arbitrary
frameworks need another adapter.

## Verification guarantees and limits

Baseline and candidate run in separate temporary copies against the same saved
contract. A baseline is reproduced only when its configured test has an assertion
failure. Import errors, timeouts, truncated output, skipped tests, missing tests
and altered inventories cannot establish verification. Every proposal rechecks
that the baseline still reproduces. Outputs record commands, durations, exit
codes, classifications, test inventories, source hashes and contract hashes.

Candidates execute as the local user. Temporary directories and `-I` are **not a
security sandbox**. Use trusted local code only. The test runner is designed to
catch incomplete or accidental test execution, not to defeat malicious Python
that manipulates its interpreter. Hashes identify content; they neither
establish authorship nor make the local database tamper-proof.

## Switch intake and human review

The CLI reads the official Console session variables `SWITCH_API_ENDPOINT`,
`SWITCH_AGENT_ID`, `SWITCH_API_TOKEN`. Explicit `PATCHROOM_SWITCH_URL`,
`PATCHROOM_SWITCH_AGENT_ID`, `PATCHROOM_SWITCH_API_KEY` override them. Do not
commit or share tokens. If Console does not forward those variables to command
processes, pass the global `--switch-credentials /absolute/path/credentials.json`
option, or set `PATCHROOM_SWITCH_CREDENTIALS_FILE`, pointing to that agent's
existing controller credential file. The CLI reads its official `env` schema;
it does not copy, display, or create a token. Keep that file outside the project. Remote servers require HTTPS; redirects are refused.

```sh
python3 -m patchroom doctor
python3 -m patchroom intake-switch live-001 --room-id ROOM --message-id REPORT_MESSAGE
python3 -m patchroom reproduce live-001 --event-id ROOM:REPORT_MESSAGE:reproduce
# Engineer and verifier complete a proposal through the room.
python3 -m patchroom review-switch live-001 --proposal-id p001 --message-id REVIEW_MESSAGE
```

The original human reporter must send exactly:

```text
accept live-001 p001 FULL_SOURCE_SHA256
```

Use `reject` to decline. PatchRoom fetches the message from the case's configured
Switch server and room. It requires server-resolved `sender_kind=user`, the
original reporter, the current proposal and full hash, and a timestamp after
proposal creation. Agent, unknown-identity, quoted, stale and mismatched approvals
are refused. Older Switch releases that omit sender_kind cannot authenticate
review; those cases remain awaiting review. There is no JSON import or CLI flag
that asserts a human identity. Local Python and SQLite access are still trusted.

The Switch client discovers operation schemas at runtime and uses HTTP
`read_context`. Console handles WebSocket/SSE, sessions and model providers.
`handoff` prepares a deduplicated local record for an agent to post through
Switch. It does not itself send chat messages or guarantee exactly-once outward
chat delivery. Agent roles and independence are orchestration instructions, not
OS-enforced separation when agents share the same local account.

## Local PR materials

`prepare-pr` writes a title, description and patch for review. It does not create
a Git branch, push, publish a PR, merge or deploy. Acceptance of a candidate is
not authorization for those operations. No GitHub write credentials are needed.

## Live status and architecture

See [validation and setup status](docs/VALIDATION.md),
[architecture](docs/ARCHITECTURE.md), and [recording guide](docs/LIVE-DEMO.md).
The actual three-agent workflow has been demonstrated through independent
verification of an explicitly automated local case. Its archived
[public evidence packet](evidence/live-run/review.md) includes the real
room handoffs. Authenticated human approval remains blocked on the installed
server's missing sender-type metadata. See the validation record for the limits.

## Sources and attribution

- [Official Switch repository](https://github.com/sandbox-quantum/switch)
- [Pinned upstream and template attribution](switch/UPSTREAM.md)
- [Hackathon](https://www.wemakedevs.org/hackathons/switch)
- [Switch quickstart](https://docs.switchagents.ai/switch-rooms/getting-started)

The adapted template retains upstream licensing and notices. The untouched
upstream checkout is ignored under `references/switch/`.
