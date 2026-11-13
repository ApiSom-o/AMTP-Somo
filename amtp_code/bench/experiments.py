"""AMTP on the shared dataset-v3, in the same format as the baselines (Section V, Exp. 1, 2, 3, 5).

    python -m bench.experiments exp1                 # replay baselines/results/exp1_queries.json (N = 10k..200k)
    python -m bench.experiments exp2-layouts         # write the shared baselines/results/exp2_layouts.json (N = 200k)
    python -m bench.experiments exp2                 # selective proof vs r_Q, every layout of that file
    python -m bench.experiments exp3                 # insert / delete batches of 1, 10, 100, 1000
    python -m bench.experiments exp5                 # 1..32 domains, replays baselines/results/exp5_workload.json
    python -m bench.experiments theta --n 200000     # θ_max sweep (θ_min = θ_max/4): query vs update cost
  dataset-v4 suites (advisor's plan; workload files in datasets/arxiv/data_v4/, the same for every scheme):
    python -m bench.experiments search1              # Search 1.1/1.2: single-domain AND queries, files/domain 10k..125k
    python -m bench.experiments verify1              # Verify 1.1: real keywords with ~10..10,000 results, one domain
    python -m bench.experiments tamper               # Verify 1.2: server modifies / hides t of ~2,000 results
    python -m bench.experiments xsearch              # Search 2.1: Boolean AND/OR queries over the 4 domains
    python -m bench.experiments xverify              # Verify 2.1: multi-domain keywords with ~10..10,000 results
    python -m bench.experiments xdomains             # Search/Verify 2.2: the same files as D = 1..32 domains
    (Exp. 4, adaptive vs Static-MT / Global-MT: python -m bench.ablation --source arxiv)

Everything runs the real AMTP code: Engine (Phases 2-3, incremental), RootAnchor with an
owner-signed transition, CloudServer admission + build_response (Phase 4, ASPA) and
DataUser.verify (Phase 5, all seven checks). Documents are the baselines' documents:
amtp_dataset.sample(N), W(d) from documents.csv, real file text encrypted with AES-GCM,
keyword keys h_w = H(AES-SIV_{K_s}(w)). Every measured query must be accepted and must
return exactly the plaintext ground truth, otherwise the run stops.

Results go to baselines/results/amtp/amtp_<suite>.csv with the baselines' columns
(<metric>_ms, _ms_median, _ms_std over --reps runs after --warmup runs), so
baselines/plot_results.py can draw AMTP next to Chen, Du and SE-COLLAB.

Choices (state them in the paper):
  * Exp. 1 / 2 / 3 put all N documents in ONE domain, i.e. the same collection every
    baseline searches; multi-domain behaviour is Exp. 5 and xdomain.
  * Every domain has its own keys (K_s, K_a), so the same word has a different h_w per domain.
    Cross-domain search follows the paper: one domain-bound query per domain, each verified
    against its own Domain Root (no shared index, no cross-domain snapshot).
  * Placement: a file goes to the least occupied partition serving its bucket
    (bucket = arXiv primary category folded into --buckets groups), as in bench.ablation.
  * Exp. 3 freezes the partitions (StaticPolicy): the paper excludes split/merge from Exp. 3.
  * end_to_end = query_gen + server_total + verify_total; decrypting the returned files
    (CP-ABE stand-in + AES-GCM) is reported separately as du_decrypt.
  * The Data Owner's independent transition validation (Phase 2, Step 5) is not implemented
    in Engine and is not part of update_ms.
"""
import argparse
import csv
import gc
import json
import os
import re
import statistics as st
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amtp.core import boolean                                    # noqa: E402
from amtp.anchor import RootAnchor, transition_message           # noqa: E402
from amtp.core.crypto import AttributeAuthority, Signer, make_ct          # noqa: E402
from amtp.dht import ciphertext_id                               # noqa: E402
from amtp.engine import Engine                                   # noqa: E402
from amtp.core.hashing import HashCounter, enc                   # noqa: E402
from amtp.owner import DomainKeys, keyword_key                   # noqa: E402
from amtp.adversary import flip_one_byte                         # noqa: E402
from amtp.server import CloudServer, build_response              # noqa: E402
from amtp.user import DataUser, Reject                           # noqa: E402
from amtp.variants import AdaptivePolicy, StaticPolicy           # noqa: E402
from bench.workload import REPO_ROOT, _primary_categories, arxiv_loader   # noqa: E402

RESULTS = os.path.join(REPO_ROOT, "baselines", "results")
DEFAULT_QUERIES = os.path.join(RESULTS, "exp1_queries.json")
OUT = os.path.join(RESULTS, "amtp")
POLICY = "auditor"


