#!/usr/bin/env python3
"""Record private, bounded review cycles. No model calls or application status changes."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_MARKER = '<!-- managed by review_cycle.py; text review only -->'
OUTCOMES = {'passed', 'revise', 'needs_input', 'plateau', 'review_unavailable', 'incomplete_package'}
FAILURES = {'review_unavailable', 'incomplete_package'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def nonempty(path):
    data = Path(path).read_bytes()
    if not data.strip():
        raise ValueError(f'Empty input: {path}')
    return data


def application(path, root=ROOT):
    root = Path(root).resolve()
    app = Path(path).resolve()
    base = root / 'output' / 'applications'
    if app.parent != base or not app.is_dir() or not (app / 'identity.json').is_file():
        raise ValueError('Use an existing application folder directly under output/applications')
    if not isinstance(read_json(app / 'identity.json'), dict):
        raise ValueError('Invalid application identity')
    return app


@contextmanager
def locked(app):
    lock = app / '.review-cycle.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError('Review operation already running; inspect a leftover lock before removing it') from exc
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def publish(parent, name, files):
    """Publish a complete immutable directory; interrupted writes stay invisible."""
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / name
    if target.exists():
        raise ValueError(f'Refusing to overwrite history: {target}')
    temporary = Path(tempfile.mkdtemp(prefix='.pending-', dir=parent))
    try:
        for filename, data in files.items():
            (temporary / filename).write_bytes(data)
        temporary.rename(target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return target


def numbered(parent):
    return sorted(p for p in parent.glob('[0-9][0-9][0-9]') if p.is_dir())


def cycles(app):
    return numbered(app / 'review-cycles')


def current_cycle(app):
    found = cycles(app)
    if not found:
        raise ValueError('Start a review cycle first')
    return found[-1]


def summary_allowed(app):
    path = app / 'review.md'
    if path.exists() and not path.read_text(encoding='utf-8').startswith(SUMMARY_MARKER):
        raise ValueError('Existing review.md is not managed by this helper; preserve it explicitly before starting')


def input_changes(app, round_dir):
    manifest = read_json(round_dir / 'manifest.json')
    changes = []
    for item in manifest['inputs']:
        original = app / item['source']
        snapshot = round_dir / item['snapshot']
        if not snapshot.is_file() or digest(snapshot.read_bytes()) != item['sha256']:
            changes.append(f"snapshot damaged: {item['snapshot']}")
        if not original.is_file() or digest(original.read_bytes()) != item['sha256']:
            changes.append(f"source changed or missing: {item['source']}")
    return changes


def inspect(app, root=ROOT):
    app = application(app, root)
    cycle = current_cycle(app)
    start = read_json(cycle / 'start.json')
    rounds = numbered(cycle / 'rounds')
    state = {'cycle': start['cycle'], 'round': len(rounds), 'limit': 3,
             'state': 'active', 'stop_reason': None, 'current': False,
             'changes': [], 'reviewed_cv': None}
    if rounds:
        latest = rounds[-1]
        state['manifest_sha256'] = digest((latest / 'manifest.json').read_bytes())
        state['changes'] = input_changes(app, latest)
        state['current'] = not state['changes']
        result_path = latest / 'result' / 'result.json'
        if result_path.exists():
            result = read_json(result_path)
            if result['manifest_sha256'] != state['manifest_sha256']:
                state['changes'].append('manifest changed since review')
                state['current'] = False
            state['state'] = result['state']
            state['stop_reason'] = result['stop_reason']
            if result['outcome'] not in FAILURES:
                state['reviewed_cv'] = str((latest / 'cv.md').relative_to(app))
        else:
            state['state'] = 'awaiting_review'
    return state


def update_summary(app, root):
    summary_allowed(app)
    state = inspect(app, root)
    cycle = current_cycle(app)
    lines = [SUMMARY_MARKER, '# Text review cycle', '',
             f"- Cycle: {state['cycle']}; round: {state['round']}/3",
             f"- State: {state['state']}", f"- Stop reason: {state['stop_reason'] or 'none'}",
             '- This is a text-review record, not READY_TO_APPLY or proof of independent review.',
             '- Run the status command before reuse; this summary does not update when inputs change.', '']
    for rnd in numbered(cycle / 'rounds'):
        rel = rnd.relative_to(app)
        lines += [f'## Round {int(rnd.name)}', '', f'- [Input manifest]({rel}/manifest.json)',
                  f'- [CV snapshot]({rel}/cv.md)']
        result_path = rnd / 'result' / 'result.json'
        if result_path.exists():
            result = read_json(result_path)
            lines += [f'- [Full report]({rel}/result/report.md)',
                      f'- [Findings and author decisions]({rel}/result/result.json)',
                      f"- Result: {result['state']}", '', result['summary'], '']
            lines += [f'- Question: {q}' for q in result['questions']]
        lines.append('')
    lines += ['Previous cycles remain under review-cycles/. Final document review is separate.', '']
    fd, name = tempfile.mkstemp(prefix='.review-summary-', dir=app)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write('\n'.join(lines))
        os.replace(name, app / 'review.md')
    finally:
        if os.path.exists(name):
            os.unlink(name)


def refresh_summary(app, root=ROOT):
    app = application(app, root)
    with locked(app):
        update_summary(app, root)
    return inspect(app, root)


def start(app, reason='initial', evidence=None, root=ROOT):
    app = application(app, root)
    with locked(app):
        summary_allowed(app)
        previous = cycles(app)
        if reason not in {'initial', 'new_facts', 'user_requested'}:
            raise ValueError('Reason must be initial, new_facts or user_requested')
        files = {}
        if previous:
            state = inspect(app, root)
            if state['state'] in {'active', 'awaiting_review', 'revise'}:
                raise ValueError('Finish the current cycle before starting another')
            if reason == 'initial' or evidence is None:
                raise ValueError('Restart requires new_facts or user_requested and a recorded response/request')
            files['restart-evidence.md'] = nonempty(evidence)
        elif reason != 'initial':
            raise ValueError('The first cycle must use reason initial')
        number = len(previous) + 1
        if number > 999:
            raise ValueError('Cycle capacity reached')
        metadata = {'version': 1, 'cycle': number, 'limit': 3, 'reason': reason, 'created_at': now()}
        if files:
            metadata['evidence_sha256'] = digest(files['restart-evidence.md'])
        files['start.json'] = json_bytes(metadata)
        publish(app / 'review-cycles', f'{number:03}', files)
        update_summary(app, root)
    return inspect(app, root)


def snapshot(app, facts, sources=(), assets=(), root=ROOT):
    app = application(app, root)
    with locked(app):
        summary_allowed(app)
        state = inspect(app, root)
        if state['state'] not in {'active', 'revise'} or state['round'] >= 3:
            raise ValueError('No next round allowed in this cycle')
        cycle = current_cycle(app)
        number = state['round'] + 1
        paths = [('cv.md', app / 'cv.md'), ('job.md', app / 'job.md'), ('facts.md', Path(facts))]
        paths += [(f'source-{i:03}{Path(p).suffix}', Path(p)) for i, p in enumerate(sources, 1)]
        paths += [(f'asset-{i:03}{Path(p).suffix}', Path(p)) for i, p in enumerate(assets, 1)]
        files, inputs = {}, []
        for name, path in paths:
            # Keep the live path, not a symlink's old target, for freshness checks.
            path = Path(os.path.abspath(path))
            if not path.resolve().is_relative_to(Path(root).resolve()):
                raise ValueError('Inputs must be inside this workspace; copy selected sources into documents first')
            data = nonempty(path)
            files[name] = data
            inputs.append({'source': os.path.relpath(path, app), 'snapshot': name, 'sha256': digest(data)})
        files['manifest.json'] = json_bytes({'version': 1, 'cycle': state['cycle'], 'round': number,
                                             'created_at': now(), 'inputs': inputs})
        publish(cycle / 'rounds', f'{number:03}', files)
        update_summary(app, root)
    return inspect(app, root)


def validate_result(value, manifest_hash):
    if not isinstance(value, dict):
        raise ValueError('Result must be a JSON object')
    required = {'manifest_sha256', 'outcome', 'reviewer_id', 'package_complete', 'report',
                'summary', 'findings', 'decisions', 'questions'}
    if not required <= value.keys():
        raise ValueError('Result is missing required fields: ' + ', '.join(sorted(required - value.keys())))
    if value['manifest_sha256'] != manifest_hash:
        raise ValueError('Result does not refer to the current round manifest')
    outcome = value['outcome']
    if outcome not in OUTCOMES:
        raise ValueError('Unknown outcome')
    for field in ('report', 'summary'):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f'{field} must be nonempty text')
    if type(value['package_complete']) is not bool:
        raise ValueError('package_complete must be a boolean')
    if value['reviewer_id'] is not None and (not isinstance(value['reviewer_id'], str) or not value['reviewer_id'].strip()):
        raise ValueError('reviewer_id must be nonempty text or null for a failed review')
    if outcome in FAILURES and value['package_complete']:
        raise ValueError('Failed review must explicitly mark package_complete false')
    if outcome not in FAILURES and (not value['package_complete'] or not isinstance(value['reviewer_id'], str)
                                   or not value['reviewer_id'].strip()):
        raise ValueError('Completed review requires a full package and an independent reviewer ID')
    if not isinstance(value['questions'], list) or len(value['questions']) > 5 or any(
            not isinstance(q, str) or not q.strip() for q in value['questions']):
        raise ValueError('Supply at most five nonempty questions')
    if outcome == 'needs_input' and not value['questions']:
        raise ValueError('needs_input requires questions')
    if not isinstance(value['findings'], list) or not isinstance(value['decisions'], list):
        raise ValueError('Findings and decisions must be lists')
    ids = set()
    for finding in value['findings']:
        if not isinstance(finding, dict) or any(not isinstance(finding.get(k), str) or not finding[k].strip()
                for k in ('id', 'severity', 'quote', 'reference', 'action')):
            raise ValueError('Each finding needs id, severity, quote, reference and action')
        if finding['id'] in ids:
            raise ValueError('Duplicate finding ID')
        ids.add(finding['id'])
        if finding['severity'] not in {'BLOCKER', 'MAJOR', 'MINOR', 'GAP'} or finding['action'] not in {'fix', 'ask', 'retain_gap'}:
            raise ValueError('Invalid finding severity or action')
        if finding['action'] == 'retain_gap' and finding['severity'] != 'GAP':
            raise ValueError('Retained experience gaps must have severity GAP')
    decisions = set()
    for decision in value['decisions']:
        if not isinstance(decision, dict) or decision.get('finding_id') not in ids:
            raise ValueError('Decision must refer to a finding')
        if decision['finding_id'] in decisions:
            raise ValueError('Duplicate author decision')
        decisions.add(decision['finding_id'])
        if decision.get('decision') not in {'accepted', 'rejected', 'needs_answer', 'retained_gap'} or not isinstance(
                decision.get('rationale'), str) or not decision['rationale'].strip():
            raise ValueError('Each decision needs a supported disposition and rationale')
    if ids != decisions:
        raise ValueError('Record one author decision per finding')
    if outcome == 'passed' and (value['questions'] or any(
            f['severity'] in {'BLOCKER', 'MAJOR'} or f['action'] == 'ask' for f in value['findings'])
            or any(d['decision'] == 'needs_answer' for d in value['decisions'])):
        raise ValueError('Cannot pass with unresolved material findings or questions')


def record(app, result, root=ROOT):
    app = application(app, root)
    with locked(app):
        summary_allowed(app)
        state = inspect(app, root)
        if state['state'] != 'awaiting_review':
            raise ValueError('No pending round; existing results cannot be overwritten')
        validate_result(result, state['manifest_sha256'])
        if state['changes'] and result['outcome'] not in FAILURES:
            raise ValueError('Inputs changed since snapshot; record incomplete_package before restarting')
        if result['outcome'] not in FAILURES:
            for path in (app / 'review-cycles').glob('*/rounds/*/result/result.json'):
                if read_json(path)['reviewer_id'] == result['reviewer_id']:
                    raise ValueError('Use a fresh independent reviewer for each round')
        saved = dict(result)
        outcome = saved['outcome']
        saved['state'] = 'limit_reached' if outcome == 'revise' and state['round'] == 3 else outcome
        saved['stop_reason'] = None if saved['state'] == 'revise' else saved['state']
        saved['recorded_at'] = now()
        rnd = current_cycle(app) / 'rounds' / f"{state['round']:03}"
        publish(rnd, 'result', {'result.json': json_bytes(saved), 'report.md': (saved['report'] + '\n').encode('utf-8')})
        update_summary(app, root)
    return inspect(app, root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    for command in ('start', 'snapshot', 'record', 'status'):
        sub = subs.add_parser(command)
        sub.add_argument('application', type=Path)
        if command == 'start':
            sub.add_argument('--reason', choices=['initial', 'new_facts', 'user_requested'], default='initial')
            sub.add_argument('--evidence', type=Path)
        elif command == 'snapshot':
            sub.add_argument('--facts', required=True, type=Path)
            sub.add_argument('--source', action='append', type=Path, default=[])
            sub.add_argument('--asset', action='append', type=Path, default=[])
        elif command == 'record':
            sub.add_argument('--result', required=True, type=Path)
        else:
            sub.add_argument('--refresh-summary', action='store_true', help='Rebuild review.md from committed journal records')
    args = parser.parse_args()
    try:
        if args.command == 'start':
            result = start(args.application, args.reason, args.evidence)
        elif args.command == 'snapshot':
            result = snapshot(args.application, args.facts, args.source, args.asset)
        elif args.command == 'record':
            result = record(args.application, read_json(args.result))
        else:
            result = refresh_summary(args.application) if args.refresh_summary else inspect(args.application)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == 'status' and result['changes']:
            raise SystemExit(2)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
