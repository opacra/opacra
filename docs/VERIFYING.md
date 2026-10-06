# Verifying an Opacra download

Every release is signed with the Opacra release key:

```
Opacra Releases <opacra@proton.me>
D861 7219 6FEC AAB6 84F5  B3FD CB65 D212 D0B1 162B
```

The same fingerprint is published in this repository (`contrib/gpg/opacra-release-key.asc`),
on https://opacra.org and on the opacra-dev GitHub account. Check that at least two of these
agree before you trust the key.

```
gpg --import opacra-release-key.asc
gpg --verify SHA256SUMS-v0.1.2.asc            # must say: Good signature from "Opacra Releases"
sha256sum -c SHA256SUMS-v0.1.2.asc 2>/dev/null | grep OK
```

`gpg` will also warn that the key "is not certified with a trusted signature". That only means
you have not personally certified the key; what matters is the "Good signature" line and that the
fingerprint matches the one above.

## For maintainers: signing a release

After `contrib/launch/package_release.sh`:

```
cd dist
sha256sum opacra-v<version>-linux-x64.tar.gz > SHA256SUMS-v<version>
gpg --local-user D86172196FECAAB684F5B3FDCB65D212D0B1162B --clearsign SHA256SUMS-v<version>
gpg --verify SHA256SUMS-v<version>.asc
```

Publish `SHA256SUMS-v<version>.asc` next to the download. The private key and its revocation
certificate are kept offline; the key expires on 5 October 2028 and can be extended before then.
