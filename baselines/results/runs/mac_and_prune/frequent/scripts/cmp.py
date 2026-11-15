import csv,statistics as st,collections as C,os,sys,json
S=sys.argv[1]
tier={json.loads(l)["query_id"]:json.loads(l)["tier"] for l in open(os.path.join(S,"queries.jsonl"))}
F={"AMTP":"base/amtp_search_single.csv","AMTP+prune":"prune/amtp_search_single.csv","SE-COLLAB":"secollab/secollab_search_single.csv","Chen":"chen/chen_search_single.csv","Du":"du/du_search_single.csv"}
D={}
for k,f in F.items():
    p=os.path.join(S,f)
    if not os.path.exists(p): continue
    g=C.defaultdict(list)
    for r in csv.DictReader(open(p)):
        if r["status"]=="ok": g[(tier[r["query_id"]],int(r["kQ"]))].append(r)
    D[k]=g
names=list(D)
for title,col,s,fmt in [("end-to-end ms","end_to_end_ms_median",1,"{:.2f}"),("proof KB","proof_bytes",1/1024,"{:.1f}")]:
    print("\n"+title+"  (tier df>=, kQ) | "+" | ".join(names))
    for key in sorted(D["AMTP"]):
        print(key,"| "+" | ".join(fmt.format(st.median(float(r[col])*s for r in D[n][key])) if D[n].get(key) else "-" for n in names),
              " pQ:", " ".join(str(st.median(float(r["pQ"]) for r in D[n][key])) for n in names if n.startswith("AMTP") and D[n].get(key)))
