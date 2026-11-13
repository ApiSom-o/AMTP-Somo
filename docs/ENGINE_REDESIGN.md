# NewAMTP engine redesign: goal, rules and plan

This is the team's shared knowledge base for moving the AMTP prototype to its target design.
Read it before changing code in this repository, whether you are a team member or an AI coding
assistant working for one. It says where the code is now, where it must end up, the order of
work, and the rules that keep the paper's results valid.

Companion documents: [`AMTP_PAPER.md`](AMTP_PAPER.md) (the protocol as the paper defines it),
[`IMT_UPDATE_COST.md`](IMT_UPDATE_COST.md) (why the IMT has `next` pointers), the dataset README in
[`../datasets/arxiv/README.md`](../datasets/arxiv/README.md), and the experiment runner
[`../scripts/aws_run_all.sh`](../scripts/aws_run_all.sh).

---

## 1. Goal

Rebuild AMTP as **ten engines, one per function**, with the same protocol and the same results,
then remove the bottlenecks that make AMTP slower than it needs to be.

The redesign is done when all of these hold:

1. Every phase of the paper (1 to 5), all seven verification checks and all nine attack scenarios
   still work, and every measured query is still accepted and matches the plaintext ground truth.
2. The code is organised as the engines in section 4, with no duplicated code paths.
3. AMTP and all three baselines run from one shared benchmark harness with one CSV schema.
4. The bottlenecks marked "code only" in section 7 are fixed and measured.
5. Protocol changes (B3, B4) are either approved by the supervisor and written into the paper,
   or explicitly left out.

## 2. Ground rules

These apply to every change, by anyone.

| # | Rule | Why |
|---|---|---|
| R1 | **Behaviour first, speed second.** A refactor must give the same `R_D` and the same query results as the code before it. Check it with the tests and the full-rebuild oracle before measuring anything. | A faster scheme that answers differently invalidates every figure. |
| R2 | **The protocol is the paper.** Do not change what is hashed, what is proven or what is checked unless the change is listed as a protocol change (section 7) and the supervisor approved it. | The security argument covers the paper's definitions only. |
| R3 | **Same dataset, same keywords, same queries for every scheme.** All schemes read `documents.csv` through `baselines/amtp_dataset.py` and use the workload files in `datasets/arxiv/data_v4/`. | The comparison is only fair on identical input. |
| R4 | **Same engineering for every scheme.** An optimisation that is not specific to AMTP (binary encoding, integer ids, a worker pool) goes into shared code or is applied to the baselines as well. Main result tables use one core per scheme. | Reviewers reject a comparison where only the proposed scheme was tuned. |
| R5 | **Keep the correctness gates.** Never remove a check that stops a run when a query is rejected or differs from ground truth. | These gates are what make the measured numbers trustworthy. |
| R6 | **No results or raw data in git.** Results go to `baselines/results/` locally or on the cloud machine and are not committed. Only the compressed dataset parts in `datasets/arxiv/data_v4/` and the shared workload files are versioned. | Keeps the repository small and the history clean. |
| R7 | **Branches and pull requests.** Work on a branch, open a pull request into `main`, and describe what changed and how it was checked. | Lets the team review protocol-sensitive code. |
| R8 | **Commits under a team member's name.** No assistant names, co-author lines or session links in commits, code or docs. | Team policy for this repository. |
| R9 | **One stage at a time.** Finish and merge a stage (section 6) before starting the next. Each stage is measured against the previous one. | If a number changes, it must be clear which change caused it. |

## 3. Where the code is now

NewAMTP starts from AMTP `main` at commit `0edbce4` (stage 1), with previous results and the old
dataset-v3 parts removed.

