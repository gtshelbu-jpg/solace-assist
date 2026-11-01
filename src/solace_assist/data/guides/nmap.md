## When to use it

Start with Nmap when you know which lab host you are allowed to investigate and
want to identify its reachable services. Version detection asks services questions;
it is more intrusive than simply reading an existing packet capture.

## Useful options

| Option | Meaning |
| --- | --- |
| `-p 22,80,443` | Inspect only this explicit list of ports. |
| `--top-ports 20` | Inspect the 20 highest-ranked ports in Nmap's service data. |
| `-sV` | Send probes to identify service/software versions. |
| `--version-light` | Reduce version-probe intensity; identification may be less complete. |

## Examples to review

Inspect a small port list on an authorized lab host:

```sh
nmap -sV -p 22,80,443 192.0.2.10
```

Use a short common-port list and lighter version detection:

```sh
nmap -sV --version-light --top-ports 20 192.0.2.10
```

`192.0.2.10` is a documentation placeholder, not a real target supplied by Assist.
Replace it only with a host you own or are explicitly authorized to test.

## Common mistakes and cautions

- An open port or a version banner is not proof of an exploitable vulnerability.
- Service identification can be incomplete, proxied or misleading.
- Do not expand to an entire subnet just because a single-host example worked.
- Version probes can affect fragile devices. Keep the scope and change window explicit.

## Related tools

Use tcpdump or Wireshark to inspect captured traffic; use smbclient when the
authorized investigation specifically concerns SMB shares.
