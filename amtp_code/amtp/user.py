"""Data User side: build the trapdoor (Phase 4, Step 1), verify the answer
(Phase 5, Steps 1-3) and decrypt only after acceptance (Phase 5, Step 4)."""
import json
import os
import time

from .core import boolean
from .core.crypto import aes_gcm_decrypt, hmac_tag, unpack_ct, unwrap, InvalidTag
from .dht import ciphertext_id
from .core.hashing import H, enc_bq, lp, u64
from .index import domain_root, gamma, imt_leaf, rho
from .core.merkle import merkle_root, multiverify
from .owner import keyword_key
from .server import query_digest

# The seven terms of Accept_Q, in the order Phase 5 evaluates them.
CHECKS = [
    ("ctx", "Query context", "Same domain, epoch, Boolean expression and nonce as the query I sent"),
    ("anchor", "Anchored snapshot", "H(i ‖ e ‖ R^part ‖ R^idx) equals the Domain Root read from the blockchain"),
    ("idx", "Index evidence", "One entry per keyword; every 'absent' claim has a valid non-membership proof"),
    ("papc", "Complete posting lists (PAPC)", "Rebuilt ρ̂ from the returned lists and found it in the index tree"),
    ("part", "Partition authentication", "Every listed location is inside its partition, and every partition is inside the domain"),
    ("comp", "Exact Boolean result", "My own Eval(B_Q) gives exactly the returned files: none missing, none extra"),
    ("ct", "Ciphertext integrity", "Every returned file hashes to its cid"),
]


def _ctx_bytes(field, value) -> bytes:
    """Binary encoding of one query-context field, for the b_ctx comparison."""
    if field == "B_Q":
        return enc_bq(boolean.from_json(value))
    if field == "epoch":
        return u64(value)
    if field == "nonce":
        return bytes.fromhex(value)
    if not isinstance(value, str):
        raise ValueError("domain must be a string")
    return lp(value)


def _ct_bytes(r) -> bytes:
    """The raw CT_d bytes of one R_ct entry (hex on the JSON wire)."""
    try:
        return bytes.fromhex(r["ct"])
    except (TypeError, ValueError):
        raise Reject("ct", f"file {str(r.get('cid'))[:8]} is not a well-formed ciphertext") from None


class Reject(Exception):
    def __init__(self, check, detail):
        super().__init__(detail)
        self.check, self.detail = check, detail


