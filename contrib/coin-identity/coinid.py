#!/usr/bin/env python3
"""
coinid.py - chain-identity tooling for a CryptoNote/Monero-derived coin.

Generates the values that make a fork a *separate* network:
  * address prefixes (so addresses start with a chosen string, e.g. "Pa")
  * P2P network IDs (random 16-byte UUIDs)
  * genesis coinbase transactions (valid ed25519 points + optional message)

Pure Python; needs `pycryptodome` for original Keccak-256 (cn_fast_hash).

Examples
  python3 coinid.py prefix Pa            # find a base58 prefix whose addresses start with "Pa"
  python3 coinid.py network-id           # print a fresh network ID as a C initializer
  python3 coinid.py genesis --reward 2384185791015 --message "headline of the day"
  python3 coinid.py address --prefix 12345   # show an example address for a prefix
"""
import argparse
import os
import secrets
import sys

try:
    from Crypto.Hash import keccak as _keccak
except ImportError:  # no pycryptodome: use the built-in pure-Python version below
    _keccak = None


# --------------------------------------------------------------------------- hashing
_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
       0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
       0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
       0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
       0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
       0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M64 = (1 << 64) - 1


def _keccak_f(a):
    for rc in _RC:
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ (((c[(x + 1) % 5] << 1) | (c[(x + 1) % 5] >> 63)) & _M64) for x in range(5)]
        a = [[a[x][y] ^ d[x] for y in range(5)] for x in range(5)]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                r = _ROT[x][y]
                b[y][(2 * x + 3 * y) % 5] = ((a[x][y] << r) | (a[x][y] >> (64 - r))) & _M64 if r else a[x][y]
        a = [[b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        a[0][0] ^= rc
    return a


def _keccak256_py(data: bytes) -> bytes:
    rate = 136
    msg = bytearray(data) + b"\x01"
    msg += b"\x00" * ((-len(msg)) % rate)
    msg[-1] |= 0x80
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(msg), rate):
        for i in range(rate // 8):
            a[i % 5][i // 5] ^= int.from_bytes(msg[off + 8 * i: off + 8 * i + 8], "little")
        a = _keccak_f(a)
    return b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


def keccak256(data: bytes) -> bytes:
    """Original Keccak-256 (NOT SHA3-256) - what CryptoNote calls cn_fast_hash."""
    if _keccak is None:
        return _keccak256_py(data)
    k = _keccak.new(digest_bits=256)
    k.update(data)
    return k.digest()


# --------------------------------------------------------------------------- ed25519
Q = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, Q - 2, Q)) % Q
I = pow(2, (Q - 1) // 4, Q)


def _xrecover(y):
    xx = (y * y - 1) * pow(D * y * y + 1, Q - 2, Q)
    x = pow(xx, (Q + 3) // 8, Q)
    if (x * x - xx) % Q != 0:
        x = (x * I) % Q
    if x % 2 != 0:
        x = Q - x
    return x


_BY = (4 * pow(5, Q - 2, Q)) % Q
_BX = _xrecover(_BY)
BASE = (_BX, _BY, 1, (_BX * _BY) % Q)  # extended coordinates (X, Y, Z, T)


def _add(p, q):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % Q
    b = (y1 + x1) * (y2 + x2) % Q
    c = t1 * 2 * D * t2 % Q
    dd = z1 * 2 * z2 % Q
    e, f, g, h = b - a, dd - c, dd + c, b + a
    return (e * f % Q, g * h % Q, f * g % Q, e * h % Q)


def _scalarmult(p, e):
    r = (0, 1, 1, 0)
    while e > 0:
        if e & 1:
            r = _add(r, p)
        p = _add(p, p)
        e >>= 1
    return r


def _encode_point(p) -> bytes:
    x, y, z, _ = p
    zi = pow(z, Q - 2, Q)
    x, y = x * zi % Q, y * zi % Q
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decode_point(s: bytes):
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if (x & 1) != (s[31] >> 7):
        x = Q - x
    p = (x, y, 1, x * y % Q)
    # on-curve check: -x^2 + y^2 = 1 + d x^2 y^2
    if (-x * x + y * y - 1 - D * x * x * y * y) % Q != 0:
        raise ValueError("point not on curve")
    return p


def is_valid_point(s: bytes) -> bool:
    try:
        _decode_point(s)
        return True
    except ValueError:
        return False


def nums_point(label: bytes) -> bytes:
    """A "nothing up my sleeve" point: hash the label, decode it as a point and
    multiply by the cofactor 8.  Nobody knows its discrete log, so nobody holds a
    secret key for it.  Deterministic, so anyone can reproduce it from the label."""
    ctr = 0
    while True:
        h = keccak256(b"Opacra NUMS point|" + label + b"|" + ctr.to_bytes(4, "little"))
        ctr += 1
        y = int.from_bytes(h, "little") & ((1 << 255) - 1)
        if y >= Q:
            continue
        try:
            p = _decode_point(h)
        except ValueError:
            continue
        p8 = _scalarmult(p, 8)
        enc = _encode_point(p8)
        if enc == _encode_point((0, 1, 1, 0)):  # identity: low-order input
            continue
        return enc


def gen_keypair():
    """Random CryptoNote keypair: secret scalar (mod l) and public point s*G."""
    sec = secrets.randbelow(L - 1) + 1
    return sec.to_bytes(32, "little"), _encode_point(_scalarmult(BASE, sec))


# --------------------------------------------------------------------------- varint / base58
def varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_ENC_BLOCK_SIZES = [0, 2, 3, 5, 6, 7, 9, 10, 11]


def _encode_block(block: bytes) -> str:
    num = int.from_bytes(block, "big")
    size = _ENC_BLOCK_SIZES[len(block)]
    chars = []
    for _ in range(size):
        num, rem = divmod(num, 58)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars))


def cn_base58_encode(data: bytes) -> str:
    out = []
    for i in range(0, len(data), 8):
        out.append(_encode_block(data[i:i + 8]))
    return "".join(out)


def encode_address(prefix: int, spend_pub: bytes, view_pub: bytes, payment_id: bytes = b"") -> str:
    body = varint(prefix) + spend_pub + view_pub + payment_id
    return cn_base58_encode(body + keccak256(body)[:4])


# --------------------------------------------------------------------------- prefix search
def _address_bounds(prefix: int, extra_len: int = 0):
    """Smallest/largest possible address for a prefix (keys all-0x00 / all-0xff)."""
    lo = encode_address(prefix, b"\x00" * 32, b"\x00" * 32, b"\x00" * extra_len)
    hi = encode_address(prefix, b"\xff" * 32, b"\xff" * 32, b"\xff" * extra_len)
    return lo, hi


def find_prefixes(target: str, max_prefix: int = 1 << 21, extra_len: int = 0, limit: int = 5):
    """Prefixes whose every address starts with `target` (checked at both extremes).

    The leading characters depend only on the first 8-byte base58 block, and a
    fixed-length block encodes monotonically, so checking the all-zero and
    all-0xff keys proves the property for every key in between."""
    found = []
    for p in range(1, max_prefix):
        lo, hi = _address_bounds(p, extra_len)
        if lo.startswith(target) and hi.startswith(target):
            found.append((p, len(lo)))
            if len(found) >= limit:
                break
    return found


# --------------------------------------------------------------------------- genesis
def genesis_tx(reward: int, message: str = "", unlock_window: int = 60):
    """Version-1 coinbase for block 0, same layout as Monero's GENESIS_TX.

    The output key and the transaction public key are "nothing up my sleeve"
    points derived from the message (see nums_point), so nobody has ever held a
    secret key for the genesis output, even if a future upgrade (such as FCMP++)
    made old pre-RingCT outputs spendable.  Today it is also unspendable because it
    has a unique amount and no ring of the required size can reference it.  The
    whole transaction is reproducible from the message alone.
    """
    label = message.encode("utf-8")
    out_key = nums_point(b"genesis output|" + label)
    tx_pub = nums_point(b"genesis txpub|" + label)
    extra = b"\x01" + tx_pub                      # TX_EXTRA_TAG_PUBKEY
    if message:
        msg = message.encode("utf-8")
        if len(msg) > 255:
            raise ValueError("genesis message must be <= 255 bytes")
        extra += b"\x02" + varint(len(msg)) + msg  # TX_EXTRA_NONCE
    tx = (
        varint(1)                   # version
        + varint(unlock_window)     # unlock_time = height(0) + CRYPTONOTE_MINED_MONEY_UNLOCK_WINDOW
        + varint(1) + b"\xff" + varint(0)          # 1 input: txin_gen(height 0)
        + varint(1) + varint(reward) + b"\x02" + out_key  # 1 output: txout_to_key
        + varint(len(extra)) + extra
    )
    return tx.hex(), out_key.hex(), tx_pub.hex()


def network_id() -> bytes:
    return os.urandom(16)


def c_uuid(b: bytes) -> str:
    return ", ".join("0x%02X" % x for x in b)


# --------------------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("prefix", help="find address prefixes producing a leading string")
    sp.add_argument("target")
    sp.add_argument("--integrated", action="store_true", help="search for integrated addresses (+8 byte payment id)")
    sp.add_argument("--limit", type=int, default=5)

    sub.add_parser("network-id", help="print a random network id")

    sg = sub.add_parser("genesis", help="build a genesis coinbase transaction")
    sg.add_argument("--reward", type=int, required=True, help="atomic units; must equal the block reward at height 0")
    sg.add_argument("--message", default="")

    sa = sub.add_parser("address", help="show a random example address for a prefix")
    sa.add_argument("--prefix", type=int, required=True)
    sa.add_argument("--integrated", action="store_true")

    args = ap.parse_args()
    if args.cmd == "prefix":
        for p, n in find_prefixes(args.target, extra_len=8 if args.integrated else 0, limit=args.limit):
            print(f"{p}\t(address length {n})")
    elif args.cmd == "network-id":
        print("{ { " + c_uuid(network_id()) + " } }")
    elif args.cmd == "genesis":
        tx, out_key, tx_pub = genesis_tx(args.reward, args.message)
        print(tx)
    elif args.cmd == "address":
        _, s = gen_keypair()
        _, v = gen_keypair()
        print(encode_address(args.prefix, s, v, secrets.token_bytes(8) if args.integrated else b""))


if __name__ == "__main__":
    main()
