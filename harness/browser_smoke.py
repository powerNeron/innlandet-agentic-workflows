"""Opt-in Chrome/Node UI check against real local Ollama and reviewed catalog."""
import argparse
from pathlib import Path
import subprocess
import threading
import time

from hamar_agent.real_sources import create_municipal_service
from hamar_agent.provider_registry import ProviderRegistry
from hamar_agent.web import create_server


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-local-llm",action="store_true")
    parser.add_argument("--output",type=Path,required=True,help="New directory for screenshots/downloads")
    parser.add_argument("--chrome",default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    args=parser.parse_args(argv)
    if not args.enable_local_llm:parser.error("Explicit --enable-local-llm required")
    args.output.mkdir(exist_ok=False)
    folder=args.output.resolve()
    service=create_municipal_service([Path("output/municipal-catalog.json")],Path("docs/approved-service-pages.json"),model="llama3.2:3b",timeout=90)
    def service_factory(provider, model):
        if provider != "ollama":
            raise ValueError("Browser smoke allows only the local Ollama provider")
        return create_municipal_service([Path("output/municipal-catalog.json")],
            Path("docs/approved-service-pages.json"),model=model,timeout=90,provider=provider)
    server=create_server(port=0,service=service,service_factory=service_factory,
                         provider_registry=ProviderRegistry())
    threading.Thread(target=server.serve_forever,daemon=True).start()
    chrome=None
    try:
        chrome=subprocess.Popen([args.chrome,"--headless","--disable-gpu","--disable-background-networking","--disable-component-update","--disable-sync","--no-first-run","--no-default-browser-check","--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1","--remote-debugging-address=127.0.0.1","--remote-debugging-port=0","--user-data-dir="+str(folder/"profile"),"about:blank"],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        active=folder/"profile"/"DevToolsActivePort"
        for _ in range(100):
            if active.exists():break
            time.sleep(.1)
        port=active.read_text().splitlines()[0]
        driver=Path(__file__).with_name("browser_smoke.cjs").resolve()
        result=subprocess.run(["node",str(driver),port,"http://127.0.0.1:"+str(server.server_port),str(folder)],capture_output=True,text=True,encoding="utf-8",timeout=55)
        with (folder/"browser-check.txt").open("x",encoding="utf-8") as stream:stream.write(result.stdout+result.stderr)
        print(result.stdout);print(result.stderr)
        return result.returncode
    finally:
        if chrome is not None:chrome.terminate()
        server.shutdown();server.server_close()


if __name__=="__main__":raise SystemExit(main())
