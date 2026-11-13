"""Root Anchor (RA): stand-in for the smart contract that stores finalized roots.

It accepts a new Domain Root only if
  * the owner's signature on the transition is valid, and
  * the epoch is exactly e* + 1 and the predecessor root matches,
then recomputes the Global Root R_G over all current Domain Roots.
The prototype would deploy this logic as a Solidity contract on a local chain.
"""
from dataclasses import dataclass

from .crypto import sig_ok
from .hashing import H, enc
from .merkle import merkle_root


def transition_message(domain, epoch, r_d: bytes, prev: bytes) -> bytes:
    return enc({"domain": domain, "epoch": epoch, "R_D": r_d, "prev": prev})


@dataclass
class AnchorEntry:
    domain: str
    epoch: int
    R_D: bytes
    R_G: bytes
    block: int


class RootAnchor:
    def __init__(self):
        self.owners = {}      # domain -> owner public key
        self.current = {}     # domain -> (epoch, R_D)
        self.history = []     # every accepted transition
        self.R_G = merkle_root([])
        self.block = 0

    def register_domain(self, domain, owner_public_key):
        self.owners[domain] = owner_public_key
        self.current[domain] = (0, b"\x00" * 32)

    def submit(self, domain, epoch, r_d: bytes, sig: bytes):
        e_star, prev = self.current[domain]
        if epoch != e_star + 1:
            raise ValueError(f"epoch must be {e_star + 1}, got {epoch}")
        if not sig_ok(self.owners[domain], transition_message(domain, epoch, r_d, prev), sig):
            raise ValueError("owner signature invalid")
        self.current[domain] = (epoch, r_d)
        self.R_G = merkle_root(
            [H(d, e, r) for d, (e, r) in sorted(self.current.items())]
        )
        self.block += 1
        self.history.append(AnchorEntry(domain, epoch, r_d, self.R_G, self.block))

    def latest(self, domain):
        """What a Data User reads: (e*, R_D^(e*))."""
        return self.current[domain]
