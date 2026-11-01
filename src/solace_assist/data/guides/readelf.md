## When to use it

Use readelf for an initial inventory of an ELF executable, shared object or object
file. It interprets the file format rather than intentionally launching the inspected
program. Untrusted binary parsers should still be kept updated and isolated.

## Useful options

| Option | Meaning |
| --- | --- |
| `-h` | Show the ELF file header, including class, architecture and entry point. |
| `-S` | List section headers. Uppercase `S` is different from lowercase `s`. |
| `--symbols` | Show symbol-table entries when the file has them. |
| `--wide` | Avoid normal 80-column truncation/wrapping for relevant output. |

## Examples to review

Identify the ELF architecture and header:

```sh
readelf -h sample.elf
```

Inspect sections:

```sh
readelf -S sample.elf
```

Inspect symbols with wider output:

```sh
readelf --wide --symbols sample.elf
```

## Common mistakes and cautions

- `sample.elf` must be an actual input file, not a command you want Assist to run.
- Stripped binaries may lack useful symbol names; absence is not a parser failure.
- Do not execute an unknown file merely to discover which architecture it targets.
- readelf ships with Binutils on Arch; package names and executable names differ.

## Related tools

Use radare2 or Ghidra for disassembly/decompilation, and Binwalk for embedded-file signatures.
