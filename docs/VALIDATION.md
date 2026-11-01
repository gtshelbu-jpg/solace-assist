# Testing and validation

## Run the test suite

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests use disposable databases and homes without root or indexed-tool execution.
Install the optional `tui` extra for headless Textual checks; otherwise UI tests
explicitly skip. Check the skip count before reporting complete UI coverage.

## Coverage

- Task search, categories, source/version records and many-executable mappings.
- Notes, favorites and tags across metadata refresh and schema migration.
- Private database/backup permissions and preservation of imported snapshots.
- Transaction rollback, bounded archive reads without extraction, FTS/SQL input
  handling and terminal-control-sequence filtering.
- Fixed read-only Pacman queries and operation without a Pacman installation.
- A 5,000-record fixture and keyboard navigation at wide/narrow terminal sizes.
- Bundled guide loading, searchable text and provenance in the shared catalog.

Headless checks do not replace interactive testing in supported terminals.
Before distributing a package, also inspect wheel contents and test the CLI from
the built wheel independently of the source checkout. Native Arch packages need
clean-builder validation and a separately reviewed signing/distribution workflow.

## Documentation and metadata trust

Bundled guides record upstream sources, review dates and version scope. Source
review is not runtime validation of an example against an installed binary.
Purpose-only references and imported package metadata do not acquire inferred
flags or invented guides. Unknown/version-specific options must remain explicit.

Package caches are rolling snapshots. Imported archives are not independently
signature-verified by Assist. Metadata availability establishes neither installation
nor authenticity, and importing it never authorizes execution or installation.

Assisted-shell mode and Elephant integration are not implemented. Do not describe
catalog tests as cross-shell PTY, terminal-renderer or launcher validation.
