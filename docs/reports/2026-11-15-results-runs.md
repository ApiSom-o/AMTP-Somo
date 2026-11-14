# รายงาน: เอาโฟลเดอร์ผลการรัน `baselines/results/runs/` ขึ้น repo — 15 พ.ย. 2026

## ทำอะไร

ก่อนหน้านี้ `.gitignore` กันทั้งโฟลเดอร์ `baselines/results/runs/` ไว้ (กติกาเดิม "ไม่ commit ผลการทดลอง") ตอนนี้เจ้าของงานให้เอาขึ้น เพื่อให้เพื่อนเห็นผลดิบทุกเครื่องด้วย ไม่ใช่แค่ชุดที่คัดแล้วใน `new_amtp_result`

- แก้ `.gitignore` ให้ commit `runs/` ได้ รวมถึง log ของการรัน (`*.log` ซึ่งปกติถูกกันทั้ง repo)
- เพิ่ม 705 ไฟล์ (~55 MB) ไม่มีไฟล์ไหนใหญ่เกิน 50 MB

## มีอะไรบ้าง

| โฟลเดอร์ | คืออะไร |
|---|---|
| `runs/cloud/w1` … `w9` | ผลที่ดึงมาจากเครื่อง AWS แต่ละเครื่อง เช่น `paper_v` (γ มี v), `paper_nov` (γ ไม่มี v), `paper_calib_*` (รอบ calibration), `paper_nov_q`, `paper_v_exp3fix` (ex3 หลังแก้ Validator) พร้อม log ของ worker |
| `runs/cloud/preview_v`, `preview_nov` | ผลชุดที่ดึงมาระหว่างรัน ใช้ดูตัวอย่างก่อนรันจบ |
| `runs/new_amtp_result/gamma_with_v`, `gamma_without_v` | ชุดที่รวมจากหลายเครื่องก่อนคัดลอกไปไว้ที่ `baselines/results/new_amtp_result/` |

w2 กับ w10 (split/merge θ = 128 / 256) และ w3 (Global-MT(v)) **ยังรันอยู่** ไฟล์ของสามเครื่องนี้ใน `runs/` จึงยังเป็นผลบางส่วน (เช่นรอบ calibration) จะเพิ่มผลจริงเมื่อรันเสร็จ

## ไม่ได้เอาขึ้น

- `runs/smoke_*/`: smoke test เก่าบน Mac ในไฟล์มี path ในเครื่องของเจ้าของงาน และไม่ได้ใช้ในผลใดๆ
- `runs/**/.seen_*`, `.pulled_*`: ไฟล์สถานะของสคริปต์เฝ้าดูเครื่อง cloud ใช้ภายในเครื่องเท่านั้น

## ตรวจก่อนขึ้น

ค้นทุกไฟล์แล้ว ไม่พบกุญแจ AWS, private key, IP address หรืออีเมล

## ไม่ได้แตะ

ข้อมูลและรูปใน `baselines/results/new_amtp_result/`, โค้ดทั้งหมด