| Path | What it does today |
|---|---|
| `amtp_code/amtp/hashing.py` | `H(...)` (SHA-256 over length-prefixed parts), `enc()` canonical JSON, global `HashCounter` |
| `amtp_code/amtp/merkle.py` | positional Merkle tree, `set_leaf`, `try_append`, `multiproof`, `multiverify` |
| `amtp_code/amtp/crypto.py` | AES-GCM, AES-SIV, HMAC, Ed25519 (stand-in for ABS), policy key wrap (stand-in for CP-ABE) |
| `amtp_code/amtp/boolean.py` | AND/OR parser and evaluator, used for queries and access policies |
| `amtp_code/amtp/nlp.py` | RAKE keyword extraction (Phase 1, step 3) |
| `amtp_code/amtp/dht.py` | ciphertext store: consistent-hash ring with replicas |
| `amtp_code/amtp/engine.py` | **incremental** index: partitions, postings, γ, ρ, R^post, partition tree, indexed IMT, `commit()` |
| `amtp_code/amtp/variants.py` | partition policies: AMTP (adaptive), Static-MT, Global-MT |
| `amtp_code/amtp/index.py` | `DomainState` (**full rebuild** of every commitment), `PartitionLayout` (second, demo-only index builder), helpers `gamma`, `rho`, `imt_leaf` |
| `amtp_code/amtp/owner.py` | demo Data Owner: encrypts and publishes through `PartitionLayout` + `DomainState` |
| `amtp_code/amtp/anchor.py` | Root Anchor: signed transitions, `e' = e* + 1`, global root `R_G` |
| `amtp_code/amtp/server.py` | Cloud Server: admission, **nine attack modes inline**, `build_response` (ASPA) |
| `amtp_code/amtp/user.py` | Data User: trapdoor, seven checks of Accept_Q, decryption |
| `amtp_code/amtp/scenario.py`, `web/`, `run.py` | interactive demo |
| `amtp_code/bench/experiments.py` | AMTP benchmark suites (legacy exp1/2/3/5/theta and the dataset-v4 suites), `run_xquery` (cross-domain), `tamper_response`, `full_check` |
| `amtp_code/bench/ablation.py`, `workload.py`, `extraction.py`, `plot.py` | Exp. 4 ablation, workload loaders, keyword-extraction timing, plots |
| `baselines/*_sim.py` | Chen et al., Du et al., SE-COLLAB, each with its own copy of the timing, CSV and query-replay code |
| `baselines/plot_*.py` | six plotting scripts |
| `scripts/aws_run_all.sh` | runs the advisor's experiment plan on one machine |

Known facts about the current code that the plan depends on:

- **Two index builders.** The benchmarks use `Engine` (incremental). The demo uses `PartitionLayout` + `DomainState`, which follow different rules (version bumped per insert, no merge, emptiest partition across all buckets).
- **Publishing rebuilds everything.** `Domain.publish_snapshot()` in `bench/experiments.py` calls `Engine.snapshot()`, which builds a full `DomainState` (every γ, ρ and Merkle tree) so that `build_response` has something to read.
- **Cross-domain search exists at benchmark level only.** `run_xquery` sends one domain-bound query per domain, one after another, and verifies each against that domain's own root. There is no engine for it.
- **Owner-side transition validation (Phase 2, step 5) is not implemented.**
- **Legacy suites still use dataset-v3 workload files.** `exp1`, `exp2`, `exp5` and `theta` replay `baselines/results/exp1_queries.json`, `exp2_layouts.json` and `exp5_workload.json`, built from dataset-v3, whose parts are not in NewAMTP. The dataset-v4 suites (`search1`, `verify1`, `tamper`, `xsearch`, `xverify`, `xdomains`) do not need them.

## 4. Target architecture

### 4.1 The ten engines

Each engine has one job, one input and one output. "Pool" means its work splits into independent
tasks that can run in a worker pool (section 8).

