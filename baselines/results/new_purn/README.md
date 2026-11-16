# new_purn — กราฟรอบ "prune" (16 พ.ย. 2026) แยกจากผลเดิม

รอบ prune คือ AMTP ที่เปิดทุก query flag (AND pruning, result-only partition check, greedy planner) และใช้ placement fill รันบน cloud ที่ commit `767289c`

โฟลเดอร์ผลเดิม (`new_new/`, `new_amtp_result/`) ไม่ถูกแก้

## แต่ละรูปใช้ผลจากรอบไหน

| ส่วนในรูป | มาจาก | เปิด flag |
|---|---|---|
| เส้น AMTP ใน ex1 (search), ex2 (verify), ex5 (หลาย domain) และ story ทั้ง 5 รูป | **รอบ prune** เครื่อง 1 · ผลดิบ `runs/cloud/prune_w1/paper_prune_v/amtp/` | ✅ |
| เส้น AMTP ใน ex3 (update) | รอบ fill (`new_new/data/fill/`, commit `869cf73`) · ไม่รันใหม่ เพราะโค้ด update ไม่เปลี่ยน | – |
| เส้น baseline (SE-COLLAB, Chen, Du) ทุกรูป | `new_amtp_result/gamma_with_v/` · ไม่รันใหม่ เพราะโค้ด baseline ไม่เปลี่ยน | – |
| ex4 (split / merge) | **ยังไม่มี** รอเครื่อง 2–5 ของรอบ prune | – |

```
new_purn/graphs/
  paper/   25 รูป + figure_points.csv   ex1_search, ex2_verify, ex3_update, ex5_multidomain
  story/   5 รูป (story/main/)           กราฟเล่าเรื่องที่เหลือต้องใช้ ex4
```

## ข้อควรรู้

- **update ของ ex5 ช้าลง ~20% เมื่อเทียบกับรอบ fill:** server ใช้ 37–42 เทียบกับ 30–33 ms น่าจะเป็นต้นทุนของ AND pruning ที่เก็บ R^post tree ไว้ตอนสร้าง snapshot (`amtp/index.py`)
- **OR และ keyword เดียว:** server ช้าลง 4–13% เมื่อเปิด flag (ขั้นวางแผนของ AND pruning) ยืนยันบน Mac แล้ว (`runs/mac_and_prune/flag_overhead/`)

## ทำซ้ำ

```
R=baselines/results/new_amtp_result; T=$(mktemp -d); mkdir $T/amtp
for f in baselines/results/runs/cloud/prune_w1/paper_prune_v/amtp/*; do ln -s $PWD/$f $T/amtp/; done
for f in baselines/results/new_new/data/fill/amtp_exp3_dynamic_update.*; do ln -s $PWD/$f $T/amtp/; done
for s in secollab chen du; do ln -s $PWD/$R/gamma_with_v/$s $T/$s; done
.venv/bin/python baselines/plot_paper.py $T --out baselines/results/new_purn/graphs/paper
.venv/bin/python baselines/plot_story.py --run $T --out baselines/results/new_purn/graphs/story   # หยุดที่รูป ex4 (ยังไม่มีข้อมูล)
```

รายละเอียดและตัวเลข: `docs/reports/2026-11-16-prune-results.md`
