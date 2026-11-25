"use client";
import {QueueReviewButton} from "./reviewed-batch-queue";
import {parseRewardDistributionReview,policyTask,reviewRoute} from "../lib/reward-distribution-review";
import {useEffect,useRef,useState} from "react";
import {useLanguage} from "./language-provider";
import {MAX_AMOUNT, type City, type DomainTask, scopedCities, readyPreflight,validNativeConfig,scopedStudyChoices,type StudyChoice,fixedTavernReview,scopedExternalCities} from "@/lib/native-task-contract";

type Row=Record<string,unknown>;
type Draft=Record<string,unknown>;
const record=(v:unknown):v is Row=>!!v&&typeof v==="object"&&!Array.isArray(v);
const gods=["Pan","Dionysus","Tyche","Plutus","Theia","Hephaestus"];
const favour=[["resource","Collect resource favour"],["look","Visit information pages"],["online","Stay online"],["complete","Collect completed tasks"]];
const inventories:Partial<Record<DomainTask,[string,string]>>={research:["academies","academies"],tavernManager:["taverns","taverns"],activateMiracle:["miracles","miracles"],activateShrine:["shrine-status","shrine"],autoPirate:["pirate-fortresses","fortresses"]};
async function api(path:string,body?:unknown):Promise<unknown>{
  const r=await fetch("/api/controller/"+path,{cache:"no-store",...(body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})});
  if(!r.ok)throw new Error("Request unavailable");
  return r.json();
}
export function NativeDomainEditor({account,accountName,task,enabled,role}:{account:string;accountName:string;task:DomainTask;enabled:boolean;role:string}){
  const {t}=useLanguage();
  const [cities,setCities]=useState<City[]>([]);
  const [monitorX,setMonitorX]=useState(50),[monitorY,setMonitorY]=useState(50);
  const [externalIslands,setExternalIslands]=useState<string[]>([]),[monitorBusy,setMonitorBusy]=useState(false),[monitorNote,setMonitorNote]=useState("");
  const monitorFlight=useRef(false);
  const [fixedTavern,setFixedTavern]=useState(false),[percentage,setPercentage]=useState(100);
  const [studies,setStudies]=useState<StudyChoice[]|null>(null),[studyIndex,setStudyIndex]=useState(-1);
  const [data,setData]=useState<unknown>(null);
  const [ready,setReady]=useState(false);
  const [loading,setLoading]=useState(Boolean(account&&enabled));
  const [error,setError]=useState(false);
  const [chosen,setChosen]=useState<number[]>([]);
  const [city,setCity]=useState(0);
  const [wood,setWood]=useState(0);
  const [luxury,setLuxury]=useState(0);
  const [choices,setChoices]=useState<string[]>([]);
  const [extra,setExtra]=useState(false);
  const [all,setAll]=useState(true);
  const [count,setCount]=useState(1);
  const [interval,setInterval]=useState(task==="donationBot"?1440:task==="searchForIslandSpaces"?20:2);
  const [policy,setPolicy]=useState(task==="tavernManager"?2:1);
  const [wonder,setWonder]=useState("");
  const [donations,setDonations]=useState<Record<string,{donation_type:string;percentage:number}>>({});
  const [scheduled,setScheduled]=useState(false);
  const [mission,setMission]=useState(0);
  const [day,setDay]=useState(0);
  const [night,setNight]=useState(0);
  const [dayStart,setDayStart]=useState(10);
  const [dayEnd,setDayEnd]=useState(18);
  const [nightStart,setNightStart]=useState(19);
  const [nightEnd,setNightEnd]=useState(9);
  const [convert,setConvert]=useState("none");
  const [convertAmount,setConvertAmount]=useState(0);
  const [wait,setWait]=useState(0);
  const [dumpMode,setDumpMode]=useState("region");
  const [x,setX]=useState(50);
  const [y,setY]=useState(50);
  const [radius,setRadius]=useState(15);
  const [delay,setDelay]=useState(1.5);
  const [review,setReview]=useState<{config:Draft;summary:string;previewId?:string;ttl?:number}|null>(null);
  const [approved,setApproved]=useState(false);
  const [busy,setBusy]=useState(false);
  const [locked,setLocked]=useState(false);
  const [message,setMessage]=useState("");
  const mounted=useRef(false);
  const inFlight=useRef(false);
  const prefix="accounts/"+encodeURIComponent(account);
  const inventory=inventories[task];
  const resource=inventory?.[0];
  const field=inventory?.[1];
  const needsCities=["loginDaily","donationBot","searchForIslandSpaces"].includes(task);
  useEffect(()=>{
    let live=true;mounted.current=true;
    if(!account||!enabled)return ()=>{mounted.current=false;};
    Promise.all([api(prefix+"/tasks/preflight?task="+encodeURIComponent(task)),needsCities?api(prefix+"/cities"):Promise.resolve(null),resource?api(prefix+"/"+resource):Promise.resolve(null)]).then(([p,c,d])=>{
      if(!live)return;
      setReady(readyPreflight(p,account,task));
      if(needsCities)setCities(scopedCities(c,account));
      if(field){
        if(!record(d)||d.account_id!==account||d.synthetic_demo===true){setError(true);return;}
        setData(d[field]);
        if(task==="research")setStudies(scopedStudyChoices(d.studies));
      }
    }).catch(()=>{if(live)setError(true);}).finally(()=>{if(live)setLoading(false);});
    return ()=>{live=false;mounted.current=false;};
  },[account,enabled,prefix,task,needsCities,resource,field]);
  const rows=Array.isArray(data)?data.filter(record):[];
  const cityLabel=(id:number)=>cities.find(c=>c.id===id)?.name??"—";
  const owned=(id:number)=>cities.some(c=>c.id===id);
  const selectedRows=rows.filter(row=>chosen.includes(Number(row.city_id)));
  const rowNames=selectedRows.map(row=>String(row.city_name)).join(", ");
  const coords=Array.from(new Set(cities.map(c=>c.coords??"").filter(x=>/^(?:[1-9][0-9]?|100):(?:[1-9][0-9]?|100)$/.test(x))));
  const monitorChoices=Array.from(new Set([...coords,...externalIslands]));
  const fortress=rows.find(r=>r.city_id===city);
  const missions=fortress&&Array.isArray(fortress.missions)?fortress.missions.filter(record):[];
  const selectedWonder=rows.find(row=>row.wonder===wonder);
  let config:Draft={};let summary="";let scoped=true;
  switch(task){
    case "loginDaily":
      config={wine_city:city,wood_city:wood||null,luxury_city:luxury||null,favour_tasks:choices,collect_ambrosia:extra};
      scoped=owned(city)&&(!wood||owned(wood))&&(!luxury||owned(luxury));
      summary=t("Daily wine reward city")+": "+cityLabel(city)+"\n"+t("Wood reward city")+": "+(wood?cityLabel(wood):t("Skip"))+"\n"+t("Luxury reward city")+": "+(luxury?cityLabel(luxury):t("Skip"))+"\n"+choices.map(v=>t(favour.find(x=>x[0]===v)?.[1]??v)).join(", ")+(extra?"\n"+t("Collect ambrosia"):"");break;
    case "research": {
      if(studyIndex>=0){
        const choice=studies?.find(r=>r.index===studyIndex);
        config=choice?{study_choice:choice}:{};
        scoped=!!choice;summary=choice?t("Study")+": "+choice.name+"\n"+t("One-time research submission. Verify the advisor after launch."):"";
        break;
      }
      config={cities_ids:chosen,qty:all?null:count};
      scoped=selectedRows.length===chosen.length&&(!all?selectedRows.length===1&&Number(selectedRows[0].crystal)>=300000:true);
      summary=rowNames+"\n"+(all?t("Automatic experiments"):t("Experiments")+": "+count);break;
    }
    case "tavernManager": {
      if(fixedTavern){
        const targets=rows.filter(r=>r.has_tavern===true&&(all||chosen.includes(Number(r.city_id))));
        const draft=fixedTavernReview(targets,percentage);
        config=draft?{run_hours:0,fixed_servings:draft}:{};
        scoped=!!draft;
        summary=draft?t("Set fixed serving percentage once")+": "+percentage+"%\n"+draft.rows.map(r=>r.city_name+": "+t("Level")+" "+r.current_level+" → "+r.target_level+"; "+t("Wine per hour")+" "+r.current_wine+" → "+r.target_wine).join("\n"):"";
        break;
      }
      config={cities_ids:all?null:chosen,run_hours:interval,notification_mode:policy};
      scoped=all?rows.some(row=>row.has_tavern===true):selectedRows.length===chosen.length&&selectedRows.every(row=>row.has_tavern===true);
      summary=(all?t("All cities with taverns"):rowNames)+"\n"+t("Repeat every (hours; 0 once)")+": "+interval+"\n"+t(["Every change","Only errors","None"][policy-1]);break;
    }
    case "activateMiracle":
      config={wonder,iterations:count};scoped=!!selectedWonder;
      summary=selectedWonder?String(selectedWonder.wonder_name)+" · "+String(selectedWonder.temple_city)+"\n"+t("Activations")+": "+count:"";break;
    case "activateShrine":
      config={godids:chosen,mode:policy,times:policy===2?0:count};scoped=record(data)&&typeof data.city_name==="string";
      summary=(record(data)?String(data.city_name):"")+"\n"+chosen.map(id=>gods[id-1]).join(", ")+"\n"+t("Favour per cycle")+": "+100*chosen.length+"\n"+t(["Fixed activations","Automatic repetition","Fixed then automatic"][policy-1])+(policy!==2?": "+count:"");break;
    case "donationBot": {
      const selected=Object.entries(donations).filter(([,v])=>v.donation_type!=="none");
      config={cities_dict:Object.fromEntries(selected),waiting_time:interval,donate_method:policy};
      scoped=selected.every(([id])=>owned(Number(id)));
      summary=selected.map(([id,v])=>cityLabel(Number(id))+" · "+t(v.donation_type==="resource"?"Forest":v.donation_type==="tradegood"?"Luxury resource":"Both projects")+": "+v.percentage).join("\n")+"\n"+t(["Storage percentage to keep","Production percentage to donate","Fixed donation amount"][policy-1])+" · "+t("minutes")+": "+interval;break;
    }
    case "autoPirate":
      config={pirateCount:count,pirateSchedule:scheduled,pirateMissionChoice:scheduled?null:mission,pirateMissionDayChoice:scheduled?day:null,pirateMissionNightChoice:scheduled?night:null,dayStart:scheduled?dayStart:null,dayEnd:scheduled?dayEnd:null,nightStart:scheduled?nightStart:null,nightEnd:scheduled?nightEnd:null,autoConvert:convert==="none"?"n":"y",convertPerMission:convert==="none"?0:convert==="all"?"all":convertAmount,maxRandomWaitingTime:wait,piracyCities:[{id:city}]};
      scoped=!!fortress&&(scheduled?[day,night]:[mission]).every(id=>missions.some(m=>m.number===id));
      summary=(fortress?String(fortress.city_name):"")+"\n"+t("Mission count")+": "+count+"\n"+(scheduled?t("Day mission")+": "+day+" ("+dayStart+"–"+dayEnd+") · "+t("Night mission")+": "+night+" ("+nightStart+"–"+nightEnd+")":t("Mission")+": "+mission)+"\n"+t("Convert capture points")+": "+t(convert==="none"?"None":convert==="all"?"All":"Fixed amount")+(convert==="amount"?": "+convertAmount:"")+"\n"+t("Maximum random wait (seconds)")+": "+wait;break;
    case "searchForIslandSpaces":
      config={time:interval,islandList:all?[]:choices,fights:extra?"y":"n"};scoped=all?coords.length>0:choices.length>0&&choices.every(c=>monitorChoices.includes(c));
      summary=(all?t("All owned islands"):choices.join(", "))+"\n"+t("minutes")+": "+interval+"\n"+t("Monitor fight activity")+": "+t(extra?"Yes":"No");break;
    case "dumpWorld":
      config={waiting_time:delay,coords:dumpMode==="region"?[x,y]:null,radius:dumpMode==="region"?radius:null,shallow:dumpMode==="shallow",non_empty_islands:dumpMode==="shallow"?false:extra};
      summary=t(dumpMode==="region"?"Map region":dumpMode==="shallow"?"Shallow map":"Full world")+(dumpMode==="region"?": "+x+":"+y+" · "+t("Radius")+": "+radius:"")+"\n"+t("Request interval (seconds)")+": "+delay+(extra&&dumpMode!=="shallow"?"\n"+t("Only occupied islands"):"");break;
  }
  const valid=scoped&&validNativeConfig(task,config);
  const disabled=busy||locked||loading||!enabled||role==="viewer";
  const canReview=!disabled&&ready&&!error&&valid&&!monitorBusy;
  const change=()=>{setReview(null);setApproved(false);};
  const verifyIsland=async()=>{
    if(disabled||monitorFlight.current||!Number.isInteger(monitorX)||!Number.isInteger(monitorY)||monitorX<1||monitorX>100||monitorY<1||monitorY>100)return;
    const key=monitorX+":"+monitorY;
    change();
    if(coords.includes(key)){setAll(false);setChoices(old=>Array.from(new Set([...old,key])));return;}
    if(externalIslands.length>=10&&!externalIslands.includes(key)){setMonitorNote("Clear external islands before adding more than ten.");return;}
    monitorFlight.current=true;setMonitorBusy(true);setMonitorNote("");setAll(false);
    setExternalIslands(old=>old.filter(c=>c!==key));setChoices(old=>old.filter(c=>c!==key));
    try{
      scopedExternalCities(await api(prefix+"/island-destinations?x="+monitorX+"&y="+monitorY),account,monitorX,monitorY);
      if(mounted.current){setExternalIslands(old=>Array.from(new Set([...old,key])));setChoices(old=>Array.from(new Set([...old,key])));setAll(false);setMonitorNote("Verified island added.");}
    }catch{if(mounted.current)setMonitorNote("Island unavailable. No unverified coordinates were added.");}
    finally{monitorFlight.current=false;if(mounted.current)setMonitorBusy(false);}
  };
  const numeric=(label:string,value:number,set:(v:number)=>void,min:number,max:number,step=1)=><label className="field"><span>{t(label)}</span><input type="number" step={step} min={min} max={max} value={Number.isNaN(value)?"":value} onChange={e=>{change();set(e.target.value===""?NaN:Number(e.target.value));}}/></label>;
  const toggle=(label:string,value:boolean,set:(v:boolean)=>void)=><label className="check-label"><input type="checkbox" checked={value} onChange={e=>{change();set(e.target.checked);}}/>{t(label)}</label>;
  const select=(label:string,value:string|number,options:[string|number,string][],set:(v:string)=>void)=><label className="field"><span>{t(label)}</span><select value={value} onChange={e=>{change();set(e.target.value);}}>{options.map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>;
  const citySelect=(label:string,value:number,set:(v:number)=>void,optional=false)=>select(label,value,[[0,t(optional?"Skip":"Choose a city")],...cities.map(c=>[c.id,c.name] as [number,string])],v=>set(Number(v)));
  const choose=(id:number,checked:boolean)=>setChosen(old=>checked?[...old,id]:old.filter(x=>x!==id));
  const toggleChoice=(id:string,checked:boolean)=>setChoices(old=>checked?[...old,id]:old.filter(x=>x!==id));
  const missionSelect=(label:string,value:number,set:(v:number)=>void)=>select(label,value,[[0,t("Choose mission")],...missions.map(m=>[Number(m.number),t("Mission")+" "+m.number+" · "+m.duration_seconds+" "+t("seconds")] as [number,string])],v=>set(Number(v)));
  const prepare=async()=>{
    if(!canReview||inFlight.current)return;
    change();
    if(task!=="loginDaily"&&!policyTask(task)){setReview({config,summary});return;}
    inFlight.current=true;setBusy(true);setMessage("");
    try{
      const data=parseRewardDistributionReview(await api(prefix+"/reward-distribution-plan",{task,draft:config}),account,task,config);
      const d=data.daily;
      if(mounted.current)setReview({config,previewId:data.preview_id,ttl:data.expires_in,summary:summary+"\n"+(d?t("Observed favour")+": "+d.favour+"/"+d.limit+"; "+t("Collectable tasks")+": "+d.collectable+"; "+t("Reset in seconds")+": "+d.reset_seconds+"\n"+t("Recurring policy; eligibility and reward quantities can change. No reward collected by preview."):data.policySummary+"\n"+t("Observed current state; future eligibility and costs may change."))});
    }catch{if(mounted.current)setMessage("Operation preview unavailable; refresh before retrying.");}
    finally{inFlight.current=false;if(mounted.current)setBusy(false);}
  };
  useEffect(()=>{
    if(!review?.ttl)return;
    const timer=window.setTimeout(()=>{setReview(null);setApproved(false);setMessage("Review expired; prepare a new preview.");},review.ttl*1000);
    return ()=>window.clearTimeout(timer);
  },[review]);
  const launch=async()=>{
    if(!canReview||!review||!approved||inFlight.current||JSON.stringify(review.config)!==JSON.stringify(config))return;
    inFlight.current=true;setBusy(true);setLocked(true);setApproved(false);
    try{
      const p=await api(prefix+"/tasks/preflight?task="+encodeURIComponent(task));
      if(!mounted.current)return;
      if(!readyPreflight(p,account,task)){setMessage("Readiness changed; refresh and review again.");return;}
      const result=(review.previewId?await api(prefix+"/tasks/"+reviewRoute(task),{preview_id:review.previewId,confirmed:true,request_id:crypto.randomUUID()}):await api(prefix+"/tasks",{task,config:review.config,confirmed:true,request_id:crypto.randomUUID()})) as {status?:string};
      if(mounted.current)setMessage(result.status==="started"?"Task started. See Activity for status.":"Request recorded. Check Activity before another attempt.");
    }catch{if(mounted.current)setMessage("Request outcome uncertain or rejected. Check Activity before retrying.");}
    finally{inFlight.current=false;if(mounted.current)setBusy(false);}
  };
  return <section className="native-automation-editor">
    {loading?<p role="status">{t("Retrieving authenticated controller data…")}</p>:error||!ready?<p role="alert">{t("Task prerequisites are not ready. Check the account and notifications.")}</p>:<p>{t("Ready to review")}</p>}
    <fieldset disabled={disabled}><legend>{t("Settings")}</legend>
      {task==="loginDaily"&&<>{citySelect("Daily wine reward city",city,setCity)}{citySelect("Wood reward city",wood,setWood,true)}{citySelect("Luxury reward city",luxury,setLuxury,true)}{favour.map(([id,name])=><div key={id}>{toggle(name,choices.includes(id),v=>toggleChoice(id,v))}</div>)}{toggle("Collect ambrosia",extra,setExtra)}</>}
      {task==="research"&&<>{select("Research action",studyIndex,[[-1,t("Academy experiments")],...(studies??[]).map(r=>[r.index,t("Study")+": "+r.name] as [number,string])],v=>setStudyIndex(Number(v)))}{studies===null&&<p>{t("Study advisor unavailable; experiments remain available.")}</p>}{studyIndex<0&&<>{rows.map(r=><label key={String(r.city_id)} className="check-label"><input type="checkbox" checked={chosen.includes(Number(r.city_id))} onChange={e=>{change();choose(Number(r.city_id),e.target.checked);}}/>{String(r.city_name)} · {String(r.crystal)} {t("Glass")} · {t(r.cooldown?"Cooling down":"Ready")}</label>)}{toggle("Automatic experiments",all,setAll)}{!all&&numeric("Experiments",count,setCount,1,10000)}<p>{t("Each experiment requires at least 300,000 crystal and has an approximately four-hour cooldown.")}</p></>}</>}
      {task==="tavernManager"&&<>{select("Tavern operation",fixedTavern?"fixed":"equilibrium",[["equilibrium",t("Equilibrium (optimize consumption)")],["fixed",t("Set fixed serving percentage once")]],v=>setFixedTavern(v==="fixed"))}{toggle("All cities with taverns",all,setAll)}{rows.filter(r=>r.has_tavern===true).map(r=><label key={String(r.city_id)} className="check-label"><input type="checkbox" checked={all||chosen.includes(Number(r.city_id))} disabled={all} onChange={e=>{change();choose(Number(r.city_id),e.target.checked);}}/>{String(r.city_name)} · {t("Wine")}: {String(r.wine)} · {t("Wine per hour")}: {String(r.wine_per_hour??"—")} · {t("Population")}: {String(r.population??"—")}</label>)}{fixedTavern?<>{numeric("Serving percentage",percentage,setPercentage,0,100)}{!valid&&<p>{t("Verified serving choices are required for all selected taverns.")}</p>}</>:<>{numeric("Repeat every (hours; 0 once)",interval,setInterval,0,24)}{select("Notifications",policy,[[1,t("Every change")],[2,t("Only errors")],[3,t("None")]],v=>setPolicy(Number(v)))}</>}</>}
      {task==="activateMiracle"&&<>{select("Wonder",wonder,[["",t("Choose wonder")],...rows.map(r=>[String(r.wonder),String(r.wonder_name)+" · "+String(r.temple_city)+" · "+t("Level")+" "+r.level+" · "+r.available_in_seconds+" "+t("seconds")] as [string,string])],setWonder)}{numeric("Activations",count,setCount,1,100)}</>}
      {task==="activateShrine"&&<>{record(data)&&<p>{String(data.city_name)} · {t("Current favour")}: {String(data.favor??"—")}</p>}{gods.map((g,i)=><div key={g}>{toggle(g,chosen.includes(i+1),v=>choose(i+1,v))}</div>)}<p>{t("Favour per cycle")}: {chosen.length*100}</p>{select("Activation schedule",policy,[[1,t("Fixed activations")],[2,t("Automatic repetition")],[3,t("Fixed then automatic")]],v=>setPolicy(Number(v)))}{policy!==2&&numeric("Activations",count,setCount,1,10)}</>}
      {task==="donationBot"&&<>{select("Donation method",policy,[[1,t("Storage percentage to keep")],[2,t("Production percentage to donate")],[3,t("Fixed donation amount")]],v=>{setPolicy(Number(v));setDonations({});})}{cities.slice(0,100).map(c=>{const row=donations[c.id]??{donation_type:"none",percentage:0};return <fieldset key={c.id}><legend>{c.name}</legend>{select("Island project",row.donation_type,[["none",t("None")],["resource",t("Forest")],["tradegood",t("Luxury resource")],["both",t("Both projects")]],v=>setDonations(old=>({...old,[c.id]:{...row,donation_type:v}})))}{row.donation_type!=="none"&&numeric("Policy amount",row.percentage,v=>setDonations(old=>({...old,[c.id]:{...row,percentage:v}})),0,policy===3?MAX_AMOUNT:100)}</fieldset>;})}{numeric("Repeat every (minutes)",interval,setInterval,1,10080)}</>}
      {task==="autoPirate"&&<><p className="subtle-message">{t("Managed piracy stops at a game challenge. Complete the challenge manually before a new reviewed launch.")}</p>{select("Pirate fortress city",city,[[0,t("Choose a city")],...rows.map(r=>[Number(r.city_id),String(r.city_name)+" · "+t("Level")+" "+r.fortress_level] as [number,string])],v=>{setCity(Number(v));setMission(0);setDay(0);setNight(0);})}{numeric("Mission count",count,setCount,1,100000)}{toggle("Separate day and night missions",scheduled,setScheduled)}{scheduled?<>{missionSelect("Day mission",day,setDay)}{numeric("Day starts",dayStart,setDayStart,0,23)}{numeric("Day ends",dayEnd,setDayEnd,0,23)}{missionSelect("Night mission",night,setNight)}{numeric("Night starts",nightStart,setNightStart,0,23)}{numeric("Night ends",nightEnd,setNightEnd,0,23)}</>:missionSelect("Mission",mission,setMission)}{select("Convert capture points",convert,[["none",t("None")],["all",t("All")],["amount",t("Fixed amount")]],setConvert)}{convert==="amount"&&numeric("Capture points",convertAmount,setConvertAmount,0,MAX_AMOUNT)}{numeric("Maximum random wait (seconds)",wait,setWait,0,3600)}</>}
      {task==="searchForIslandSpaces"&&<>{toggle("All owned islands",all,setAll)}{!all&&monitorChoices.map(c=><div key={c}>{toggle(c+(externalIslands.includes(c)?" · "+t("Verified external island"):""),choices.includes(c),v=>toggleChoice(c,v))}</div>)}<fieldset disabled={monitorBusy}><legend>{t("Verify external island")}</legend>{numeric("Map X",monitorX,setMonitorX,1,100)}{numeric("Map Y",monitorY,setMonitorY,1,100)}<button type="button" className="secondary-button" disabled={monitorBusy} onClick={()=>void verifyIsland()}>{t("Verify and add island")}</button><button type="button" className="secondary-button" disabled={monitorBusy||!externalIslands.length} onClick={()=>{change();setChoices(old=>old.filter(c=>!externalIslands.includes(c)));setExternalIslands([]);setMonitorNote("");}}>{t("Clear external islands")}</button>{monitorNote&&<p role="status">{t(monitorNote)}</p>}</fieldset>{numeric("Check every (minutes)",interval,setInterval,3,1440)}{toggle("Monitor fight activity",extra,setExtra)}</>}
      {task==="dumpWorld"&&<><p className="subtle-message">{t("Completed managed scans are available in Activity as aggregate CSV reports without player names.")}</p>{select("Map extent",dumpMode,[["region",t("Map region")],["full",t("Full world")],["shallow",t("Shallow map")]],setDumpMode)}{dumpMode==="region"&&<>{numeric("Map X",x,setX,0,100)}{numeric("Map Y",y,setY,0,100)}{numeric("Radius",radius,setRadius,0,200)}</>}{numeric("Request interval (seconds)",delay,setDelay,1,10,.5)}{dumpMode!=="shallow"&&toggle("Only occupied islands",extra,setExtra)}<p>{t("World dump output is stored on the controller.")}</p></>}
    </fieldset>
    {!valid&&!loading&&<p>{t("Complete the required settings before review.")}</p>}
    <button type="button" className="secondary-button" disabled={!canReview} onClick={()=>void prepare()}>{t("Review settings")}</button>
    {review&&<section className="preview-panel"><h4>{t("Review automation")} · {accountName}</h4><p style={{whiteSpace:"pre-line"}}>{review.summary}</p><label className="check-label"><input type="checkbox" checked={approved} disabled={disabled} onChange={e=>setApproved(e.target.checked)}/>{t("I approve starting this automation")}</label><button type="button" className="primary-button" disabled={!canReview||!approved} onClick={()=>void launch()}>{t("Start automation")}</button>{review.previewId&&<QueueReviewButton key={review.previewId} account={account} accountName={accountName} task={task} previewId={review.previewId} ttl={review.ttl??null} summary={review.summary} disabled={!canReview||!approved} onQueued={()=>{setLocked(true);setApproved(false);}}/>}</section>}
    {message&&<p role="status">{t(message)}</p>}
  </section>;
}
