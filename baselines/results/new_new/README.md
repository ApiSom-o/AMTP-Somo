# new_new — ผลใหม่จาก cloud (16 พ.ย. 2026) แยกจากผลเดิมทั้งหมด

โฟลเดอร์นี้เก็บ**เฉพาะ**ค่าใหม่และกราฟใหม่ โฟลเดอร์เดิม `new_amtp_result/` (`gamma_with_v/`, `graph_op/`, `fill_v/`, `graph_fill/`) ไม่ถูกแก้ ยังเหมือนใน main ทุกไฟล์

## ข้างในมีอะไร

```
new_new/
  data/
    global_mt_v_t64/        Global-MT(v), θ_max = 64, 1,674 batch (เครื่อง w3, commit 089726d)
                            เฉพาะแถว Global-MT(v) · ผลดิบอยู่ที่ runs/cloud/w3/paper_v_gmtv/
    fill/                   รอบ "fill" ของ AMTP ครบทุกชุด (commit 869cf73, placement fill)
                            search1, verify1, tamper, xsearch, xverify, xdomains, ex3, ex5,
                            ex4 θ = 64 / 128 / 256 + Global-MT(v) θ = 64 (splitmerge_n100000_t64_gmtv/)
                            ผลดิบอยู่ที่ runs/cloud/fill_w1..fill_w5/
  graphs/
    main_with_global_mt_v/  ผลหลักเดิม (gamma_with_v) + เส้น Global-MT(v)
      story/                กราฟเล่าเรื่อง (main/ = ด้านที่ชนะ, limits/ = ด้านที่แพ้)
      paper/                กราฟตามแผน paper ex1–ex5 · Global-MT(v) อยู่ใน ex4_split_merge/theta_64/
    fill/                   รอบ fill (AMTP ใหม่ + baseline เดิมจาก gamma_with_v)
      story/
      paper/
```

แต่ละโฟลเดอร์กราฟมี `figure_points.csv` เก็บตัวเลขทุกจุดที่ plot

## ดูรูปไหนก่อน

| อยากดู | รูป |
|---|---|
| AMTP เทียบ Static-MT และ Global-MT(v) ตอน update | `graphs/main_with_global_mt_v/story/main/update_vs_batch.png` |
| partition ใหญ่สุดของแต่ละแบบ | `graphs/main_with_global_mt_v/story/main/max_partition_vs_batch.png` |
| query ของ Global-MT(v) เทียบ AMTP | `graphs/main_with_global_mt_v/paper/ex4_split_merge/theta_64/query_verify_vs_batch.png` |
| split/merge ของรอบ fill | `graphs/fill/story/main/update_vs_batch.png` |
| search / verify ของรอบ fill | `graphs/fill/paper/ex1_search/`, `graphs/fill/paper/ex2_verify/` |

## ตัวเลขหลัก

- **Global-MT(v), θ = 64:**
  - update 66.2 s ต่อ batch ช้ากว่า AMTP (4.9 s) 13.5×
  - query เร็วกว่า AMTP: verify 27.3 เทียบ 44.6 ms และ server 10.2 เทียบ 15.0 ms
  - AMTP คุ้มกว่าจนกว่าจะมี query เกินประมาณ 2,800 ครั้งต่อ epoch
- **รอบ fill:**
  - AMTP update เร็วกว่า Static-MT 13.4× / 11.7× / 9.9× ที่ θ = 64 / 128 / 256 (ผลหลักเดิมได้ 4.9× / 4.2× / 2.7×)
  - ex3 ที่ b = 1,000: insert 14.1 s (เดิม 76.5 s) และ delete 20.1 s (เดิม 63.6 s)
- **Global-MT(v) รอบ fill:** Global-MT(v) ของรอบ fill (เครื่อง amtp-worker7, commit `869cf73`, placement fill, engine ใหม่) ครบ 1,674 batch แล้ว อยู่ที่ `data/fill/splitmerge_n100000_t64_gmtv/` (ผลดิบ `runs/cloud/fill_w5/`) และอยู่ในกราฟ `graphs/fill/` แล้ว: update median ทั้ง stream AMTP 1.1 s · Static-MT 14.8 s (13.4×) · Global-MT(v) 28.5 s (**25.7×**) · query (server + verify, median ทุกจุดวัด) AMTP 51.7 · Static-MT 46.1 · Global-MT(v) 30.0 ms → AMTP คุ้มกว่า Global-MT(v) จนกว่าจะมี query เกิน ~1,260 ครั้งต่อ epoch (Static-MT ~2,450)
- ตัวเลข Global-MT(v) ของ w3 ข้างบน (66.2 s, 13.5×, ~2,800) มาจากโค้ดก่อนแก้ engine ใช้เทียบได้กับผลหลักเดิม (`main_with_global_mt_v`) เท่านั้น ห้ามเทียบกับรอบ fill

รายละเอียด การตรวจ และวิธีทำกราฟซ้ำ: `docs/reports/2026-11-16-cloud-gmtv-fill.md`
