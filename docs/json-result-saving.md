# Safe JSON result saving ? KIUA-2003

## Implementation and decisions

Local stacked branch feat/json-result-saving starts from feat/source-workflow at daa5e0d. PR 2 is unchanged. Evidence fix e833983 remains separate. No schema, workflow interface, summarizer or verification component is modified.

storage.save_result(result: Result, destination: Path) -> Path serializes through Result.to_json(), preflights UTF-8 encoding, then opens the destination with exclusive creation mode x, UTF-8 encoding and LF newlines. Existing filesystem entries are never overwritten. There is no check-then-create race or overwrite flag. It returns the requested Path only after the file closes successfully.

Parent directories must already exist. Missing parents, directory destinations, permission errors and disk/write errors propagate to the caller. Serialization and encoding failures occur before the destination is opened. Saving does not interpret evidence, change statuses, or imply semantic fact-checking.

The CLI accepts optional --output. Without it, JSON stdout remains unchanged. With it, saving must succeed before JSON is printed to stdout. Handled saving/serialization failures produce an error on stderr and exit code 2 without success JSON. There are no success messages mixed into JSON stdout.

## Usage

From the repository root, Python 3.12, standard library only:

```powershell
python -m unittest discover -s eval -p 'test_*.py' -v
python -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json
```

For optional saving, first choose an existing output directory. For example, create output/ once if it does not exist, then run:

```powershell
python -X utf8 -m hamar_agent --fixture fixtures/water-synthetic.json --output output/demo.json
```

The same JSON is printed to stdout and written as UTF-8 to the new file. Repeating this filename fails without changing the existing file. Choose a different filename for another run. output/ is already ignored by Git. In PyCharm append --output output/demo.json to module hamar_agent parameters; use the repository root as working directory.

## Limitations

Exclusive creation guarantees no replacement, not atomic completion or crash durability. A write/close error or interruption can leave an empty or partial newly created file; no cleanup or deletion is attempted. A failed stdout write after a successful save can leave a valid saved file despite terminal failure. No automatic retries, directory creation, filename generation, backups, fsync or concurrent-reader publication protocol are included.

The destination is an explicit user-supplied local path, not confined to output/. Prefer the ignored output/ directory. No personal-data detection, live retrieval or provider integration is added; use synthetic inputs only. Shared-schema limitations, including the separate evidence-reference follow-up, remain unchanged.

## Validation record

Python 3.12.10: python -m unittest discover -s eval -p 'test_*.py' -v passed all 39 tests: 25 existing and 14 new storage/CLI tests. Tests cover exact UTF-8/LF JSON, duplicate and empty-file preservation, missing parent, directory destination, permission and write errors, serialization and encoding errors before opening, CLI stdout compatibility, saving success and clean CLI failures. Tests use temporary directories and synthetic data; no network or paid API is required. Mocked write errors test error propagation; crash durability is not claimed.

## Prompt and ownership record

User approved local implementation of storage, CLI integration, tests and documentation on a stacked branch. powerNeron owns this component. JeppeGs's modules and shared interfaces remain unchanged. Remote writes, PR creation and merging require separate approval.