# ---------------------------------------------------------------- documents
class Corpus:
    """Encrypts each dataset document once (Phase 1) and caches the result,
    so every N reuses the same ciphertexts and keyword keys."""

    def __init__(self, a):
        self.D = arxiv_loader()
        self.data = a.data
        self.keys = {}                                  # domain -> DomainKeys (K_s, K_a), one pair per domain
        self.authority = AttributeAuthority()
        cat = _primary_categories(self.D.load(a.data)["dir"])
        groups = sorted(set(cat.values()) | set(self.D.DOMAINS))
        self.bucket_of = {g: i % a.buckets for i, g in enumerate(groups)}
        self.cat = cat
        self._h, self._docs = {}, {}

    def keys_for(self, domain):
        if domain not in self.keys:
            self.keys[domain] = DomainKeys()
        return self.keys[domain]

    def h(self, word, domain):
        """h_w under the domain's own K_s (the same word has a different key in every domain)"""
        if (domain, word) not in self._h:
            self._h[(domain, word)] = keyword_key(self.keys_for(domain).k_s, word)
        return self._h[(domain, word)]

    def encrypt(self, doc, domain):
        """Phase 1 for one document: (cid, CT, keyword keys, bucket)."""
        key = (doc.doc_id, domain)
        if key not in self._docs:
            k_d = os.urandom(32)
            aad = {"domain": domain, "doc": doc.doc_id, "policy": POLICY}
            body = enc({"title": doc.doc_id,
                        "body": self.D.read_bytes(doc, self.data).decode("utf-8", "replace")})
            ct = make_ct(k_d, body, self.authority.wrap(k_d, POLICY), aad)    # raw CT bytes
            bucket = self.bucket_of[self.cat.get(doc.doc_id, doc.domain)]
            self._docs[key] = (ciphertext_id(ct), ct, frozenset(self.h(w, domain) for w in doc.keywords), bucket)
        return self._docs[key]

    def encrypt_version(self, doc, domain, suffix):
        """Another valid ciphertext of the same document with `suffix` appended (an older version of the file)."""
        k_d = os.urandom(32)
        aad = {"domain": domain, "doc": doc.doc_id, "policy": POLICY}
        body = enc({"title": doc.doc_id,
                    "body": (self.D.read_bytes(doc, self.data) + suffix).decode("utf-8", "replace")})
        return make_ct(k_d, body, self.authority.wrap(k_d, POLICY), aad)

    def user(self, domains):
        return DataUser("du", "du", "", [POLICY], self.authority.user_keys([POLICY]),
                        {d: self.keys_for(d) for d in domains})


class Domain:
    """One AMTP domain: engine + owner signer, registered on the anchor and the server."""

    def __init__(self, name, corpus, docs, a, anchor, server, policy=None, extra_words=None):
        self.name, self.corpus = name, corpus
        self.signer = Signer()
        server.register_query_key(name, corpus.keys_for(name).k_a)
        self.anchor, self.server = anchor, server
        self.eng = Engine(name, policy or AdaptivePolicy(a.buckets, a.theta_min, a.theta_max))
        anchor.register_domain(name, self.signer.public, self.eng.R_D)      # R^(0)
        self.cids = []
        for i, d in enumerate(docs):
            cid, ct, keys, bucket = corpus.encrypt(d, name)
            if extra_words and i in extra_words:
                keys = keys | {corpus.h(w, name) for w in extra_words[i]}
            server.store_ciphertext(cid, ct)
            self.eng.insert(cid, keys, bucket)
            self.cids.append(cid)
        self.eng.commit()
        self.finalize()

    def finalize(self):
        """Owner signs the transition, the anchor accepts it, the server exposes the snapshot."""
        _, prev = self.anchor.latest(self.name)
        sig = self.signer.sign(transition_message(self.name, self.eng.epoch, self.eng.R_D, prev))
        self.anchor.submit(self.name, self.eng.epoch, self.eng.R_D, sig)

    def publish_snapshot(self):
        state = self.eng.snapshot()
        if state.R_D != self.eng.R_D:
            raise SystemExit("CORRECTNESS GATE FAILED: incremental R_D != full rebuild")
        self.server.store_state(state)
        return state


# ---------------------------------------------------------------- queries
_OPS = re.compile(r"(\(|\)|\bAND\b|\bOR\b)")


def quote_terms(query):
    """Shared queries write multi-word keywords without quotes; AMTP's parser wants them quoted."""
    parts = [p.strip() for p in _OPS.split(query)]
    return " ".join(p if p in ("(", ")", "AND", "OR") else f'"{p}"' for p in parts if p)


def ground_truth(text, inv, cids):
    """Evaluate the query on plaintext keyword sets (positions -> cids)."""
    ast = boolean.parse(text)
    sets = {w: inv.get(w, set()) for w in boolean.leaves(ast)}
    return {cids[i].hex() for i in boolean.evaluate(ast, sets)}


def load_queries(path, explicit):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        print(f"[queries] replay {os.path.relpath(path)} ({len(rows)} queries)")
        return rows
    if explicit:
        raise SystemExit(f"query file not found: {path}")
    raise SystemExit(f"{path} not found: run a baseline's exp1 first (it writes the shared queries)")


def run_query(dom, state, user, text):
    """One full query: trapdoor -> admission + ASPA response -> 7 checks -> decrypt."""
    t0 = time.perf_counter()
    t_q, ctx = user.make_query(dom.name, text, dom.anchor)
    t1 = time.perf_counter()
    h0 = HashCounter.calls
    reason = dom.server._admit(t_q)                     # same admission as CloudServer.search
    if reason:
        raise SystemExit(f"query rejected at admission: {reason}")
    resp = build_response(state, boolean.from_json(t_q["B_Q"]), t_q["nonce"], dom.server.dht)
    for desc in resp["proof"]["partitions"]:
        desc.pop("_positions", None)
    t2 = time.perf_counter()
    h1 = HashCounter.calls
    wire = json.dumps(resp)                             # what travels to the user (not timed)
    resp = json.loads(wire)
    t3 = time.perf_counter()
    rep = user.verify(ctx, resp)
    t4 = time.perf_counter()
    h2 = HashCounter.calls
    if not rep["accepted"]:
        raise SystemExit(f"CORRECTNESS GATE FAILED: honest query rejected at {rep['failed']}")
    t5 = time.perf_counter()
    opened = user.decrypt(resp)
    t6 = time.perf_counter()
    if any(o["status"] != "open" for o in opened):
        raise SystemExit("CORRECTNESS GATE FAILED: an authorised user could not decrypt a result")
    times = {"query_gen": (t1 - t0) * 1e3, "server_total": (t2 - t1) * 1e3,
             "verify_total": (t4 - t3) * 1e3, "du_decrypt": (t6 - t5) * 1e3,
             "end_to_end": (t1 - t0 + t2 - t1 + t4 - t3) * 1e3}
    ev = resp["proof"]["evidence"]
    info = {"rQ": len(resp["R_ct"]),
            "pQ": sum(len(c) for e in ev if e["status"] == "present" for _, c in e["L"]),
            "sQ": len(resp["proof"]["partitions"]),
            "keys_absent": sum(e["status"] == "absent" for e in ev),
            "proof_bytes": len(json.dumps(resp["proof"])), "token_bytes": len(json.dumps(t_q)),
            "response_bytes": len(wire), "hash_server": h1 - h0, "hash_verify": h2 - h1,
            "ids": {r["cid"] for r in resp["R_ct"]}}
    return times, info


