"""Prepare a reviewable PR description locally, without GitHub writes."""
from .core import case_path, export
from .store import Store


def prepare_pr(work, case_id):
    store = Store(work)
    state = store.get(case_id)
    proposals = store.proposals(case_id)
    proposal = next((p for p in proposals if p['id'] == state['current_proposal']), None)
    if not proposal or proposal['status'] != 'verified':
        raise ValueError('a currently verified proposal is required to prepare PR materials')
    export(work, case_id)
    directory = case_path(work, case_id)
    title = 'Fix ' + case_id + ': ' + state['report'].splitlines()[0][:90]
    body = ('## Problem\n\n' + state['report'] + '\n\n## Change\n\n'
            + proposal['explanation'] + '\n\n## Validation\n\n'
            + 'Baseline reproduction fails; candidate passes the protected unittest suite.\n\n'
            + 'Proposal: ' + proposal['id'] + '\n\nSource SHA-256: '
            + proposal['source_sha256'] + '\n\nContract SHA-256: ' + proposal['contract_sha256']
            + '\n\nCase state: ' + state['status'] + '\n\n'
            + 'Evidence is exported in review.md and proposals/' + proposal['id']
            + '/. Attach appropriate evidence when publishing.\n\n'
            + 'Passing configured tests does not prove production correctness.\n')
    (directory / 'pr-title.txt').write_text(title + '\n')
    (directory / 'pr-body.md').write_text(body)
    return dict(title=str(directory / 'pr-title.txt'), body=str(directory / 'pr-body.md'),
                patch=str(directory / 'candidate.patch'), published=False)
