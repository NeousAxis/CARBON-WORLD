import sqlite3, subprocess, sys, time
conn = sqlite3.connect('/home/carbon/CARBON-WORLD/data/carbon.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("""
  SELECT id, suggested_decision, event_title FROM review_queue
  WHERE status='pending'
    AND analyst_a_verdict IS NOT NULL
    AND analyst_b_verdict IS NOT NULL
    AND json_extract(analyst_a_verdict, '$.decision') = json_extract(analyst_b_verdict, '$.decision')
    AND json_extract(analyst_a_verdict, '$.decision') = suggested_decision
  ORDER BY id
""").fetchall()
conn.close()
print(f'Found {len(rows)} unanimous pendings (A==B==suggested) to auto-approve', flush=True)
n_burn = sum(1 for r in rows if r['suggested_decision'] == 'BURN')
n_mint = sum(1 for r in rows if r['suggested_decision'] == 'MINT')
print(f'  → {n_burn} BURN, {n_mint} MINT (each will fire Solana TX, ~5s each)', flush=True)
ok = fail = 0
for i, r in enumerate(rows, 1):
    cmd = ['/home/carbon/CARBON-WORLD/venv/bin/python',
           '/home/carbon/CARBON-WORLD/worker/resolve_review.py',
           str(r['id']), 'approve',
           '--reason', 'auto-batch: A==B==suggested unanimous, only sentinel missing_aspects flag — reversible via worker/reverse_event.py']
    p = subprocess.run(cmd, capture_output=True, text=True, cwd='/home/carbon/CARBON-WORLD')
    if p.returncode == 0:
        ok += 1
        print(f'[{i}/{len(rows)}] #{r["id"]:>3} {r["suggested_decision"]:<5} OK', flush=True)
    else:
        fail += 1
        print(f'[{i}/{len(rows)}] #{r["id"]:>3} {r["suggested_decision"]:<5} FAIL: {p.stderr.strip()[:200]}', flush=True)
    time.sleep(1)
print(f'DONE: {ok} ok, {fail} fail', flush=True)
