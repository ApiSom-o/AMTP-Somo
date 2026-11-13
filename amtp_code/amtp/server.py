"""Cloud Server (Phase 4): admit the query, evaluate it, assemble evidence.

The server is untrusted. `mode` lets the demo make it misbehave in one
specific way so the user can watch Phase 5 catch it. Every attack below is a
real modification of the real response; nothing about the verdict is faked.
"""
import copy
import time

from .core import boolean
from .core.crypto import hmac_ok
from .dht import DHT, StorageError
from .core.hashing import H, TAG_QUERY, enc_bq
from .index import EMPTY_SLOT, SENTINEL_LO
from .core.merkle import MerkleTree

ATTACKS = {
    "honest": "Honest server",
    "tamper_ct": "Modify a returned file",
    "drop_result": "Hide one matching file",
    "extra_result": "Add a file that does not match",
    "hide_posting": "Remove an entry from a keyword's posting list",
    "false_absent": "Claim a keyword does not exist",
    "forge_partition": "Forge a partition's content",
    "stale": "Answer from an old epoch (rollback)",
    "replay": "Replay an earlier response",
    "storage_loss": "Ciphertext lost in storage",
}


def flip_one_byte(ct_hex: str, index: int = -1) -> str:
    """Tamper with a returned ciphertext: XOR one byte of the raw CT bytes (hex on the wire)."""
    b = bytearray.fromhex(ct_hex)
    b[index] ^= 0x01
    return b.hex()


def query_digest(domain, b_q, epoch, t, nonce_hex) -> bytes:
    """H(tag ‖ i ‖ Enc(B_Q) ‖ e* ‖ t ‖ η): the message under τ_Q, all fields binary."""
    return H(TAG_QUERY, domain, enc_bq(boolean.from_json(b_q)), epoch, t, bytes.fromhex(nonce_hex))


def bq_error(b_q):
    """None if B_Q is a canonical AND/OR tree over 32-byte hex query keys, else the reason."""
    try:
        ast = boolean.from_json(b_q)
        if any(len(bytes.fromhex(h)) != 32 for h in boolean.leaves(ast)):
            return "query keys must be 32-byte values"
        if enc_bq(boolean.canonical(ast)) != enc_bq(ast):
            return "B_Q is not in canonical form"
    except (TypeError, ValueError, IndexError, KeyError):
        return "B_Q is malformed"
    return None


