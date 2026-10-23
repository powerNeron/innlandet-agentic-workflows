"""Record two isolated CLI runs; never fetch municipal HTML or overwrite logs."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'comp2/evidence'


def main():
    commands = [
        ('walking-skeleton-synthetic.json', ['-m', 'hamar_agent', '--fixture', 'fixtures/water-synthetic.json']),
        ('walking-skeleton-real.json', ['-m', 'hamar_agent', '--real-sources', '--source', 'hamar-byggesak', '--model', 'llama3.2:3b', '--ollama-timeout', '90']),
    ]
    records = []
    for name, arguments in commands:
        path = OUT / name
        if path.exists():
            raise FileExistsError(name)
        started = datetime.now(timezone.utc).isoformat()
        run = subprocess.run([sys.executable, '-X', 'utf8', *arguments], cwd=ROOT, capture_output=True, encoding='utf-8', timeout=200)
        record = {'command': ['python','-X','utf8',*arguments], 'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': run.returncode, 'python': sys.version.split()[0], 'output': 'comp2/evidence/'+name}
        if run.returncode == 0:
            data = json.loads(run.stdout)
            with path.open('x', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
        else:
            # Avoid publishing arbitrary interpreter/OS paths from error output.
            record['output'] = None
            record['failure'] = 'CLI failed; successful execution is not claimed.'
        records.append(record)
        print(name, 'exit_code='+str(run.returncode))
    with (OUT/'new-command-register.json').open('x', encoding='utf-8') as stream:
        json.dump(records, stream, indent=2)


if __name__ == '__main__':
    main()
