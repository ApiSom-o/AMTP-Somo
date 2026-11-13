"""Cryptographic primitives (all real, from the `cryptography` library).

  AES-GCM          document encryption E_d                     (real)
  AES-SIV          deterministic keyword encryption DEnc        (real)
  HMAC-SHA256      query authentication tag tau_Q               (real)
  Ed25519          owner signature on root transitions          (stand-in for ABS)
  Policy key wrap  hides K_d behind an attribute policy         (stand-in for CP-ABE)

About the two stand-ins (be explicit about this when presenting):
  * ABS is replaced by an ordinary Ed25519 signature: it proves "the Data Owner
    approved this root", but does not hide which owner signed.
  * CP-ABE is replaced by a policy-tree key wrap: each attribute has a secret
    key, AND splits K_d into XOR shares, OR copies it. A user without the right
    attributes really cannot unwrap K_d. Unlike real CP-ABE it is NOT
    collusion-resistant and the encryptor needs the attribute master secret.
    The full prototype should use a real scheme (e.g. FAME/BSW07 in Charm).
"""
import hmac
import hashlib
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature, InvalidTag

from .boolean import parse


# ---------- symmetric ----------

def aes_gcm_encrypt(key: bytes, plaintext: bytes, aad: bytes) -> dict:
    nonce = os.urandom(12)
    return {"N": nonce.hex(), "C": AESGCM(key).encrypt(nonce, plaintext, aad).hex()}


def aes_gcm_decrypt(key: bytes, box: dict, aad: bytes) -> bytes:
    return AESGCM(key).decrypt(bytes.fromhex(box["N"]), bytes.fromhex(box["C"]), aad)


def keyword_cipher(k_s: bytes, word: str) -> bytes:
    """C_w = DEnc_{K_s}(Norm(w)). Same word + same key -> same ciphertext."""
    return AESSIV(k_s).encrypt(word.strip().lower().encode(), None)


def hmac_tag(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


def hmac_ok(key: bytes, msg: bytes, tag: bytes) -> bool:
    return hmac.compare_digest(hmac_tag(key, msg), tag)


# ---------- signatures (ABS stand-in) ----------

class Signer:
    def __init__(self):
        self._sk = Ed25519PrivateKey.generate()
        self.public = self._sk.public_key()

    def sign(self, msg: bytes) -> bytes:
        return self._sk.sign(msg)


def sig_ok(public: Ed25519PublicKey, msg: bytes, sig: bytes) -> bool:
    try:
        public.verify(sig, msg)
        return True
    except InvalidSignature:
        return False


# ---------- attribute policy key wrap (CP-ABE stand-in) ----------

class AttributeAuthority:
    """Plays the Domain Authority's role of issuing attribute keys."""

    def __init__(self):
        self._msk = os.urandom(32)

    def attribute_key(self, attr: str) -> bytes:
        return HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None,
            info=b"attr:" + attr.lower().encode(),
        ).derive(self._msk)

    def user_keys(self, attrs) -> dict:
        return {a.lower(): self.attribute_key(a) for a in attrs}

    def wrap(self, secret: bytes, policy: str) -> dict:
        return self._wrap(secret, parse(policy))

    def _wrap(self, secret, node):
        if node[0] == "leaf":
            box = aes_gcm_encrypt(self.attribute_key(node[1]), secret, node[1].encode())
            return {"t": "attr", "a": node[1], **box}
        if node[0] == "OR":
            return {"t": "or", "k": [self._wrap(secret, c) for c in node[1]]}
        shares = [os.urandom(len(secret)) for _ in node[1][:-1]]
        last = secret
        for s in shares:
            last = bytes(x ^ y for x, y in zip(last, s))
        shares.append(last)
        return {"t": "and", "k": [self._wrap(s, c) for s, c in zip(shares, node[1])]}


def unwrap(blob: dict, user_keys: dict):
    """Return K_d, or None if the user's attributes do not satisfy the policy."""
    t = blob["t"]
    if t == "attr":
        key = user_keys.get(blob["a"])
        if key is None:
            return None
        try:
            return aes_gcm_decrypt(key, blob, blob["a"].encode())
        except InvalidTag:
            return None
    parts = [unwrap(child, user_keys) for child in blob["k"]]
    if t == "or":
        return next((p for p in parts if p is not None), None)
    if any(p is None for p in parts):
        return None
    out = parts[0]
    for p in parts[1:]:
        out = bytes(x ^ y for x, y in zip(out, p))
    return out


__all__ = [
    "aes_gcm_encrypt", "aes_gcm_decrypt", "keyword_cipher", "hmac_tag", "hmac_ok",
    "Signer", "sig_ok", "AttributeAuthority", "unwrap", "InvalidTag",
]