| # | Engine | Paper phase | Input → output | Comes from today | Pool |
|---|---|---|---|---|---|
| 1 | **Ingest** | 1 | document, policy, W(d) → `cid`, `CT`, `{h_w}`, bucket | `owner.encrypt`, `bench.experiments.Corpus`, `crypto`, `nlp` | yes, per document |
| 2 | **Storage** | 1, 4 | `put(cid, CT)` / `get(cid)` → `CT` or `StorageError` | `dht.py` | yes, batch fetch |
| 3 | **Partition** | 3 | `insert(cid, {h}, bucket)` / `delete(cid)` → dirty `(pid, slot)` set, `Move(cid)` | `engine.insert/delete/split/merge`, `variants.py` | no |
| 4 | **Commitment** | 2 | dirty set → `R_D(e)` and a read-only view of every tree | `engine.commit`, `merkle.py`, `index.gamma/rho/imt_leaf` | yes, per dirty keyword |
| 5 | **Anchor** | 2 (step 5) | `(domain, e, R_D, σ_root)` → accepted `(e*, R_D)`, `R_G` | `anchor.py`, `crypto.Signer` | no |
| 6 | **Query** | 4 (step 1) | Boolean text, user keys → `T_Q`; admission on the server side | `boolean.py`, `user.make_query`, `server._admit` | no |
| 7 | **Proof** | 4 | admitted `T_Q`, Commitment view, Storage → `R_Q` with `Π_Q` | `server.build_response`, `_absent_evidence`, `evaluate_on_state` | yes, per keyword |
| 8 | **Verify** | 5 (steps 1 to 3) | `ctx`, `R_Q`, `(e*, R_D)` from Anchor → accept/reject, checklist, `M̂` | `user.verify` and its `_check_*` methods, `merkle.multiverify` | yes, map-reduce |
| 9 | **Access** | 5 (step 4) | accepted `R_ct`, attribute keys → plaintext or "locked" | `crypto.unwrap`, `user.decrypt` | yes, per file |
| 10 | **Router** (new) | cross-domain | `T_Q` over domains `{D1..Dk}` → per-domain queries, combined result | `bench.experiments.run_xquery` | yes, per domain |

Plus one new owner-side component, the **Validator** (D3): it replays the dirty-path evidence Δ
against the anchored old root before the owner signs, instead of rebuilding the index.

Two pieces sit outside the core:

- **Adversary plug-in**: the nine attack modes from `server.py`, wrapped around an honest Proof engine's output. Demo and tests only; benchmarks never load it.
- **Shared harness**: dataset loading, query replay, timing (reps and warm-up), CSV writer, plots. Used by AMTP and every baseline.

### 4.2 Data flow

Update path (owner and cloud, Phases 1 to 3, one epoch):

```
Ingest ──cid,{h}──▶ Partition ──dirty──▶ Commitment ──Δ, π^upd──▶ Validator ──σ_root──▶ Anchor
   │ put CT                                   │ live read view                      │ (e*, R_D)
   ▼                                          ▼                                      ▼
Storage                                     Proof                                  Verify
```

Query path (user and cloud, Phases 4 and 5):

```
Query ──T_Q──▶ Router ──per domain──▶ Proof ──R_Q, Π_Q──▶ Verify ──accept──▶ Access
                                        ▲  get CT                ▲ R_D(e*) from Anchor
                                     Storage                     (never from the server)
```

The edge that matters most is **Commitment → Proof**: Proof must read the Commitment engine's
live trees, not a `DomainState` rebuilt for every epoch (B1).

### 4.3 What R_D commits to

```
R_G = MerkleRoot(R_D1 … R_Dn)                      audit only; not needed to verify a query
└─ R_D(e) = H(i ‖ e ‖ R^part ‖ R^idx)              anchored; checked by b_anchor
   ├─ R^part = MerkleRoot([A_j] in PID order)       PARTITION SIDE (Partition engine)
   │  └─ A_j = H(PID ‖ v ‖ R_P)
   │     └─ R_P = MerkleRoot(slots of P_j)
   │        └─ slot ℓ : cid | ⊥ (tombstone)
   └─ R^idx = MerkleRoot(IMT leaves)                INDEX SIDE (Commitment engine)
      └─ I_w = H(h_w ‖ ρ_w ‖ next(h_w))
         └─ ρ_w = H(h_w ‖ |Sel(h_w)| ‖ R^post_w)
            └─ R^post_w = MerkleRoot([γ_w,j] in PID order)
               └─ γ_w,j = H(PID ‖ v ‖ H(Enc(L_w,j)))
                  └─ L_w,j = [(cid, ℓ), …] sorted by ℓ
```

The two sides meet at the same `(cid, ℓ)` and the same `(PID, v)`; `b_part` checks that they agree.
`b_papc` rebuilds the index side from the returned posting lists.

### 4.4 Target folder layout

```
amtp/core/        hashing.py  merkle.py  encoding.py  crypto.py  boolean.py   (primitives, no state)
amtp/engines/     ingest.py  storage.py  partition.py  commitment.py  anchor.py
                  query.py   router.py   proof.py      verify.py      access.py  validator.py
amtp/plugins/     adversary.py                                                 (nine attacks, demo + tests)
harness/          dataset.py  queries.py  measure.py  writer.py  plot.py       (all four schemes)
schemes/          amtp.py  chen.py  du.py  secollab.py                         (setup / search / verify / update)
demo/             web/                                                         (calls engines, never its own index)
tests/            oracle.py (DomainState full rebuild = reference R_D)  test_*.py
datasets/arxiv/   unchanged
```

