## When to use it

Use the Wireshark GUI for interactive protocol trees and TShark for a terminal
workflow over the same packet-analysis engine. These examples use TShark to read
an existing capture; they do not enable live capture or change interface state.

## Useful options

| Option | Meaning |
| --- | --- |
| `-r capture.pcap` | Read saved traffic. |
| `-c 20` | Stop after reading/processing the specified packet count. |
| `-Y 'expression'` | Apply a Wireshark display filter. |
| `-f 'expression'` | Specify a capture filter for capture workflows; this is not the display-filter language. |

## Examples to review

Print a bounded summary from an existing capture:

```sh
tshark -r capture.pcap -c 20
```

Display TCP traffic from the capture using the protocol name as a display filter:

```sh
tshark -r capture.pcap -Y 'tcp'
```

The `tcp` expression selects packets dissected as TCP. Put a display expression
containing spaces in one quoted argument. Confirm additional protocol fields in
the installed Wireshark display-filter reference before building a more specific filter.

## Common mistakes and cautions

- `-Y` is not a tcpdump-style capture filter; `-f` and `-Y` are not interchangeable.
- A packet-count limit is not a promise to return that many matching displayed packets.
- Do not run the whole GUI as root just to open a capture file.
- Captures and exported results can contain sensitive traffic.

## Related tools

Use tcpdump for a small capture workflow and Wireshark for visual follow-up.
