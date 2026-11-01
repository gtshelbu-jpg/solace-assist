## When to use it

Use tcpdump to answer “what packets are present?” before building a more complex
analysis workflow. Prefer reading an existing capture when you do not need to
collect new traffic.

## Useful options

| Option | Meaning |
| --- | --- |
| `-r capture.pcap` | Read a saved capture instead of sniffing a live interface. |
| `-i wlan0` | Select an interface; substitute the actual interface name. |
| `-n` | Keep addresses/ports numeric instead of resolving names. |
| `-c 100` | Stop after processing the requested packet count. |
| `-w capture.pcap` | Write packet data to a capture file instead of the normal decoded listing. |

## Examples to review

Inspect the first 20 packets of an existing capture without live sniffing:

```sh
tcpdump -n -c 20 -r capture.pcap
```

Collect a bounded capture on an authorized interface:

```sh
sudo tcpdump -i wlan0 -n -c 100 -w capture.pcap
```

The first command reads a file. The second requires appropriate capture privileges,
uses a real interface you select, and creates or replaces the named output file.

## Common mistakes and cautions

- A pcap is binary packet data; it is not the same as redirecting a text listing.
- Captures can contain credentials, personal data and confidential payloads.
- A Wi-Fi interface in normal operation is not automatically a monitor-mode capture.
- No root privileges are normally needed merely to read a file you can access.

## Related tools

TShark/Wireshark provides protocol-aware display filters and deeper offline analysis.
