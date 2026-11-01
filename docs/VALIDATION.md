# MVP validation record

The initial CLI/core and headless Textual tests run in disposable homes/databases,
without root or tool/package execution. Textual 8.2.8 and Python 3.14 were used on
the development workstation. Standard-library core/CLI tests also run without
Textual installed; UI tests then explicitly skip.

Tests cover the bundled task queries, categories, metadata sources/version records,
many-executable package mappings, favorites/notes/tags across synchronization,
private file permissions, import rollback, bounded archive parsing without file
extraction, FTS/SQL input handling, read-only Pacman queries, non-Arch fallback,
5,000-record performance and keyboard interaction at 140x42 and 80x24 sizes.

A real BlackArch metadata archive (5,111 package records) was downloaded over HTTPS
into `/tmp/opencode` and imported as **not independently signature-verified metadata**.
Its SHA256 was `1528402e6fe9b3afb9258be0e58fb90a947f46700bcd3a8634efa6b3363d6e9a`.
This hash records the tested input, not an assertion of package authenticity.
Existing Arch cache snapshots added 15,614 package records. A combined disposable
catalog contained 20,725 package records, with no repository enablement, signing-key
import, package installation or execution of indexed programs. Initial imports
took approximately one second for BlackArch and three seconds for local sources
on this machine; these are observations, not hardware-independent promises.

Package caches are rolling snapshots. Imported metadata is not a command guide,
and metadata availability does not establish installation or trust.
An import never authorizes an install action. Future synchronization/download
features must not blur this boundary or disable verification.

Remaining validation: distribution packaging in a clean Arch builder; full
interactive terminal/emulator coverage; documentation accuracy/version review;
cross-shell PTY/renderer/adapters; Elephant integration; binary packaging and
release process. No shell feature, native signed package or production release
is claimed by this MVP.

## Source-checked guides (0.1.0a2)

Eight original guides add descriptions, option explanations, examples and cautions.
The bundled guide index records upstream URLs, review date and version scope;
the catalog records each guide's content hash. Both interfaces display provenance
and distinguish source review from runtime validation. Indexed binaries were not
executed to test the examples. Remaining six purpose references and imported
package records do not acquire invented guides.

Tests additionally cover content refresh, searchable guide text and version-1
migration with a private SQLite backup, preserving personal state, recent history,
installed snapshots and imported package metadata. Original source/documentation
is MIT licensed; third-party rights remain separate in NOTICE.
