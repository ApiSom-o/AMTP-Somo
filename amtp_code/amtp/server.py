"""Cloud Server: Phase 2 update preparation and Phase 4 search for an HONEST server.

There is no attack code here. The demo and the tests load the adversary plug-in
(amtp/adversary.py), which wraps this server; the benchmarks never do.
"""
import time

from .core import boolean
from .core.crypto import hmac_ok, sig_ok
from .dht import DHT, StorageError
from .engine import Engine
from .update import delta, enc_aff, request_digest
from .core.hashing import H, TAG_QUERY, enc_bq
from .index import SENTINEL_LO

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
        self.engines = {}         # domain -> Engine (the CS's working index)
        self.owner_keys = {}      # domain -> public keys allowed to sign U_op
        self.docs = {}            # domain -> Doc_i (id -> cid), finalized
        self.request_nonces = set()
        self._pending = {}        # domain -> candidate awaiting validation and anchoring

    # ----- Phase 2: update protocol (CS side) -----
    def create_domain(self, domain, policy, owner_keys, ops_per_epoch=1):
        """Set up the domain's index; returns the genesis PIDs (public setup data for R^(0))."""
        eng = Engine(domain, policy, ops_per_epoch)
        self.engines[domain] = eng
        self.owner_keys[domain] = list(owner_keys)
        self.docs[domain] = {}
        self.store_state(eng.snapshot())
        return sorted(eng.parts)

    def prepare_update(self, domain, requests) -> dict:
        """Admit up to b signed requests, apply them, adapt and repair, and return the candidate
        transition: roots, placements, Aff_i, Δ_i and the evidence π^upd for the validating owner."""
        eng = self.engines[domain]
        if domain in self._pending:
            raise ValueError("a candidate for this domain is still awaiting validation")
        if not requests or len(requests) > eng.ops_per_epoch:
            raise ValueError(f"an epoch takes 1..{eng.ops_per_epoch} requests")
        r_old, r_part_old, r_idx_old = eng.R_D, eng.part_tree.root, eng.imt.root
        docs, seen, placements, deletes = dict(self.docs[domain]), set(), [], []
        for req in requests:
            u, sig = req["U"], req["sig"]
            if not any(sig_ok(k, request_digest(u), sig) for k in self.owner_keys[domain]):
                raise ValueError("σ_op invalid")
            if u["domain"] != domain or u["epoch"] != eng.epoch:
                raise ValueError("request is not for the current finalized epoch")
            if u["nonce"] in self.request_nonces or u["nonce"] in seen:
                raise ValueError("request nonce already used")
            seen.add(u["nonce"])
            if u["op"] == "insert":
                cid = H(u["ct"])
                if docs.get(u["id"]) is not None or cid in eng.loc:
                    raise ValueError("identifier or ciphertext already live")
                self.dht.put(cid, u["ct"])
                placements.append(list(eng.insert(cid, {H(c) for c in u["C"]}, u["bucket"])))
                docs[u["id"]] = cid
            else:
                cid = u["cid"]
                if docs.get(u["id"]) != cid:
                    raise ValueError("delete of a document that is not live")
                eng.delete(cid)
                placements.append(None)
                deletes.append(cid)
                docs[u["id"]] = None
        st = eng.commit(evidence=True)
        pi = dict(st["pi"], R_part_old=r_part_old, R_idx_old=r_idx_old)
        d = delta(domain, eng.epoch, requests, enc_aff(st["aff"]), r_old, eng.R_D)
        proposal = {"domain": domain, "epoch_old": eng.epoch - 1, "epoch_new": eng.epoch,
                    "R_old": r_old, "R_new": eng.R_D, "placements": placements,
                    "aff": st["aff"], "delta": d, "pi": pi, "stats": {k: v for k, v in st.items()
                                                                       if k not in ("aff", "pi")}}
        self._pending[domain] = (docs, deletes, seen)
        return proposal

    def finalize_update(self, domain, snapshot=True):
        """After the Root Anchor accepted the transition: expose the successor snapshot and drop
        the ciphertexts of deleted documents (only now, as Phase 2 requires). snapshot=False skips
        building the query snapshot (update-only benchmarks)."""
        docs, deletes, seen = self._pending.pop(domain)
        self.docs[domain] = {i: c for i, c in docs.items() if c is not None}
        self.request_nonces |= seen
        for cid in deletes:
            self.dht.delete(cid)
        if not snapshot:
            return None
        eng = self.engines[domain]
        state = eng.snapshot()
        if state.R_D != eng.R_D:
            raise RuntimeError("incremental R_D differs from the full rebuild")
        self.store_state(state)
        return state

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
    def search(self, t_q: dict, respond=None) -> dict:
        """Admit the query, pin the current finalized snapshot and answer it. `respond(state, B_Q, η)`
        replaces the honest builder; only the adversary plug-in passes one."""
        start = time.perf_counter()
        reason = self._admit(t_q)
        if reason:
            return {"status": "rejected", "reason": reason}
        b_q = boolean.from_json(t_q["B_Q"])
        state = self.current(t_q["domain"])
        try:
            if respond is None:
                response = build_response(state, b_q, t_q["nonce"], self.dht)
            else:
                response = respond(state, b_q, t_q["nonce"])
        except StorageError as err:
            return {"status": "storage_error", "reason": str(err), "cs_ms": _ms(start)}
        for desc in response["proof"]["partitions"]:
            desc.pop("_positions", None)          # internal helper, not sent
        return {"status": "ok", "response": response, "cs_ms": _ms(start)}

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