class CloudServer:
    MAX_AGE_S = 300

    def __init__(self):
        self.states = {}          # domain -> {epoch: DomainState}
        self.query_keys = {}      # domain -> K_a
        self.dht = DHT()
        self.used_nonces = set()
        self.last_response = {}   # domain -> last honest response (for the replay scenario)

    # ----- storage (called by the Data Owner) -----
    def store_ciphertext(self, cid, ct):
        self.dht.put(cid, ct)

    def store_state(self, state):
        self.states.setdefault(state.domain, {})[state.epoch] = state

    def register_query_key(self, domain, k_a):
        self.query_keys[domain] = k_a

    def current(self, domain):
        epochs = self.states[domain]
        return epochs[max(epochs)]

    # ----- Phase 4 -----
    def search(self, t_q: dict, mode: str = "honest") -> dict:
        start = time.perf_counter()
        reason = self._admit(t_q)
        if reason:
            return {"status": "rejected", "reason": reason}
        domain = t_q["domain"]
        b_q = boolean.from_json(t_q["B_Q"])
        state = self.current(domain)
        attack = {"mode": mode, "label": ATTACKS.get(mode, mode), "applied": False, "what": ""}

        try:
            response = self._attack(mode, attack, state, b_q, t_q)
        except StorageError as err:
            return {"status": "storage_error", "reason": str(err), "attack": attack,
                    "cs_ms": _ms(start)}
        for desc in response["proof"]["partitions"]:
            desc.pop("_positions", None)          # internal helper, not sent
        if mode == "honest":
            self.last_response[domain] = copy.deepcopy(response)
        return {"status": "ok", "response": response, "attack": attack, "cs_ms": _ms(start)}

    def _admit(self, t_q):
        domain = t_q.get("domain")
        if domain not in self.states:
            return "unknown domain"
        reason = bq_error(t_q["B_Q"])
        if reason:
            return reason
        msg = query_digest(domain, t_q["B_Q"], t_q["epoch"], t_q["t"], t_q["nonce"])
        if not hmac_ok(self.query_keys[domain], msg, bytes.fromhex(t_q["tau"])):
            return "query tag τ_Q is invalid (user has no query key for this domain)"
        if abs(time.time() - t_q["t"]) > self.MAX_AGE_S:
            return "timestamp too old"
        if t_q["nonce"] in self.used_nonces:
            return "nonce already used"
        if t_q["epoch"] != self.current(domain).epoch:
            return "requested epoch is not the current finalized epoch"
        self.used_nonces.add(t_q["nonce"])
        return None

    def _attack(self, mode, attack, state, b_q, t_q):
        domain, nonce = t_q["domain"], t_q["nonce"]
        keys = sorted(boolean.leaves(b_q))
        present = [h for h in keys if lookup(state, bytes.fromhex(h)) is not None]

        if mode == "stale":
            older = self.states[domain].get(state.epoch - 1)
            if older is not None:
                resp = build_response(older, b_q, nonce, self.dht)
                resp["epoch"] = state.epoch      # pretend it is the current epoch
                attack.update(applied=True, what=f"used snapshot of epoch {older.epoch} "
                                                 f"but labelled it epoch {state.epoch}")
                return resp
        if mode == "replay" and domain in self.last_response:
            attack.update(applied=True, what="returned the previous search's response")
            return copy.deepcopy(self.last_response[domain])
        if mode == "hide_posting" and present:
            h, cid = _pick_entry(state, b_q, present, self.dht)
            attack.update(applied=True, what=f"removed file {cid[:8]} from one keyword's list")
            return build_response(state, b_q, nonce, self.dht, hide=(h, cid))
        if mode == "false_absent" and present:
            h = present[0]
            attack.update(applied=True, what="claimed one queried keyword is not indexed")
            return build_response(state, b_q, nonce, self.dht, fake_absent=h)
        if mode == "storage_loss":
            m_q = evaluate_on_state(state, b_q)
            if m_q:
                cid = bytes.fromhex(sorted(m_q)[0][0])
                attack.update(applied=True, what="all replicas of one result file are offline")
                return build_response(state, b_q, nonce, self.dht,
                                      offline=set(self.dht.replica_nodes(cid)))

        resp = build_response(state, b_q, nonce, self.dht)
        rct = resp["R_ct"]
        if mode == "tamper_ct" and rct:
            rct[0]["ct"] = flip_one_byte(rct[0]["ct"])
            attack.update(applied=True, what=f"changed one byte of file {rct[0]['cid'][:8]}")
        elif mode == "drop_result" and rct:
            gone = rct.pop()
            attack.update(applied=True, what=f"left out file {gone['cid'][:8]}")
        elif mode == "extra_result":
            inside = {r["cid"] for r in rct}
            extra = next((c for c in sorted(state.loc) if c.hex() not in inside), None)
            if extra is not None:
                pid, slot = state.loc[extra]
                rct.append({"cid": extra.hex(), "pid": pid, "loc": slot,
                            "ct": self.dht.get(extra).hex()})
                attack.update(applied=True, what=f"added non-matching file {extra.hex()[:8]}")
        elif mode == "forge_partition" and resp["proof"]["partitions"]:
            desc = resp["proof"]["partitions"][0]
            fake = list(state.by_pid[desc["pid"]].slots) + [H("forged file")]
            tree = MerkleTree(fake)
            desc.update(R_P=tree.root.hex(), n_slots=len(fake),
                        proof=[x.hex() for x in tree.multiproof(desc["_positions"])])
            attack.update(applied=True,
                          what=f"slipped a forged file into partition {desc['pid']}")
        if mode != "honest" and not attack["applied"]:
            attack["what"] = "not applicable to this query, server answered honestly"
        return resp


def _ms(start):
    return round((time.perf_counter() - start) * 1000, 2)


def _components(state, h: bytes, posting=None):
    """L_h on the wire: [(PID, [(cid hex, ℓ), ...]), ...] in PID order."""
    posting = state.postings[h] if posting is None else posting
    return [(pid, [(cid.hex(), slot) for cid, slot in comp]) for pid, comp in posting]


def evaluate_on_state(state, b_q) -> set:
    sets = {}
    for h in boolean.leaves(b_q):
        hb = bytes.fromhex(h)
        sets[h] = {(cid, pid, slot) for pid, comp in _components(state, hb)
                   for cid, slot in comp} if lookup(state, hb) is not None else set()
    return boolean.evaluate(b_q, sets)


