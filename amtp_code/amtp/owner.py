"""Data Owner side (Phases 1-3): encrypt, index, sign and publish an epoch."""
import os

from .anchor import transition_message
from .core.crypto import Signer, keyword_cipher, make_ct
from .dht import ciphertext_id
from .core.hashing import H, enc
from .index import DomainState, PartitionLayout, extract_keywords


class DomainKeys:
    """Per-domain secrets issued by the Domain Authority.
    K_s: keyword key (never given to the Cloud Server)
    K_a: query-authentication key (shared with authorised users and the CS)"""

    def __init__(self):
        self.k_s = os.urandom(64)   # AES-SIV-256 key
        self.k_a = os.urandom(32)


def keyword_key(k_s: bytes, word: str) -> bytes:
    """h_w = H(C_w) with C_w = DEnc_{K_s}(w)"""
    return H(keyword_cipher(k_s, word))


class DataOwner:
    def __init__(self, domain, name, keys: DomainKeys, authority, anchor, server,
                 theta_min=1, theta_max=4):
        self.domain, self.name = domain, name
        self.keys, self.authority = keys, authority
        self.anchor, self.server = anchor, server
        self.signer = Signer()
        self.layout = PartitionLayout(domain, theta_min, theta_max)
        self.fwd = {}           # cid -> keyword keys   (Fwd_i)
        self.epoch = 0
        anchor.register_domain(domain, self.signer.public)

    def encrypt(self, doc: dict):
        """Phase 1: CT_d = <E_d, C_Kd, aad_d> as raw bytes,  cid_d = H(CT_d)."""
        k_d = os.urandom(32)
        aad = {"domain": self.domain, "doc": doc["id"], "policy": doc["policy"]}
        body = enc({"title": doc["title"], "body": doc["body"]})
        ct = make_ct(k_d, body, self.authority.wrap(k_d, doc["policy"]), aad)   # raw bytes
        # W(d): taken from the shared dataset (documents.csv) when given, so AMTP indexes exactly
        # the keyword sets every baseline uses; otherwise the demo extractor is applied.
        if doc.get("keywords") is not None:
            keywords = {k.strip() for k in doc["keywords"] if k and k.strip()}
        else:
            keywords = extract_keywords(doc["title"] + " " + doc["body"])
        return ct, ciphertext_id(ct), {keyword_key(self.keys.k_s, w) for w in keywords}

    def add_documents(self, docs):
        """Upload documents, then build, sign and anchor the next epoch."""
        for doc in docs:
            ct, cid, keys = self.encrypt(doc)
            self.server.store_ciphertext(cid, ct)
            self.fwd[cid] = keys
            self.layout.insert(cid)
        return self.publish()

    def publish(self):
        new_epoch = self.epoch + 1
        state = DomainState(self.domain, new_epoch, self.layout.snapshot(), dict(self.fwd))
        _, prev = self.anchor.latest(self.domain)
        sig = self.signer.sign(transition_message(self.domain, new_epoch, state.R_D, prev))
        self.server.store_state(state)
        self.anchor.submit(self.domain, new_epoch, state.R_D, sig)
        self.epoch = new_epoch
        return state
