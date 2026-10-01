# -*- coding: utf-8 -*-
"""Resource-path names for 64-bit entity hashes (MurmurHash64A, seed 0).

Names come from FileDiver's hashes/hashes.txt + cracked.txt (BSD-3-Clause).
Each name is self-verifying: murmur64a(name) must equal the hash.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HASH_DIR = os.path.join(ROOT, "reference", "filediver", "hashes")
_M = 0xC6A4A7935BD1E995
_MASK = (1 << 64) - 1


def murmur64a(data, seed=0):
    h = (seed ^ (len(data) * _M)) & _MASK
    n = len(data) // 8
    for i in range(n):
        k = int.from_bytes(data[i * 8:i * 8 + 8], "little")
        k = (k * _M) & _MASK
        k ^= k >> 47
        k = (k * _M) & _MASK
        h ^= k
        h = (h * _M) & _MASK
    tail = data[n * 8:]
    if tail:
        h ^= int.from_bytes(tail, "little")
        h = (h * _M) & _MASK
    h ^= h >> 47
    h = (h * _M) & _MASK
    h ^= h >> 47
    return h


_names = None


def names():
    """-> {hash: resource path}"""
    global _names
    if _names is None:
        _names = {}
        for fn in ("hashes.txt", "cracked.txt"):
            with open(os.path.join(HASH_DIR, fn), encoding="utf-8", errors="replace") as f:
                for line in f:
                    s = line.strip()
                    if s:
                        _names.setdefault(murmur64a(s.encode("utf-8")), s)
    return _names


def name(h):
    return names().get(h)


if __name__ == "__main__":
    assert murmur64a(b"mods/dsh/double_leveller") == 0xB26F455725B61AEB
    print("murmur64a self-test OK; %d names" % len(names()))
