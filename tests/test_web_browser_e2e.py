"""Real Next.js/browser gateway E2E; all identity and game observations synthetic.

Run after npm run build with DAEDALUS_RUN_WEB_E2E=1. Both mock services bind
loopback; the controller uses a temporary trusted test TLS certificate.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import socket
import ssl
import subprocess
import threading
import time
import urllib.request
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("DAEDALUS_RUN_WEB_E2E") != "1", reason="opt-in synthetic web build E2E")
ROOT = Path(__file__).resolve().parents[1]
USER = {"id": "12345678-1234-4234-8234-123456789abc", "aud": "authenticated", "role": "authenticated", "email": "synthetic@example.invalid", "app_metadata": {}, "user_metadata": {}, "created_at": "2026-01-01T00:00:00Z"}


def jwt():
    def part(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    return part({"alg":"HS256","typ":"JWT"})+"."+part({"sub":USER["id"],"aud":"authenticated","exp":int(time.time())+3600,"role":"authenticated"})+".c3ludGhldGlj"


@pytest.fixture
def web_stack(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    assert (ROOT/"apps/web/.next/BUILD_ID").is_file(), "Build the actual Next.js app first"
    token = secrets.token_urlsafe(40)
    access = jwt()
    counts = Counter()
    state = {"disabled": False, "running": False, "request_id":None, "ambiguous":False}
    accounts = [{"id":name,"player":"Same player","world":world,"enabled":True,"session_status":"authenticated"} for name,world in [("alpha","s1-en"),("beta","s2-en")]]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):
            pass

        def reply(self,value,status=200):
            raw=json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            path=urlsplit(self.path).path
            body=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))) or b"{}")
            if path=="/auth/v1/token":
                if body.get("email")!=USER["email"] or body.get("password")!="fixture-only-password":
                    return self.reply({"message":"Invalid login","code":"invalid_credentials"},400)
                return self.reply({"access_token":access,"refresh_token":"fixture-refresh","expires_in":3600,"token_type":"bearer","user":USER})
            if path=="/auth/v1/logout":
                return self.reply({})
            if self.headers.get("Authorization")!="Bearer "+token:
                return self.reply({},401)
            counts["POST "+path]+=1
            if path=="/api/v1/accounts/alpha/tasks":
                state["request_id"]=body.get("request_id")
                if state["ambiguous"]:return self.reply({"detail":"Fixture response lost"},503)
                state["running"]=True
                return self.reply({"account_id":"alpha","task":body.get("task"),"request_id":state["request_id"],"task_id":"a"*24,"pid":123,"status":"started"})
            if path=="/api/v1/accounts/alpha/tasks/"+"a"*24+"/stop":
                state["running"]=False
                return self.reply({"status":"stopped"})
            return self.reply({},404)

        def do_GET(self):
            path=urlsplit(self.path).path
            if path=="/auth/v1/user":
                return self.reply(USER if self.headers.get("Authorization")=="Bearer "+access else {},200 if self.headers.get("Authorization")=="Bearer "+access else 401)
            if path=="/rest/v1/web_operators":
                return self.reply(None if state["disabled"] else {"role":"owner"})
            if self.headers.get("Authorization")!="Bearer "+token:
                return self.reply({},401)
            counts[path]+=1
            if path=="/api/v1/accounts":return self.reply({"accounts":accounts})
            if path=="/api/v1/health":return self.reply({"mode":"task_control_opt_in","version":"0.1.0b1"})
            if path=="/api/v1/capabilities":return self.reply({"operations":[{"name":"alertAttacks","workflow":{"web":"native"}}]})
            if path.startswith("/api/v1/warehouses/"):
                aid=path.split("/")[-1];is_a=aid=="alpha"
                return self.reply({"account_id":aid,"cities":[{"account_id":aid,"city_id":1 if is_a else 2,"city_name":"Athens" if is_a else "Sparta","island":"12:34","resources":{"unsecured":{"wood":300000 if is_a else 10,"wine":0,"marble":0,"glass":0,"sulfur":0},"capacity":500000}}]})
            if path.endswith("/military"):
                aid=path.split("/")[-2]
                return self.reply({"account_id":aid,"observed_at":int(time.time()),"cities":[{"city_id":1,"city_name":"Athens" if aid=="alpha" else "Sparta","troops":[{"unit":"Synthetic Swordsman","amount":17}],"fleet":[{"unit":"Synthetic Ship","amount":3}]}]})
            if path.endswith("/cities"):return self.reply({"cities":[{"city_id":1,"city_name":"Athens"}]})
            if path.endswith("/preflight"):
                return self.reply({"account_id":path.split("/")[-3],"task":parse_qs(urlsplit(self.path).query).get("task",[""])[0],"ready":True,"reason":"Fixture ready","unresolved_request":False})
            if path.endswith("/activity"):
                aid=path.split("/")[-2]
                events=[{"task":"alertAttacks","request_id":state["request_id"],"status":"unconfirmed" if state["ambiguous"] else "started","created_at":1000,"updated_at":1001}] if aid=="alpha" and state["request_id"] else []
                return self.reply({"account_id":aid,"events":events,"next_before":None})
            if path.endswith("/tasks"):
                aid=path.split("/")[-2];running=state["running"] and aid=="alpha"
                return self.reply({"account_id":aid,"engine_tasks":[{"task":"alertAttacks","task_id":"a"*24,"status":"running"}] if running else [],"requests":[]})
            return self.reply({},404)

    auth=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    backend=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    cert,key=tmp_path/"cert.pem",tmp_path/"key.pem"
    subprocess.run(["openssl","req","-x509","-newkey","rsa:2048","-nodes","-days","1","-subj","/CN=localhost","-addext","subjectAltName=IP:127.0.0.1,DNS:localhost","-keyout",str(key),"-out",str(cert)],check=True,capture_output=True)
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cert,key)
    backend.socket=tls.wrap_socket(backend.socket,server_side=True)
    for server in (auth,backend):threading.Thread(target=server.serve_forever,daemon=True).start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    origin=f"http://localhost:{port}"
    env={"PATH":os.environ["PATH"],"HOME":str(tmp_path),"NODE_EXTRA_CA_CERTS":str(cert),"SUPABASE_URL":f"http://127.0.0.1:{auth.server_port}","SUPABASE_PUBLISHABLE_KEY":"fixture-public-key","DAEDALUS_API_BASE_URL":f"https://127.0.0.1:{backend.server_port}","DAEDALUS_API_TOKEN":token,"NEXT_TELEMETRY_DISABLED":"1"}
    # No inherited production environment, no external endpoints.
    log=tmp_path/"next.log"
    with log.open("wb") as out:
        process=subprocess.Popen(["node","node_modules/next/dist/bin/next","start","-H","127.0.0.1","-p",str(port)],cwd=ROOT/"apps/web",env=env,stdout=out,stderr=out)
        try:
            deadline=time.monotonic()+25
            while time.monotonic()<deadline:
                try:
                    with urllib.request.urlopen(origin+"/login",timeout=1):break
                except OSError:time.sleep(.2)
            else:pytest.fail("Synthetic Next.js server failed to start")
            with playwright.sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True)
                context=browser.new_context(locale="en-US",viewport={"width":1280,"height":800},accept_downloads=True)
                context.route("**/*",lambda route:route.continue_() if route.request.url.startswith(origin+"/") else route.abort())
                yield context,origin,counts,state
                browser.close()
        finally:
            process.terminate();process.wait(timeout=10)
            for server in (auth,backend):server.shutdown();server.server_close()


def test_authenticated_dashboard_browser(web_stack):
    context,origin,counts,state=web_stack
    assert context.request.get(origin+"/api/controller/accounts").status==401
    page=context.new_page();page.set_default_timeout(10_000);page.goto(origin+"/login")
    page.get_by_label("Email address").fill(USER["email"])
    page.get_by_label("Password",exact=True).fill("fixture-only-password")
    page.get_by_role("button",name="Sign in securely").click()
    page.get_by_role("heading",name="Overview",exact=True).wait_for()
    session=[cookie for cookie in context.cookies() if cookie["name"].startswith("sb-")]
    assert session and all(cookie["httpOnly"] and cookie["sameSite"]=="Lax" for cookie in session)
    nav=page.get_by_role("navigation",name="Main navigation")
    nav.get_by_role("button",name="Warehouses").click()
    page.get_by_role("cell",name="Athens").wait_for()
    page.get_by_role("cell",name="Sparta").wait_for()
    wood=page.get_by_role("columnheader",name="Wood",exact=True)
    sort=wood.get_by_role("button")
    sort.focus();page.keyboard.press("Enter")
    assert wood.get_attribute("aria-sort")=="descending"
    assert page.locator(".warehouse-data-table tbody tr").first.get_by_role("cell",name="Athens").count()==1
    page.keyboard.press("Enter")
    assert wood.get_attribute("aria-sort")=="ascending"
    assert page.locator(".warehouse-data-table tbody tr").first.get_by_role("cell",name="Sparta").count()==1
    assert page.evaluate("document.activeElement.matches(':focus-visible')")
    baseline=sum(n for path,n in counts.items() if "/warehouses/" in path)
    page.get_by_label("Search warehouses").fill("Athens")
    page.get_by_role("cell",name="Sparta").wait_for(state="detached")
    page.get_by_role("button",name="Reset filters").click()
    page.get_by_role("cell",name="Sparta").wait_for()
    page.get_by_label("Resource",exact=True).select_option("wood")
    page.get_by_label("Minimum unsecured stock").fill("1000")
    page.get_by_role("cell",name="Sparta").wait_for(state="detached")
    with page.expect_download() as download:
        page.get_by_label("Export report").select_option("csv")
    content=Path(download.value.path()).read_text();assert "Athens" in content and "Sparta" not in content
    nav.get_by_role("button",name="Military").click()
    page.get_by_role("cell",name="Synthetic Swordsman").first.wait_for()
    page.get_by_role("cell",name="Synthetic Ship").last.wait_for()
    assert page.get_by_role("cell",name="Synthetic Ship").count()==2
    assert page.get_by_text("See controller details").count()==0
    nav.get_by_role("button",name="Warehouses").click()
    page.get_by_role("cell",name="Athens").wait_for()
    assert sum(n for path,n in counts.items() if "/warehouses/" in path)==baseline
    page.reload();page.get_by_role("heading",name="Warehouses",exact=True).wait_for()
    page.get_by_role("cell",name="Athens").wait_for()
    # Verify selected-account scope is keyed by IDs even with duplicate display names.
    page.get_by_role("button",name="One",exact=True).click()
    page.get_by_label("Choose single account").select_option("beta")
    page.get_by_role("cell",name="Sparta").wait_for()
    page.get_by_role("cell",name="Athens").wait_for(state="detached")
    page.get_by_role("button",name="Selected",exact=True).click()
    picker=page.locator(".selected-picker").get_by_role("checkbox")
    assert picker.count()==2
    picker.first.check()
    page.get_by_role("cell",name="Athens").wait_for()
    page.get_by_role("cell",name="Sparta").wait_for()
    page.get_by_role("button",name="All accounts",exact=True).click()
    page.get_by_role("cell",name="Athens").wait_for()
    # Basic responsive navigation and language/appearance behavior.
    page.get_by_role("button",name="Switch appearance").click()
    assert page.locator(".app-shell.theme-dark").count()==1
    page.get_by_label("Language").select_option("ru")
    assert page.locator("html").get_attribute("lang")=="ru"
    page.get_by_label("Язык").select_option("en")
    page.emulate_media(reduced_motion="reduce",contrast="more")
    assert page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
    assert page.evaluate("getComputedStyle(document.querySelector('.scope-row')).transitionDuration") in ("0s", "0s, 0s")
    assert page.evaluate("getComputedStyle(document.querySelector('.scope-row')).borderTopWidth")=="2px"
    page.set_viewport_size({"width":390,"height":844})
    page.get_by_role("button",name="Open navigation").click()
    nav.get_by_role("button",name="Overview").click()
    page.get_by_role("heading",name="Overview",exact=True).wait_for()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.set_viewport_size({"width":1280,"height":800})
    nav.get_by_role("button",name="Automations").click()
    page.get_by_role("button",name="Alert Attacks",exact=False).click()
    page.get_by_role("button",name="Review settings").click()
    page.get_by_label("I approve starting this automation").check()
    page.get_by_role("button",name="Start automation").click()
    page.get_by_text("Task launch confirmed. See Activity for execution status.").wait_for()
    assert counts["POST /api/v1/accounts/alpha/tasks"]==1 and state["running"]
    nav.get_by_role("button",name="Activity").click()
    stop=page.get_by_role("button",name="Stop",exact=True)
    stop.wait_for();page.once("dialog",lambda dialog:dialog.accept());stop.click()
    stop.wait_for(state="detached");assert not state["running"]
    assert counts["POST /api/v1/accounts/alpha/tasks/"+"a"*24+"/stop"]==1
    # Lost reply may not be retried or rendered as success.
    state["ambiguous"]=True
    nav.get_by_role("button",name="Automations").click()
    page.get_by_role("button",name="Alert Attacks",exact=False).click()
    page.get_by_role("button",name="Review settings").click()
    page.get_by_label("I approve starting this automation").check()
    page.get_by_role("button",name="Start automation").click()
    page.get_by_text("Launch not confirmed. Check Activity and existing tasks before retrying.").wait_for()
    assert page.get_by_role("button",name="Start automation").is_disabled()
    assert counts["POST /api/v1/accounts/alpha/tasks"]==2
    state["disabled"]=True
    assert context.request.get(origin+"/api/controller/accounts").status==401