### 4.5 Interface sketch

Names and shapes the engines should converge on. Adjust details in review, keep the boundaries.

```python
class Ingest:      def encrypt(self, doc, domain) -> tuple[bytes, dict, frozenset[bytes], int]   # cid, CT, {h_w}, bucket
class Storage:     def put(self, cid: bytes, ct: bytes) -> None
                   def get(self, cid: bytes) -> bytes                                           # raises StorageError
class Partition:   def insert(self, cid, keys, bucket) -> None
                   def delete(self, cid) -> None
                   def adapt(self) -> DirtySet                                                  # split / merge / none
class Commitment:  def commit(self, dirty: DirtySet) -> CommitResult                            # R_D, Δ, stats
                   def view(self) -> CommitmentView                                             # read-only, for Proof
class Validator:   def check(self, old_root, new_root, delta) -> bool
class Anchor:      def submit(self, domain, epoch, r_d, sig) -> None
                   def latest(self, domain) -> tuple[int, bytes]
class Query:       def make(self, domain, text, anchor) -> tuple[dict, dict]                    # T_Q, ctx
                   def admit(self, t_q) -> str | None                                           # server side
class Router:      def split(self, t_q, domains) -> list[dict]
                   def combine(self, results) -> set
class Proof:       def build(self, view: CommitmentView, b_q, nonce, storage) -> dict          # R_Q with Π_Q
class Verify:      def verify(self, ctx, r_q, anchored_root) -> dict                            # accepted, failed, checks, M_hat
class Access:      def decrypt(self, r_q, attr_keys) -> list[dict]
```

## 5. Paper figure updates

The design figures (Phase 1 to Phase 5 panels) need these changes so that paper, figures and code
say the same thing.

| ID | Change | Type |
|---|---|---|
| D1 | Remove the B+ tree and the Cuckoo filter from the indexing and query figures. Only the IMT is evidence; the server may use any lookup structure. | figure + text |
| D2 | IMT leaf is `I_w = H(h_w ‖ ρ_w ‖ next(h_w))` (eq. 20). Non-membership is one bracketing leaf: `h_lo < h < next(h_lo)`. | paper behind code |
| D3 | Commitment runs on the cloud server; the owner's Validator replays Δ on dirty paths at `O(|W_aff| · log n)` instead of re-deriving everything. | missing in code |
| D4 | Draw Phases 2 and 3 as one pass: place → adapt → repair → one candidate root → one validation → one anchor (one epoch). | figure only |
| D5 | Either state the real `W_aff` (with `v` inside γ, a version bump re-commits every keyword in the partition) or move `v` out of γ (= B4). | protocol change |
| D6 | For AND queries, prove only partitions shared by every keyword's `Sel(h)` (= B3). | protocol change |
| D7 | Accept_Q has seven terms: `b_ctx ∧ b_anchor ∧ b_idx ∧ b_papc ∧ b_part ∧ b_comp ∧ b_ct`. Cross-domain: the user reads each domain's `(e*, R_D)` from the anchor; `R_G` stays audit-only. | figure + text |
| D8 | Phase 1 figure: show "W(d) given by the shared dataset" as an alternative to RAKE. Decide whether the signed update `σ_op` is checked (it is not, in code) or drop it from the figure. | figure + code |

The "commitment tree" in section 4.3 should replace the partition-only tree in the current figure.

## 6. Plan

| Stage | Scope | Done when |
|---|---|---|
| **1** | Current AMTP code, cleaned; previous results and dataset-v3 removed | **Done** (commit `c7e2a81`) |
| **2** | Engine layout and code cleanup, no behaviour change | tests pass, oracle `R_D` matches, the dataset-v4 suites give the same accept/reject and result sets as stage 1 |
| **3** | Code-only bottleneck fixes and multiprocessing | each fix measured against stage 2 on the same machine and inputs; 1-core numbers reported separately from multi-core |
| **4** | Protocol changes B3 / B4, after supervisor approval | paper text and figures updated, security argument rechecked, all experiments re-run |

