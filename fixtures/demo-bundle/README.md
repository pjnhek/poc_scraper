# Demo Bundle

Pre-recorded JSON fixtures the pipeline can replay against instead of calling
Exa, Browserbase, or the writer/judge LLMs. Replay mode runs offline, in
seconds instead of minutes, with deterministic output for the demo path.

## Layout

```
fixtures/demo-bundle/
  exa/<method>_<digest>.json          # search_about, search_news
  browserbase/<method>_<digest>.json  # render
  llm/writer/<method>_<digest>.json   # writer-side synthesize
  llm/judge/<method>_<digest>.json    # judge-side synthesize
```

`<digest>` is a 16-character truncated SHA256 of the sorted-key JSON
serialization of the call signature, so the same call from the same code
always resolves to the same file. See `src/clients/replay.py` for the
canonical implementation.

## Running in replay mode

```
make run-demo
```

is sugar for:

```
DEMO_BUNDLE=fixtures/demo-bundle uv run python -m src.pipeline
```

When `DEMO_BUNDLE` is set, `Settings.require_for_pipeline` skips the API-key
checks; the pipeline reads every external call from this directory.

A missing fixture raises `ReplayMissError` and crashes the run. That is
intentional: a missing fixture means the bundle is incomplete for the
current pipeline shape, and the operator must re-record before continuing.
Adding `ReplayMissError` to the per-stage narrow exception tuples would
mask incompleteness as a transient degraded row.

## Recording a fresh bundle

```
RECORD_BUNDLE=fixtures/demo-bundle make run
```

This wraps the real Exa, Browserbase, writer, and judge clients in tee
wrappers that mirror every response to disk. The live API keys still have
to be set; the wrappers do not bypass them. Inspect the captured JSON
before committing.

## Phase 5 vs Phase 8

Phase 5 ships the replay/record machinery and a minimal directory shell
(this README plus three empty subdirectories). It does NOT ship the real
demo bundle, because Phase 6 polishes the sheet output and a bundle
recorded against pre-polish output would have to be re-recorded anyway.

Phase 8 records the real bundle (10 prospect domains, 3 external services,
roughly 100-200 JSON files) against the stabilized pipeline output, and
that bundle becomes the demo path the README and Loom walk through.

## Security: scrub before commit

Recorded LLM responses may contain text the live providers happened to
return. Before committing a fresh bundle, scan every JSON file for:

- API tokens, session cookies, or other secrets that may have leaked
  into a prompt or a response.
- Customer PII (the seller side stays vendor-neutral per `configs/icp.yaml`,
  but Exa or Browserbase responses can include the prospect company's
  customer testimonials, support tickets, or named employees).
- Anything that violates the public-repo discipline guard
  (`scripts/check_public_discipline.py`); the guard runs at commit time
  and blocks bundle files matching `.secrets-denylist`.

If in doubt, delete the file and re-record with a tighter query.