def measure_fn(fn, a):
    """--warmup unrecorded runs of fn(), then --reps recorded ones with the GC off.
    fn() returns (times, info); returns (summary of times, last info, every recorded info)."""
    for _ in range(a.warmup):
        fn()
    samples, infos = [], []
    gc.disable()
    try:
        for _ in range(max(1, a.reps)):
            m, info = fn()
            samples.append(m)
            infos.append(info)
    finally:
        gc.enable()
    return summarize(samples), infos[-1], infos


def measure(dom, state, user, text, a):
    res, info, _ = measure_fn(lambda: run_query(dom, state, user, text), a)
    return res, info


_SUM = ("rQ", "pQ", "sQ", "keys_absent", "proof_bytes", "token_bytes", "response_bytes", "hash_server", "hash_verify")


def run_xquery(doms, states, user, text):
    """Cross-domain search as the paper defines it (System model, last paragraph): the user sends one
    domain-bound query per domain and verifies each response against that domain's own anchored root.
    Times and sizes are summed over the domains (sequential, one user); ids = union of the results,
    rQ_per_domain = result count of every domain in order."""
    times, info = {}, {k: 0 for k in _SUM}
    ids, per = set(), []
    for dom, state in zip(doms, states):
        t, i = run_query(dom, state, user, text)
        for k, v in t.items():
            times[k] = times.get(k, 0.0) + v
        for k in _SUM:
            info[k] += i[k]
        ids |= i["ids"]
        per.append(i["rQ"])
    info["ids"], info["rQ_per_domain"] = ids, per
    return times, info


def tamper_response(resp, kind, targets, extra=None):
    """The server's cheat on t files, the same changes as the CloudServer modes (amtp/server.py), with the honest proof:
      modify      flip one byte of the raw CT bytes of the returned files in `targets` (tamper_ct)
      hide        leave the files in `targets` out of R_ct (drop_result)
      inject      add the R_ct entries in `extra` (files that do not match the query; extra_result)
      old_version replace the ciphertext of the files in `targets` by extra[cid], an older version of the file"""
    if kind == "modify":
        for r in resp["R_ct"]:
            if r["cid"] in targets:
                r["ct"] = flip_one_byte(r["ct"])
    elif kind == "hide":
        resp["R_ct"] = [r for r in resp["R_ct"] if r["cid"] not in targets]
    elif kind == "inject":
        resp["R_ct"] = resp["R_ct"] + list(extra)
    elif kind == "old_version":
        for r in resp["R_ct"]:
            if r["cid"] in targets:
                r["ct"] = extra[r["cid"]].hex()
    else:
        raise ValueError(kind)


def full_check(user, ctx, resp):
    """Full check: verify the proof, then check EVERY returned file instead of stopping at the first fault, and
    count the files the user can name as wrong: modified (H(CT) != cid), not matching the query, or missing.
    Returns -1 if the proof itself is invalid (then no file can be named)."""
    try:
        m_h = user._check_ctx_anchor_idx(ctx, resp, {})
        descs = user._check_papc(resp, m_h, {})
        user._check_partitions(resp, m_h, descs, {})
    except Reject:
        return -1
    m_hat = boolean.evaluate(boolean.from_json(ctx["B_Q"]), m_h)
    proj = {(r["cid"], r["pid"], r["loc"]) for r in resp["R_ct"]}
    modified = sum(ciphertext_id(bytes.fromhex(r["ct"])).hex() != r["cid"] for r in resp["R_ct"])
    return len(m_hat - proj) + len(proj - m_hat) + modified


def run_tampered(dom, state, user, text, kind, targets, extra=None):
    """One query whose response the server tampered with. Times the user's normal verification (early abort:
    stops at the first failed check) and the full check (every file, names the wrong ones).
    Returns detected = rejected, the first Phase 5 check that failed and the number of files named."""
    t_q, ctx = user.make_query(dom.name, text, dom.anchor)
    if dom.server._admit(t_q):
        raise SystemExit("query rejected at admission")
    resp = build_response(state, boolean.from_json(t_q["B_Q"]), t_q["nonce"], dom.server.dht)
    for desc in resp["proof"]["partitions"]:
        desc.pop("_positions", None)
    if targets or extra:
        tamper_response(resp, kind, targets, extra)
    resp = json.loads(json.dumps(resp))
    t0 = time.perf_counter()
    rep = user.verify(ctx, resp)
    t1 = time.perf_counter()
    localized = full_check(user, ctx, resp)
    t2 = time.perf_counter()
    return ({"verify_total": (t1 - t0) * 1e3, "full_check": (t2 - t1) * 1e3},
            {"detected": not rep["accepted"], "failed": rep["failed"] or "", "localized": localized})


