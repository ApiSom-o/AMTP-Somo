"""วัดเวลาสกัด keyword ของ AMTP (Phase 1, Step 3: W(d) = {Norm(w) : w in Extract(d)}) แยกจากการทดลองอื่น

ทำไมต้องแยก: ตอนทดลอง Search / Update ทุก scheme (AMTP, Chen, Du, SE-COLLAB) ใช้ keyword ชุดเดียวกัน
จาก documents.csv (ไม่มีใครสกัดเอง) ผลที่เทียบกันจึงไม่รวมเวลาสกัด keyword ; ต้นทุนนี้รายงานแยกด้วยสคริปต์นี้
(เป็นงานของ DO ฝั่ง local ก่อนอัปโหลด ทำครั้งเดียวต่อเอกสาร)

วิธีวัด
  - เอกสาร = amtp_dataset.sample(N) ชุดเดียวกับการทดลองอื่น (+ insert pool ถ้าใส่ --pool)
  - อ่านไฟล์ .txt ก่อน (ไม่นับเวลา I/O) แล้วจับเวลาเฉพาะ extract_keywords() = tokenise + Norm + RAKE (+ chunking ถ้ายาว)
  - ปิด garbage collector ระหว่างจับเวลา, รอบ warm-up ไม่บันทึก, --repeats > 1 ใช้ค่ามัธยฐานของแต่ละเอกสาร
  - ตรวจด้วยว่า keyword ที่สกัดได้ตรงกับคอลัมน์ keywords ใน documents.csv (match_csv) — ต้องได้ 100%
  - เวลารวมของแต่ละ N ใน --sizes คิดจากเอกสารชุดเดียวกับ sample(N) (N/4 ไฟล์แรกของแต่ละ domain)

ผลลัพธ์ (โฟลเดอร์ --out)
  amtp_extraction_raw.csv      1 แถว = 1 เอกสาร
  amtp_extraction_summary.csv  ต่อ domain และรวม: ms ต่อเอกสาร (mean/median/std/p95/min/max), docs/s, คำต่อเอกสาร
  amtp_extraction_by_n.csv     เวลาสกัดรวมของทั้งชุดเอกสารสำหรับแต่ละ N
  amtp_extraction_meta.json    สเปกเครื่อง + พารามิเตอร์ (ใส่ใน Experimental Setup)

ตัวอย่าง (รันจากโฟลเดอร์ amtp_code/)
  python -m bench.extraction --n 200000 --pool --sizes 10000 50000 100000 200000
  python -m bench.extraction --n 4000 --repeats 3                 # ลองเร็ว ๆ
  python -m bench.extraction --data ~/amtp_file_db                # dataset อยู่ที่อื่น
"""
import argparse
import csv
import gc
import json
import os
import platform
import statistics as st
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amtp import nlp  # noqa: E402
from amtp.nlp import extract_keywords  # noqa: E402
from bench.workload import arxiv_loader  # noqa: E402


def read_text(data_dir, file_path):
    """อ่าน .txt แบบเดียวกับตอนสร้าง dataset (utf-8, ข้ามไบต์ที่อ่านไม่ได้) ; ไม่นับเวลา"""
    with open(os.path.join(data_dir, file_path), "rb") as f:
        return f.read().decode("utf-8", "ignore")


