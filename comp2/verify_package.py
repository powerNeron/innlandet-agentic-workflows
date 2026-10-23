"""Read-only evidence checks; exit 2 when submission-critical gaps remain.

Optional --output writes a new audit file exclusively. No original is changed.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'comp2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    checks = {}
    source_manifest = json.loads((ROOT/'resultat/logger/pakke-manifest.json').read_text(encoding='utf-8'))
    checks['original_resultat_manifest'] = all(sha(ROOT/'resultat'/item['path']) == item['sha256'] for item in source_manifest['files'])
    copies = json.loads((BASE/'evidence/selection-manifest.json').read_text(encoding='utf-8'))
    checks['selected_copies_byte_identical'] = all(sha(ROOT/r['source']) == sha(BASE/r['copy']) == r['sha256'] for r in copies)
    data = json.loads((BASE/'evidence/selected-results.json').read_text(encoding='utf-8'))
    tables = []
    for lang, key in [('english','en'), ('norwegian','no')]:
        with (BASE/'tables'/lang/'results.csv').open(encoding='utf-8', newline='') as stream:
            rows = list(csv.reader(stream))[1:]
        assert len(rows) == len(data['rows'])
        for row, source in zip(rows, data['rows']):
            assert row == [source['id'], source[key], source['observed'],source['denominator'],source['unit_'+key],data['test_date'],source['source'],source['limit_'+key]]
            assert (BASE/source['source']).is_file(), source['source']
        tables.append([[row[i] for i in [0,2,3,5,6]] for row in rows])
    checks['bilingual_results_values_dates_sources_identical'] = tables[0] == tables[1]
    # Performance text translations must retain every decimal exactly.
    performance = [(BASE/'tables'/lang/'performance.md').read_text(encoding='utf-8') for lang in ['english','norwegian']]
    number = r'(?<![A-Za-z])\d+(?:\.\d+)?'
    checks['bilingual_performance_numbers_identical'] = re.findall(number,performance[0]) == re.findall(number,performance[1])
    archive = json.loads((BASE/'evidence/archived-evidence-audit.json').read_text(encoding='utf-8'))
    checks['archived_saved_positive_outputs_17'] = archive['real_ollama']['verified_saved_outputs'] == archive['real_ollama']['verified_saved_claims'] == 17
    assert archive['offline']['total'] == 282
    assert archive['real_ollama']['tests'] == archive['real_ollama']['passed'] == 23
    smoke = json.loads((BASE/'evidence/ollama-summary.json').read_text(encoding='utf-8'))
    checks['ollama_23_expected_outcomes'] = len(smoke['rows']) == smoke['tests'] == smoke['passing'] == 23 and all(row['pass'] for row in smoke['rows'])
    browser = (BASE/'evidence/aisha-browser.txt').read_text(encoding='utf-8')
    layouts = [json.loads(line.split(' ',2)[2]) for line in browser.splitlines() if line.startswith('AISHA_HERO_LAYOUT ')]
    checks['current_aisha_three_viewports'] = len(layouts) == 3 and all(r['headings'] == 1 and not r['overflow'] and r['copy'][0] == 'Aisha Agent' for r in layouts)
    checks['browser_no_console_or_http_errors'] = 'HTTP_FAILURES []' in browser and '"javascript_exceptions":[],"console_errors":[]' in browser
    new = json.loads((BASE/'evidence/new-command-register.json').read_text(encoding='utf-8'))
    checks['new_cli_runs_exit_zero'] = len(new) == 2 and all(row['exit_code'] == 0 for row in new)
    result_summaries = []
    selected = {row['source_id']: row for row in json.loads((ROOT/'docs/reviewed-service-selection.json').read_text(encoding='utf-8'))}
    for filename in ['walking-skeleton-synthetic.json', 'walking-skeleton-real.json']:
        result = json.loads((BASE/'evidence'/filename).read_text(encoding='utf-8'))
        paragraphs = {p['id']: p['text'] for p in result['source']['paragraphs']}
        checks[filename+'_exact_claim_support'] = bool(result['claims']) and all(c['text'] == c['evidence_quote'] == paragraphs[c['paragraph_id']] for c in result['claims'])
        checks[filename+'_no_verification_findings'] = not result['verification']['findings']
        if not result['source']['synthetic']:
            approved = selected[result['source']['id']]
            checks['new_real_claim_matches_approved_hash_and_url'] = result['source']['url'] == approved['url'] and all(hashlib.sha256(c['text'].encode('utf-8')).hexdigest() == approved['paragraph_sha256'][int(c['paragraph_id'][1:])-1] for c in result['claims'])
        result_summaries.append({'file':filename, 'claims':len(result['claims']), 'provider':result['provider'], 'source_id':result['source']['id']})
    tex = (BASE/'report/main.tex').read_text(encoding='utf-8')
    checks['neurips_preprint_declaration'] = r'\usepackage[preprint]{neurips_2025}' in tex
    checks['no_neurips_checklist'] = not re.search(r'\\(?:section|input)\{[^}]*checklist', tex, re.I)
    checks['ten_main_sections'] = len(re.findall(r'\\section\{',tex.split(r'\appendix')[0])) == 10
    checks['figures_and_table_inputs_exist'] = all((BASE/'report'/p).is_file() for p in re.findall(r'\\(?:includegraphics(?:\[[^]]*\])?|input)\{([^}]+)\}',tex))
    safe = ['git','-c','safe.directory='+ROOT.as_posix()]
    status = subprocess.run(safe+['status','--porcelain','--untracked-files=all'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.splitlines()
    checks['only_comp2_changes'] = all(line[3:].startswith('comp2/') for line in status)
    checks['no_staged_changes'] = subprocess.run(safe+['diff','--cached','--quiet'],cwd=ROOT).returncode == 0
    # The status check above covers both tracked differences and untracked files.
    candidates = []
    for path in BASE.rglob('*'):
        if not path.is_file() or path.suffix.lower() in {'.png','.pdf','.py'}:
            continue
        text = path.read_text(encoding='utf-8-sig')
        patterns = [r'(?i)[A-Z]:[\\/](?:Users|Documents and Settings)[\\/]', r'(?i)(?<![\w.-])[\w.+-]+@[\w.-]+\.[a-z]{2,}', r'\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_]{15,}']
        if any(re.search(pattern,text) for pattern in patterns):
            candidates.append(path.relative_to(BASE).as_posix())
    checks['no_detected_home_paths_emails_or_key_patterns_in_text'] = not candidates
    # This scan supplements manual review; it cannot prove absence of every kind of personal data.
    blockers = [
        'Supplied NeurIPS 2025 template is unavailable; no compiled formatting verification.',
        'No LaTeX compiler found; report.pdf and 3-4 main-page / <=2 prompt-page checks are missing.',
        'Demonstration and submission dates are not confirmed; milestone schedule is relative only.',
        'Genuine participant-confirmed meeting reports are unavailable.',
        'Historical raw-HTML handling remains an unresolved assignment privacy-compliance issue.',
    ]
    record = {'audit_utc':datetime.now(timezone.utc).isoformat(), 'checks':checks, 'checked_original_resultat_files':len(source_manifest['files']), 'new_cli_results':result_summaries, 'sensitive_pattern_candidates':candidates, 'latex_tools_found':[name for name in ['pdflatex','xelatex','lualatex','tectonic','latexmk'] if shutil.which(name)], 'submission_critical_blockers':blockers, 'technical_checks_passed':all(checks.values()), 'submission_ready':False, 'commit_and_push_permitted':False}
    if args.output:
        with args.output.open('x',encoding='utf-8') as stream:
            json.dump(record,stream,ensure_ascii=False,indent=2)
    print(json.dumps(record,ensure_ascii=False,indent=2))
    raise SystemExit(2 if all(checks.values()) else 1)


if __name__ == '__main__':
    main()