# ---------------------------------------------------------------- output (same as the baselines)
class Writer:
    """Collects rows, prints them without _std/_median, writes <out>/amtp_<name>.csv on close()."""

    def __init__(self, name, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        self.path = os.path.join(out_dir, f"amtp_{name}.csv")
        self.rows = []

    def add(self, **row):
        self.rows.append(row)
        show = {k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()
                if not k.endswith("_std") and not k.endswith("_median")}
        print("  " + "  ".join(f"{k}={v}" for k, v in show.items()), flush=True)

    def close(self):
        if not self.rows:
            return
        keys = list(dict.fromkeys(k for r in self.rows for k in r))
        with open(self.path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(self.rows)
        print(f"-> {os.path.relpath(self.path)}")
        arxiv_loader().write_manifest(self.path)              # machine / commit / command: <csv>.manifest.json


def summarize(samples, prefix=""):
    """<name>_ms (mean), <name>_ms_median, <name>_ms_std, like every baseline."""
    out = {}
    for k in samples[0]:
        v = [s[k] for s in samples]
        out[f"{prefix}{k}_ms"] = st.mean(v)
        out[f"{prefix}{k}_ms_median"] = st.median(v)
        out[f"{prefix}{k}_ms_std"] = st.pstdev(v)
    return out


def setup(name, corpus, docs, a, policy=None, extra_words=None):
    anchor, server = RootAnchor(), CloudServer()
    t0 = time.perf_counter()
    dom = Domain(name, corpus, docs, a, anchor, server, policy, extra_words)
    state = dom.publish_snapshot()
    lay = dom.eng.layout()
    print(f" N={len(docs)}: setup={time.perf_counter() - t0:.1f}s partitions={lay['partitions']} "
          f"max={lay['max_partition']} keys={lay['keys']}", flush=True)
    return dom, state, lay


# ---------------------------------------------------------------- experiments
def suite_exp1(a):
    """Exp. 1: replay the shared queries for every N; AMTP answers every shape."""
    corpus = Corpus(a)
    rows = load_queries(a.queries or DEFAULT_QUERIES, a.queries)
    sizes = sorted({r["N"] for r in rows})
    print(f"[exp1] Boolean search scalability  sizes={sizes} θ=({a.theta_min},{a.theta_max})")
    w = Writer("exp1_boolean_scalability", a.out)
    for n in sizes:
        src = corpus.D.sample(n, a.domains, a.data)
        dom, state, lay = setup("D", corpus, src, a)
        user = corpus.user(["D"])
        inv = corpus.D.inverted_index(src)
        for q in (r for r in rows if r["N"] == n):
            text = quote_terms(q["query"])
            res, info = measure(dom, state, user, text, a)
            if info.pop("ids") != ground_truth(text, inv, dom.cids):
                raise SystemExit(f"CORRECTNESS GATE FAILED: result != ground truth for {q['query']}")
            w.add(N=n, kQ=q["kQ"], shape=q["shape"], domain=q.get("domain", ""), status="ok",
                  partitions=lay["partitions"], **info, **res)
        del dom, state, src, inv
        gc.collect()
    w.close()


def amtp_partition_order(corpus, src, a):
    """Positions of src grouped by the AMTP partition they land in (placement ignores keywords)."""
    probe, _, _ = setup("D", corpus, src, a)
    by_part = {}
    for i, cid in enumerate(probe.cids):
        pid, slot = probe.eng.loc[cid]
        by_part.setdefault(pid, []).append((slot, i))
    return [[i for _, i in sorted(by_part[p])] for p in sorted(by_part)]


def suite_exp2_layouts(a):
    """Write the shared Exp. 2 file (baselines/results/exp2_layouts.json) that every scheme replays:
    clustered and dispersed in document order (amtp_dataset.exp2_doc_layouts), plus AMTP's worst case
    'partition_spread' = one file per AMTP partition, round robin (needs AMTP's placement, hence here)."""
    corpus = Corpus(a)
    n = a.n
    src = corpus.D.sample(n, a.domains, a.data)
    parts = amtp_partition_order(corpus, src, a)
    layouts = corpus.D.exp2_doc_layouts(n, a.rq)
    spread = {}
    for r in (r for r in a.rq if r <= n):
        chosen, depth = [], 0
        while len(chosen) < r:
            chosen += [p[depth] for p in parts if depth < len(p)][:r - len(chosen)]
            depth += 1
        spread[str(r)] = chosen
    layouts["partition_spread"] = {"prefix": "par", "docs": spread,
                                   "note": f"one file per AMTP partition (θ = {a.theta_max}/{a.theta_min}, "
                                           f"{len(parts)} partitions), round robin"}
    out = {"N": n, "rq": a.rq, "dataset": corpus.D.DATASET_TAG, "domains": a.domains, "layouts": layouts}
    with open(corpus.D.EXP2_FILE, "w", encoding="utf-8") as f:
        f.write("{\n" + ",\n".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}"
                                   for k, v in out.items()) + "\n}\n")
    print(f"-> {os.path.relpath(corpus.D.EXP2_FILE)}  N={n} layouts={list(layouts)}")


def suite_exp2(a):
    """Exp. 2: one marker keyword matching exactly r_Q files, at fixed N, in every layout of the shared
    file baselines/results/exp2_layouts.json (the same files in every scheme)."""
    corpus = Corpus(a)
    lay_file = corpus.D.load_exp2_layouts()
    n = lay_file["N"]
    src = corpus.D.sample(n, lay_file["domains"], a.data)
    print(f"[exp2] selective proof / verification  N={n} layouts={list(lay_file['layouts'])}")
    extra = corpus.D.exp2_markers(lay_file, n)
    dom, state, lay = setup("D", corpus, src, a, extra_words=extra)
    user = corpus.user(["D"])
    w = Writer("exp2_selective_proof", a.out)
    for r in lay_file["rq"]:
        for name, spec in lay_file["layouts"].items():
            res, info = measure(dom, state, user, f"{spec['prefix']}{r}", a)
            info.pop("ids")
            if info["rQ"] != r:
                raise SystemExit(f"expected {r} results, got {info['rQ']}")
            w.add(N=n, rQ=r, layout=name, partitions=lay["partitions"],
                  **{k: info[k] for k in ("sQ", "proof_bytes", "response_bytes", "hash_server", "hash_verify")},
                  **res)
    w.close()