def stats(ms):
    s = sorted(ms)
    p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
    return {"extract_ms": round(st.mean(s), 4), "extract_ms_median": round(st.median(s), 4),
            "extract_ms_std": round(st.pstdev(s), 4), "extract_ms_p95": round(p95, 4),
            "extract_ms_min": round(s[0], 4), "extract_ms_max": round(s[-1], 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200_000, help="จำนวนเอกสารเริ่มต้นที่วัด (สูงสุด 500,000 = 4 domain x 125,000)")
    ap.add_argument("--sizes", type=int, nargs="*", default=None, help="N ที่ต้องการเวลารวม (ต้อง <= --n)")
    ap.add_argument("--domains", nargs="+", default=None)
    ap.add_argument("--pool", action="store_true", help="วัด insert pool ด้วย (เอกสารใหม่ของ Experiment 3)")
    ap.add_argument("--repeats", type=int, default=1, help="จับเวลาเอกสารละกี่รอบ (ใช้มัธยฐาน)")
    ap.add_argument("--warmup", type=int, default=200, help="จำนวนเอกสารที่รันก่อนเพื่ออุ่นเครื่อง (ไม่บันทึก)")
    ap.add_argument("--data", default=None, help="โฟลเดอร์ amtp_file_db")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    ds = arxiv_loader()
    data_dir = os.path.abspath(os.path.expanduser(a.data or ds.DEFAULT_DATA))
    domains = a.domains or ds.DOMAINS
    args = (nlp.THETA_DOC, nlp.L_CH, nlp.L_OV, nlp.KAPPA, nlp.MAX_WORDS)   # ค่าเดียวกับที่ใช้สร้าง dataset-v4

    docs = list(ds.sample(a.n, domains, data_dir))
    if a.pool:
        docs += [d for d in ds.insert_pool(domains, data_dir)]
    print(f"dataset: {data_dir}\n  {len(docs)} documents, params theta_doc={args[0]} L_ch={args[1]} L_ov={args[2]} "
          f"kappa={args[3]} max_words={args[4]}, repeats={a.repeats}")

    texts = [read_text(data_dir, d.file_path) for d in docs]      # I/O ไม่นับเวลา
    for t in texts[:a.warmup]:                                     # warm-up
        extract_keywords(t, *args)

    rows = []
    gc_was = gc.isenabled()
    gc.disable()
    t_start = time.perf_counter()
    try:
        for i, (d, text) in enumerate(zip(docs, texts), 1):
            runs = []
            for _ in range(a.repeats):
                t0 = time.perf_counter()
                W, ext = extract_keywords(text, *args)
                runs.append((time.perf_counter() - t0) * 1e3)
            rows.append({"doc_id": d.doc_id, "domain": d.domain, "is_initial": int(d.is_initial),
                         "n_words": ext["n_words"], "n_chars": len(text), "mode": ext["mode"],
                         "n_chunks": len(ext["chunks"]), "n_keywords": len(W),
                         "extract_ms": round(st.median(runs), 5), "match_csv": int(W == list(d.keywords))})
            if i % 20000 == 0:
                gc.collect()
                print(f"  {i}/{len(docs)}  ({time.perf_counter() - t_start:.0f}s)", flush=True)
    finally:
        if gc_was:
            gc.enable()

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "amtp_extraction_raw.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    groups = [("ALL-initial", [r for r in rows if r["is_initial"]])]
    groups += [(f"{dom}-initial", [r for r in rows if r["is_initial"] and r["domain"] == dom]) for dom in domains]
    if a.pool:
        groups += [("ALL-pool", [r for r in rows if not r["is_initial"]])]
    summary = []
    for name, g in groups:
        if not g:
            continue
        ms = [r["extract_ms"] for r in g]
        summary.append({"group": name, "docs": len(g), **stats(ms),
                        "total_s": round(sum(ms) / 1e3, 3), "docs_per_s": round(len(g) / (sum(ms) / 1e3), 1),
                        "words_per_doc": round(st.mean(r["n_words"] for r in g), 1),
                        "keywords_per_doc": round(st.mean(r["n_keywords"] for r in g), 2),
                        "chunked_docs": sum(r["mode"] == "chunked" for r in g),
                        "match_csv_pct": round(100 * sum(r["match_csv"] for r in g) / len(g), 3)})
    with open(os.path.join(a.out, "amtp_extraction_summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)

    by_n = []
    for n in sorted(set(a.sizes or [])):
        if n > a.n:
            print(f"  ! skip N={n} (> --n {a.n})")
            continue
        ids = {d.doc_id for d in ds.sample(n, domains, data_dir)}
        ms = [r["extract_ms"] for r in rows if r["doc_id"] in ids]
        by_n.append({"N": n, "docs": len(ms), "total_extract_s": round(sum(ms) / 1e3, 3), **stats(ms)})
    if by_n:
        with open(os.path.join(a.out, "amtp_extraction_by_n.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(by_n[0]))
            w.writeheader()
            w.writerows(by_n)

    meta = {
        "what": "AMTP Phase 1 keyword extraction (Extract + Norm), timed separately from search/update experiments",
        "date": datetime.now().isoformat(timespec="seconds"),
        "machine": {"platform": platform.platform(), "processor": platform.processor() or platform.machine(),
                    "cpu_count": os.cpu_count(), "python": sys.version.split()[0]},
        "params": {"theta_doc": args[0], "L_ch": args[1], "L_ov": args[2], "kappa": args[3], "max_phrase_words": args[4]},
        "dataset": getattr(ds, "DATASET_TAG", ""), "data_dir": data_dir, "domains": domains, "n": a.n, "pool": a.pool,
        "repeats": a.repeats, "warmup_docs": a.warmup, "timer": "time.perf_counter, gc disabled, file I/O excluded",
        "single_process": True,
    }
    with open(os.path.join(a.out, "amtp_extraction_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    for s in summary:
        print(f"{s['group']:12s} docs={s['docs']:6d}  mean={s['extract_ms']:.3f} ms  median={s['extract_ms_median']:.3f}  "
              f"p95={s['extract_ms_p95']:.3f}  total={s['total_s']:.1f}s  match_csv={s['match_csv_pct']}%")
    for b in by_n:
        print(f"N={b['N']:7d}  total extraction = {b['total_extract_s']:.2f}s")
    print(f"written -> {os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
