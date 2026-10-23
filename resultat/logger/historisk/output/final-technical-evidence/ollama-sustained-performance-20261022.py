"""Sustained low-concurrency local Ollama test; output excludes prompt/answer text."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading
import time

import psutil
from hamar_agent.real_sources import create_municipal_service

service=create_municipal_service([Path("output/municipal-catalog.json")],Path("docs/approved-service-pages.json"),model="llama3.2:3b",timeout=90)
STOP=threading.Event(); SAMPLES=[]; SOURCE="hamar-sfo"

def sample_gpu():
    try:
        v=subprocess.check_output(["nvidia-smi","--query-gpu=utilization.gpu,memory.used,temperature.gpu","--format=csv,noheader,nounits"],text=True,timeout=2).strip().split(",")
        return {"gpu_utilization_pct":int(v[0]),"gpu_vram_mib":int(v[1]),"gpu_temperature_c":int(v[2])}
    except Exception: return {"gpu_metrics":"unavailable"}

def monitor():
    while not STOP.is_set():
        vm=psutil.virtual_memory(); row={"timestamp":datetime.now(timezone.utc).isoformat(),"cpu_pct":psutil.cpu_percent(interval=None),"ram_used_mib":round((vm.total-vm.available)/1048576),"ram_available_mib":round(vm.available/1048576)}
        row.update(sample_gpu()); rss=[]
        for p in psutil.process_iter(["name","memory_info"]):
            try:
                if p.info["name"] and "ollama" in p.info["name"].lower():rss.append(round(p.info["memory_info"].rss/1048576))
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        row["ollama_process_rss_mib"]=sum(rss) if rss else None;SAMPLES.append(row)
        if row.get("gpu_temperature_c",0)>=80 or row.get("gpu_vram_mib",0)>7000 or row["ram_available_mib"]<2048:STOP.set()
        STOP.wait(.5)

def call(i):
    start=time.monotonic()
    try:
        result=service.run(SOURCE)
        ok=bool(result.claims) and not result.verification.has_findings
        return {"id":i,"ok":ok,"outcome":"verified" if ok else "verification_rejected","seconds":round(time.monotonic()-start,3)}
    except Exception as exc:return {"id":i,"ok":False,"outcome":type(exc).__name__,"seconds":round(time.monotonic()-start,3)}

def percentile(xs,p):
    if not xs:return None
    xs=sorted(xs);return round(xs[min(len(xs)-1,int((len(xs)-1)*p))],3)

def main():
    started=time.monotonic(); watcher=threading.Thread(target=monitor,daemon=True);watcher.start();rows=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for wave in range(30):
            if STOP.is_set():break
            batch=[pool.submit(call,wave*2+j) for j in range(2)]
            results=[f.result() for f in batch];rows.extend(results)
            if STOP.is_set() or not all(r["ok"] for r in results):
                STOP.set();break
    STOP.set();watcher.join(timeout=3);duration=round(time.monotonic()-started,3);times=[r["seconds"] for r in rows]
    summary={"recorded_at_utc":datetime.now(timezone.utc).isoformat(),"criteria":"performance-sustained-criteria-20261022.json","model":"llama3.2:3b","source_id":SOURCE,"live_network_or_html":False,"requests_completed":len(rows),"concurrency_cap":2,"duration_seconds":duration,"sustained_60_seconds":duration>=60,"all_60_verified_no_errors":len(rows)==60 and all(r["ok"] for r in rows),"timeouts_or_errors":sum(not r["ok"] for r in rows),"latency_seconds":{"p50":percentile(times,.5),"p95":percentile(times,.95),"p99":percentile(times,.99),"max":max(times) if times else None},"requests":rows,"resource_sample_count":len(SAMPLES),"resource_samples":SAMPLES,"resource_summary":{"peak_cpu_pct":max((x["cpu_pct"] for x in SAMPLES),default=None),"peak_ram_used_mib":max((x["ram_used_mib"] for x in SAMPLES),default=None),"minimum_ram_available_mib":min((x["ram_available_mib"] for x in SAMPLES),default=None),"peak_gpu_utilization_pct":max((x.get("gpu_utilization_pct",0) for x in SAMPLES),default=None),"peak_gpu_vram_mib":max((x.get("gpu_vram_mib",0) for x in SAMPLES),default=None),"peak_gpu_temperature_c":max((x.get("gpu_temperature_c",0) for x in SAMPLES),default=None),"peak_ollama_process_rss_mib":max((x.get("ollama_process_rss_mib") or 0 for x in SAMPLES),default=None)},"limitations":["Single host, one approved source, concurrency two and one local model.","GPU utilization may include unrelated local processes; Ollama process RSS does not include GPU model memory.","This controlled duration is not a production multi-user capacity guarantee."]}
    path=Path("output/final-technical-evidence/ollama-sustained-performance-20261022.json")
    with path.open("x",encoding="utf-8") as f:json.dump(summary,f,ensure_ascii=False,indent=2)
    print(json.dumps({"completed":len(rows),"duration_seconds":duration,"sustained_60_seconds":summary["sustained_60_seconds"],"all_60_verified_no_errors":summary["all_60_verified_no_errors"],"latency":summary["latency_seconds"],"resource_summary":summary["resource_summary"],"evidence":str(path)},ensure_ascii=False))
    return 0 if summary["sustained_60_seconds"] and summary["all_60_verified_no_errors"] and summary["latency_seconds"]["p95"]<=30 else 1

if __name__=="__main__":raise SystemExit(main())
