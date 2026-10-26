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
    def test_agents_and_codex_skills_Stay_in_sync(self):
        agents_dir = ROOT / '.agents' / 'skills'
        codex_dir = ROOT / 'codex' / 'skills'
        agents_skills = {p.name for p in agents_dir.iterdir() if p.is_dir()}
        codex_skills = {p.name for p in codex_dir.iterdir() if p.is_dir()}
        self.assertEqual(agents_skills, EXPECTED_SKILLS)
        self.assertEqual(codex_skills, EXPECTED_SKILLS)
        for name in EXPECTED_SKILLS:
            agent_skill = agents_dir / name / 'SKILL.md'
            codex_skill = codex_dir / name / 'SKILL.md'
            self.assertTrue(agent_skill.is_file(), f'Missing {agent_skill}')
            self.assertTrue(codex_skill.is_file(), f'Missing {codex_skill}')
            content = agent_skill.read_text(encoding='utf-8')
            self.assertEqual(content, codex_skill.read_text(encoding='utf-8'), f'Drift in {name}/SKILL.md')
            self.assertIn(f'name: {name}\n', content)
            self.assertIn('description: ', content)
            self.assertIn('AGENTS.md', content)
            self.assertIn('docs/CODEX.md', content)

    def test_mapped_upstream_files_exist(self):
        for rel in UPSTREAM_FILES:
            self.assertTrue((ROOT / rel).is_file(), f'Missing upstream file: {rel}')

    def test_cross_platform_contracts_align(self):
        for doc in ('AGENTS.md', 'CLAUDE.md', 'docs/CODEX.md', 'docs/REVIEW_CYCLE.md'):
            text = (ROOT / doc).read_text(encoding='utf-8')
            for platform in ('Codex', 'Claude Code', 'Antigravity'):
                self.assertIn(platform, text, f'{doc} should mention {platform}')
            if doc != 'docs/CODEX.md':
                self.assertIn('docs/CODEX.md', text)
        self.assertIn('REVIEW_CYCLE.md', (ROOT / 'docs/CODEX.md').read_text(encoding='utf-8'))
        claude_text = (ROOT / 'CLAUDE.md').read_text(encoding='utf-8')
        self.assertIn('docs/REVIEW_CYCLE.md', claude_text)
        self.assertIn('scripts/application.py', claude_text)
        self.assertIn('scripts/review_cycle.py', claude_text)
        self.assertIn('READY_TO_APPLY', claude_text)

    def test_gitignore_protects_private_and_local_agent_files(self):
        ignored = [
            'profile/profile.md',
            'profile/sources.md',
            'profile/intake.md',
            'story-bank/2026-01-win.md',
            'content/calendar.md',
            'tracker/applications.md',
            'tracker/inbox.md',
            'output/applications/example/cv.md',
            'documents/sources/resume.docx',
            'tmp/scratch.json',
            '.venv/pyvenv.cfg',
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
            'codex/skills/ocs-workspace/SKILL.md',
            '.claude/commands/apply.md',
        ]
        for rel in tracked:
            res = subprocess.run(['git', 'check-ignore', '-q', rel], cwd=ROOT)
            self.assertNotEqual(res.returncode, 0, f'Expected {rel} NOT to be git-ignored')


if __name__ == '__main__':
    unittest.main()