def suite_exp3(a):
    """Exp. 3: insert b fresh documents (insert pool) then delete them again, at fixed N.
    Partitions are frozen (no split/merge). update = engine insert/delete + commit
    (posting + PAPC + IMT repair, R_D) + owner signature + anchor; prepare = Phase 1 encryption."""
    corpus = Corpus(a)
    pool = corpus.D.insert_pool(a.domains, a.data)
    print(f"[exp3] dynamic update  sizes={a.sizes} batches={a.batches}")
    w = Writer("exp3_dynamic_update", a.out)
    for n in a.sizes:
        src = corpus.D.sample(n, a.domains, a.data)
        dom, _, lay = setup("D", corpus, src, a)
        dom.eng.policy = StaticPolicy(a.buckets, a.theta_min, a.theta_max)
        cursor = 0
        for b in a.batches:
            rows = {"insert": [], "delete": []}
            stats = {}
            for rep in range(a.warmup + a.reps):
                batch = [pool[(cursor + i) % len(pool)] for i in range(b)]
                cursor = (cursor + b) % len(pool)
                t0 = time.perf_counter()
                prepared = [corpus.encrypt(d, "D") for d in batch]
                t_prep = (time.perf_counter() - t0) * 1e3
                gc.disable()
                try:
                    t0 = time.perf_counter()
                    for cid, ct, keys, bucket in prepared:
                        dom.server.store_ciphertext(cid, ct)
                        dom.eng.insert(cid, keys, bucket)
                    st_ins = dom.eng.commit()
                    dom.finalize()
                    t_ins = (time.perf_counter() - t0) * 1e3
                    t0 = time.perf_counter()
                    for cid, *_ in prepared:
                        dom.eng.delete(cid)
                    st_del = dom.eng.commit()
                    dom.finalize()
                    t_del = (time.perf_counter() - t0) * 1e3
                finally:
                    gc.enable()
                for d in batch:                                # fresh encryption next time round
                    corpus._docs.pop((d.doc_id, "D"), None)
                if rep < a.warmup:
                    continue
                rows["insert"].append({"update": t_ins, "prepare": t_prep, "commit": st_ins["update_ms"]})
                rows["delete"].append({"update": t_del, "commit": st_del["update_ms"]})
                stats = {"insert": st_ins, "delete": st_del}
            if dom.eng.snapshot().R_D != dom.eng.R_D:
                raise SystemExit("CORRECTNESS GATE FAILED: incremental R_D != full rebuild")
            for op in ("insert", "delete"):
                res = summarize(rows[op])
                mean = res["update_ms"]
                s = stats[op]
                w.add(N=n, batch=b, op=op, partitions=lay["partitions"], **res,
                      per_doc_ms=mean / b, throughput_docs_s=b / (mean / 1e3),
                      hash_calls=s["hash_calls"], keys_refreshed=s["keys_refreshed"],
                      posting_components_refreshed=s["posting_components_refreshed"],
                      partitions_changed=s["partitions_changed"], splits=s["splits"], merges=s["merges"])
        del dom
        gc.collect()
    w.close()


def suite_exp5(a):
    """Exp. 5: D independent domains, replaying the shared baselines/results/exp5_workload.json (the same
    domains, queries and update files as SE-COLLAB). The target domain (groups[0], identical for every D) is
    queried, then updated alone. Measures query cost, the anchor's Global Root update, and checks that every
    other Domain Root is unchanged."""
    corpus = Corpus(a)
    meta, groups, queries, fresh = corpus.D.load_exp5_workload(a.exp5_workload, a.data)
    if len(fresh) < a.warmup + a.reps:
        raise SystemExit("exp5_workload.json has fewer update files than warmup + reps")
    target = groups[0]
    inv = corpus.D.inverted_index(target)
    counts = [d for d in meta["domain_counts"] if d <= len(groups)]
    print(f"[exp5] multi-domain  D={counts} per-domain={meta['per_domain']} queries={len(queries)}")
    w = Writer("exp5_domains", a.out)
    for nd in counts:
        anchor, server = RootAnchor(), CloudServer()
        t0 = time.perf_counter()
        doms = [Domain(f"D{k:02d}", corpus, groups[k], a, anchor, server) for k in range(nd)]
        states = [d.publish_snapshot() for d in doms]
        t_setup = time.perf_counter() - t0
        user = corpus.user([d.name for d in doms])
        print(f" D={nd}: setup={t_setup:.1f}s", flush=True)
        base = dict(scheme="AMTP", deploy_model="domains", domains=nd, N_target=meta["per_domain"],
                    N_total=nd * meta["per_domain"])
        for q in queries:
            text = quote_terms(q["query"])
            res, info = measure(doms[0], states[0], user, text, a)
            if info.pop("ids") != ground_truth(text, inv, doms[0].cids):
                raise SystemExit(f"CORRECTNESS GATE FAILED: result != ground truth for {q['query']}")
            w.add(**base, kQ=q["kQ"], q=q["q"], shape=q["shape"], op="query", status="ok", **info, **res)
        samples = []
        for rep in range(a.warmup + a.reps):                 # update the target domain only
            before = {d.name: anchor.latest(d.name) for d in doms[1:]}
            cid, ct, keys, bucket = corpus.encrypt(fresh[rep], doms[0].name)
            t0 = time.perf_counter()
            server.store_ciphertext(cid, ct)
            doms[0].eng.insert(cid, keys, bucket)
            doms[0].eng.commit()
            t1 = time.perf_counter()
            doms[0].finalize()                               # signature + anchor + Global Root
            t2 = time.perf_counter()
            if any(anchor.latest(d.name) != before[d.name] for d in doms[1:]):
                raise SystemExit("ISOLATION FAILED: updating one domain changed another Domain Root")
            if rep >= a.warmup:
                samples.append({"update": (t2 - t0) * 1e3, "domain_update": (t1 - t0) * 1e3,
                                "anchor_update": (t2 - t1) * 1e3})
        w.add(**base, op="update_one_domain", update_kind="dynamic", status="ok",
              untouched_roots_unchanged=nd - 1, **summarize(samples))
        del doms, states, anchor, server
        gc.collect()
    w.close()


