# Upstream reference

Selected repository: https://github.com/sandbox-quantum/switch

Commit inspected: `9e158a7214c40793a4c68d9e3713d255cde7fa55`.

This is the official framework linked by the hackathon organizers. It is the
closest fit for the required Switch integration; no claim is made that it ranks
first among all GitHub projects.

`patchroom.template.yaml` adapts the structure of
`examples/agent-templates/triage-pair.template.yaml` at this commit. Changes:
adds a verifier, local project parameter, checkout evidence commands, explicit
handoffs, and human review instructions. The upstream license and notice are
preserved alongside it. Upstream uses Apache 2.0 with a modified Commons Clause;
do not describe the template as MIT licensed.

The unmodified repository is checked out under `references/switch/`, ignored
by the PatchRoom Git repository. It is a reference dependency, not our submission.

Template specification: https://github.com/sandbox-quantum/switch/blob/9e158a7214c40793a4c68d9e3713d255cde7fa55/docs/TEMPLATES.md

No upstream core changes or hackathon core contribution claims are made.