def _pick_entry(state, b_q, present, dht):
    """Pick a (keyword, file) whose removal changes the visible result if possible."""
    m_q = {c for c, _, _ in evaluate_on_state(state, b_q)}
    for h in present:
        for _, comp in _components(state, bytes.fromhex(h)):
            for cid, _ in comp:
                if cid in m_q:
                    return h, cid
    h = present[0]
    return h, _components(state, bytes.fromhex(h))[0][1][0][0]


def build_response(state, b_q, nonce, dht, hide=None, fake_absent=None, offline=()):
    """R_Q = <i, e*, B_Q, η, R^part, R^idx, R^ct_Q, Π_Q> with ASPA multiproofs."""
    evidence, leaf_sets = [], {}
    for h in sorted(boolean.leaves(b_q)):
        hb = bytes.fromhex(h)
        posting = None if h == fake_absent else lookup(state, hb)
        if posting is not None:
            comps = _components(state, hb, posting)
            if hide and hide[0] == h:
                comps = [(pid, [e for e in comp if e[0] != hide[1]]) for pid, comp in comps]
                comps = [(pid, comp) for pid, comp in comps if comp]
            pos = state.imt_pos[hb]
            evidence.append({"h": h, "status": "present", "L": comps, "pos": pos,
                             "next": state.imt_next[hb].hex(), "n": state.imt_n,
                             "proof": [x.hex() for x in state.imt.multiproof([pos])]})
            leaf_sets[h] = {(cid, pid, slot) for pid, comp in comps for cid, slot in comp}
        else:
            evidence.append(_absent_evidence(state, hb, lie=(h == fake_absent)))
            leaf_sets[h] = set()

    m_q = boolean.evaluate(b_q, leaf_sets)
    m_cov = set().union(*leaf_sets.values()) if leaf_sets else set()
    # group the covered slots by partition once (O(|m_cov|)), instead of scanning
    # all of m_cov for every partition (O(|S_cov| x |m_cov|))
    slots_by_pid = {}
    for _, pid, slot in m_cov:
        slots_by_pid.setdefault(pid, set()).add(slot)
    s_cov = sorted(slots_by_pid)

    partitions = []
    for pid in s_cov:
        positions = sorted(slots_by_pid[pid])
        tree = state.part_trees[pid]
        partitions.append({
            "pid": pid, "v": state.by_pid[pid].v, "R_P": tree.root.hex(),
            "n_slots": len(state.by_pid[pid].slots), "pos": state.part_pos[pid],
            "proof": [x.hex() for x in tree.multiproof(positions)],
            "_positions": positions,
        })
    dom_positions = sorted(state.part_pos[pid] for pid in s_cov)
    domain_proof = {"n": len(state.partitions),
                    "proof": [x.hex() for x in state.part_tree.multiproof(dom_positions)]
                    if dom_positions else []}

    r_ct = []
    for cid, pid, slot in sorted(m_q, key=lambda x: (x[1], x[2])):
        ct = dht.get(bytes.fromhex(cid), offline=offline)   # raw CT bytes; may raise StorageError
        r_ct.append({"cid": cid, "pid": pid, "loc": slot, "ct": ct.hex()})   # hex on the JSON wire

    return {
        "domain": state.domain, "epoch": state.epoch, "B_Q": b_q, "nonce": nonce,
        "R_part": state.R_part.hex(), "R_idx": state.R_idx.hex(), "R_ct": r_ct,
        "proof": {"evidence": evidence, "partitions": partitions, "domain": domain_proof},
    }


def lookup(state, hb: bytes):
    """Phase 4 lookup: the Cuckoo filter answers "absent" at once (no false negatives); otherwise
    the B+ Search Tree gives the posting state. None = not indexed. Neither structure is evidence:
    present keys are proven by PAPC + IMT, absent keys by IMT non-membership."""
    if not state.cuckoo.might_contain(hb):
        return None
    return state.postings.get(hb)


def _absent_evidence(state, hb: bytes, lie=False):
    """Non-membership: the predecessor leaf h_lo with h_lo < h < next(h_lo).
    For a key that IS indexed (lie=True) the honest predecessor has next(h_lo) = h,
    so the forged absence claim fails the bracket check."""
    lo = state.postings.predecessor(hb) or SENTINEL_LO     # B+ tree: largest indexed key below h
    pos = state.imt_pos[lo]
    leaf = {"pos": pos, "h": lo.hex(), "rho": state.imt_rho[lo].hex(),
            "next": state.imt_next[lo].hex()}
    return {"h": hb.hex(), "status": "absent", "lo": leaf, "n": state.imt_n,
            "proof": [x.hex() for x in state.imt.multiproof([pos])]}
