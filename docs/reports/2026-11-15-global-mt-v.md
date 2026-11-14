# รายงาน: เพิ่ม `--variants` เพื่อรัน Global-MT(v) แยก (15 พ.ย. 2026)

## ทำไม

กราฟ ablation (ex4) แบบ γ มี v ตอนนี้เทียบ AMTP, Static-MT กับ **Global-MT ที่ไม่ bump v** ซึ่งไม่ยุติธรรม เพราะ Global-MT ไม่ต้องจ่ายค่า v เลย ส่วน AMTP และ Static-MT ต้องคำนวณ γ ใหม่ทุก keyword ของ partition ที่เปลี่ยน version

ตัวที่ยุติธรรมคือ **Global-MT(v)** = AMTP ตาม paper ทุกอย่าง (γ มี v, bump v เมื่อ partition ถูกแก้) แค่มี partition เดียว มีในโค้ดอยู่แล้ว (`--global-versioned`) แต่ตอนรันจริงบน cloud ไม่ได้เปิด

AMTP และ Static-MT แบบมี v ที่ θ = 64 รันครบแล้ว (w1, commit `7485556`, 1,674 batch, ~15 ชั่วโมง) จึงรันเพิ่มแค่ Global-MT(v) แทนการรันใหม่ทั้งหมด

## แก้อะไร

| ไฟล์ | แก้อะไร |
|---|---|
| `amtp_code/bench/ablation.py` | เพิ่ม `--variants "A,B,..."` เลือก variant ที่จะรัน (ค่าเริ่มต้นเหมือนเดิม) ชื่อที่ไม่รู้จักจะถูกปฏิเสธ |
| `amtp_code/tests/test_ablation_variants.py` (ใหม่) | ยืนยันว่ารัน variant เดียวได้ workload เดียวกับตอนรันพร้อมตัวอื่น: ทุกแถวใน updates / layout / queries (ยกเว้นเวลา) ต้องเท่ากันทุกฟิลด์ เช่น hash_calls, keys_refreshed, proof_bytes; และชื่อผิดถูกปฏิเสธ |

- ไม่แตะ engine: `git diff 7485556 -- amtp_code/amtp/` ว่างเปล่า (0 บรรทัด)
- เอกสาร, ลำดับ update และ query สร้างจาก seed ก่อนวนลูป variant และในลูปไม่มีการสุ่มร่วมกัน การตัด variant อื่นออกจึงไม่เปลี่ยน workload (test ข้างบนยืนยัน)
- pytest ผ่านทั้งหมด 158 ข้อ ทั้งโหมดปกติและ `AMTP_GAMMA_V=0`

## ผลลองบน Mac (ขนาดเล็ก, ไม่ได้ commit)

5,000 ไฟล์, θ = 64/16, b = 100, skew 0.95, insert 50 batch + hot delete 0.65, γ มี v:

| variant | update ต่อ batch (median) | hash ต่อ batch | partition ใหญ่สุด |
|---|---|---|---|
| AMTP | 966 ms | 0.80 ล้าน | 64 |
| Static-MT | 1,218 ms | 0.97 ล้าน | 446 |
| Global-MT(v) | 2,408 ms | 2.02 ล้าน | 6,752 |
| Global-MT (ไม่ bump v) | 86 ms | 0.06 ล้าน | 6,752 |

## รันบน cloud

เงื่อนไขเหมือน w1 ทุกอย่าง: γ มี v, seed 1, 1 run, 100k ไฟล์, θ = 64/16, 1,000 batch × 100, skew 0.95, hot-delete 0.65, query ทุก 100 batch, r7i.4xlarge งานเดียวต่อเครื่อง

```bash
cd ~/NewAMTP/amtp_code && ../.venv/bin/python -m bench.ablation --source arxiv --n 100000 --theta-max 64 --theta-min 16 \
  --batches 1000 --batch-size 100 --delete-frac 0 --fresh-source initial --skews 0.95 --runs 1 \
  --hot-delete-frac 0.65 --query-every 100 --variants "Global-MT(v),Global-MT" \
  --out ~/NewAMTP/baselines/results/runs/paper_v_gmtv/amtp/splitmerge_n100000_t64
```

- **Global-MT (ไม่มี v) รันคู่ไปด้วยเพื่อเทียบเครื่อง:** ถ้าเวลาใกล้กับ Global-MT บน w1 แปลว่าเครื่องเร็วเท่ากัน
- **`hash_calls` ไม่ขึ้นกับเครื่อง** รายงานคู่กับเวลาเสมอ
- Global-MT ไม่ใช้ θ (มี partition เดียวเสมอ) ผลชุดนี้จึงใช้ได้กับกราฟทุกค่า θ แต่ต้องเขียนใน caption ว่าเป็นผลชุดเดียวกัน
- เวลาที่คาด: ~6–7 ชั่วโมง (ประเมินจากผลเล็ก อาจคลาดได้ ~2 เท่า)

## กราฟที่จะทำ

γ มี v, θ = 64: AMTP + Static-MT (w1, `7485556`) + Global-MT(v) (รอบนี้) — update ต่อ batch, hash ต่อ batch, partition ใหญ่สุด
caption: "Global-MT(v) รันแยกด้วย workload / seed เดียวกัน, engine ไม่เปลี่ยน (commit ต่างแค่ตัวเลือก --variants)"