Stage 2, in order (one pull request per step is fine):

1. Create `amtp/core/` and move the primitives (`hashing`, `merkle`, `crypto`, `boolean`) without changing them.
2. Move `DomainState` into `tests/oracle.py`. Keep a test that compares the incremental `R_D` with the oracle.
3. Point the demo at `Engine`; delete `PartitionLayout` and the `DataOwner` publish path. Replace `index.extract_keywords` with `nlp.py`.
4. Split `engine.py` into the Partition and Commitment engines, with `variants.py` as Partition's policy.
5. Split `server.py` into Query (admission) and Proof (`build_response`); move the nine attacks into `plugins/adversary.py`.
6. Split `user.py` into Query (trapdoor), Verify and Access.
7. Turn `run_xquery` into the Router engine.
8. Build the shared harness from the duplicated `Writer`, `summarize`, `measure`, `OpCounter` and query-replay code; move each baseline into `schemes/`. Merge the plotting scripts.
9. Decide the legacy suites: regenerate `exp1_queries.json`, `exp2_layouts.json`, `exp5_workload.json` on dataset-v4, or retire `exp1`, `exp2`, `exp5`, `theta`.
10. Add the Validator (D3) with Δ evidence, timed as part of the update cost.

## 7. Bottleneck and weak-point register

"Code only" means no change to what the paper defines. "Protocol" needs supervisor approval (R2).

| ID | Severity | Where (today) | Problem | Fix | Type | Stage |
|---|---|---|---|---|---|---|
| B1 | critical | `Domain.publish_snapshot` → `Engine.snapshot` → `DomainState._build` | Every publish rebuilds every γ, ρ and Merkle tree (≈ N × 20 postings at N = 500k) and holds a second full copy of the index, throwing away the incremental work. | Proof reads a read-only view of the Commitment engine; the full rebuild becomes a test oracle run every k epochs. | code only | 2–3 |
| B2 | high | `CloudServer.store_state`, `CloudServer.search` | The server keeps every epoch's full state forever and deep-copies every honest response (only for the replay demo). | Keep the current epoch, plus the previous one only when the adversary plug-in is loaded. | code only | 3 |
| B3 | critical | `build_response` (ASPA over `M_cov = ⋃ M_h`), `user._check_papc` | Every proof carries the full posting list of every query keyword, so an AND query costs as much as its most common keyword. Most likely reason AMTP lost to Chen et al. | Partition-pruned PAPC: make R^post leaves `H(PID ‖ γ)`; for AND, open components only in partitions shared by every keyword, send the rest as γ hashes. Process keywords rarest first. | protocol | 4 |
| B4 | high | `Engine.commit` (version bump marks every key in `keys_in[pid]` dirty), `index.gamma` | `v` is inside every γ, so changing one file re-commits every keyword of its partition (up to ≈ θ_max × 20) instead of the file's 20. | Bind `v` only at `A = H(PID ‖ v ‖ R_P)`; drop it from γ. Freshness argument must be rechecked. | protocol | 4 |
| B5 | medium | `hashing.enc`, `index.gamma`, `dht.ciphertext_id`, JSON + hex responses | Canonical JSON with hex strings on the hashing hot path; cids hash a hex-expanded JSON ciphertext. | `core/encoding.py`: fixed-width binary encoding, `cid = H(raw CT bytes)`, CBOR/msgpack on the wire. Same rule for the baselines (R4). | code only | 3 |
| B6 | medium | `DHT.get` | Every read deep-copies and re-hashes the ciphertext; the user hashes it again in `b_ct`. | Immutable bytes, no copy; verify-on-read optional (storage-loss demo). | code only | 3 |
| B7 | high | `Engine.comp`, `fwd`, `keys_in`, `gam` | ≈ 10M posting entries at 500k files as nested dicts keyed by 32-byte `bytes`: several GB before B1's copy. | Integer ids for cids and keywords at ingest; postings as integer arrays per (keyword, partition). | code only | 3 |
| B8 | low | `merkle.multiverify` (`remaining.pop(0)`), `AdaptivePolicy.adapt` (`queue.pop(0)`, partner scan over all partitions), `Engine._rebuild_part_tree`, `Engine._post_root` | Small quadratic or full-rebuild spots that grow with small θ or large proofs. | Index pointer; `deque` + heap keyed by `(live, PID)`; free-position trick (as in the IMT) for the partition tree and R^post trees. | code only | 3 |
| B9 | low | `CloudServer.used_nonces` | Nonce set never shrinks. | Keep nonces only for the `MAX_AGE_S` window. | code only | 3 |
| B10 | low | `HashCounter` (class-level globals) | Undercounts as soon as work runs in other processes. | Counter object per engine; workers return their counts. | code only | 3 |
| B11 | medium | `Corpus.encrypt`, whole pipeline | Everything is single-threaded; ingest of 500k files is serial. | Worker pool for Ingest, Commitment per domain, Proof, Verify (section 8). | code only | 3 |
| W1 | high | `owner.py` + `index.PartitionLayout` vs `engine.py` + `variants.py` | The demo and the benchmarks run different index code. | Stage 2, step 3. | consistency | 2 |
| W2 | medium | `bench.experiments.run_xquery` | Cross-domain search exists only inside the benchmark, sequential per domain. | Router engine; per-domain work can run in parallel. | missing engine | 2 |
| W3 | high | Phase 2, step 5 | Owner-side transition validation is described in the paper but not implemented or timed. | Validator (D3). | paper vs code | 2 |
| W4 | low | `CloudServer._admit` | A commit between `make_query` and `search` rejects an honest query with no hint. | Return the current `e*` in the rejection; client retries once. | usability | 3 |
| W5 | low | `crypto.py` | CP-ABE and ABS are stand-ins (documented). | No change; Access and Anchor engines isolate them for a later real scheme. | known limitation | — |

