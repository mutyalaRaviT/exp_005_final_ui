"""exp_42 2026-09-08 — time /api/open for the generated big files and summarise what came back.
Usage: python3 testdata/perf_open.py 8047 100 1000 2000
"""
import json
import sys
import time
import urllib.request

port = sys.argv[1]
for n in sys.argv[2:]:
    path = f"corpus/sas/big_{n}.sas"
    req = urllib.request.Request(f"http://localhost:{port}/api/open", data=json.dumps({"path": path}).encode(),
                                 headers={"content-type": "application/json"})
    t0 = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=3600))
    dt = time.time() - t0
    kinds = {}
    for b in d["blocks"]:
        kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    print(f"big_{n}: open {dt:.1f}s · ok={d['ok']} · blocks={len(d['blocks'])} · empty py={sum(1 for b in d['blocks'] if not b['py'])}"
          f" · ds edges={len(d.get('lineage', {}).get('ds_lineage', []))} · json {len(json.dumps(d))//1024} KB")
    print("   receipts:", d["receipts"])
    print("   kinds:", kinds)
    if d["errors"]:
        print("   errors:", d["errors"][:3])
    json.dump(d, open(f"out/bench_perf_open_{n}.json", "w"))