def build_response(state, b_q, nonce, dht, timing=None):
    """R_Q = <i, e*, B_Q, η, R^part, R^idx, R^ct_Q, Π_Q> with ASPA multiproofs.
    `timing` (a dict, benchmarks only) receives the time of each server phase in ms:
    lookup (Search Tree + IMT evidence), eval (Boolean evaluation), proof (ASPA), fetch (DHT)."""
    t0 = time.perf_counter()
    evidence, leaf_sets = [], {}
    for h in sorted(boolean.leaves(b_q)):
        hb = bytes.fromhex(h)
        posting = lookup(state, hb)
        if posting is not None:
            comps = _components(state, hb, posting)
            pos = state.imt_pos[hb]
            evidence.append({"h": h, "status": "present", "L": comps, "pos": pos,
                             "next": state.imt_next[hb].hex(), "n": state.imt_n,
                             "proof": [x.hex() for x in state.imt.multiproof([pos])]})
            leaf_sets[h] = {(cid, pid, slot) for pid, comp in comps for cid, slot in comp}
        else:
            evidence.append(_absent_evidence(state, hb))
            leaf_sets[h] = set()

    t1 = time.perf_counter()
    m_q = boolean.evaluate(b_q, leaf_sets)
    t2 = time.perf_counter()
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

    t3 = time.perf_counter()
    r_ct = []
    for cid, pid, slot in sorted(m_q, key=lambda x: (x[1], x[2])):
        ct = dht.get(bytes.fromhex(cid))     # raw CT bytes; may raise StorageError
        r_ct.append({"cid": cid, "pid": pid, "loc": slot, "ct": ct.hex()})   # hex on the JSON wire
    if timing is not None:
        t4 = time.perf_counter()
        timing.update(lookup=(t1 - t0) * 1e3, eval=(t2 - t1) * 1e3, proof=(t3 - t2) * 1e3,
                      fetch=(t4 - t3) * 1e3)

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


def _absent_evidence(state, hb: bytes):
    """Non-membership: the predecessor leaf h_lo with h_lo < h < next(h_lo). (If the key IS
    indexed, the honest predecessor has next(h_lo) = h and the user's bracket check fails.)"""
    lo = state.postings.predecessor(hb) or SENTINEL_LO     # B+ tree: largest indexed key below h
    pos = state.imt_pos[lo]
    leaf = {"pos": pos, "h": lo.hex(), "rho": state.imt_rho[lo].hex(),
            "next": state.imt_next[lo].hex()}
    return {"h": hb.hex(), "status": "absent", "lo": leaf, "n": state.imt_n,
            "proof": [x.hex() for x in state.imt.multiproof([pos])]}