## 8. Multiprocessing plan

Verification is a map-reduce:

| Step | Work | Runs |
|---|---|---|
| 1 | context + anchor checks (`b_ctx`, `b_anchor`, evidence shape) | main process, first, O(1) |
| 2 | plan tasks: equal-**byte** chunks; workers receive indices, not data | main process |
| 3 (map) | γ for each posting component; slot multiproof per partition; `H(CT) = cid` per returned file | worker pool |
| 4 (reduce) | per keyword R^post → ρ → IMT leaf vs R^idx; one domain multiproof vs R^part; `M̂ = Eval(B_Q)` vs the returned set | main process |
| 5 | Accept_Q; on failure report the **first failing check in check order**, as the 1-core code does | main process |

Rules:

- **Split by bytes, not by partition or keyword.** One common keyword can be 1,000× longer than the rest; per-keyword or per-partition tasks leave most workers idle.
- **Remove work before spreading it.** Do B5 and B8 (and, if approved, B3) first; they shrink the map step itself.
- **Python on Linux:** use the `fork` start method; never pickle the whole response to every worker; return hash counts from each worker (B10).
- **Expected speedup (Amdahl):** `S = 1 / (s + (1 − s) / N)`. With a sequential share `s = 0.10` and `N = 16` cores, `S ≈ 6.4×`, about `5×` after pool overhead. Measure `s` by profiling verify at N = 500k before choosing `N`.
- **Fairness (R4):** main tables use one core for every scheme; add a separate speedup-vs-cores figure (1, 2, 4, 8, 16). If a baseline's verification splits the same way, give it the same pool.
- Verification runs on the user's side, so a many-core user is an assumption; server-side parallelism (Proof, Commitment, Router) is the less debatable case.

## 9. Experiments

Advisor's plan (dataset-v4, 4 domains × 125,000 files, κ = 20), as run by `scripts/aws_run_all.sh`:

| Step | Experiment | Schemes |
|---|---|---|
| `search1` | Search 1.1 / 1.2: single domain, AND queries, vary #query keywords and files per domain (10k to 125k) | all four |
| `verify1` | Verify 1.1: single domain, vary #returned files (about 10 to 10,000) | all four |
| `tamper` | Verify 1.2: server modifies / hides / injects / sends old versions of t files; early-abort time, full-check time, files identified | all four |
| `xsearch` | Search 2.1: cross-domain Boolean AND / OR | AMTP, SE-COLLAB |
| `xverify` | Verify 2.1: multi-domain verification, vary #returned files | AMTP, SE-COLLAB |
| `xdomains` | Search / Verify 2.2: the same files as D = 1 to 32 domains | AMTP, SE-COLLAB |
| `update` | update cost, insert / delete batches | AMTP, Chen et al. |
| `theta` | θ sweep: query vs update cost | AMTP |
| `splitmerge` | split / merge under skewed growth, θ_max = 64 / 128 / 256 | AMTP, Static-MT, Global-MT |

