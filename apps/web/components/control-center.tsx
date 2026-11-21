"use client";
import Image from "next/image";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, ArrowDownToLine, ArrowRight, Bell, Building2, CheckCircle2, ChevronDown,
  ChevronRight, CircleAlert, CircleHelp, ClipboardList, CloudOff, Compass,
  Download, Filter, Globe2, Landmark, Layers3, LayoutDashboard, LockKeyhole,
  LogOut, Menu, Moon, MoreHorizontal, Printer, RefreshCw, Search, Settings2,
  ShieldCheck, Ship, Sun, UsersRound, Warehouse, Workflow, X
} from "lucide-react";

type Account = { id: string; email?: string | null; world?: string; player?: string; name?: string; enabled?: boolean; session_status?: string; synthetic?: boolean };
type WarehouseCity = {
  account_id: string; city_id: number; city_name: string; island?: string | null; captured_at?: string;
  resources: { unsecured: Record<string, number | null>; total?: Record<string, number | null>; capacity?: number | null }
};
type WarehouseResult = { account_id: string; cities: WarehouseCity[]; synthetic_demo?: boolean };
type Page = "overview" | "accounts" | "warehouses" | "automations" | "military" | "activity" | "settings";
type Result = Record<string, unknown>;
const NAV: { id: Page; title: string; icon: typeof LayoutDashboard; subtitle: string }[] = [
  { id: "overview", title: "Overview", icon: LayoutDashboard, subtitle: "Your workspace at a glance" },
  { id: "accounts", title: "Accounts", icon: UsersRound, subtitle: "Players, worlds and sessions" },
  { id: "warehouses", title: "Warehouses", icon: Warehouse, subtitle: "One combined report across your accounts" },
  { id: "automations", title: "Automations", icon: Workflow, subtitle: "Supported game operations" },
  { id: "military", title: "Military", icon: ShieldCheck, subtitle: "Troops, fleets and movements" },
  { id: "activity", title: "Activity", icon: Activity, subtitle: "Tasks, receipts and reconciliation" },
  { id: "settings", title: "Settings", icon: Settings2, subtitle: "Preferences, access and connection" }
];
const RESOURCES = ["wood", "wine", "marble", "glass", "sulfur"] as const;
type Resource = (typeof RESOURCES)[number];
// Native Ikariam top-bar sprite dimensions, not the larger island-resource paintings.
const RESOURCE_ICON_SIZE: Record<Resource, {width: number; height: number}> = {
  wood: {width: 25, height: 20},
  wine: {width: 24, height: 20},
  marble: {width: 25, height: 19},
  glass: {width: 23, height: 18},
  sulfur: {width: 25, height: 19},
};
function ResourceIcon({resource, small = false}: {resource: Resource; small?: boolean}) {
  return <Image
    src={`/ikariam-resources/${resource}.webp`}
    alt=""
    aria-hidden="true"
    width={RESOURCE_ICON_SIZE[resource].width}
    height={RESOURCE_ICON_SIZE[resource].height}
    className={small ? "resource-image resource-image-small" : "resource-image"}
    unoptimized
  />;
}

const TASK_GROUPS = [
  { name: "City & research", icon: Building2, tasks: ["constructionList", "research", "tavernManager", "loginDaily", "activateMiracle", "activateShrine"] },
  { name: "Resources & trade", icon: Layers3, tasks: ["sendResources", "resourceTransportManager", "consolidateResources", "distributeResources", "buyResources", "sellResources", "donationBot"] },
  { name: "Military & missions", icon: Ship, tasks: ["trainArmy", "UpgradeUnits", "autoPirate"] },
  { name: "Alerts & exploration", icon: Compass, tasks: ["alertAttacks", "alertLowWine", "searchForIslandSpaces"] },
  { name: "System & advanced", icon: Settings2, tasks: ["dumpWorld", "viewArmy", "shipMovements"] }
];
const INVENTORIES: Record<string, { resource: string; scope: "account" | "city"; title: string }> = {
  research: {resource: "academies", scope: "account", title: "Academy research & cooldowns"},
  tavernManager: {resource: "taverns", scope: "account", title: "City taverns & wine"},
  activateMiracle: {resource: "miracles", scope: "account", title: "Miracles & cooldowns"},
  activateShrine: {resource: "shrine-status", scope: "account", title: "Shrine status"},
  autoPirate: {resource: "pirate-fortresses", scope: "account", title: "Pirate fortresses"},
  trainArmy: {resource: "trainable-units", scope: "city", title: "Trainable units"},
  UpgradeUnits: {resource: "workshop-upgrades", scope: "city", title: "Workshop upgrades"},
  buyResources: {resource: "market-quotes", scope: "city", title: "Market offers"},
  sellResources: {resource: "market-quotes", scope: "city", title: "Market offers"},
  viewArmy: {resource: "military", scope: "account", title: "Military inventory"},
  shipMovements: {resource: "ship-movements", scope: "account", title: "Ship movements"}
};
const format = (n: number | null | undefined) => typeof n === "number" ? new Intl.NumberFormat("en-US").format(n) : "—";
function name(a: Account) { return a.email || a.name || a.player || a.id; }
function readable(text: string) { return text.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]/g, " ").replace(/\b\w/g, c => c.toUpperCase()); }
function isConnected(a: Account) { return a.session_status === "authenticated"; }
function accountWorld(a: Account) { return a.world || "Unknown world"; }
function safeCsv(value: unknown) { const str=String(value??""); const protectedValue=/^[=+@-]/.test(str)?"'"+str:str;return '"'+protectedValue.replace(/"/g,'""')+'"'; }
async function controller<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api/controller/" + path, { ...init, cache: "no-store", headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers } });
  if (!response.ok) {
    const details = await response.json().catch(() => ({}));
    throw new Error(details.error || "Unable to load this resource");
  }
  return await response.json() as T;
}
function download(filename: string, contents: string, mime: string) {
  const url = URL.createObjectURL(new Blob([contents], { type: mime }));
  const element = document.createElement("a"); element.href = url; element.download = filename; element.click();
  setTimeout(() => URL.revokeObjectURL(url), 400);
}
function Status({ ok, label }: { ok: boolean | null; label: string }) {
  return <span className={"status " + (ok === true ? "status-ok" : ok === false ? "status-error" : "status-neutral")}>
    <span className="status-dot" /> {label}
  </span>;
}
function Empty({ title, description, icon: Icon = CircleHelp }: { title: string; description: string; icon?: typeof CircleHelp }) {
  return <div className="empty-state"><div className="empty-glyph"><Icon size={24}/></div><strong>{title}</strong><p>{description}</p></div>;
}
function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return <Empty title="No observed records" description="The backend has not returned any items for this view." />;
  const keys = Array.from(new Set(rows.flatMap(r=>Object.keys(r)))).filter(k=>!["account_id","raw","cookie","token"].includes(k)).slice(0,10);
  return <div className="table-scroll"><table><thead><tr>{keys.map(k=><th key={k}>{readable(k)}</th>)}</tr></thead><tbody>
    {rows.map((row,i)=><tr key={i}>{keys.map(k=><td key={k}>{typeof row[k]==="object" && row[k]!==null ? "Details available in controller" : String(row[k] ?? "—")}</td>)}</tr>)}
  </tbody></table></div>;
}

