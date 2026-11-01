## When to use it

Use Binwalk for a first map of recognizable formats embedded in a firmware image
or binary blob. Offsets and signatures help decide where to investigate next;
they are not proof that every match is a complete or correctly identified file.

## Examples to review

Inspect the signatures in an existing firmware image:

```sh
binwalk firmware.bin
```

Check the options actually supported by the installed build before enabling extraction:

```sh
binwalk --help
```

The upstream reference checked here is **Binwalk v3**, a Rust rewrite. This guide
deliberately does not carry over v2 extraction flags or third-party extraction recipes.

## Understanding the result

- An offset is a location in the input file, not automatically a partition boundary.
- Compressed, encrypted and random-looking data are not interchangeable conclusions.
- Missing recognizable signatures does not prove that the input contains no useful data.

## Common mistakes and cautions

- Work on a copy of the firmware and keep the original/hash for reproducibility.
- Extraction workflows may invoke other programs, consume disk space and expose parser bugs.
- Do not extract untrusted firmware as root or execute recovered programs automatically.
- Tools named in online examples may refer to a different Binwalk major version.

## Related tools

readelf inspects recovered ELF files; Ghidra/radare2 help investigate executable code.