What the figures must bring out, beyond time: AMTP **never accepts a wrong result** (every tamper
is detected), and it **identifies which files are wrong** (`full_check`), while keeping the
advisor's parameters on the x-axes.

Running on the cloud machine:

```bash
git clone https://github.com/pperabha/NewAMTP.git && cd NewAMTP
python3 -m venv .venv && .venv/bin/pip install -r amtp_code/requirements.txt
.venv/bin/python datasets/arxiv/unpack.py          # ~3 min, 4 GB in data/amtp_file_db_v4/
bash scripts/aws_run_all.sh check                  # dataset, unit tests, self-tests
tmux new -s amtp                                   # long runs survive a dropped SSH connection
bash scripts/aws_run_all.sh search1 verify1 tamper
```

SE-COLLAB needs `charm-crypto` with the PBC library (see `baselines/README.md`).

## 10. Working in this repository (for people and AI coding assistants)

1. Read this file, `AMTP_PAPER.md`, and the code you are about to change.
2. State which stage and which register item (B#, W#, D#) the change belongs to.
3. For stage 2 changes: run the tests and the oracle comparison before and after; results must be identical.
4. For stage 3 changes: measure before and after on the same machine, inputs and core count; report both.
5. Never weaken a correctness gate, a verification check or an attack scenario to make a number better.
6. Never change hashed content, proof shape or check logic without an approved protocol change (B3, B4).
7. Do not commit results, raw data, `.venv/`, `data/` or key files (`*.pem`).
8. Commit under your own name, with no assistant attribution (R8); open a pull request into `main`.

Checks to run:

```bash
.venv/bin/python -m pytest -q amtp_code                   # unit tests (32 at stage 1)
bash scripts/aws_run_all.sh check                          # dataset + tests + baseline self-tests
```

## 11. Notation

| Symbol | Meaning |
|---|---|
| `i`, `D_i` | domain |
| `e`, `e*` | epoch; latest finalized epoch on the anchor |
| `h_w = H(DEnc_Ks(w))` | protected keyword token |
| `cid = H(CT)` | ciphertext id |
| `P_j`, `PID`, `v`, `ℓ` | partition, its id, its version, a slot in it |
| `L_w,j` | posting component: files with keyword `w` in partition `j`, as `(cid, ℓ)` |
| `Sel(h_w)` | partitions that contain keyword `w` |
| `γ_w,j`, `R^post_w`, `ρ_w` | PAPC: per-component commitment, its Merkle root, the keyword commitment |
| `I_w`, `R^idx` | IMT leaf with `next` pointer; IMT root |
| `A_j`, `R_P`, `R^part` | partition leaf, partition slot root, partition-tree root |
| `R_D`, `R_G` | domain root; global root over domains |
| `B_Q`, `T_Q`, `τ_Q`, `η` | Boolean query, trapdoor, query tag, nonce |
| `M_h`, `M_Q`, `M̂`, `M_cov`, `S_cov` | per-keyword match set, result set, user's own result, covered entries, covered partitions |
| `R_Q`, `Π_Q`, `R_ct` | response, proof, returned ciphertexts |
| PAPC | partition-aware posting commitment |
| ASPA | authenticated selective proof assembly (multiproofs) |
| IMT | indexed Merkle tree |
| AUDC, `Δ`, `π^upd` | audit digest of a transition and its evidence |
| `θ_min`, `θ_max` | merge and split thresholds, `0 < θ_min`, `2θ_min < θ_max` |
| `W_base`, `W_aff` | keys touched by an update; keys repaired after split / merge |

## 12. Open questions for the supervisor

1. B3: may the AND proof open only partitions shared by every keyword (partition-pruned PAPC)?
2. B4: may the partition version leave γ and stay only in `A_j`? Does the freshness claim still hold as written?
3. D8: keep the per-update signature `σ_op` (and implement it) or drop it?
4. Legacy suites (`exp1`, `exp2`, `exp5`, `theta`): regenerate their workloads on dataset-v4 or retire them?
5. Multiprocessing: report verification on one core only, or add a speedup-vs-cores figure, and on which machine?
