# Independent search flows and source update proposals

The portal has two separate interactions:

- **Vanlig kommunesøk** submits the first field to `/api/search` and displays reviewed document matches and original official links. It does not invoke Ollama.
- **Spør AI-agenten** submits its own question directly to `/api/answer`; it does not require a preceding search and does not reuse the selected category or ordinary-search result. It runs retrieval, the existing local Ollama adapter, claim verifier and one bounded correction/re-verification path. A new AI question clears the prior answer and JSON download state. Editing the question also hides the result for the old question.

The current real-source adapter intentionally allows only a complete approved paragraph as a published claim. The existing verifier provides evidence-reference and claim checks but cannot reliably establish arbitrary Norwegian paraphrase semantics. To preserve the evidence guarantee, real-source answers remain exact approved excerpts, separately labeled with their original excerpt and citations. The interface does not claim that exact matching proves factual truth. Natural paraphrase publication requires a separately validated semantic verification method; no such method was introduced here. Unsupported questions receive an insufficient-evidence result with no AI claim.

Source update handling is proposal-only and offline. See [source-update proposal policy](source-update-proposals.md) for the manual command and the reason live HTML requests remain disabled under the current privacy boundary.

Validation command:

```powershell
python -X utf8 -m harness.offline_tests
```
