"""Offline verifier regressions using synthetic temporary evidence and mocked Git."""
from contextlib import redirect_stdout, redirect_stderr
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from comp2 import verify_package as verifier


class PackageVerifierTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.base = self.root / 'comp2'
        self.put('resultat/original.txt', 'Synthetic original evidence.')
        digest = verifier.sha(self.root / 'resultat/original.txt')
        self.put('resultat/logger/pakke-manifest.json', {
            'files': [{'path': 'original.txt', 'sha256': digest}]})
        self.put('comp2/evidence/copy.txt', 'Synthetic original evidence.')
        self.put('comp2/evidence/selection-manifest.json', [{
            'source': 'resultat/original.txt', 'copy': 'evidence/copy.txt', 'sha256': digest}])
        row = dict(id='T1', en='Synthetic result', no='Syntetisk resultat', observed='1',
                   denominator='1', unit_en='case', unit_no='tilfelle',
                   source='evidence/copy.txt', limit_en='Synthetic only', limit_no='Kun syntetisk')
        self.put('comp2/evidence/selected-results.json', {'test_date': '2026-10-23', 'rows': [row]})
        for lang, key in [('english', 'en'), ('norwegian', 'no')]:
            path = self.root / 'comp2/tables' / lang / 'results.csv'
            path.parent.mkdir(parents=True)
            with path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['id', 'measure', 'observed', 'denominator', 'unit', 'date', 'source', 'limit'])
                writer.writerow([row['id'], row[key], '1', '1', row['unit_' + key], '2026-10-23',
                                 row['source'], row['limit_' + key]])
            self.put(f'comp2/tables/{lang}/performance.md', 'Synthetic performance: 12 1.5')
        self.put('comp2/evidence/archived-evidence-audit.json', {
            'offline': {'total': 282}, 'real_ollama': {
                'verified_saved_outputs': 17, 'verified_saved_claims': 17, 'tests': 23, 'passed': 23}})
        self.put('comp2/evidence/ollama-summary.json', {
            'rows': [{'pass': True} for _ in range(23)], 'tests': 23, 'passing': 23})
        layout = {'headings': 1, 'overflow': False, 'copy': ['Aisha Agent']}
        self.put('comp2/evidence/aisha-browser.txt',
                 ('AISHA_HERO_LAYOUT desktop ' + json.dumps(layout) + '\n') * 3 +
                 'HTTP_FAILURES []\n{"javascript_exceptions":[],"console_errors":[]}')
        self.put('comp2/evidence/new-command-register.json', [{'exit_code': 0}, {'exit_code': 0}])
        self.claim = 'Synthetic service information.'
        for kind, synthetic in [('synthetic', True), ('real', False)]:
            self.put(f'comp2/evidence/walking-skeleton-{kind}.json', {
                'source': {'id': kind, 'synthetic': synthetic, 'url': 'https://example.invalid/service',
                           'paragraphs': [{'id': 'p1', 'text': self.claim}]},
                'claims': [{'text': self.claim, 'evidence_quote': self.claim, 'paragraph_id': 'p1'}],
                'verification': {'findings': []}, 'provider': 'offline-test'})
        self.put('docs/reviewed-service-selection.json', [{
            'source_id': 'real', 'url': 'https://example.invalid/service',
            'paragraph_sha256': [hashlib.sha256(self.claim.encode()).hexdigest()]}])

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding='utf-8')

    def change_json(self, name, change):
        data = json.loads((self.root / name).read_text(encoding='utf-8'))
        change(data)
        self.put(name, data)

    def evidence_fails(self, key):
        result = verifier.verify_evidence(self.root)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIs(result['checks'][key], False)
        return result

    def invoke(self, args=(), status=b'', git_error=None):
        result = subprocess.CompletedProcess([], 0, stdout=status, stderr=b'')
        stdout = io.StringIO()
        with patch.object(verifier, 'ROOT', self.root), \
                patch.object(verifier.subprocess, 'run', return_value=result, side_effect=git_error), \
                redirect_stdout(stdout):
            code = verifier.main(list(args))
        return code, json.loads(stdout.getvalue())

    def test_all_preserved_evidence_checks_pass_without_git_or_report(self):
        with patch.object(verifier.subprocess, 'run', side_effect=AssertionError('Git not part of evidence')):
            evidence = verifier.verify_evidence(self.root)
        self.assertEqual(evidence['status'], 'PASS')
        self.assertEqual(len(evidence['checks']), 15)
        self.assertTrue(all(evidence['checks'].values()))
        self.assertEqual(len(evidence['saved_cli_results']), 2)

    def test_original_hash_corruption(self):
        self.put('resultat/original.txt', 'Modified synthetic original.')
        self.evidence_fails('original_resultat_manifest')

    def test_copy_hash_corruption(self):
        self.put('comp2/evidence/copy.txt', 'Modified synthetic copy.')
        self.evidence_fails('selected_copies_byte_identical')

    def test_missing_manifest_does_not_skip_security(self):
        (self.root / 'resultat/logger/pakke-manifest.json').unlink()
        self.put('comp2/security.txt', 'reviewer@example.invalid')
        result = self.evidence_fails('original_resultat_manifest')
        self.assertFalse(result['checks']['no_detected_home_paths_emails_or_key_patterns_in_text'])
        self.assertEqual(len(result['checks']), 15)

    def test_invalid_json_produces_structured_error(self):
        self.put('comp2/evidence/ollama-summary.json', '{invalid')
        result = self.evidence_fails('ollama_23_expected_outcomes')
        self.assertTrue(any(e['error'] == 'JSONDecodeError' for e in result['errors']))

    def test_csv_value_corruption(self):
        path = self.base / 'tables/english/results.csv'
        path.write_text(path.read_text().replace('2026-10-23', '2026-10-24'), encoding='utf-8')
        self.evidence_fails('bilingual_results_values_dates_sources_identical')

    def test_csv_row_count_corruption(self):
        path = self.base / 'tables/english/results.csv'
        path.write_text(path.read_text().splitlines()[0] + '\n', encoding='utf-8')
        self.evidence_fails('bilingual_results_values_dates_sources_identical')

    def test_table_source_must_exist(self):
        (self.base / 'evidence/copy.txt').unlink()
        self.evidence_fails('bilingual_results_values_dates_sources_identical')

    def test_performance_numeric_mismatch(self):
        self.put('comp2/tables/norwegian/performance.md', '12 9.5')
        self.evidence_fails('bilingual_performance_numbers_identical')

    def test_archived_totals_still_enforced(self):
        self.change_json('comp2/evidence/archived-evidence-audit.json',
                         lambda d: d['offline'].update(total=281))
        self.evidence_fails('archived_saved_positive_outputs_17')

    def test_recorded_ollama_outcome_failure(self):
        self.change_json('comp2/evidence/ollama-summary.json', lambda d: d['rows'][0].update({'pass': False}))
        self.evidence_fails('ollama_23_expected_outcomes')

    def test_browser_layout_and_errors_remain_checked(self):
        self.put('comp2/evidence/aisha-browser.txt', 'No valid synthetic browser record.')
        result = self.evidence_fails('current_aisha_three_viewports')
        self.assertFalse(result['checks']['browser_no_console_or_http_errors'])

    def test_recorded_cli_exit_failure(self):
        self.change_json('comp2/evidence/new-command-register.json', lambda d: d[0].update(exit_code=1))
        self.evidence_fails('new_cli_runs_exit_zero')

    def test_claim_corruption(self):
        self.change_json('comp2/evidence/walking-skeleton-synthetic.json',
                         lambda d: d['claims'][0].update(text='Unsupported synthetic claim.'))
        self.evidence_fails('walking-skeleton-synthetic.json_exact_claim_support')

    def test_unresolved_findings(self):
        self.change_json('comp2/evidence/walking-skeleton-real.json',
                         lambda d: d['verification'].update(findings=['synthetic finding']))
        self.evidence_fails('walking-skeleton-real.json_no_verification_findings')

    def test_provenance_hash_and_url(self):
        for field, value in [('url', 'https://example.invalid/wrong'), ('paragraph_sha256', ['0' * 64])]:
            with self.subTest(field=field):
                original = (self.root / 'docs/reviewed-service-selection.json').read_text()
                self.change_json('docs/reviewed-service-selection.json', lambda d: d[0].update({field: value}))
                self.evidence_fails('new_real_claim_matches_approved_hash_and_url')
                self.put('docs/reviewed-service-selection.json', original)

    def test_all_security_patterns_fail_without_echoing_content(self):
        for content in ['C:/Users/Synthetic/private', 'synthetic@example.invalid', 'ghp_' + 'x' * 20]:
            with self.subTest(pattern_type=content[:3]):
                self.put('comp2/security.txt', content)
                result = self.evidence_fails('no_detected_home_paths_emails_or_key_patterns_in_text')
                self.assertNotIn(content, json.dumps(result))

    def test_unreadable_evidence_text_fails(self):
        (self.base / 'tables/english/performance.md').write_bytes(b'\xff')
        self.evidence_fails('bilingual_performance_numbers_identical')

    def test_default_and_compatibility_mode_do_not_require_reports(self):
        for args in [[], ['--evidence-only']]:
            code, result = self.invoke(args, status=b' M README.md\0')
            self.assertEqual(code, 0)
            self.assertEqual(result['schema_version'], '2.0')
            self.assertEqual(result['evidence']['status'], 'PASS')
            self.assertEqual(result['report']['status'], 'NOT RUN')
            self.assertTrue(all(v == 'NOT RUN' for v in result['report']['checks'].values()))
            self.assertEqual(result['worktree']['status'], 'WARNING')
            self.assertFalse(result['submission_ready'])
            self.assertFalse(result['commit_and_push_permitted'])

    def test_unrelated_code_change_warns_and_strict_gate_fails(self):
        status = b' M hamar_agent/web.py\0'
        self.assertEqual(self.invoke(status=status)[0], 0)
        code, result = self.invoke(['--strict-worktree', '--scope-path', 'README.md'], status)
        self.assertEqual(code, 2)
        self.assertEqual(result['evidence']['status'], 'PASS')
        self.assertEqual(result['worktree']['changes'][0]['scope_status'], 'OUT_OF_SCOPE')

    def test_in_scope_is_never_approved(self):
        code, result = self.invoke(['--strict-worktree', '--scope-path', 'README.md'], b' M README.md\0')
        self.assertEqual(code, 0)
        change = result['worktree']['changes'][0]
        self.assertEqual(change['scope_status'], 'IN_SCOPE')
        self.assertFalse(change['approved'])
        self.assertTrue(result['worktree']['warnings'])

    def test_staging_fails_strict_even_inside_scope(self):
        for status in [b'M  README.md\0', b'MM README.md\0', b'A  README.md\0', b'D  README.md\0']:
            with self.subTest(status=status):
                code, result = self.invoke(['--strict-worktree', '--scope-path', 'README.md'], status)
                self.assertEqual(code, 2)
                self.assertFalse(result['worktree']['checks']['no_staged_changes'])
                self.assertEqual(result['evidence']['status'], 'PASS')

    def test_untracked_deletions_and_special_names_reported(self):
        payload = b'?? docs/new file.md\0 D docs/old.md\0 M docs/line\nbreak.md\0'
        code, result = self.invoke(status=payload)
        self.assertEqual(code, 0)
        changes = result['worktree']['changes']
        self.assertTrue(changes[0]['untracked'])
        self.assertEqual(changes[1]['worktree_status'], 'D')
        self.assertEqual(changes[2]['path'], 'docs/line\nbreak.md')
        self.assertTrue(all(c['scope_status'] == 'UNREVIEWED' for c in changes))

    def test_rename_requires_both_paths_in_scope(self):
        code, result = self.invoke(['--strict-worktree', '--scope-path', 'docs/'],
                                   b' R docs/new name.md\0outside/old.md\0')
        self.assertEqual(code, 2)
        change = result['worktree']['changes'][0]
        self.assertTrue(change['renamed'])
        self.assertEqual(change['original_path'], 'outside/old.md')
        self.assertEqual(change['scope_status'], 'OUT_OF_SCOPE')

    def test_staged_rename_and_copy_parse(self):
        rows = verifier.parse_git_status(b'R  new.md\0old.md\0C  copy.md\0source.md\0')
        self.assertTrue(rows[0]['renamed'])
        self.assertTrue(rows[0]['staged'])
        self.assertTrue(rows[1]['copied'])
        self.assertEqual(rows[1]['original_path'], 'source.md')

    def test_conflicts_fail_strict_gate(self):
        code, result = self.invoke(['--strict-worktree', '--scope-path', 'README.md'], b'UU README.md\0')
        self.assertEqual(code, 2)
        self.assertTrue(result['worktree']['changes'][0]['conflicted'])

    def test_git_failure_is_visible_and_independent(self):
        for error in [FileNotFoundError(), subprocess.CalledProcessError(128, 'git'),
                      subprocess.TimeoutExpired('git', 10)]:
            with self.subTest(error=type(error).__name__):
                code, result = self.invoke(git_error=error)
                self.assertEqual(code, 0)
                self.assertEqual(result['worktree']['status'], 'ERROR')
                self.assertTrue(result['worktree']['warnings'])
                self.assertEqual(result['evidence']['status'], 'PASS')
                self.assertEqual(self.invoke(['--strict-worktree'], git_error=error)[0], 2)

    def test_malformed_git_output_not_silently_clean(self):
        for payload in [b' M no-terminator', b'R  missing-source\0', b'ZZ bad.md\0']:
            with self.subTest(payload=payload):
                code, result = self.invoke(['--strict-worktree'], payload)
                self.assertEqual(code, 2)
                self.assertEqual(result['worktree']['status'], 'ERROR')

    def test_directory_scope_boundary_and_relative_validation(self):
        code, result = self.invoke(['--strict-worktree', '--scope-path', 'docs/'], b' M docs-other/a.md\0')
        self.assertEqual(code, 2)
        self.assertEqual(result['worktree']['changes'][0]['scope_status'], 'OUT_OF_SCOPE')
        for path in ['../outside', '/absolute', 'C:/private', 'C:relative', 'docs/../outside', '']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                verifier.normalize_scope_paths(self.root, [path])

    def test_clean_worktree_passes_strict_without_scope(self):
        code, result = self.invoke(['--strict-worktree'])
        self.assertEqual(code, 0)
        self.assertEqual(result['worktree']['status'], 'CLEAN')

    def test_missing_report_is_only_explicit_gate_failure(self):
        code, result = self.invoke(['--check-report'])
        self.assertEqual(code, 2)
        self.assertEqual(result['report']['status'], 'FAIL')
        self.assertEqual(result['evidence']['status'], 'PASS')

    def test_report_original_checks_preserved(self):
        source = self.root / 'separate/main.tex'
        self.put('separate/main.tex', r'\usepackage[preprint]{neurips_2025}' +
                 '\n' + r'\section{Synthetic section}' * 10 + r'\input{table.tex}')
        self.put('separate/table.tex', 'Synthetic table')
        code, result = self.invoke(['--check-report', '--report-source', str(source)])
        self.assertEqual(code, 0)
        self.assertEqual(result['report']['status'], 'PASS')
        self.assertFalse(result['submission_ready'])
        (self.root / 'separate/table.tex').unlink()
        self.assertFalse(verifier.verify_report(source)['checks']['figures_and_table_inputs_exist'])
        self.put('separate/main.tex', r'\section{NeurIPS checklist}')
        result = verifier.verify_report(source)
        self.assertFalse(result['checks']['no_neurips_checklist'])
        self.assertFalse(result['checks']['ten_main_sections'])
        self.assertFalse(result['checks']['neurips_preprint_declaration'])

    def test_integrity_failure_has_exit_priority(self):
        self.put('resultat/original.txt', 'Corruption')
        code, result = self.invoke(['--strict-worktree', '--check-report'], b'M  README.md\0')
        self.assertEqual(code, 1)
        self.assertEqual(result['evidence']['status'], 'FAIL')
        self.assertEqual(result['report']['status'], 'FAIL')

    def test_security_failure_not_downgraded_by_documentation_scope(self):
        self.put('comp2/security.txt', 'synthetic@example.invalid')
        code, result = self.invoke(['--scope-path', 'docs/'], b' M docs/guide.md\0')
        self.assertEqual(code, 1)
        self.assertEqual(result['evidence']['status'], 'FAIL')

    def test_output_is_exclusive_and_does_not_overwrite(self):
        output = self.root / 'audit.json'
        code, result = self.invoke(['--output', str(output)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.read_text()), result)
        before = output.read_bytes()
        code, result = self.invoke(['--output', str(output)])
        self.assertEqual(code, 1)
        self.assertIn('output_error', result)
        self.assertEqual(output.read_bytes(), before)

    def test_invalid_cli_combinations_exit_two(self):
        for args in [['--evidence-only', '--check-report'], ['--report-source', 'unused.tex'],
                     ['--scope-path', '../outside']]:
            with self.subTest(args=args), patch.object(verifier, 'ROOT', self.root), \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                verifier.main(args)
            self.assertEqual(raised.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