# ---------------------------------------------------------------- dataset-v4 suites (advisor's plan)
def q_text(keywords):
    return " AND ".join(f'"{k}"' for k in keywords)


def suite_search1(a):
    """Search 1.1 / 1.2 (single domain): queries_search_single.jsonl, every domain, every files-per-domain
    size. Each query must return exactly its result_size from the file and the plaintext ground truth."""
    corpus = Corpus(a)
    qs = corpus.D.search_single_queries()
    print(f"[search1] domains={a.s_domains} files/domain={a.fpd} queries={len(qs)}")
    w = Writer("search_single", a.out)
    for dname in a.s_domains:
        for n in a.fpd:
            src = corpus.D.domain_docs(dname, n, a.data)
            dom, state, lay = setup(dname, corpus, src, a)
            user = corpus.user([dname])
            inv = corpus.D.inverted_index(src)
            for q in (q for q in qs if q["domain"] == dname):
                res, info = measure(dom, state, user, q["text"], a)
                ids = info.pop("ids")
                if len(ids) != q["result_size"][str(n)] or ids != ground_truth(q["text"], inv, dom.cids):
                    raise SystemExit(f"CORRECTNESS GATE FAILED: {q['query_id']} at n={n}")
                w.add(scheme="AMTP", domain=dname, N=n, query_id=q["query_id"], kQ=q["kQ"], shape=q["shape"],
                      status="ok", partitions=lay["partitions"], **info, **res)
            del dom, state, src, inv
            gc.collect()
        corpus._docs.clear()                                   # next domain: free its cached ciphertexts
        corpus._h.clear()
    w.close()


def suite_verify1(a):
    """Verification 1.1 (single domain): verify_keywords.csv single_domain rows at --fix files per domain;
    x-axis = target result size (10 / 100 / 1,000 / 10,000), 5 real keywords per target and domain."""
    corpus = Corpus(a)
    rows = corpus.D.verify_keywords("single_domain", a.fix)
    print(f"[verify1] files/domain={a.fix} keywords={len(rows)}")
    w = Writer("verify_single", a.out)
    for dname in a.s_domains:
        src = corpus.D.domain_docs(dname, a.fix, a.data)
        dom, state, lay = setup(dname, corpus, src, a)
        user = corpus.user([dname])
        for r in (r for r in rows if r["domain"] == dname):
            res, info = measure(dom, state, user, q_text([r["keyword"]]), a)
            info.pop("ids")
            if info["rQ"] != r["result_size"]:
                raise SystemExit(f"CORRECTNESS GATE FAILED: {r['keyword']} gave {info['rQ']} not {r['result_size']}")
            w.add(scheme="AMTP", domain=dname, N=a.fix, keyword=r["keyword"], target_results=r["target_results"],
                  rank=r["rank"], status="ok", partitions=lay["partitions"],
                  **{k: info[k] for k in ("rQ", "sQ", "proof_bytes", "response_bytes", "hash_server", "hash_verify")},
                  **res)
        del dom, state, src
        gc.collect()
    w.close()


def suite_tamper(a):
    """Verification 1.2 (single domain): tamper_sets.jsonl. Per domain, the query keyword (~2,000 results) at its
    files_per_domain; the server modifies / hides / replaces by an older version the first t doc_ids of tamper_order,
    or injects the first t files of amtp_dataset.inject_order (files that do not match). Records the detection, the
    first failed check, the early-abort verification time, the full-check time and how many files the user names."""
    corpus = Corpus(a)
    sets = [r for r in corpus.D.tamper_sets() if r["domain"] in a.s_domains]
    print(f"[tamper] {[(r['domain'], r['query_keyword'], r['result_size']) for r in sets]} kinds={a.tamper_kinds}")
    w = Writer("tamper_detection", a.out)
    for ts in sets:
        dname, n = ts["domain"], ts["files_per_domain"]
        src = corpus.D.domain_docs(dname, n, a.data)
        by_id = {d.doc_id: d for d in src}
        dom, state, lay = setup(dname, corpus, src, a)
        user = corpus.user([dname])
        cid_of = {d.doc_id: corpus.encrypt(d, dname)[0].hex() for d in src}
        inj = corpus.D.inject_order(ts, a.data)
        text = q_text([ts["query_keyword"]])
        base = dict(scheme="AMTP", domain=dname, N=n, keyword=ts["query_keyword"], rQ=ts["result_size"],
                    partitions=lay["partitions"])

        def row(kind, t, res, infos):
            w.add(**base, tamper=kind, tampered=t, status="ok", detected_runs=sum(i["detected"] for i in infos),
                  runs=len(infos), failed_check=infos[-1]["failed"], localized=infos[-1]["localized"], **res)

        res, _, infos = measure_fn(lambda: run_tampered(dom, state, user, text, "none", None), a)
        if any(i["detected"] for i in infos):
            raise SystemExit("CORRECTNESS GATE FAILED: honest response rejected")
        row("none", 0, res, infos)
        for kind in a.tamper_kinds:
            for t in ts["tamper_counts"]:
                if kind == "inject":
                    targets, extra = set(), []
                    for i in inj[:t]:
                        cid = bytes.fromhex(cid_of[i])
                        pid, slot = state.loc[cid]
                        extra.append({"cid": cid_of[i], "pid": pid, "loc": slot, "ct": dom.server.dht.get(cid).hex()})
                else:
                    targets = {cid_of[i] for i in ts["tamper_order"][:t]}
                    extra = ({cid_of[i]: corpus.encrypt_version(by_id[i], dname, corpus.D.OLD_VERSION_SUFFIX)
                              for i in ts["tamper_order"][:t]} if kind == "old_version" else None)
                res, _, infos = measure_fn(lambda: run_tampered(dom, state, user, text, kind, targets, extra), a)
                row(kind, t, res, infos)
        del dom, state, src, cid_of, by_id
        gc.collect()
    w.close()


