"""Flask front end for the user-side demo. All logic lives in the amtp package."""
import json
import threading
import time

from flask import Flask, jsonify, render_template, request

from amtp.core.boolean import ParseError
from amtp.scenario import DOMAINS, EXAMPLE_QUERIES, World
from amtp.adversary import ATTACKS

app = Flask(__name__)
_lock = threading.Lock()
world = World()


def _state():
    domains = []
    for d, name in DOMAINS.items():
        epoch, r_d = world.anchor.latest(d)
        domains.append({"id": d, "name": name, "epoch": epoch, "R_D": r_d.hex(),
                        "pending": [p["title"] for p in world.pending[d]]})
    users = [{"uid": u.uid, "name": u.name, "role": u.role, "attrs": u.attrs,
              "domains": sorted(u.domain_keys)} for u in world.users.values()]
    history = [{"block": h.block, "domain": h.domain, "epoch": h.epoch,
                "R_D": h.R_D.hex(), "R_G": h.R_G.hex()} for h in world.anchor.history[-6:]]
    return {"domains": domains, "users": users, "R_G": world.anchor.R_G.hex(),
            "history": list(reversed(history)), "attacks": list(ATTACKS.items()),
            "examples": EXAMPLE_QUERIES}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def state():
    with _lock:
        return jsonify(_state())


@app.post("/api/search")
def search():
    body = request.get_json(force=True)
    with _lock:
        user = world.users[body["uid"]]
        out = []
        for d in body.get("domains", []):
            out.append(_search_one(user, d, body.get("query", ""), body.get("mode", "honest")))
        return jsonify({"results": out})


def _search_one(user, domain, text, mode):
    card = {"domain": domain, "name": DOMAINS[domain]}
    try:
        t_q, ctx = user.make_query(domain, text, world.anchor)
    except ParseError as err:
        return {**card, "status": "bad_query", "reason": str(err)}
    except PermissionError as err:
        return {**card, "status": "no_key", "reason": str(err)}

    card["trapdoor"] = {
        "epoch": ctx["epoch"], "R_D": ctx["R_D"], "nonce": t_q["nonce"], "tau": t_q["tau"],
        "keywords": [{"word": w, "h": h} for h, w in sorted(ctx["word_of"].items(),
                                                             key=lambda x: x[1])],
        "expression": ctx["text"],
    }
    result = world.adversary.search(t_q, mode)
    card["attack"] = result.get("attack")
    card["cs_ms"] = result.get("cs_ms")
    if result["status"] != "ok":
        status = "refused" if result["status"] == "rejected" else result["status"]
        return {**card, "status": status, "reason": result["reason"]}

    wire = json.dumps(result["response"])          # what travels over the network
    resp = json.loads(wire)
    report = user.verify(ctx, resp)
    card.update(status="accepted" if report["accepted"] else "rejected",
                checks=report["checks"], verify_ms=report["verify_ms"])
    proof = resp["proof"]
    card["stats"] = {
        "response_bytes": len(wire), "proof_bytes": len(json.dumps(proof)),
        "present": sum(e["status"] == "present" for e in proof["evidence"]),
        "absent": sum(e["status"] == "absent" for e in proof["evidence"]),
        "partitions": len(proof["partitions"]), "returned": len(resp["R_ct"]),
    }
    if report["accepted"]:
        start = time.perf_counter()
        card["files"] = user.decrypt(resp)
        card["decrypt_ms"] = round((time.perf_counter() - start) * 1000, 2)
    return card


@app.post("/api/publish")
def publish():
    d = request.get_json(force=True)["domain"]
    with _lock:
        before = len(world.owners[d].structure_log)
        doc = world.publish_next(d)
        splits = [f"{r[0]} {r[1][:8]}" for r in world.owners[d].structure_log[before:]]
        return jsonify({"published": doc and doc["title"], "splits": splits, "state": _state()})


@app.post("/api/reset")
def reset():
    global world
    with _lock:
        world = World()
        return jsonify(_state())