class DataUser:
    def __init__(self, uid, name, role, attrs, attr_keys, domain_keys):
        self.uid, self.name, self.role = uid, name, role
        self.attrs = sorted(attrs)
        self.attr_keys = attr_keys        # from the DA (CP-ABE stand-in)
        self.domain_keys = domain_keys    # domain -> DomainKeys (K_s, K_a)

    # ---------- Phase 4, Step 1 ----------
    def make_query(self, domain, text, anchor):
        if domain not in self.domain_keys:
            raise PermissionError(f"{self.name} has no query key for domain {domain}")
        keys = self.domain_keys[domain]
        words_ast = boolean.parse(text)
        word_of = {}

        def protect(word):
            h = keyword_key(keys.k_s, word).hex()
            word_of[h] = word
            return h

        b_q = boolean.canonical(boolean.map_leaves(words_ast, protect))
        b_q = json.loads(json.dumps(b_q))                 # same form the server sees
        epoch, r_d = anchor.latest(domain)                # independently read (R_D, e*)
        t, nonce = int(time.time()), os.urandom(16).hex()
        tau = hmac_tag(keys.k_a, query_digest(domain, b_q, epoch, t, nonce)).hex()
        t_q = {"domain": domain, "B_Q": b_q, "epoch": epoch, "t": t, "nonce": nonce, "tau": tau}
        ctx = {"domain": domain, "B_Q": b_q, "epoch": epoch, "nonce": nonce,
               "R_D": r_d.hex(), "word_of": word_of, "text": boolean.to_text(words_ast)}
        return t_q, ctx

    # ---------- Phase 5, Steps 1-3 ----------
    def verify(self, ctx, resp):
        start = time.perf_counter()
        results, m_hat, failed = {}, None, None
        phase, t = {}, time.perf_counter()

        def lap(name):
            nonlocal t
            now = time.perf_counter()
            phase[name] = (now - t) * 1e3
            t = now
        try:
            m_h = self._check_ctx_anchor_idx(ctx, resp, results)
            lap("idx")                                        # b_ctx, b_anchor, b_idx
            descs = self._check_papc(resp, m_h, results)
            lap("papc")
            self._check_partitions(resp, m_h, descs, results)
            lap("part")
            m_hat = self._check_result(ctx, resp, m_h, results)
            lap("comp")
            self._check_ciphertexts(ctx, resp, results)
            lap("ct")
        except Reject as r:
            results[r.check] = (False, r.detail)
            failed = r.check
        except (KeyError, ValueError, TypeError, IndexError, OverflowError, AttributeError) as err:
            # Malformed response: reject at the first check not yet passed
            failed = next(k for k, *_ in CHECKS if k not in results)
            results[failed] = (False, f"malformed evidence ({type(err).__name__})")
        checklist = []
        for key, label, meaning in CHECKS:
            ok, detail = results.get(key, (None, "not checked: an earlier check already failed"))
            checklist.append({"key": key, "label": label, "meaning": meaning,
                              "ok": ok, "detail": detail})
        return {"accepted": failed is None, "failed": failed, "checks": checklist,
                "M_hat": sorted(m_hat) if m_hat is not None else None,
                "verify_ms": round((time.perf_counter() - start) * 1000, 2), "phase_ms": phase}

    def _check_ctx_anchor_idx(self, ctx, resp, results):
        # b_ctx
        for field in ("domain", "epoch", "B_Q", "nonce"):
            if _ctx_bytes(field, resp[field]) != _ctx_bytes(field, ctx[field]):
                raise Reject("ctx", f"{field} differs from my query "
                                    f"(got {str(resp[field])[:24]}, expected {str(ctx[field])[:24]})")
        results["ctx"] = (True, f"domain {ctx['domain']}, epoch {ctx['epoch']}, nonce matches")

        # b_anchor
        computed = domain_root(resp["domain"], resp["epoch"],
                               bytes.fromhex(resp["R_part"]), bytes.fromhex(resp["R_idx"]))
        if computed.hex() != ctx["R_D"]:
            raise Reject("anchor", f"rebuilt root {computed.hex()[:12]}… ≠ anchored "
                                   f"{ctx['R_D'][:12]}… (old or forged snapshot)")
        results["anchor"] = (True, f"matches R_D = {ctx['R_D'][:12]}… on the anchor")

        # b_idx
        r_idx = bytes.fromhex(resp["R_idx"])
        wanted = boolean.leaves(boolean.from_json(ctx["B_Q"]))
        ev = resp["proof"]["evidence"]
        if sorted(e["h"] for e in ev) != sorted(wanted):
            raise Reject("idx", "evidence is missing or duplicated for some keyword")
        m_h, absent = {}, 0
        for e in ev:
            h = e["h"]
            if e["status"] not in ("present", "absent"):
                raise Reject("idx", f"unknown evidence status {str(e['status'])[:16]!r}: "
                                    "every keyword must be proven present or absent")
            if e["status"] == "absent":
                lo = e["lo"]
                lo_h, lo_next = bytes.fromhex(lo["h"]), bytes.fromhex(lo["next"])
                if not (lo_h < bytes.fromhex(h) < lo_next):
                    raise Reject("idx", "absent-proof predecessor does not bracket the keyword "
                                        "(h_lo < h < next(h_lo) fails): the keyword is indexed")
                leaves = {lo["pos"]: imt_leaf(lo_h, bytes.fromhex(lo["rho"]), lo_next)}
                if not multiverify(r_idx, e["n"], leaves, [bytes.fromhex(x) for x in e["proof"]]):
                    raise Reject("idx", "non-membership proof does not match R^idx")
                m_h[h] = set()
                absent += 1
            else:
                m_h[h] = self._parse_postings(e)
        results["idx"] = (True, f"{len(ev) - absent} keyword(s) present, "
                                f"{absent} proven absent")
        return m_h

    @staticmethod
    def _parse_postings(e):
        comps, pids, seen = e["L"], [], set()
        out = set()
        for pid, comp in comps:
            if not comp:
                raise Reject("idx", "empty posting component")
            if [s for _, s in comp] != sorted(s for _, s in comp):
                raise Reject("idx", "posting list is not in canonical order")
            for cid, slot in comp:
                if cid in seen:
                    raise Reject("idx", "same file listed twice for one keyword")
                seen.add(cid)
                out.add((cid, pid, slot))
            pids.append(pid)
        if pids != sorted(set(pids)):
            raise Reject("idx", "partition list is not canonical")
        return out

    def _check_papc(self, resp, m_h, results):
        descs = {d["pid"]: d for d in resp["proof"]["partitions"]}
        if len(descs) != len(resp["proof"]["partitions"]):
            raise Reject("papc", "a partition descriptor appears twice")
        r_idx = bytes.fromhex(resp["R_idx"])
        n_ok = 0
        for e in resp["proof"]["evidence"]:
            if e["status"] == "absent":          # already proven by the non-membership check
                continue
            gammas = []
            for pid, comp in e["L"]:
                if pid not in descs:
                    raise Reject("papc", f"no version supplied for partition {pid}")
                gammas.append(gamma(pid, descs[pid]["v"], comp))
            hb = bytes.fromhex(e["h"])
            leaf = imt_leaf(hb, rho(hb, len(e["L"]), merkle_root(gammas)), bytes.fromhex(e["next"]))
            if not multiverify(r_idx, e["n"], {e["pos"]: leaf},
                               [bytes.fromhex(x) for x in e["proof"]]):
                raise Reject("papc", "rebuilt ρ̂ is not in the index tree: "
                                     "a posting list was changed or shortened")
            n_ok += 1
        results["papc"] = (True, f"rebuilt and matched {n_ok} posting commitment(s)")
        return descs

    def _check_partitions(self, resp, m_h, descs, results):
        m_cov = set().union(*m_h.values()) if m_h else set()
        s_cov = {pid for _, pid, _ in m_cov}
        if set(descs) != s_cov:
            raise Reject("part", "partition descriptors do not match the covered partitions")
        where = {}
        for cid, pid, slot in m_cov:
            if where.setdefault(cid, (pid, slot)) != (pid, slot):
                raise Reject("part", f"file {cid[:8]} claimed at two different locations")
        # group the covered locations by partition once (O(|m_cov|)), instead of scanning
        # all of m_cov for every partition (O(|S_cov| x |m_cov|))
        by_pid = {}
        for cid, pid, slot in m_cov:
            by_pid.setdefault(pid, []).append((cid, slot))
        dom_leaves, positions = {}, set()
        for pid, d in descs.items():
            v_map = {}
            for cid, slot in by_pid.get(pid, ()):
                if v_map.setdefault(slot, cid) != cid:
                    raise Reject("part", "two files claim the same slot")
            if not multiverify(bytes.fromhex(d["R_P"]), d["n_slots"],
                               {s: bytes.fromhex(c) for s, c in v_map.items()},
                               [bytes.fromhex(x) for x in d["proof"]]):
                raise Reject("part", f"slot proof fails inside partition {pid}")
            if d["pos"] in positions:
                raise Reject("part", "two partitions claim one position")
            positions.add(d["pos"])
            dom_leaves[d["pos"]] = H(pid, d["v"], bytes.fromhex(d["R_P"]))
        if dom_leaves:
            dp = resp["proof"]["domain"]
            if not multiverify(bytes.fromhex(resp["R_part"]), dp["n"], dom_leaves,
                               [bytes.fromhex(x) for x in dp["proof"]]):
                raise Reject("part", "partition root A = H(PID ‖ v ‖ R_P) is not in the "
                                     "domain's partition tree (forged partition)")
        results["part"] = (True, f"{len(m_cov)} location(s) in {len(descs)} partition(s), "
                                 f"one shared domain multiproof")

    def _check_result(self, ctx, resp, m_h, results):
        m_hat = boolean.evaluate(boolean.from_json(ctx["B_Q"]), m_h)
        proj = [(r["cid"], r["pid"], r["loc"]) for r in resp["R_ct"]]
        if len(set(proj)) != len(proj):
            raise Reject("comp", "a file is returned twice")
        missing, extra = m_hat - set(proj), set(proj) - m_hat
        if missing or extra:
            parts = []
            if missing:
                parts.append(f"{len(missing)} matching file(s) missing")
            if extra:
                parts.append(f"{len(extra)} file(s) that do not match")
            raise Reject("comp", ", ".join(parts))
        results["comp"] = (True, f"{len(m_hat)} file(s), exactly as Eval(B_Q) predicts")
        return m_hat

    def _check_ciphertexts(self, ctx, resp, results):
        for r in resp["R_ct"]:
            ct = _ct_bytes(r)
            if ciphertext_id(ct).hex() != r["cid"]:
                raise Reject("ct", f"file {r['cid'][:8]} was modified: H(CT) ≠ cid")
            try:
                aad = unpack_ct(ct)["aad"]
            except ValueError:
                raise Reject("ct", f"file {r['cid'][:8]} is not a well-formed ciphertext") from None
            if aad.get("domain") != ctx["domain"]:
                raise Reject("ct", "file belongs to another domain")
        results["ct"] = (True, f"all {len(resp['R_ct'])} hash(es) match")

    # ---------- Phase 5, Step 4 ----------
    def decrypt(self, resp):
        out = []
        for r in resp["R_ct"]:
            ct = unpack_ct(_ct_bytes(r))          # already checked by b_ct before decryption
            item = {"cid": r["cid"], "pid": r["pid"], "loc": r["loc"],
                    "policy": ct["aad"]["policy"], "doc": ct["aad"]["doc"]}
            k_d = unwrap(ct["CK"], self.attr_keys)
            if k_d is None:
                item["status"] = "locked"
            else:
                try:
                    doc = json.loads(aes_gcm_decrypt(k_d, ct["E"], ct["aad_b"]))
                    item.update(status="open", title=doc["title"], body=doc["body"])
                except InvalidTag:
                    item["status"] = "decrypt_error"
            out.append(item)
        return out