def multi_build(corpus, named_docs, a):
    """One AMTP domain per (name, docs), each with its own keys and Domain Root, on one anchor and server."""
    anchor, server = RootAnchor(), CloudServer()
    t0 = time.perf_counter()
    doms = [Domain(name, corpus, docs, a, anchor, server) for name, docs in named_docs]
    states = [d.publish_snapshot() for d in doms]
    print(f" {len(doms)} domains, {sum(len(d) for _, d in named_docs)} files: setup={time.perf_counter() - t0:.1f}s",
          flush=True)
    return doms, states, corpus.user([d.name for d in doms])


def suite_xsearch(a):
    """Search 2.1 (multi domain): queries_boolean_multi.jsonl (AND / OR / AND_of_OR / OR_of_AND, kQ 2..16) over
    the four domains, --fix files each. One query per domain, each verified on its own root (the paper's
    model); every domain's count must equal result_size_per_domain."""
    corpus = Corpus(a)
    qs = corpus.D.boolean_multi_queries()
    names = list(corpus.D.DOMAINS)
    print(f"[xsearch] domains={names} files/domain={a.fix} queries={len(qs)}")
    doms, states, user = multi_build(corpus, [(d, corpus.D.domain_docs(d, a.fix, a.data)) for d in names], a)
    w = Writer("search_multi", a.out)
    for q in qs:
        res, info, _ = measure_fn(lambda: run_xquery(doms, states, user, q["text"]), a)
        info.pop("ids")
        want = [q["result_size_per_domain"][d][str(a.fix)] for d in names]
        if info["rQ_per_domain"] != want:
            raise SystemExit(f"CORRECTNESS GATE FAILED: {q['query_id']} per-domain {info['rQ_per_domain']} != {want}")
        info["rQ_per_domain"] = " ".join(map(str, info["rQ_per_domain"]))
        w.add(scheme="AMTP", domains=len(doms), N_per_domain=a.fix, query_id=q["query_id"], kQ=q["kQ"],
              shape=q["shape"], status="ok", **info, **res)
    w.close()


def suite_xverify(a):
    """Verification 2.1 (multi domain): verify_keywords.csv multi_domain rows at --fix files per domain over the
    four domains; x-axis = total result size; counts per domain must match the file."""
    corpus = Corpus(a)
    rows = corpus.D.verify_keywords("multi_domain", a.fix)
    names = list(corpus.D.DOMAINS)
    print(f"[xverify] files/domain={a.fix} keywords={len(rows)}")
    doms, states, user = multi_build(corpus, [(d, corpus.D.domain_docs(d, a.fix, a.data)) for d in names], a)
    w = Writer("verify_multi", a.out)
    for r in rows:
        res, info, _ = measure_fn(lambda: run_xquery(doms, states, user, q_text([r["keyword"]])), a)
        info.pop("ids")
        if info["rQ_per_domain"] != r["result_size_per_domain"]:
            raise SystemExit(f"CORRECTNESS GATE FAILED: {r['keyword']} {info['rQ_per_domain']}")
        info["rQ_per_domain"] = " ".join(map(str, info["rQ_per_domain"]))
        w.add(scheme="AMTP", domains=len(doms), N_per_domain=a.fix, keyword=r["keyword"],
              target_results=r["target_results"], rank=r["rank"], status="ok", **info, **res)
    w.close()


def suite_xdomains(a):
    """Search 2.2 / Verification 2.2: the same files (--fix per dataset domain, all four) regrouped into
    D = 1..32 domains by arXiv category (domain_groups.csv); every boolean_multi query sent to every domain.
    Total result count must equal the sum of the file's per-domain counts (the groups partition the files)."""
    corpus = Corpus(a)
    qs = corpus.D.boolean_multi_queries()[:a.max_queries or None]
    names = list(corpus.D.DOMAINS)
    print(f"[xdomains] D={a.d_counts} files/domain={a.fix} queries={len(qs)}")
    w = Writer("domains_scaling", a.out)
    for dc in a.d_counts:
        groups = corpus.D.domain_groups(dc, a.fix, names, a.data)
        doms, states, user = multi_build(corpus, [(f"{dc}:{g}", docs) for g, docs in groups], a)
        for q in qs:
            res, info, _ = measure_fn(lambda: run_xquery(doms, states, user, q["text"]), a)
            info.pop("ids")
            info.pop("rQ_per_domain")
            want = sum(q["result_size_per_domain"][d][str(a.fix)] for d in names)
            if info["rQ"] != want:
                raise SystemExit(f"CORRECTNESS GATE FAILED: {q['query_id']} D={dc} gave {info['rQ']} not {want}")
            w.add(scheme="AMTP", domains=len(doms), N_total=sum(len(g) for _, g in groups), query_id=q["query_id"],
                  kQ=q["kQ"], shape=q["shape"], status="ok", **info, **res)
        del doms, states, user, groups
        corpus._docs.clear()                               # new domain names next D: drop cached ciphertexts
        corpus._h.clear()
        gc.collect()
    w.close()


