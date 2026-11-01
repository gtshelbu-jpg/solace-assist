# Native package development

After reviewing and committing the project, run:

```bash
python packaging/arch/prepare-source.py
```

This exports tracked files at the exact commit, creates a deterministic gzip
source archive, records its commit/SHA256, and writes a local-source PKGBUILD under
ignored `dist/arch/<version>/`. No `SKIP` checksum, network-source substitution,
signing-key access, package installation or system Python modification occurs.

## Build and verify

Use an unprivileged build user in a disposable Arch environment. Install the
declared build dependencies there, along with `python-textual` to include the UI
tests. From the generated recipe directory, build with an explicitly chosen key:

```bash
makepkg --sign --key "${SIGNING_KEY:?Set the reviewed full signing-key fingerprint}"
```

The recipe runs the test suite in `check()`. Without Textual, UI tests explicitly
skip; a passing CLI-only build is not complete UI validation. Inspect package
contents and verify its signature with a dedicated Pacman keyring before testing
installation in a disposable target. Do not disable signature verification.

The resulting package needs a trusted signed repository before Black's optional
Assist group can install it. Textual remains optional for the standalone CLI;
Black's optional Assist group selects the TUI dependency too. Repository trust,
key rotation/revocation and release ownership are separate distribution policies.
Never promote disposable validation signing keys into production trust.

The recipe installs the MIT license for original code/documentation and the NOTICE
preserving third-party rights. Native binary-package validation/signing is separate
from publishing the source repository.
