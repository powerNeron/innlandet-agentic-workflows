"""Build selected Compulsory 2 material without modifying upstream evidence.

Run once from the repository root. Existing output files are never overwritten.
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'comp2'


def write(name, text):
    path = DEST / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


def main():
    summary = json.loads((ROOT / 'resultat/logger/oppsummering.json').read_text(encoding='utf-8'))
    assert summary['offline']['n'] == summary['offline']['passed'] == 282
    assert summary['model']['smoke_tests'] == summary['model']['smoke_passed'] == 23
    copies = [
        ('resultat/logger/offline.txt', 'evidence/offline.txt'),
        ('resultat/logger/real-smoke/summary.json', 'evidence/ollama-summary.json'),
        ('resultat/logger/model-measurements.json', 'evidence/model-measurements.json'),
        ('resultat/logger/kommandoer.jsonl', 'evidence/original-command-register.jsonl'),
        ('resultat/english/figurer/03_workflow.mmd', 'figures/aisha-workflow.mmd'),
        ('resultat/english/figurer/01_model_response_times.png', 'figures/model-response-times.png'),
        ('output/aisha-heading-encoding-fixed-browser-20261023/browser-check.txt', 'evidence/aisha-browser.txt'),
    ]
    provenance = []
    for source, target in copies:
        raw = (ROOT / source).read_bytes()
        path = DEST / target
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
        provenance.append({'source': source, 'copy': target, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    write('evidence/selection-manifest.json', json.dumps(provenance, indent=2) + '\n')
    rows = [
        ('O1', 'Offline regression', 'Frakoblet regresjon', '282', '282', 'tests', 'tester', 'evidence/offline.txt', 'No failures or errors; not a factual-accuracy estimate.', 'Ingen feil; ikke et mål på faktisk korrekthet.'),
        ('M1', 'Real Ollama cases', 'Reelle Ollama-tilfeller', '23', '23', 'cases', 'tilfeller', 'evidence/ollama-summary.json', 'Includes expected refusals; not 23 generated answers.', 'Inkluderer forventede avvisninger; ikke 23 genererte svar.'),
        ('C1', 'Saved positive outputs', 'Lagrede positive svar', '17', '17', 'outputs', 'svar', '../docs/reports/evidence-2026-10-23.json', 'Exact approved-excerpt support; excludes repeated answer without its own output file.', 'Eksakt støtte i godkjent utdrag; gjentatt svar uten egen fil er utelatt.'),
        ('B1', 'Responsive Chrome layouts', 'Responsive Chrome-oppsett', '3', '3', 'viewports', 'visningsstørrelser', 'evidence/aisha-browser.txt', 'Desktop 1440x1100, tablet 820x1180, mobile 390x844; no human accessibility study.', 'Desktop 1440x1100, nettbrett 820x1180, mobil 390x844; ingen menneskelig tilgjengelighetsstudie.'),
        ('R1', 'Insufficient-evidence refusals', 'Avvisninger ved utilstrekkelig evidens', '4', '4', 'cases', 'tilfeller', 'evidence/ollama-summary.json', 'Expected refusals in the 23-case suite; not an additional independent sample.', 'Forventede avvisninger i serien med 23 tilfeller; ikke et ekstra uavhengig utvalg.'),
        ('P1', 'Permission and prompt boundaries', 'Tillatelses- og promptgrenser', '10', '10', 'checks', 'kontroller', '../resultat/logger/fault-injection.json', 'Synthetic controls only; global kill switch and aggregate cost budget are not enforced.', 'Kun syntetiske kontroller; global nødstopp og samlet kostnadsbudsjett er ikke håndhevet.'),
        ('G1', 'Approval and endpoint gates', 'Godkjennings- og endepunktporter', '15', '15', 'checks', 'kontroller', '../resultat/logger/approval-gates.json', 'Role assertion is not authenticated identity.', 'Angitt rolle er ikke autentisert identitet.'),
        ('M2', 'Completed performance calls', 'Fullførte ytelseskall', '14', '20', 'planned calls', 'planlagte kall', 'evidence/model-measurements.json', 'Completion count, not a pass-rate denominator; thermal stop.', 'Fullføring, ikke nevner for beståttandel; termisk stopp.'),
    ]
    shared = {'test_date': '2026-10-23', 'rows': [dict(zip(('id','en','no','observed','denominator','unit_en','unit_no','source','limit_en','limit_no'), row)) for row in rows], 'performance': summary['model']}
    write('evidence/selected-results.json', json.dumps(shared, ensure_ascii=False, indent=2) + '\n')
    for language, key in [('english','en'), ('norwegian','no')]:
        folder = DEST / 'tables' / language
        folder.mkdir(parents=True, exist_ok=True)
        header = ['ID','Measure','Observed','Denominator','Unit','Date','Source','Limitation'] if key == 'en' else ['ID','Mål','Observert','Nevner','Enhet','Dato','Kilde','Begrensning']
        with (folder / 'results.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            for r in shared['rows']:
                writer.writerow([r['id'],r[key],r['observed'],r['denominator'],r['unit_'+key],shared['test_date'],r['source'],r['limit_'+key]])
        lines = ['| '+' | '.join(header)+' |', '|'+ '|'.join(['---']*len(header))+'|']
        for r in shared['rows']:
            lines.append('| '+' | '.join([r['id'],r[key],r['observed'],r['denominator'],r['unit_'+key],shared['test_date'],r['source'],r['limit_'+key]])+' |')
        write('tables/'+language+'/results.md', '\n'.join(lines)+'\n')
        compact = shared['rows'][:7]
        title = 'Measure & Observed / evaluated' if key == 'en' else 'Mål & Observert / evaluert'
        tex = ['\\begin{tabular}{lr}', '\\toprule', title+' \\\\', '\\midrule']
        tex += [r[key]+' & '+r['observed']+'/'+r['denominator']+' \\\\' for r in compact]
        tex += ['\\bottomrule', '\\end{tabular}']
        write('tables/'+language+'/results.tex', '\n'.join(tex)+'\n')
        heading = 'Preliminary performance' if key == 'en' else 'Foreløpig ytelse'
        description = ('Only 14 of 20 planned calls completed: 12 sequential and 2 concurrent. The thermal safety threshold stopped the experiment. Nearest-rank p95; milliseconds; date 2026-10-23. No confidence interval or production service-level claim.' if key == 'en' else 'Bare 14 av 20 planlagte kall ble fullført: 12 sekvensielle og 2 samtidige. Temperaturgrensen stanset eksperimentet. Nærmeste-rang p95; millisekunder; dato 2026-10-23. Ingen konfidensintervall eller påstand om tjenestenivå i produksjon.')
        labels = ['Group','n','Median (ms)','p95 (ms)','Min (ms)','Max (ms)'] if key == 'en' else ['Gruppe','n','Median (ms)','p95 (ms)','Min (ms)','Maks (ms)']
        lines = ['# '+heading, '', description, '', '| '+' | '.join(labels)+' |', '|---|---|---|---|---|---|']
        for batch, v in summary['model']['latency_by_batch'].items():
            label = {'sequential': ('Sequential','Sekvensiell'), 'concurrency-2': ('Concurrency 2','Samtidighet 2')}[batch][key == 'no']
            lines.append('| '+' | '.join(map(str,[label,v['n'],v['median_ms'],v['p95_nearest_rank_ms'],v['min_ms'],v['max_ms']]))+' |')
        lines += ['', 'Source: `evidence/model-measurements.json`. Tokens: 4120 input; 1716 output.']
        write('tables/'+language+'/performance.md', '\n'.join(lines)+'\n')
    write('figures/captions.md', '''# Figure captions / figurtekster

English — Figure 1. Aisha Agent: approved local context, automatic multi-stage processing, exact-paragraph verification, and one bounded correction. Human source admission precedes runtime. Live municipal HTML retrieval is disabled. Source: aisha-workflow.mmd; implementation: hamar_agent/portal.py, real_sources.py, application.py and ollama_provider.py.

Norsk — Figur 1. Aisha Agent: godkjent lokal kontekst, automatisk flertrinnsbehandling, verifisering av hele avsnitt og én avgrenset korrigering. Menneskelig kildegodkjenning skjer før kjøring. Direkte henting av kommunal HTML er deaktivert. Kilde: aisha-workflow.mmd; implementasjon: hamar_agent/portal.py, real_sources.py, application.py og ollama_provider.py.

English — Figure 2 (supporting material). Preliminary model response times, 2026-10-23: 12 sequential and 2 concurrent observations; 14 of 20 planned calls completed before the thermal stop. Milliseconds, nearest-rank p95; not a production latency guarantee. Source: evidence/model-measurements.json. The selected PNG is the existing English figure, unchanged; Norwegian equivalent remains in resultat/norsk/figurer/01_model_response_times.png.

Norsk — Figur 2 (støttemateriale). Foreløpige modellresponstider, 2026-10-23: 12 sekvensielle og 2 samtidige observasjoner; 14 av 20 planlagte kall fullført før termisk stopp. Millisekunder, nærmeste-rang p95; ingen garanti for responstid i produksjon. Kilde: evidence/model-measurements.json. Valgt PNG er den eksisterende engelske figuren, uendret; norsk motstykke finnes i resultat/norsk/figurer/01_model_response_times.png.
''')
    # Render the architecture from the selected workflow using an existing plotting dependency.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(10,2.05))
    ax.set(xlim=(0,10), ylim=(0,2.05))
    ax.axis('off')
    texts = ['Question +\nprivacy gate','Local approved\ncontext + sufficiency','Ollama: select\nwhole paragraph','Verify exact\nevidence + provenance','Official citation\nor safe refusal']
    for i, text in enumerate(texts):
        x = i*2+.06
        ax.add_patch(FancyBboxPatch((x,.85),1.76,.72,boxstyle='round,pad=0.04',facecolor='#eaf3f8',edgecolor='#28536b'))
        ax.text(x+.88,1.21,text,ha='center',va='center',fontsize=9)
        if i < 4:
            ax.annotate('',(x+1.98,1.21),(x+1.8,1.21),arrowprops={'arrowstyle':'->'})
    ax.text(.1,.35,'Human-reviewed admission before runtime; live HTML acquisition disabled.',fontsize=9)
    ax.text(6.05,.35,'At most one correction + re-verification.',fontsize=9)
    fig.tight_layout(pad=.2)
    fig.savefig(DEST/'figures/aisha-workflow.pdf', bbox_inches='tight')
    fig.savefig(DEST/'figures/aisha-workflow.png', dpi=180, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    main()