function InventoryDetails({ data }: { data: Result }) {
  const entries = Object.entries(data).filter(([key]) => !["account_id", "raw", "cookie", "token", "synthetic_demo"].includes(key));
  return <div>{entries.map(([key, value]) => <div key={key} className="military-group">
    <strong className="table-label">{readable(key)}</strong>
    {Array.isArray(value) ? <DataTable rows={value.filter(x => x && typeof x === "object") as Record<string, unknown>[]} />
      : value && typeof value === "object" ? <DataTable rows={Object.entries(value).map(([name, v]) => ({name, value: typeof v === "object" ? "See controller details" : v}))} />
      : <div className="key-value"><span>{readable(key)}</span><strong>{String(value ?? "Unknown")}</strong></div>}
  </div>)}</div>;
}

export function ControlCenter({ email, role }: { email: string; role: string }) {
  const [page, setPage] = useState<Page>("overview");
  const [sidebar, setSidebar] = useState(false);
  const [theme, setTheme] = useState<"light"|"dark">("light");
  const [search, setSearch] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [health, setHealth] = useState<Result | null>(null);
  const [capabilities, setCapabilities] = useState<Result | null>(null);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(true);
  const [reload, setReload] = useState(0);
  const [scope, setScope] = useState<"all" | "selected" | "one">("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [warehouseMap, setWarehouseMap] = useState<Record<string, WarehouseResult>>({});
  const [warehouseErrors, setWarehouseErrors] = useState<Record<string,string>>({});
  const [reportLoading, setReportLoading] = useState(false);
  const [onlyLarge, setOnlyLarge] = useState(false);
  const [accountQuery, setAccountQuery] = useState("");
  const [militaryData, setMilitaryData] = useState<Record<string,Result>>({});
  const [militaryErrors, setMilitaryErrors] = useState<Record<string,string>>({});
  const [militaryTab, setMilitaryTab] = useState<"troops"|"movements">("troops");
  const [taskData, setTaskData] = useState<Record<string,Result>>({});
  const [taskErrors, setTaskErrors] = useState<Record<string,string>>({});
  const [pendingAction, setPendingAction] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [automationGroup, setAutomationGroup] = useState("All");
  const [chosenTask, setChosenTask] = useState("constructionList");
  const [automationAccount, setAutomationAccount] = useState("");
  const [cities, setCities] = useState<Record<string,unknown>[]>([]);
  const [selectedCity, setSelectedCity] = useState("");
  const [buildings, setBuildings] = useState<Record<string,unknown>[]>([]);
  const [buildingPosition, setBuildingPosition] = useState("");
  const [targetLevel, setTargetLevel] = useState(1);
  const [preview, setPreview] = useState<Result | null>(null);
  const [automationError, setAutomationError] = useState("");
  const [preflight, setPreflight] = useState<Result | null>(null);
  const [automationBusy, setAutomationBusy] = useState(false);
  const [inventory, setInventory] = useState<Result | null>(null);
  const [inventoryBusy, setInventoryBusy] = useState(false);
  const [inventoryError, setInventoryError] = useState("");
  const [marketResource, setMarketResource] = useState(0);
  const [marketSide, setMarketSide] = useState("buy");

  useEffect(() => {
    try { const stored = localStorage.getItem("daedalus-appearance"); if (stored === "dark") setTheme("dark"); } catch {}
  }, []);
  useEffect(() => { try { localStorage.setItem("daedalus-appearance", theme); } catch {} }, [theme]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {e.preventDefault();searchRef.current?.focus();} };
    window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key);
  }, []);

  useEffect(() => {
    let alive = true;setBusy(true);setLoadError("");
    Promise.allSettled([controller<{accounts:Account[]}>("accounts"), controller<Result>("health"), controller<Result>("capabilities")]).then(results => {
      if(!alive)return;
      if(results[0].status==="fulfilled") setAccounts(results[0].value.accounts ?? []);
      else setLoadError(results[0].reason instanceof Error ? results[0].reason.message : "Backend unavailable");
      setHealth(results[1].status==="fulfilled"?results[1].value:null);
      setCapabilities(results[2].status==="fulfilled"?results[2].value:null);
      setBusy(false);
    });
    return ()=>{alive=false};
  }, [reload]);

  const scopeIds = useMemo(() => {
    const ids=accounts.map(a=>a.id);
    if(scope==="all")return ids;
    if(scope==="selected")return ids.filter(id=>selected.includes(id));
    return selected[0] && ids.includes(selected[0]) ? [selected[0]] : ids.slice(0,1);
  },[accounts,scope,selected]);
  const scopeKey=scopeIds.join("|");
  const filteredAccounts=useMemo(()=>accounts.filter(a=>(name(a)+" "+accountWorld(a)+" "+(a.player||"")).toLowerCase().includes(accountQuery.toLowerCase())),[accounts,accountQuery]);

  useEffect(() => {
    if(page!=="warehouses")return;
    let live=true;setReportLoading(true);
    Promise.allSettled(scopeIds.map(id=>controller<WarehouseResult>("warehouses/"+encodeURIComponent(id)))).then(results=>{
      if(!live)return;
      const data:Record<string,WarehouseResult>={}, errors:Record<string,string>={};
      results.forEach((r,i)=>{const id=scopeIds[i];if(r.status==="fulfilled")data[id]=r.value;else errors[id]=r.reason instanceof Error?r.reason.message:"Unavailable";});
      setWarehouseMap(data);setWarehouseErrors(errors);setReportLoading(false);
    });
    return ()=>{live=false};
  // scopeKey is stable only when selected identity changes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[page,scopeKey,reload]);

  useEffect(() => {
    if(page!=="military"&&page!=="activity")return;
    let live=true;
    const resource=page==="military"?(militaryTab==="troops"?"military":"ship-movements"):"tasks";
    Promise.allSettled(scopeIds.map(id=>controller<Result>("accounts/"+encodeURIComponent(id)+"/"+resource))).then(results=>{
      if(!live)return;
      const data:Record<string,Result>={}, errors:Record<string,string>={};
      results.forEach((r,i)=>{if(r.status==="fulfilled")data[scopeIds[i]]=r.value;else errors[scopeIds[i]]=r.reason instanceof Error?r.reason.message:"Unavailable";});
      if(page==="activity"){setTaskData(data);setTaskErrors(errors);}
      else {setMilitaryData(data);setMilitaryErrors(errors);}
    });
    return ()=>{live=false};
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[page,scopeKey,militaryTab,reload]);

  useEffect(()=>{
    if(page!=="automations")return;
    const id=automationAccount || scopeIds[0] || "";
    if(!automationAccount && id)setAutomationAccount(id);
    setSelectedCity("");setCities([]);setPreview(null);setPreflight(null);setAutomationError("");
    if(!id)return;
    let live=true;
    Promise.allSettled([
      controller<{cities:Record<string,unknown>[]}>("accounts/"+encodeURIComponent(id)+"/cities"),
      controller<Result>("accounts/"+encodeURIComponent(id)+"/tasks/preflight?task="+encodeURIComponent(chosenTask))
    ]).then(results=>{
      if(!live)return;
      if(results[0].status==="fulfilled")setCities(results[0].value.cities??[]);
      else setAutomationError("Cities could not be loaded from the authenticated worker.");
      if(results[1].status==="fulfilled")setPreflight(results[1].value);
    });
    return ()=>{live=false};
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[page,chosenTask,automationAccount,reload]);

  useEffect(()=>{
    if(page!=="automations" || !selectedCity || !automationAccount || chosenTask!=="constructionList") {setBuildings([]);return;}
    let live=true;setBuildingPosition("");setPreview(null);
    controller<{buildings:Record<string,unknown>[]}>("accounts/"+encodeURIComponent(automationAccount)+"/cities/"+encodeURIComponent(selectedCity)+"/buildings")
      .then(r=>{if(live)setBuildings(r.buildings??[])}).catch(()=>{if(live)setBuildings([])});
    return ()=>{live=false};
  },[page,selectedCity,automationAccount,chosenTask,reload]);

  useEffect(() => {
    const observation = INVENTORIES[chosenTask];
    if (page !== "automations" || !observation || !automationAccount || (observation.scope === "city" && !selectedCity)) {
      setInventory(null); setInventoryBusy(false); setInventoryError(""); return;
    }
    let live = true;
    setInventoryBusy(true); setInventoryError(""); setInventory(null);
    const url = "accounts/" + encodeURIComponent(automationAccount)
      + (observation.scope === "city" ? "/cities/" + encodeURIComponent(selectedCity) : "")
      + "/" + observation.resource
      + (observation.resource === "market-quotes" ? "?resource_type=" + marketResource + "&side=" + encodeURIComponent(marketSide) : "");
    controller<Result>(url).then(data => {if (live) setInventory(data);})
      .catch(error => {if (live) setInventoryError(error instanceof Error ? error.message : "Current inventory unavailable");})
      .finally(() => {if (live) setInventoryBusy(false);});
    return () => {live = false;};
  }, [page, chosenTask, automationAccount, selectedCity, marketResource, marketSide, reload]);

  const accountById=useMemo(()=>Object.fromEntries(accounts.map(a=>[a.id,a])) as Record<string,Account>,[accounts]);
  const rows=useMemo(()=>scopeIds.flatMap(id=>(warehouseMap[id]?.cities??[])),[scopeKey,warehouseMap]);
  const displayedRows=rows.filter(c=>{
    if (!onlyLarge) return true;
    const vals=RESOURCES.map(r=>c.resources?.unsecured?.[r]);
    return vals.some(v => v===null||v===undefined) || vals.reduce<number>((sum,v)=>sum+(typeof v==="number"?v:0),0)>=220000;
  });
  // Stable totals use exact observed numeric fields; an unknown field remains visually unknown.
  const resourceTotals=Object.fromEntries(RESOURCES.map(k=>[k,{value:rows.reduce((sum,c)=>sum+(c.resources?.unsecured?.[k]??0),0),complete:rows.every(c=>typeof c.resources?.unsecured?.[k]==="number") && Object.keys(warehouseErrors).length===0}])) as Record<(typeof RESOURCES)[number], {value:number;complete:boolean}>;
  const countConnected=accounts.filter(isConnected).length;
  const errorCount=Object.keys(warehouseErrors).length;
  const pageInfo=NAV.find(n=>n.id===page)!;
  const refresh=()=>setReload(v=>v+1);
  const go=(target:Page)=>{setPage(target);setSearch("");setSidebar(false);setActionMessage("");};
  const exportRows=(kind:"csv"|"json"|"txt")=>{
    const cols=displayedRows.map(city=>({
      account:name(accountById[city.account_id]||{id:city.account_id}),world:accountWorld(accountById[city.account_id]||{id:city.account_id}),
      island:city.island||"—",city:city.city_name,city_id:city.city_id,
      ...Object.fromEntries(RESOURCES.map(r=>[r,city.resources?.unsecured?.[r]??null])),
      captured_at:city.captured_at||null
    }));
    if(kind==="json")download("daedalus-warehouses.json",JSON.stringify({rows:cols,unavailable_accounts:Object.keys(warehouseErrors)},null,2),"application/json");
    if(kind==="csv"){const keys=["account","world","island","city","city_id",...RESOURCES,"captured_at"];download("daedalus-warehouses.csv",keys.join(",")+"\n"+cols.map(r=>keys.map(k=>safeCsv(r[k as keyof typeof r])).join(",")).join("\n"),"text/csv");}
    if(kind==="txt")download("daedalus-warehouses.txt",cols.map(r=>[r.account,r.world,r.island,r.city,...RESOURCES.map(k=>readable(k)+": "+(r[k as keyof typeof r]??"Unknown"))].join(" | ")).join("\n"),"text/plain");
  };
  const safeAction=async (path:string, body:unknown, key:string)=>{
    setPendingAction(key);setActionMessage("");
    try { await controller<Result>(path,{method:"POST",body:JSON.stringify(body)});setActionMessage("Request received. Refresh Activity to confirm actual outcome.");refresh(); }
    catch(e) {setActionMessage(e instanceof Error ? e.message : "Outcome uncertain; do not repeat before reviewing Activity.");}
    finally {setPendingAction("");}
  };
  const showPreview=async()=>{
    if(!selectedCity||!buildingPosition||!automationAccount)return;
    setAutomationBusy(true);setAutomationError("");setPreview(null);
    try{
      const p=await controller<Result>("accounts/"+encodeURIComponent(automationAccount)+"/cities/"+encodeURIComponent(selectedCity)+"/construction-preview",
        {method:"POST",body:JSON.stringify({upgrades:[{position:Number(buildingPosition),target_level:targetLevel}]})});
      setPreview(p);
    }catch(e){setAutomationError(e instanceof Error?e.message:"Planner unavailable");}
    finally {setAutomationBusy(false);}
  };

  return <div className={"app-shell "+(theme==="dark"?"theme-dark":"theme-light")}>
    {sidebar && <button className="mobile-backdrop" aria-label="Close navigation" onClick={()=>setSidebar(false)}/>}
    <aside className={"sidebar "+(sidebar?"sidebar-open":"")}>
      <button className="brand" onClick={()=>go("overview")} aria-label="Daedalus overview"><Image className="sidebar-wordmark" src="/brand/daedalus-horizontal-dark.svg" alt="Daedalus" width={1700} height={520} priority /><small>CONTROL CENTER</small></button>
      <div className="workspace-label">WORKSPACE</div>
      <nav aria-label="Main navigation" className="navigation">{NAV.map(({id,title,icon:Icon})=><button key={id} className={"nav-item "+(page===id?"nav-active":"")} onClick={()=>go(id)} aria-current={page===id?"page":undefined}><Icon size={18} strokeWidth={1.8}/><span>{title}</span>{page===id&&<span className="nav-current" />}</button>)}</nav>
      <div className="sidebar-spacer"/>
      <div className="sidebar-card"><div className="sidebar-card-top"><span className="live-mini"/><span>CONTROLLER STATUS</span></div><strong>{health?"Connected":"Not observed"}</strong><span className="sidebar-hint">{health ? String(health.mode??"Mode unknown").replace(/_/g," ") : "Check backend connectivity"}</span></div>
      <div className="sidebar-profile"><div className="avatar">{email.charAt(0).toUpperCase()}</div><span className="profile-text"><strong>{email}</strong><small>{readable(role)}</small></span></div>
    </aside>
    <div className="main-panel">
      <header className="topbar">
        <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={()=>setSidebar(true)}><Menu size={21}/></button>
        <div className="breadcrumb"><span>Workspace</span><ChevronRight size={15}/><strong>{pageInfo.title}</strong></div>
        <div className="topbar-spacer"/>
        <div className="search-box"><Search size={17}/><input ref={searchRef} aria-label="Search navigation" placeholder="Search pages…" value={search} onChange={e=>setSearch(e.target.value)}/><kbd>⌘ K</kbd>{search&&<div className="search-results">{NAV.filter(n=>n.title.toLowerCase().includes(search.toLowerCase())).map(n=><button key={n.id} onClick={()=>go(n.id)}>{n.title}<ArrowRight size={15}/></button>)}</div>}</div>
        <button className="icon-button" aria-label="Switch appearance" title="Toggle dark mode" onClick={()=>setTheme(t=>t==="light"?"dark":"light")}>{theme==="light"?<Moon size={19}/>:<Sun size={19}/>}</button>
        <button className="icon-button" title="Refresh data" aria-label="Refresh all observed data" onClick={refresh}><RefreshCw size={18}/></button>
        <div className="topbar-avatar" aria-label={email}>{email.charAt(0).toUpperCase()}</div>
      </header>
      <main className="main-content">
        <div className="heading-row"><div><div className="heading-kicker">DAEDALUS / {pageInfo.title.toUpperCase()}</div><h1>{pageInfo.title}</h1><p className="page-subtitle">{pageInfo.subtitle}</p></div><div className="page-actions">{page==="warehouses"&&<button className="primary-button" onClick={()=>window.print()} disabled={!displayedRows.length}><Printer size={16}/> Print combined report</button>}{page!=="settings"&&<button className="secondary-button" onClick={refresh}><RefreshCw size={15}/> Refresh</button>}</div></div>
        {loadError&&<div role="alert" className="alert-banner"><CircleAlert size={19}/><div><strong>Controller connection unavailable</strong><span>{loadError}. Observed values are not treated as zero.</span></div></div>}
        {page!=="settings"&&page!=="accounts"&&<div className="scope-row"><div className="scope-caption"><Globe2 size={17}/><span>ACCOUNT SCOPE</span></div><div className="segmented" aria-label="Account scope">{(["all","selected","one"] as const).map(s=><button key={s} className={scope===s?"segment-on":""} onClick={()=>setScope(s)}>{s==="all"?"All accounts":s==="selected"?"Selected":"One"}</button>)}</div>{scope!=="all"&&<div className="scope-picker">{scope==="one"?<select aria-label="Choose single account" value={selected[0]||accounts[0]?.id||""} onChange={e=>setSelected([e.target.value])}>{accounts.map(a=><option key={a.id} value={a.id}>{name(a)}</option>)}</select>:<div className="selected-picker">{accounts.map(a=><label key={a.id}><input type="checkbox" checked={selected.includes(a.id)} onChange={e=>setSelected(prev=>e.target.checked?[...prev,a.id]:prev.filter(v=>v!==a.id))}/>{name(a)}</label>)}</div>}</div>}<span className="scope-count">{scopeIds.length} of {accounts.length} accounts</span></div>}
        {page==="overview"&&<div className="content-stack">
          <div className="hero-banner"><div className="hero-copy"><div className="hero-eyebrow"><span className="hero-eyebrow-icon">✦</span> YOUR OPERATIONS, AT A GLANCE</div><h2>Everything in order.</h2><p>Observe your worlds, understand what is running, and take deliberate action from one calm workspace.</p><button className="hero-button" onClick={()=>go("warehouses")}>Explore warehouses <ArrowRight size={17}/></button></div><div className="hero-art" aria-hidden="true"><div className="hero-ring ring1"/><div className="hero-ring ring2"/><div className="hero-ring ring3"/><div className="hero-inner" /></div></div>
          <div className="metric-grid">
            <section className="metric-card"><div className="metric-top"><span>Configured accounts</span><UsersRound size={19}/></div><strong>{busy?"—":format(accounts.length)}</strong><small>Across configured worlds</small></section>
            <section className="metric-card"><div className="metric-top"><span>Authenticated sessions</span><CheckCircle2 size={19}/></div><strong>{busy?"—":format(countConnected)}</strong><small>{accounts.length? "Of "+accounts.length+" accounts":"No account data yet"}</small></section>
            <section className="metric-card"><div className="metric-top"><span>Task controller</span><Workflow size={19}/></div><strong className="metric-text">{health?.mode==="task_control_opt_in"?"Enabled":health?"Read-only":"Unknown"}</strong><small>Execution is verified per account</small></section>
            <section className="metric-card"><div className="metric-top"><span>Controller</span><Activity size={19}/></div><strong className="metric-text">{health?"Online":"Not observed"}</strong><small>{health? "Version "+String(health.version??"unknown"):"Refresh to check reachability"}</small></section>
          </div>
          <div className="two-column"><section className="panel"><div className="panel-heading"><div><h3>Account readiness</h3><p>Session status reported by the authoritative controller</p></div><button className="text-button" onClick={()=>go("accounts")}>View all <ArrowRight size={14}/></button></div>{accounts.length?<div className="simple-list">{accounts.slice(0,6).map(a=><div className="list-row" key={a.id}><div className="row-avatar">{name(a).charAt(0).toUpperCase()}</div><div className="list-main"><strong>{name(a)}</strong><span>{accountWorld(a)} · {a.player||"Player not named"}</span></div><Status ok={isConnected(a)} label={isConnected(a)?"Authenticated":readable(a.session_status||"Unknown")}/></div>)}</div>:<Empty title="Accounts unavailable" description="Connect the backend to display actual configured accounts." icon={UsersRound}/>}</section>
            <section className="panel"><div className="panel-heading"><div><h3>Quick access</h3><p>Jump into your everyday operations</p></div></div><div className="quick-actions">{([{id:"warehouses",label:"Combined warehouses",desc:"See unsecured stock across accounts",icon:Warehouse},{id:"automations",label:"Configure automations",desc:"Review prerequisites before action",icon:Workflow},{id:"activity",label:"Monitor activity",desc:"Inspect tasks and uncertain results",icon:Activity}] as const).map(a=><button onClick={()=>go(a.id)} className="quick-action" key={a.id}><span><a.icon size={20}/></span><div><strong>{a.label}</strong><small>{a.desc}</small></div><ChevronRight size={16}/></button>)}</div></section></div>
        </div>}
        {page==="accounts"&&<section className="panel">
          <div className="panel-heading"><div><h3>Managed accounts <span className="muted-count">{accounts.length}</span></h3><p>Identities, worlds and authenticated game sessions</p></div><div className="mini-search"><Search size={16}/><input aria-label="Filter accounts" placeholder="Find an account…" value={accountQuery} onChange={e=>setAccountQuery(e.target.value)}/></div></div>
          {filteredAccounts.length?<div className="table-scroll"><table><thead><tr><th>Account</th><th>World</th><th>Player</th><th>Game session</th><th>Status</th></tr></thead><tbody>{filteredAccounts.map(a=><tr key={a.id}><td><div className="table-account"><div className="row-avatar">{name(a).charAt(0).toUpperCase()}</div><span><strong>{name(a)}</strong><small>{a.id}</small></span></div></td><td><div className="world-cell">🌐 {accountWorld(a)}</div></td><td>{a.player||"—"}</td><td><Status ok={isConnected(a)} label={readable(a.session_status||"Unknown")}/></td><td><Status ok={a.enabled!==false} label={a.enabled===false?"Disabled":"Configured"}/></td></tr>)}</tbody></table></div>:<Empty title={accounts.length?"No matching accounts":"No accounts observed"} description="Your controller owns account configuration. The browser does not create game logins." icon={UsersRound}/>}
          <div className="panel-footer"><LockKeyhole size={16}/><span>Gameforge authentication, Selenium and CAPTCHA recovery stay exclusively in the Daedalus macOS app. No passwords are accepted here.</span></div>
        </section>}
        {page==="warehouses"&&<div className="content-stack">
          <div className="report-toolbar"><div><strong>Live warehouse report</strong><span>{reportLoading?"Fetching selected accounts…":rows.length+" city snapshots · "+Object.keys(warehouseMap).length+" accounts reported"}{errorCount>0&&" · "+errorCount+" unavailable"}</span></div><div className="report-tools"><label className="check-label"><input type="checkbox" checked={onlyLarge} onChange={e=>setOnlyLarge(e.target.checked)}/> ≥ 220K unsecured</label><div className="export-menu"><Download size={16}/><select aria-label="Export report" defaultValue="" onChange={e=>{if(e.target.value)exportRows(e.target.value as "csv"|"json"|"txt");e.target.value="";}}><option value="" disabled>Export report</option><option value="csv">CSV</option><option value="json">JSON</option><option value="txt">TXT</option></select></div></div></div>
          {Object.keys(warehouseErrors).length>0&&<div role="alert" className="notice"><CircleAlert size={18}/><span>Some accounts could not be retrieved: {Object.entries(warehouseErrors).map(([id])=>name(accountById[id]||{id})).join(", ")}. Totals may be incomplete.</span></div>}
          <div className="resource-grid">{RESOURCES.map(k=><div className="resource-card" key={k}><span className={"resource-gem resource-"+k}><ResourceIcon resource={k}/></span><div><span>{readable(k)} · unsecured</span><strong>{rows.length?format(resourceTotals[k].value):"—"}</strong><small>{resourceTotals[k].complete?"Observed total":"Partial / unknown"}</small></div></div>)}</div>
          <section className="panel print-panel"><div className="panel-heading"><div><h3>City inventory <span className="muted-count">{displayedRows.length}</span></h3><p>Grouped by island · authenticated observations, not estimates</p></div><span className="table-info">{reportLoading?"Loading…":"Last refreshed on demand"}</span></div>
          {displayedRows.length?<div className="table-scroll"><table><thead><tr><th>Island / City</th><th>Account</th>{RESOURCES.map(k=><th className="numeric" key={k}><span className="resource-heading"><ResourceIcon resource={k} small/>{readable(k)}</span></th>)}<th className="numeric">Capacity</th></tr></thead><tbody>{displayedRows.slice().sort((a,b)=>(a.island||"").localeCompare(b.island||"")||a.city_name.localeCompare(b.city_name)).map(c=><tr key={c.account_id+":"+c.city_id}><td><div className="city-cell"><strong>{c.city_name}</strong><small>{c.island||"Island unknown"}</small></div></td><td>{name(accountById[c.account_id]||{id:c.account_id})}</td>{RESOURCES.map(k=><td className="numeric tabular" key={k}>{format(c.resources?.unsecured?.[k])}</td>)}<td className="numeric tabular">{format(c.resources?.capacity)}</td></tr>)}</tbody></table></div>:<Empty title={reportLoading?"Retrieving warehouses…":"No warehouse snapshots"} description={onlyLarge?"No observed cities satisfy the current filter. Unknown values are not treated as zero.":"Use a connected IkaBot session to fetch real warehouses. Unavailable accounts remain explicit."} icon={Warehouse}/>}</section>
        </div>}
        {page==="automations"&&<div className="content-stack">
          <div className="notice"><ShieldCheck size={18}/><span>Automation uses the existing game engine. Inspect authoritative city data and preflight before preparing a change. No task starts without a separate reviewed, account-specific confirmation.</span></div>
          <div className="automation-layout"><section className="panel action-catalog"><div className="panel-heading"><div><h3>Operation library</h3><p>Search and select a workflow</p></div></div><div className="category-tabs"><button className={automationGroup==="All"?"active":""} onClick={()=>setAutomationGroup("All")}>All</button>{TASK_GROUPS.map(g=><button className={automationGroup===g.name?"active":""} onClick={()=>setAutomationGroup(g.name)} key={g.name}>{g.name}</button>)}</div><div className="action-list">{TASK_GROUPS.filter(g=>automationGroup==="All"||g.name===automationGroup).map(g=><div key={g.name}><div className="action-group-title"><g.icon size={15}/>{g.name}</div>{g.tasks.map(t=><button className={"action-card "+(chosenTask===t?"action-card-selected":"")} onClick={()=>setChosenTask(t)} key={t}><span><strong>{readable(t)}</strong><small>{t==="constructionList"?"Real building preview":"Preflight / adapter status"}</small></span><ChevronRight size={16}/></button>)}</div>)}</div></section>
            <section className="panel automation-detail"><div className="panel-heading"><div><div className="section-kicker">WORKFLOW INSPECTOR</div><h3>{readable(chosenTask)}</h3><p>Live account-bound data and availability</p></div><Status ok={preflight?.ready===true} label={preflight?.ready===true?"Ready to review":"Not approved"}/></div>
              <div className="editor-body"><label className="field"><span>Account</span><select value={automationAccount} onChange={e=>setAutomationAccount(e.target.value)}>{accounts.map(a=><option key={a.id} value={a.id}>{name(a)} · {accountWorld(a)}</option>)}</select></label>
                {preflight&&<div className="preflight-card"><div className="preflight-top"><span><ShieldCheck size={18}/> Authoritative preflight</span><Status ok={preflight.ready===true} label={preflight.ready===true?"Ready":"Unavailable"}/></div><p>{typeof preflight.reason==="string"?preflight.reason:"The controller has checked prerequisites for this account and operation."}</p>{preflight.unresolved_request===true&&<p className="warning-text">An earlier request is unresolved. Review Activity before any new operation.</p>}</div>}
                {chosenTask==="constructionList"?<><div className="form-section-title">Choose a real city</div><label className="field"><span>City</span><select value={selectedCity} onChange={e=>setSelectedCity(e.target.value)}><option value="">Select an authenticated city</option>{cities.map((c,i)=><option key={i} value={String(c.city_id??c.id??"")}>{String(c.name??c.city_name??c.id??"City")}</option>)}</select></label>{selectedCity&&<><div className="form-section-title">Buildings in this city</div><div className="building-list">{buildings.length?buildings.map((b,i)=><label key={i} className={"building-item "+(buildingPosition===String(b.position)?"building-chosen":"")}><input type="radio" name="building" checked={buildingPosition===String(b.position)} onChange={()=>{setBuildingPosition(String(b.position??""));setTargetLevel(Number(b.level??0)+1);setPreview(null);}}/><span><strong>{String(b.name??b.building??b.type??"Building")}</strong><small>Position {String(b.position??"—")}</small></span><span className="level-pill">Level {String(b.level??"—")}</span></label>):<Empty title="Building data not available" description="This account/city has no authenticated building inventory." icon={Building2}/>}</div><label className="field"><span>Target level</span><input type="number" min="1" max="150" value={targetLevel} onChange={e=>{setTargetLevel(Number(e.target.value));setPreview(null);}}/></label><button className="primary-button" disabled={automationBusy||!buildingPosition} onClick={showPreview}>{automationBusy?"Preparing preview…":"Preview upgrade (read-only)"}<ArrowRight size={16}/></button></>}</> :INVENTORIES[chosenTask]?<div className="inventory-editor">
                  {INVENTORIES[chosenTask].scope === "city" && <label className="field"><span>Choose your city</span><select value={selectedCity} onChange={e=>setSelectedCity(e.target.value)}><option value="">Select an authenticated city</option>{cities.map((c,i)=><option key={i} value={String(c.city_id??c.id??"")}>{String(c.name??c.city_name??c.id??"City")}</option>)}</select></label>}
                  {INVENTORIES[chosenTask].resource === "market-quotes" && <div className="market-fields"><label className="field"><span>Resource</span><select value={marketResource} onChange={e=>setMarketResource(Number(e.target.value))}>{RESOURCES.map((resource,index)=><option key={resource} value={index}>{readable(resource)}</option>)}</select></label><label className="field"><span>Market action</span><select value={marketSide} onChange={e=>setMarketSide(e.target.value)}><option value="buy">Buy available offers</option><option value="sell_to_offers">Sell to available offers</option><option value="create_offer">Create offer (preview)</option></select></label></div>}
                  <div className="form-section-title">{INVENTORIES[chosenTask].title}</div>
                  {inventoryBusy ? <p className="soft-loading">Retrieving authenticated controller data…</p> : inventoryError ? <div role="alert" className="inline-error">{inventoryError}</div> : inventory ? <InventoryDetails data={inventory}/> : <p className="subtle-message">Select an authenticated city to inspect the available data.</p>}
                  <div className="read-only-foot"><LockKeyhole size={16}/><span>Inventory is read-only. Starting this task requires a separately audited, account-scoped configuration and confirmation flow.</span></div>
                </div> :<div className="empty-adapter"><Landmark size={24}/><strong>Domain editor pending audit</strong><p>This upstream operation is catalogued, but a web-safe, independently reviewed adapter is required before this browser can execute it. The preflight shown above is informational.</p></div>}
                {preview&&<div className="preview-panel"><h4>Read-only construction preview</h4><p>These values come from IkaBot. Preview does not authorize or execute upgrades.</p>{Object.entries(preview).filter(([k,v])=>typeof v!=="object").map(([k,v])=><div key={k} className="key-value"><span>{readable(k)}</span><strong>{String(v??"Unknown")}</strong></div>)}{Object.entries(preview).filter(([k,v])=>Array.isArray(v)).map(([k,v])=><div key={k}><div className="form-section-title">{readable(k)}</div><DataTable rows={(v as unknown[]).filter(x=>x && typeof x==="object").map(x=>x as Record<string,unknown>)} /></div>)}</div>}
                {automationError&&<p role="alert" className="form-error">{automationError}</p>}
                <div className="read-only-foot"><LockKeyhole size={16}/><span>Dispatch unavailable from this panel until configuration parity and per-account approval are verified. No JSON executor is exposed.</span></div>
              </div></section></div>
        </div>}
        {page==="military"&&<div className="content-stack"><div className="under-tabs"><button className={militaryTab==="troops"?"tab-selected":""} onClick={()=>setMilitaryTab("troops")}>Troops & fleet</button><button className={militaryTab==="movements"?"tab-selected":""} onClick={()=>setMilitaryTab("movements")}>Movements</button></div><section className="panel"><div className="panel-heading"><div><h3>{militaryTab==="troops"?"Military strength":"Ship movements"}</h3><p>Read-only observations for the selected accounts</p></div><Status ok={Object.keys(militaryErrors).length===0&&Object.keys(militaryData).length>0} label="Controller data"/></div>{scopeIds.map(id=><div className="account-data-block" key={id}><div className="account-data-title"><div className="row-avatar">{name(accountById[id]||{id}).charAt(0).toUpperCase()}</div><strong>{name(accountById[id]||{id})}</strong><span>{accountWorld(accountById[id]||{id})}</span></div>{militaryErrors[id]?<div className="inline-error">{militaryErrors[id]}</div>:militaryData[id]?<div>{Object.entries(militaryData[id]).filter(([k])=>!["account_id","synthetic_demo"].includes(k)).map(([key,value])=><div key={key} className="military-group"><strong className="table-label">{readable(key)}</strong>{Array.isArray(value)?<DataTable rows={value.filter(x=>x && typeof x==="object") as Record<string,unknown>[]} />:typeof value==="object"&&value!==null?<DataTable rows={Object.entries(value).map(([key,v])=>({type:key,value:typeof v==="object"?"See controller details":v}))}/>:<div className="key-value"><span>{readable(key)}</span><strong>{String(value??"Unknown")}</strong></div>}</div>)}</div>:<div className="soft-loading">Retrieving current observations…</div>}</div>)}</section></div>}
        {page==="activity"&&<div className="content-stack">
          {actionMessage&&<div role="status" className="notice"><CircleAlert size={18}/>{actionMessage}</div>}
          <section className="panel"><div className="panel-heading"><div><h3>Managed task activity</h3><p>Observed engine tasks and durable controller request receipts</p></div><span className="table-info">No automatic replay on uncertain outcomes</span></div>{scopeIds.map(id=><div className="account-data-block" key={id}><div className="account-data-title"><div className="row-avatar">{name(accountById[id]||{id}).charAt(0).toUpperCase()}</div><strong>{name(accountById[id]||{id})}</strong><span>{accountWorld(accountById[id]||{id})}</span></div>{taskErrors[id]?<div className="inline-error">{taskErrors[id]}</div>:taskData[id]?<>
            <div className="form-section-title">Engine tasks</div>{(Array.isArray(taskData[id].engine_tasks)?taskData[id].engine_tasks as Result[]:[]).length?
            <div className="activity-items">{(taskData[id].engine_tasks as Result[]).map((t,i)=><div className="activity-item" key={i}><div><strong>{String(t.task??t.name??"Managed task")}</strong><small>{String(t.status??"Status unknown")} · {String(t.task_id??t.id??"")}</small></div>{role!=="viewer"&&<button className="danger-outline" disabled={pendingAction===id+":"+String(t.task_id??t.id)} onClick={()=>{if(window.confirm("Stop this managed task? The action may interrupt its running operation."))safeAction("accounts/"+encodeURIComponent(id)+"/tasks/"+encodeURIComponent(String(t.task_id??t.id))+"/stop",{},id+":"+String(t.task_id??t.id));}}>Stop</button>}</div>)}</div>:<p className="subtle-message">No currently reported managed tasks.</p>}
            <div className="form-section-title">Request receipts</div>{(Array.isArray(taskData[id].requests)?taskData[id].requests as Result[]:[]).length?<div className="activity-items">{(taskData[id].requests as Result[]).map((r,i)=><div className="activity-item" key={i}><div><strong>{String(r.task??"Request")} <span className="status-neutral-label">{String(r.status??"unknown")}</span></strong><small>{String(r.request_id??"ID unavailable")}</small></div>{role!=="viewer"&&r.status==="unconfirmed"&&<button className="danger-outline" onClick={()=>{if(window.confirm("Only acknowledge after independently checking that this request will not execute again. Have you inspected its actual state?"))safeAction("accounts/"+encodeURIComponent(id)+"/tasks/requests/"+encodeURIComponent(String(r.request_id))+"/acknowledge",{confirmed:true},"ack:"+i);}}>Reconcile</button>}</div>)}</div>:<p className="subtle-message">No durable request receipts returned.</p>}</>:<p className="soft-loading">Checking controller activity…</p>}</div>)}</section>
        </div>}
        {page==="settings"&&<div className="settings-grid"><section className="panel settings-panel"><div className="panel-heading"><div><h3>Appearance</h3><p>Choose a comfortable workspace</p></div><Sun size={19}/></div><div className="settings-row"><div><strong>Color theme</strong><small>System typography, refined for clarity</small></div><div className="segmented"><button className={theme==="light"?"segment-on":""} onClick={()=>setTheme("light")}><Sun size={15}/> Light</button><button className={theme==="dark"?"segment-on":""} onClick={()=>setTheme("dark")}><Moon size={15}/> Dark</button></div></div><div className="settings-row"><div><strong>Reduced motion</strong><small>Respects your device accessibility setting</small></div><span className="settings-value">Automatic</span></div></section>
          <section className="panel settings-panel"><div className="panel-heading"><div><h3>Authentication</h3><p>Your private administrator session</p></div><LockKeyhole size={19}/></div><div className="settings-row"><div><strong>Signed in as</strong><small>{email}</small></div><Status ok={true} label={readable(role)}/></div><div className="settings-row"><div><strong>Web sessions</strong><small>Validated against Supabase on privileged requests</small></div><span className="settings-value">Secure cookies</span></div><button className="secondary-button" onClick={async()=>{await fetch("/api/logout",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});window.location.assign("/login");}}><LogOut size={15}/> Sign out</button></section>
          <section className="panel settings-panel"><div className="panel-heading"><div><h3>Backend connection</h3><p>Safe operational status, no credentials disclosed</p></div><Activity size={19}/></div>{[["Availability",health?"Connected":"Unavailable"],["Mode",health?.mode??"Unknown"],["Version",health?.version??"Unknown"],["Synthetic data",health?.synthetic_demo?"Yes":"No or unknown"],["Engine dispatch",capabilities?.structured_engine_dispatch?"Available":"Not reported"]].map(([k,v])=><div className="settings-row" key={String(k)}><strong>{String(k)}</strong><span className="settings-value">{String(v)}</span></div>)}<button className="secondary-button" onClick={refresh}><RefreshCw size={16}/> Recheck backend</button></section>
          <section className="panel settings-panel"><div className="panel-heading"><div><h3>Security boundaries</h3><p>Safer by design</p></div><ShieldCheck size={19}/></div><div className="security-list"><p><CheckCircle2 size={17}/> No backend bearer token or vault material in the browser</p><p><CheckCircle2 size={17}/> No browser-based Gameforge or Selenium login</p><p><CheckCircle2 size={17}/> Operations require authenticated controllers</p><p><CheckCircle2 size={17}/> Read-only previews before any proposed mutation</p><p><CheckCircle2 size={17}/> No private offline data cache</p></div></section>
        </div>}
        <footer className="content-footer"><div>Daedalus · Private operations workspace</div><span>Observed data only · {health?"Controller available":"Controller not connected"}</span></footer>
      </main>
    </div>
  </div>;
}