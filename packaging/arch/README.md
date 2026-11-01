# Native package development

After reviewing and committing the project, run:

```bash
python packaging/arch/prepare-source.py
```

This exports tracked files at the exact commit, creates a deterministic gzip
source archive, records its commit/SHA256, and writes a local-source PKGBUILD under
ignored `dist/arch/<version>/`. No `SKIP` checksum, network-source substitution,
signing-key access, package installation or system Python modification occurs.

Build/test/sign that recipe in an isolated Arch environment using the explicitly
chosen signing key. The resulting package needs a trusted signed repository before
Black's package manager can install it. Textual remains optional for the CLI;
Black's optional Assist group selects the TUI dependency too.

No native package build or binary-repository publication has been validated yet.
The recipe deliberately leaves license metadata unresolved: do not publish it
until the project owner chooses code/data licenses and source provenance policy.
