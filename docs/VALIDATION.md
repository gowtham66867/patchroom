# Validation record

Date: November 6, 2026 (IST).

## Local checks

- `python3 -m unittest discover -s tests -v`: **35 tests passed**.
- `python3 -m compileall -q patchroom tests scripts`: passed.
- Template YAML, runtime-field and room-membership checks: passed.
- `python3 -m patchroom demo --case-id layered-demo`: baseline reproduced,
  candidate passed six checks, case left awaiting human review.
- `python3 -m patchroom prepare-pr layered-demo`: generated local title,
  description and patch. No GitHub publication.
- Configured Python tax example: rounding failure reproduced; a corrected
  candidate passed three checks as part of the suite.

Tests cover invalid transitions, environment failures, missing/skipped tests,
execution limits, duplicate requests, preserved attempts, retries, process
restarts, orphaned workers, spoofed review senders, quoted decisions, wrong
hashes, stale timestamps, changed exports, approval invalidation and reading
existing controller credentials without copying or printing them.

## Actual live agent workflow

**Completed through independent verification; human approval was not recorded.**

Switch Console 0.40.1 provisioned three actual Codex agents on its local Switch
0.31.0 server, with a Mattermost room named `patchroom-checkout`.

For explicitly labeled automated case `live-dev-001`:

1. The development harness created a local case, with no authenticated human
   origin. This was not presented as a human submission.
2. The actual triager executed reproduction: six checks ran, two assertions
   failed at exactly $100, and the case became reproduced.
3. The actual engineer inspected the evidence, authored the one-line inclusive
   threshold fix and handed it to the verifier in the same room.
4. The actual verifier independently reran baseline and candidate. The baseline
   failed the same two assertions; the candidate passed all six checks with no
   errors or skips.
5. The verifier posted the diff, test results, hashes and evidence paths, then
   handed back to the triager. The case stopped at awaiting_human_review with
   decision null. No scripted demo command was used for this live candidate.

Evidence archive:
`work/live-switch/live-dev-001/`

- `review.md`: readable patch and verification results.
- `live-run.json`: versions, case/proposal IDs, automation labels and hashes.
- `switch-room-context.json`: actual room handoffs and responses.
- `export.json`: case, proposals and event history.
- `proposals/p001/`: tested candidate, diff, baseline recheck and candidate output.

Candidate source SHA-256:
`aee43e9c3ba5c5e0d00cbe2a7c7e9674ddb110d397d58badedcdf25c74992bdb`

Protected contract SHA-256:
`a6e7cdc43bc12fee240658a04292976ecbacf9bcfe8c52c382e428f30851f8a7`

## Runtime setup and compatibility findings

- Started the existing Docker installation; daemon 27.5.1 responded.
- Installed official Console under `/Users/gowtham/Applications/Switch Console.app`.
- Console started the local server and a healthy Mattermost container.
- `GET http://127.0.0.1:56614/health` returned `{"status":"ok"}`.
- Selected the existing detected Codex sign-in through normal Console onboarding.
- Imported, saved and provisioned the actual template in the Console UI.
- Initial reads from Downloads timed out. A source-only runtime copy under
  `/Users/gowtham/.switch/patchroom-project` resolved agent project access.
  Source-folder access later recovered; adapter updates were synced back to
  the AIAgent project. No system permission setting was changed by the agent.
- Console's command runtime did not inherit SWITCH_* variables. The CLI now
  also accepts an explicit existing controller credential file, reading its env
  schema without copying, printing or persisting its token in the project.
- Authenticated discovery, get_agent_detail and read_context calls were exercised
  against the live server. This is separate from the local HTTP mock tests.
- The installed server's read_context response omits sender_kind on ordinary
  messages. Its local message IDs are Switch IDs, distinct from Mattermost
  permalink IDs. Names alone are not sufficient proof of a human identity.

## Remaining work

Authenticated human intake/review is blocked on this server version's missing
sender-type metadata. The CLI deliberately refuses those decisions; unit tests
exercise the supported authenticated schema. A server exposing reliable
sender_kind or a separately validated authenticated identity adapter is needed
before claiming a complete human-report-to-acceptance demonstration.

## Publication on November 7, 2026

The source is public at https://github.com/gowtham66867/patchroom. GitHub Actions
ran the 35-test suite successfully. A separate static demo service was deployed
under the Texmed Google Cloud account to:
https://patchroom-demo-412542191970.asia-south1.run.app/

The site includes a 120.7-second narrated evidence presentation, English captions,
interactive stage controls, sanitized actual handoffs and test outputs. The video
is labeled as an archived-evidence walkthrough, not a live screen recording.

Anonymous homepage access returned HTTP 200. An anonymous video range request
returned HTTP 206. Browser QA confirmed the verification tab works and video
metadata loads with no media error. The hosted page does not execute Python,
repositories, agents or models. Those components run locally through Switch.

No hackathon registration or submission was automated. Final submission is a
manual entrant action under the event rules. No PR, merge or production code
change in an external target repository was performed. Test results establish
configured behavior, not production correctness.
