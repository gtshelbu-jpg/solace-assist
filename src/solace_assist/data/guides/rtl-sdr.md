## When to use it

Use `rtl_test` to check whether a supported RTL-SDR receiver can deliver samples.
Use `rtl_sdr` when you need raw I/Q data for a later, separate demodulation/decoding step.
These receiver utilities do not automatically identify a radio protocol.

## Useful options

| Option | Meaning |
| --- | --- |
| `rtl_test -s 2048000` | Check sampling at the requested rate, in samples per second. |
| `rtl_sdr -f 100000000` | Tune the recorder to a frequency in Hz. |
| `rtl_sdr -s 2048000` | Select the recorder's sample rate. |
| `rtl_sdr -n 2048000` | Bound the requested number of samples instead of recording indefinitely. |
| `-d 0` | Select a device index; the upstream utilities also accept supported serial selection. |

## Examples to review

Check sample delivery; stop the continuous test with Ctrl+C:

```sh
rtl_test -s 2048000
```

Record a bounded raw I/Q sample to a file:

```sh
rtl_sdr -f 100000000 -s 2048000 -n 2048000 recording.iq
```

The frequency is an example, not a recommendation about what you may legally receive.
At that sample rate/count the requested recording is approximately one second.
The output is raw interleaved unsigned 8-bit I/Q, not a WAV or decoded audio file.

## Common mistakes and cautions

- Check local law and consent requirements for receiving or storing signals.
- A busy USB device, driver binding or permission problem is not proof of bad RF reception.
- Disk usage grows quickly with sample rate and recording duration; use a count for initial tests.
- `-p` means different things in different RTL-SDR utilities. Do not copy flags between programs blindly.
- Keep gain, sample rate and tuning metadata with recordings so later analysis is reproducible.

## Related tools

Gqrx provides an interactive receiver; protocol-specific decoders are separate tools.
