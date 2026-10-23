"""Bounded local Ollama workflow load test; stores metrics only."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import subprocess
import threading
import time
from pathlib import Path

import psutil
from hamar_agent.real_sources import create_municipal_service

service = create_municipal_service([Path("output/municipal-catalog.json")], Path("docs/approved-service-pages.json"), model="llama3.2:3b", timeout=90)
SOURCE = "hamar-sfo"
STOP = threading.Event()
SAMPLES = []

def gpu_sample():
    try:
        raw = subprocess.check_output(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,temperature.gpu", "--format=csv,noheader,nounits"], text=True, timeout=2).strip().split(",")
        return {"gpu_utilization_pct": int(raw[0].strip()), "gpu_vram_used_mib": int(raw[1].strip()), "gpu_temperature_c": int(raw[2].strip())}
    except Exception:
        return {"gpu_metrics": "unavailable"}

def sample_resources():
    while not STOP.is_set():
        vm = psutil.virtual_memory()
        sample = {"timestamp": datetime.now(timezone.utc).isoformat(), "cpu_percent": psutil.cpu_percent(interval=None),
                  "ram_used_mib": round((vm.total-vm.available)/1048576), "ram_available_mib": round(vm.available/1048576)}
        sample.update(gpu_sample())
        ollama = []
        for proc in psutil.process_iter(["name", "memory_info"]):
            try:
                if proc.info["name"] and "ollama" in proc.info["name"].lower():
                    ollama.append(round(proc.info["memory_info"].rss/1048576))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        sample["ollama_process_rss_mib"] = sum(ollama) if ollama else None
        SAMPLES.append(sample)
        if sample.get("gpu_temperature_c", 0) >= 80 or sample.get("gpu_vram_used_mib", 0) > 7000 or sample["ram_available_mib"] < 2048:
            STOP.set()
        STOP.wait(0.5)

def one(index):
    started = time.monotonic()
    try:
        result = service.run(SOURCE)
        if result.verification.has_findings or not result.claims:
            return {"index": index, "ok": False, "kind": "verification" , "seconds": round(time.monotonic()-started, 3)}
        return {"index": index, "ok": True, "kind": "verified", "seconds": round(time.monotonic()-started, 3)}
    except Exception as exc:
        return {"index": index, "ok": False, "kind": type(exc).__name__, "seconds": round(time.monotonic()-started, 3)}

def percentile(values, p):
    if not values: return None
    values=sorted(values); return round(values[min(len(values)-1, int((len(values)-1)*p))], 3)

def main():
    watcher=threading.Thread(target=sample_resources, daemon=True); watcher.start()
    rows=[]
    for i in range(4):
        row=one(i); rows.append({**row,"batch":"sequential"})
        if not row["ok"] or STOP.is_set(): break
    if len(rows)==4 and all(r["ok"] for r in rows) and not STOP.is_set():
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(one,i+4) for i in range(8)]
            for future in as_completed(futures):
                rows.append({**future.result(),"batch":"concurrent-2"})
                if STOP.is_set(): break
    STOP.set(); watcher.join(timeout=3)
    times=[r["seconds"] for r in rows]
    output={"date":datetime.now(timezone.utc).isoformat(),"model":"llama3.2:3b","source_id":SOURCE,
            "live_network_or_html":False,"sequential_planned":4,"concurrent_planned":8,"max_concurrency":2,
            "requests_completed":len(rows),"all_verified_no_errors":len(rows)==12 and all(r["ok"] for r in rows),
            "latency_seconds":{"p50":percentile(times,.50),"p95":percentile(times,.95),"p99":percentile(times,.99),"max":max(times) if times else None},
            "requests":rows,"resource_samples":SAMPLES,
            "resource_summary":{"sample_count":len(SAMPLES),"peak_cpu_pct":max((s["cpu_percent"] for s in SAMPLES),default=None),
             "peak_ram_used_mib":max((s["ram_used_mib"] for s in SAMPLES),default=None),"min_ram_available_mib":min((s["ram_available_mib"] for s in SAMPLES),default=None),
             "peak_gpu_utilization_pct":max((s.get("gpu_utilization_pct",0) for s in SAMPLES),default=None),"peak_gpu_vram_mib":max((s.get("gpu_vram_used_mib",0) for s in SAMPLES),default=None),
             "peak_gpu_temperature_c":max((s.get("gpu_temperature_c",0) for s in SAMPLES),default=None),"peak_ollama_process_rss_mib":max((s.get("ollama_process_rss_mib") or 0 for s in SAMPLES),default=None)},
            "limitations":["Small 12-request sample; p95/p99 are descriptive only.","Shared NVIDIA activity may include unrelated local processes.","A request in flight is allowed to finish if a safety bound is crossed; no further requests are submitted."]}
    path=Path("output/final-technical-evidence/ollama-performance-20261022.json")
    with path.open("x",encoding="utf-8") as f: json.dump(output,f,ensure_ascii=False,indent=2)
    print(json.dumps({"completed":len(rows),"all_verified_no_errors":output["all_verified_no_errors"],"latency":output["latency_seconds"],"resource_summary":output["resource_summary"],"evidence":str(path)},ensure_ascii=False))
    return 0 if output["all_verified_no_errors"] else 1

if __name__=="__main__": raise SystemExit(main())
