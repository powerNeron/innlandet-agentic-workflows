"""Chrome/Node UI checks with explicit synthetic or authorized local-model mode."""
import argparse
import os
from pathlib import Path
import subprocess
import threading
import time

from hamar_agent.real_sources import create_municipal_service
from hamar_agent.provider_registry import ProviderRegistry
from hamar_agent.web import create_server
from hamar_agent.application import WorkflowService
from hamar_agent.openai_provider import OpenAIConfig


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-local-llm",action="store_true")
    parser.add_argument("--demo",action="store_true",help="Synthetic UI checks only; never reads the municipal catalog or calls a model")
    parser.add_argument("--output",type=Path,required=True,help="New directory for screenshots/downloads")
    parser.add_argument("--chrome",default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    args=parser.parse_args(argv)
    if args.demo == args.enable_local_llm:parser.error("Choose exactly one of --demo or --enable-local-llm")
    args.output.mkdir(exist_ok=False)
    folder=args.output.resolve()
    if args.demo:
        service=WorkflowService()
        registry=ProviderRegistry(ollama_models=lambda: (), openai_config_factory=OpenAIConfig,
                                  sdk_available=lambda: False, include_mock=True)
        def service_factory(provider, model):
            if (provider,model) != ("mock","mock"):
                raise ValueError("Synthetic UI smoke never constructs an inference provider")
            return WorkflowService()
        from types import SimpleNamespace
        from hamar_agent.chat import ChatBackend, ChatOpenAIClient, ChatOllamaClient
        from hamar_agent.ollama_provider import OllamaConfig
        import json
        def chat_client(provider, model):
            if provider == 'openai':
                sdk=SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(
                    output_text='Dette er et syntetisk chatsvar om algoritmer.',output=[],status='completed',error=None)),close=lambda:None)
                return ChatOpenAIClient(OpenAIConfig(model=model,api_key='synthetic-not-a-real-key',enabled=True,
                    privacy_authorized=True),sdk_client=sdk)
            return ChatOllamaClient(OllamaConfig(model=model,num_predict=512),transport=lambda *args:
                json.dumps({'message':{'content':'Dette er et syntetisk lokalt chatsvar.'},'done':True}).encode())
        chat_backend=ChatBackend(choices_factory=lambda provider:[
            {'provider':p,'model':m,'available':True,'label':p+' · syntetisk test','reason':'Kun mock, ingen ekte modell',
             'variant':'local' if p=='ollama' else 'standard','default':p=='ollama'}
            for p,m in (('openai','synthetic-cloud-fixture'),('ollama','synthetic-local-fixture')) if provider in (None,p)],
            client_factory=chat_client,paid_authorized=True,web_authorized=False,openai_dispatch_authorized=lambda:True)
    else:
        chat_backend=None
        service=create_municipal_service([Path("output/municipal-catalog.json")],Path("docs/approved-service-pages.json"),model="llama3.2:3b",timeout=90)
        registry=ProviderRegistry()
        def service_factory(provider, model):
            if provider != "ollama":
                raise ValueError("Browser smoke allows only the local Ollama provider")
            return create_municipal_service([Path("output/municipal-catalog.json")],
                Path("docs/approved-service-pages.json"),model=model,timeout=90,provider=provider)
    server=create_server(port=0,service=service,service_factory=service_factory,
                         provider_registry=registry,chat_backend=chat_backend)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    chrome=None
    browser_env={name:os.environ[name] for name in ('SYSTEMROOT','WINDIR','SYSTEMDRIVE','COMSPEC','PATH','PATHEXT','NUMBER_OF_PROCESSORS') if name in os.environ}
    for name in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP'):
        location=folder/'runtime'/name.lower();location.mkdir(parents=True,exist_ok=True);browser_env[name]=str(location)
    try:
        # Exclusive synthetic profile/log: never attach to a user's browser.
        browser_log=(folder/'chrome-startup.log').open('xb')
        try:
            chrome=subprocess.Popen([args.chrome,"--headless","--disable-gpu","--disable-background-networking","--disable-component-update","--disable-sync","--no-first-run","--no-default-browser-check","--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1","--remote-debugging-address=127.0.0.1","--remote-debugging-port=0","--user-data-dir="+str(folder/"profile"),"about:blank"],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),stdout=browser_log,stderr=subprocess.STDOUT,env=browser_env)
        finally:
            browser_log.close()
        active=folder/"profile"/"DevToolsActivePort"
        for _ in range(100):
            if active.exists() or chrome.poll() is not None:break
            time.sleep(.1)
        if not active.exists():
            raise RuntimeError('Chrome did not reach DevTools; rendering was not tested. See chrome-startup.log. Exit='+str(chrome.poll()))
        port=active.read_text().splitlines()[0]
        driver=Path(__file__).with_name("browser_smoke.cjs").resolve()
        result=subprocess.run(["node",str(driver),port,"http://127.0.0.1:"+str(server.server_port),str(folder),"synthetic" if args.demo else "real"],capture_output=True,text=True,encoding="utf-8",timeout=180,env=browser_env)
        with (folder/"browser-check.txt").open("x",encoding="utf-8") as stream:stream.write(result.stdout+result.stderr)
        print(result.stdout);print(result.stderr)
        return result.returncode
    finally:
        if chrome is not None:
            chrome.terminate()
            try:chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:chrome.kill();chrome.wait(timeout=5)
        server.shutdown();server.server_close()


if __name__=="__main__":raise SystemExit(main())
