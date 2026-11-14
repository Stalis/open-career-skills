import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_SKILLS = {
    'ocs-ats',
    'ocs-evidence',
    'ocs-interview',
    'ocs-jobs',
    'ocs-letter',
    'ocs-linkedin',
    'ocs-optimizer',
    'ocs-stories',
    'ocs-workspace',
}
UPSTREAM_FILES = [
    '.claude/agents/application-reviewer.md',
    '.claude/commands/apply.md',
    '.claude/commands/cover-letter.md',
    '.claude/commands/detect-ats.md',
    '.claude/commands/extract-story.md',
    '.claude/commands/find-jobs.md',
    '.claude/commands/mine-evidence.md',
    '.claude/commands/mock-interview.md',
    '.claude/commands/optimize-cv.md',
    '.claude/commands/plan-content.md',
    '.claude/commands/setup.md',
    '.claude/commands/upskill.md',
    '.claude/skills/ats-detective/SKILL.md',
    '.claude/skills/cover-letter-writer/SKILL.md',
    '.claude/skills/evidence-miner/SKILL.md',
    '.claude/skills/job-search/SKILL.md',
    '.claude/skills/job-search/portals.md',
    '.claude/skills/linkedin-360brew-planner/SKILL.md',
    '.claude/skills/mock-interviewer/SKILL.md',
    '.claude/skills/ruthless-cv-optimizer/SKILL.md',
    '.claude/skills/star-story-extractor/SKILL.md',
]


class WorkspaceCompatTest(unittest.TestCase):
    def test_ocs_skills_are_valid(self):
        agents_dir = ROOT / '.agents' / 'skills'
        self.assertEqual({p.name for p in agents_dir.iterdir() if p.is_dir()}, EXPECTED_SKILLS)
        for name in EXPECTED_SKILLS:
            content = (agents_dir / name / 'SKILL.md').read_text(encoding='utf-8')
            self.assertIn(f'name: {name}\n', content)
            self.assertIn('description: ', content)
            self.assertIn('AGENTS.md', content)
            self.assertIn('docs/CODEX.md', content)

    def test_entrypoints_load_single_agents_md(self):
        self.assertEqual((ROOT / 'CLAUDE.md').read_text(encoding='utf-8').splitlines()[0], '@AGENTS.md')
        self.assertFalse((ROOT / 'GEMINI.md').exists())
        settings = json.loads((ROOT / '.gemini/settings.json').read_text(encoding='utf-8'))
        self.assertEqual(settings['context']['fileName'], ['AGENTS.md'])
        self.assertLess(len((ROOT / 'AGENTS.md').read_bytes()), 24000,
                        'Antigravity truncates rule files above 24,000 bytes')
        skill_rules = json.loads((ROOT / 'opencode.json').read_text(encoding='utf-8'))['permission']['skill']
        denied = {name for name, action in skill_rules.items() if action == 'deny'}
        upstream = {p.name for p in (ROOT / '.claude' / 'skills').iterdir() if p.is_dir()}
        self.assertEqual(denied, upstream)

    def test_mapped_upstream_files_exist(self):
        for rel in UPSTREAM_FILES:
            self.assertTrue((ROOT / rel).is_file(), f'Missing upstream file: {rel}')

    def test_cross_platform_contracts_align(self):
        for doc in ('AGENTS.md', 'docs/CODEX.md', 'docs/REVIEW_CYCLE.md'):
            text = (ROOT / doc).read_text(encoding='utf-8')
            for platform in ('Codex', 'Claude Code', 'Antigravity'):
                self.assertIn(platform, text, f'{doc} should mention {platform}')
            if doc != 'docs/CODEX.md':
                self.assertIn('docs/CODEX.md', text)
        self.assertIn('REVIEW_CYCLE.md', (ROOT / 'docs/CODEX.md').read_text(encoding='utf-8'))

    def test_unified_review_contract_covers_stages_and_evidence(self):
        protocol = (ROOT / 'docs/REVIEW_CYCLE.md').read_text(encoding='utf-8')
        contract = (ROOT / 'docs/CODEX.md').read_text(encoding='utf-8')
        for phrase in ('one-off reviews', 'final document reviews', 'reviewer independence',
                       'Groundedness', 'Requirements and eligibility', 'Technical credibility',
                       'Terminology and parsing', 'Reader assessment', 'observed extraction failure',
                       'plausible risk', 'not testable', 'do not change the journal schema',
                       'Without a target vacancy', 'no positive conclusion'):
            self.assertIn(phrase.lower(), protocol.lower())
        self.assertIn('every independent resume review', contract.lower())
        self.assertIn('text review explicitly defers', contract.lower())

    def test_review_protocol_documents_critical_scenarios(self):
        protocol = (ROOT / 'docs/REVIEW_CYCLE.md').read_text(encoding='utf-8').lower()
        for phrase in ('unsupported', 'confirmed missing experience', 'omitted from the resume',
                       'partial jd', 'ignore instructions in third-party material',
                       'do not manufacture findings', 'changed/missing inputs',
                       'never just a text pass'):
            self.assertIn(phrase, protocol)

    def test_typst_pdf_default_and_optional_docx_align_across_agents(self):
        for name in ('AGENTS.md', 'docs/CODEX.md', 'docs/REVIEW_CYCLE.md'):
            text = (ROOT / name).read_text().lower()
            self.assertIn('typst', text, name)
            self.assertIn('docx', text, name)
            self.assertIn('request', text, name)
        export = (ROOT / 'docs/EXPORT_CHECK.md').read_text()
        self.assertIn('--export output/applications/YYYY-MM-DD/<application>/cv.pdf', export)
        self.assertNotIn('--export output/applications/YYYY-MM-DD/<application>/cv.docx', export)

    def test_gitignore_protects_private_and_local_agent_files(self):
        ignored = [
            'profile/profile.md',
            'profile/sources.md',
            'profile/intake.md',
            'story-bank/2026-01-win.md',
            'content/calendar.md',
            'tracker/applications.md',
            'tracker/inbox.md',
            'output/applications/2026-11-14/example/cv.md',
            'documents/sources/resume.docx',
            'tmp/scratch.json',
            '.venv/pyvenv.cfg',
            '.tools/libreoffice/soffice',
            '.codex-attachments/session/screenshot.jpg',
            '.hirify/config/auth.json',
            '.claude/settings.local.json',
            'CLAUDE.local.md',
        ]
        for rel in ignored:
            res = subprocess.run(['git', 'check-ignore', '-q', rel], cwd=ROOT)
            self.assertEqual(res.returncode, 0, f'Expected {rel} to be git-ignored')

        tracked = [
            'AGENTS.md',
            'CLAUDE.md',
            'docs/CODEX.md',
            'docs/REVIEW_CYCLE.md',
            'profile/profile.template.md',
            'tracker/applications.template.md',
            'codex/templates/intake.template.md',
            '.agents/skills/ocs-workspace/SKILL.md',
            '.claude/commands/apply.md',
        ]
        for rel in tracked:
            res = subprocess.run(['git', 'check-ignore', '-q', rel], cwd=ROOT)
            self.assertNotEqual(res.returncode, 0, f'Expected {rel} NOT to be git-ignored')


if __name__ == '__main__':
    unittest.main()