def suite_theta(a):
    """θ sweep at fixed N: query cost (shared Exp. 1 queries at that N) and update cost
    (frozen partitions, 1 and 100 fresh documents) for each θ_max, with θ_min = θ_max / 4."""
    corpus = Corpus(a)
    rows = [r for r in load_queries(a.queries or DEFAULT_QUERIES, a.queries) if r["N"] == a.n]
    if not rows:
        raise SystemExit(f"no shared queries for N = {a.n}")
    pool = corpus.D.insert_pool(a.domains, a.data)
    src = corpus.D.sample(a.n, a.domains, a.data)
    inv = corpus.D.inverted_index(src)
    print(f"[theta] N={a.n} θ_max={a.theta_values} θ_min=θ_max/4 queries={len(rows)}")
    w = Writer("theta_sweep", a.out)
    cursor = 0
    for tmax in a.theta_values:
        a.theta_max, a.theta_min = tmax, tmax // 4
        dom, state, lay = setup("D", corpus, src, a)
        user = corpus.user(["D"])
        q_samples, info_sum = [], {"sQ": [], "proof_bytes": [], "pQ": []}
        for q in rows:
            text = quote_terms(q["query"])
            res, info = measure(dom, state, user, text, a)
            if info.pop("ids") != ground_truth(text, inv, dom.cids):
                raise SystemExit(f"CORRECTNESS GATE FAILED: result != ground truth for {q['query']}")
            q_samples.append({k[:-3]: res[k + "_median"] for k in
                              ("query_gen_ms", "server_total_ms", "verify_total_ms", "end_to_end_ms")})
            for k in info_sum:
                info_sum[k].append(info[k])
        dom.eng.policy = StaticPolicy(a.buckets, a.theta_min, a.theta_max)
        upd = {}
        for b in (1, 100):
            samples = []
            for rep in range(a.warmup + a.reps):
                batch = [pool[(cursor + i) % len(pool)] for i in range(b)]
                cursor = (cursor + b) % len(pool)
                prepared = [corpus.encrypt(d, "D") for d in batch]
                t0 = time.perf_counter()
                for cid, ct, keys, bucket in prepared:
                    dom.server.store_ciphertext(cid, ct)
                    dom.eng.insert(cid, keys, bucket)
                st_ins = dom.eng.commit()
                dom.finalize()
                t_ins = (time.perf_counter() - t0) * 1e3
                for cid, *_ in prepared:
                    dom.eng.delete(cid)
                dom.eng.commit()
                dom.finalize()
                for d in batch:
                    corpus._docs.pop((d.doc_id, "D"), None)
                if rep >= a.warmup:
                    samples.append(t_ins)
                    upd.setdefault(f"keys_refreshed_b{b}", st_ins["keys_refreshed"])
            upd[f"insert_b{b}_ms_median"] = st.median(samples)
            upd[f"insert_b{b}_per_doc_ms"] = st.median(samples) / b
        if dom.eng.snapshot().R_D != dom.eng.R_D:
            raise SystemExit("CORRECTNESS GATE FAILED: incremental R_D != full rebuild")
        w.add(N=a.n, theta_max=tmax, theta_min=tmax // 4, partitions=lay["partitions"],
              max_partition=lay["max_partition"],
              **{f"query_{k}_ms_median": st.median(x[k] for x in q_samples)
                 for k in ("query_gen", "server_total", "verify_total", "end_to_end")},
              sQ_median=st.median(info_sum["sQ"]), proof_bytes_median=st.median(info_sum["proof_bytes"]),
              **upd)
        del dom, state
        gc.collect()
    w.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["exp1", "exp2-layouts", "exp2", "exp3", "exp5", "theta",
                                     "search1", "verify1", "tamper", "xsearch", "xverify", "xdomains"])
    ap.add_argument("--data", default=None, help="dataset folder (default <repo>/data/amtp_file_db_v4 or AMTP_DATA)")
    ap.add_argument("--domains", nargs="+", default=["D1", "D2", "D3", "D4"], help="dataset domains to sample")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--queries", default=None,
                    help=f"query file to replay (default {os.path.relpath(DEFAULT_QUERIES)})")
    ap.add_argument("--sizes", type=int, nargs="+", default=[10_000, 50_000, 100_000, 200_000])
    ap.add_argument("--n", type=int, default=200_000, help="N for exp2-layouts / theta")
    ap.add_argument("--rq", type=int, nargs="+", default=[10, 100, 1000, 5000])
    ap.add_argument("--batches", type=int, nargs="+", default=[1, 10, 100, 1000])
    ap.add_argument("--exp5-workload", default=os.path.join(RESULTS, "exp5_workload.json"),
                    help="shared Exp. 5 workload (python3 baselines/amtp_dataset.py exp5)")
    ap.add_argument("--buckets", type=int, default=16, help="placement groups (arXiv primary categories)")
    ap.add_argument("--theta-max", type=int, default=64)                 # docs/THETA_CHOICE.md
    ap.add_argument("--theta-min", type=int, default=16)
    ap.add_argument("--theta-values", type=int, nargs="+", default=[64, 128, 256, 512, 1024],
                    help="θ_max values for the theta sweep (θ_min = θ_max / 4)")
    D = arxiv_loader()
    ap.add_argument("--s-domains", nargs="+", default=list(D.DOMAINS), help="v4 single-domain suites: domains")
    ap.add_argument("--fpd", type=int, nargs="+", default=D.V4_SIZES, help="search1: files per domain")
    ap.add_argument("--fix", type=int, default=D.V4_FIX, help="verify1 / xsearch / xverify / xdomains: files per domain")
    ap.add_argument("--d-counts", type=int, nargs="+", default=D.D_COUNTS, help="xdomains: number of domains")
    ap.add_argument("--max-queries", type=int, default=0, help="xdomains: first n boolean_multi queries (0 = all)")
    ap.add_argument("--tamper-kinds", nargs="+", default=D.TAMPER_KINDS, choices=D.TAMPER_KINDS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    run = {"exp1": suite_exp1, "exp2-layouts": suite_exp2_layouts, "exp2": suite_exp2, "exp3": suite_exp3, "exp5": suite_exp5,
           "theta": suite_theta, "search1": suite_search1, "verify1": suite_verify1, "tamper": suite_tamper,
           "xsearch": suite_xsearch, "xverify": suite_xverify, "xdomains": suite_xdomains}
    for name in [a.mode]:
        run[name](a)


if __name__ == "__main__":
    main()
