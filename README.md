# NewAMTP

**Adaptive Multi-Domain Merkle Tree Partitioning for dynamic verifiable Boolean search over encrypted cloud data**

NewAMTP is the clean rebuild of the AMTP research prototype. It reorganises the implementation into independent
engines, one per function, removes duplicated code paths, and is the codebase for the revised experiments of the paper.

## Status

| Stage | Scope | Status |
|---|---|---|
| 1 | Current AMTP code, cleaned; previous experiment results removed | Done |
| 2 | Engine layout and one shared benchmark harness for AMTP and all baselines | Planned |

Before stage 2, `amtp_code` was brought in line with the paper's protocol flow: binary encodings and
`cid = H(CT bytes)`, B+ Search Tree and Cuckoo filter for lookup, the Phase 2 update protocol with the owner's
Validator, one code path for demo and benchmarks (attacks in an adversary plug-in), and one binary size rule for
every scheme. See `docs/ENGINE_REDESIGN.md` section 3.
| 3 | Implementation-level performance fixes and multiprocessing | Planned |
| 4 | Protocol revisions, after supervisor approval | Planned |

## Schemes compared

| Scheme | Role |
|---|---|
| AMTP | Proposed scheme |
| Chen et al. [40] | Baseline |
| Du et al. [7] | Baseline |
| SE-COLLAB [37] | Baseline |

All schemes use the same arXiv dataset (dataset-v4: 4 domains × 125,000 files, κ = 20 keywords per file) and the
same keyword sets W(d) from `documents.csv`. Experiments run on the project's cloud machine.

## Repository

| Folder | Contents |
|---|---|
| `amtp_code/` | AMTP implementation, user-side demo (`run.py`), benchmarks (`bench/`), tests |
| `baselines/` | Chen et al., Du et al., SE-COLLAB, shared dataset loader `amtp_dataset.py`, plotting |
| `datasets/arxiv/` | dataset-v4 parts (`data_v4/`), build and unpack scripts |
| `docs/` | paper summary and design notes |
| `scripts/` | `aws_run_all.sh`: the full experiment plan on one machine |

Planned layout after stage 2:

```
amtp/core/        hashing, Merkle trees, encoding, cryptography, Boolean queries
amtp/engines/     ingest, storage, partition, commitment, anchor,
                  query, router, proof, verify, access
amtp/plugins/     adversary scenarios (demo and tests only)
harness/          shared dataset loader, query sets, measurement, plots
schemes/          AMTP, Chen et al., Du et al., SE-COLLAB
datasets/arxiv/   shared arXiv dataset: build scripts and compressed parts
tests/            unit tests and the full-rebuild reference for R_D
```

## Quick start

```bash
git clone https://github.com/pperabha/NewAMTP.git && cd NewAMTP
python3 -m venv .venv && .venv/bin/pip install -r amtp_code/requirements.txt
.venv/bin/python datasets/arxiv/unpack.py         # dataset-v4 -> data/amtp_file_db_v4/ (once, a few minutes)
.venv/bin/python baselines/amtp_dataset.py        # check: D1..D4 initial 125000 pool 12500
bash scripts/aws_run_all.sh check                 # dataset present, unit tests, self-tests
```

Every scheme reads the same documents and keywords from `data/amtp_file_db_v4/documents.csv` through
`baselines/amtp_dataset.py`. Details: [`datasets/arxiv/README.md`](datasets/arxiv/README.md).

## Contributing

Work on a branch and open a pull request into `main`. Keep generated experiment results and raw data out of the
repository; only the compressed dataset parts under `datasets/arxiv/data_v4/` are versioned.

## Authors

Perabha Roiampaeng, Apisara Korcharoenkiat, Vanessa Nattacha Wenk, Wanitcha Saengbundit, Somchart Fugkeaw
(SIIT, Thammasat University)
