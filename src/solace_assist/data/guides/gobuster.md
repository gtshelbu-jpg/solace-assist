## When to use it

Use Gobuster directory mode to test a defined wordlist of candidate paths on an
authorized web application. It sends active requests: start with a small scope and
low concurrency, and agree on the testing window with the system owner.

## Useful options

| Option or mode | Meaning |
| --- | --- |
| `dir` | Select web directory/file enumeration mode. |
| `-u URL` | Set the target URL for this mode. |
| `-w wordlist.txt` | Read candidate names from a wordlist you provide. |
| `-t 5` | Set the worker/thread count. |
| `-o results.txt` | Write results to a named output file. |

## Examples to review

Inspect mode-specific help before a run:

```sh
gobuster dir --help
```

Use a small local wordlist against an authorized lab URL:

```sh
gobuster dir -u https://example.test -w wordlist.txt -t 5 -o results.txt
```

`example.test` is a reserved documentation domain; supply your approved lab URL.
The wordlist must already exist. The example writes an output file and sends requests.

## Common mistakes and cautions

- A wildcard response or application catch-all can make nonexistent paths look valid.
- A 403 response is not proof of a usable vulnerability or accessible sensitive file.
- Different Gobuster modes have different flags; DNS-mode short options changed across versions.
- Do not paste authentication headers, cookies or target secrets into shared examples.
- Low concurrency reduces load but does not replace authorization or rate-limit agreement.

## Related tools

subfinder performs passive subdomain discovery; Nmap investigates approved network services.
