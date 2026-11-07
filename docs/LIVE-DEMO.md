# Live setup and recording guide

## Environment already prepared

Switch Console is installed at `/Users/gowtham/Applications/Switch Console.app`.
The local server and Mattermost were started, the PatchRoom template was imported,
and patchroom-triager, patchroom-engineer and patchroom-verifier were provisioned
in the patchroom-checkout room. Consult VALIDATION.md for the latest observed
result; provisioning is not a complete workflow demonstration.

Console detected an existing Codex sign-in and its normal provider selection was
used. For authentication diagnostics, see the
[official Codex authentication guide](https://developers.openai.com/codex/auth/).
No authentication cache was copied into the project or committed.

## Project access

Each agent has its own working directory. All CLI calls must set the command
working directory to the actual PatchRoom project path. Reading another path may
require platform permission depending on the runtime. Never silently weaken
permissions or treat a timeout as a confirmed permission denial.

If the runtime cannot read the Downloads checkout, stage only the project code:

```sh
cd /Users/gowtham/Downloads/AIAgent/FlipTheSwitch
python3 scripts/stage_runtime.py
```

This creates `/Users/gowtham/.switch/patchroom-project`. It copies only source,
fixtures, configured examples and documentation; no credentials, Git metadata,
reference repository or existing case database. Its manifest records source
hashes. It has an independent `work/` state directory. Set the template's `project`
input to that runtime path or supply that path explicitly to the agents.

Do not refresh a runtime snapshot during an active verification. After a code
change, stage again before starting a new case. Preserve and review the runtime's
own proposal evidence; do not present evidence from a different copy as its run.

## Fresh installation elsewhere

1. Start Docker Desktop and check `docker info`.
2. Install [Switch Console](https://github.com/sandbox-quantum/switch/releases/latest).
3. Follow the local-server onboarding and select a signed-in coding provider.
4. Confirm switch-buddy responds and choose an available chat bridge.
5. Open Templates → Import template → Choose file; select
   `switch/patchroom.template.yaml`, then import and save it.
6. Select Use template. Check the project path, provider, local machine and
   bridge, then select Create all.
7. Confirm all three agents and the reporter are in the room. Ask the triager
   to read the README and run `python3 -m patchroom --help` from that project.

The template follows the pinned upstream v1 language and was imported and
provisioned in Console 0.40.1. Verify compatibility on other versions. The CLI
also discovers HTTP operation schemas and refuses incompatible requests.

## Two-minute recording

Use a fresh case ID. Record chat handoffs and the real generated evidence.

1. **Problem:** a human reports:

   > @patchroom-triager Checkout charges $5 shipping on an order of exactly
   > $100. The policy says shipping is free at $100 or more. Reproduce the
   > fixture and get a proposed fix independently verified here.

2. **Intake and reproduction:** the triager uses actual room and report message
   IDs from Switch history (not Mattermost permalink IDs) with `intake-switch`, then runs `reproduce --event-id ROOM:MESSAGE:repro`.
   Show the assertion failure and configured reproduction test ID.
3. **Engineering:** the triager hands off to the engineer with case ID,
   source revision/hash, evidence path and requested next action. The engineer
   authors a candidate; it must not invoke the scripted demo command.
4. **Verification:** the verifier invokes `propose` with its own request ID,
   reads baseline recheck and candidate evidence, and posts proposal ID, test
   count, diff and source/contract hashes.
5. **Human decision:** the original human reporter personally sends exactly:

   ```text
   accept CASE PROPOSAL FULL_SOURCE_SHA256
   ```

   Use `reject` to decline. The triager records that message with `review-switch`.
   Show the resulting state and timeline. No merge or deployment follows.

An automated development report must be labeled as such. Do not use an automated
post as evidence that a human personally reviewed the result. The CLI resolves
platform account identity; it cannot prove who physically operated an account.

## Troubleshooting

- **No project access:** set the command working directory explicitly; try the
  project-only runtime copy and report exact errors.
- **Missing Switch environment:** Console sessions normally supply
  SWITCH_API_ENDPOINT, SWITCH_AGENT_ID and SWITCH_API_TOKEN. For an external
  terminal configure the PATCHROOM_SWITCH_* variables without printing tokens.
  Alternatively pass the global `--switch-credentials PATH` option pointing to
  that agent's existing controller `credentials.json`; its token stays in that
  file. The CLI does not automatically scan or select other agents' credentials.
- **Unknown sender kind:** the server did not provide sufficient human identity
  metadata. Intake/review fails closed. Update or adapt against an authenticated
  server identity API; do not accept a sender-kind flag from a chat message.
- **Interrupted run:** wait for the worker to exit, run `recover CASE`, and retry
  with a new event ID. Existing proposal history remains.
- **Output/time limit:** inspect the stored classification. Fix the configured
  environment instead of labeling an incomplete test run successful.
- **Three failed attempts:** stop agent retries and ask for human investigation.

## Submission checklist

- [ ] Complete a real human-report-to-review workflow.
- [ ] Record and publish a short demo video.
- [ ] Review and publish the repository separately when authorized.
- [ ] Add verified live setup details and video URL to the README.
- [ ] Run the final relevant tests and include reproduction commands.
- [ ] Check the current organizer submission form and required fields.
- [ ] Submit manually by November 7, 2026, 11:59 PM IST.

Registration, submission, publication and human approval have not been automated.
