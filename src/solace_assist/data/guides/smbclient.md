## When to use it

Use smbclient to inspect the shares an authorized SMB server exposes and to browse
a selected share. A share listing is not an authorization grant, and the interactive
client also has upload/delete operations: review commands before using them.

## Useful options and syntax

| Option or form | Meaning |
| --- | --- |
| `-L HOST` | Request a server's service/share listing. |
| `-U labuser` | Select a username; without an embedded password the client can prompt. |
| `//server/share` | Select the SMB service/share to connect to. |
| `ls` | At the SMB client prompt, list the current remote directory. |
| `quit` | Leave the interactive client. |

## Examples to review

Request the share listing on an authorized lab server:

```sh
smbclient -L 192.0.2.10 -U labuser
```

Open an authorized share for interactive browsing:

```sh
smbclient //192.0.2.10/public -U labuser
```

At the resulting SMB prompt, `ls` lists the current directory and `quit` exits.
The address, username and share are placeholders; change them for your approved lab.

## Common mistakes and cautions

- Do not append a password to `-U` in a saved example or shell history.
- Server naming, Kerberos and share permissions may require a hostname/domain rather than an IP.
- Do not weaken protocol/signing policy merely to make an example connect.
- `put`, deletion and other client operations can change remote state. They are not part of this browsing example.

## Related tools

SMBMap focuses on share/permission enumeration; Wireshark helps analyze recorded protocol traffic.
