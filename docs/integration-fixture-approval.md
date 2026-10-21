# Integration fixture approval

The combined main, saving and retrieval suite previously ran 77 tests with 12 setup errors: verification-synthetic.json was not registered with the guarded fixture loader.

Reviewed this existing fixture: explicitly fictional measurements, no real municipal facts or personal information. Registered synthetic-verification-demo with its exact path and a fixed SHA-256 digest normalized for LF/CRLF. Updated the registry membership assertion to expect exactly the two reviewed synthetic fixtures. Arbitrary paths, unknown IDs and changed content remain rejected.

No fixture, shared schema, summarizer, verifier, revision module or JeppeGs test was changed. The production HTTP registry remains empty; this is local fixture approval only. The evidence fix remains separate. Changes are local to the integration worktree and are not committed or published.

Validation: all 77 combined offline tests passed on Python 3.12.10 with socket.socket and socket.create_connection blocked. No live retrieval or paid APIs used.
