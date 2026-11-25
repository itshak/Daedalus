// Native web task contracts: only reviewed operations may use the web launch route.
export const NATIVE_TASKS = ["sendResources", "distributeResources", "consolidateResources",
  "resourceTransportManager", "alertAttacks", "alertLowWine"] as const;
export type NativeTask = typeof NATIVE_TASKS[number];
export const MATERIALS = ["wood", "wine", "marble", "crystal", "sulfur"] as const;
export const MAX_AMOUNT = 1_000_000_000;
type Obj = Record<string, unknown>;
const obj = (v: unknown): v is Obj => !!v && typeof v === "object" && !Array.isArray(v);
const integer = (v: unknown, min: number, max: number): v is number =>
  typeof v === "number" && Number.isSafeInteger(v) && v >= min && v <= max;
const city = (v: unknown): v is number => integer(v, 1, 999_999_999_999);
const ids = (v: unknown, min: number): v is number[] =>
  Array.isArray(v) && v.length >= min && v.length <= 200 && v.every(city)
    && new Set(v).size === v.length;
const exact = (v: Obj, keys: string[]) =>
  Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v,k));
const amounts = (v: unknown, min = 0, nullable = false): v is (number | null)[] =>
  Array.isArray(v) && v.length === 5 && v.every(n => (nullable && n === null) || integer(n,min,MAX_AMOUNT));
const positive = (v: (number | null)[]) => v.some(n => typeof n === "number" && n > 0);
export function isNativeTask(task: unknown): task is NativeTask {
  return typeof task === "string" && (NATIVE_TASKS as readonly string[]).includes(task);
}
export function validNativeConfig(task: unknown, c: unknown): boolean {
  if (!isNativeTask(task) || !obj(c)) return false;
  switch (task) {
    case "alertAttacks":
      return exact(c,["minutes"]) && integer(c.minutes,3,1440);
    case "alertLowWine":
      return exact(c,["hours","auto_transfer","transfer_amount"]) && integer(c.hours,1,720)
        && typeof c.auto_transfer === "boolean"
        && (c.auto_transfer ? integer(c.transfer_amount,1,MAX_AMOUNT) : c.transfer_amount === 0);
    case "sendResources": {
      if (!exact(c,["routes","useFreighters"]) || typeof c.useFreighters !== "boolean"
        || !Array.isArray(c.routes) || c.routes.length < 1 || c.routes.length > 20) return false;
      const totals = new Map<number,number[]>();
      for (const r of c.routes) {
        if (!obj(r) || !exact(r,["from","to","resources"]) || !city(r.from) || !city(r.to)
          || r.from === r.to || !amounts(r.resources) || !positive(r.resources)) return false;
        const total = totals.get(r.from) ?? [0,0,0,0,0];
        for (let i=0;i<5;i++) total[i] += Number(r.resources[i]);
        if (total.some(n=>n>MAX_AMOUNT)) return false;
        totals.set(r.from,total);
      }
      return true;
    }
    case "distributeResources":
      return exact(c,["resource","mode","cities_ids","useFreighters"])
        && (MATERIALS as readonly unknown[]).includes(c.resource)
        && (c.mode === "even" || (c.mode === "producers" && c.resource !== "wood"))
        && ids(c.cities_ids,2) && typeof c.useFreighters === "boolean";
    case "consolidateResources":
      return exact(c,["limits","sourceCityIds","destinationCityId","intervalInHours","shipType"])
        && amounts(c.limits,-1) && c.limits.some(n=>n!==-1)
        && ids(c.sourceCityIds,1) && city(c.destinationCityId) && !c.sourceCityIds.includes(c.destinationCityId)
        && integer(c.intervalInHours,1,336) && integer(c.shipType,1,3);
    case "resourceTransportManager": {
      if (typeof c.useFreighters !== "boolean" || !integer(c.interval_hours,0,720)
        || typeof c.notify !== "string" || !["none","start","all"].includes(c.notify)) return false;
      const common = ["mode","interval_hours","resource_config","useFreighters","notify"];
      if (c.mode === "consolidate")
        return exact(c,[...common,"origin_cities","destination_city","send_mode"])
          && ids(c.origin_cities,1) && city(c.destination_city) && !c.origin_cities.includes(c.destination_city)
          && (c.send_mode === "keep" || c.send_mode === "send")
          && amounts(c.resource_config,0,true)
          && (c.send_mode === "keep" ? c.resource_config.some(n=>n!==null) : positive(c.resource_config));
      return c.mode === "distribute" && exact(c,[...common,"origin_city","destination_cities"])
        && city(c.origin_city) && ids(c.destination_cities,1) && !c.destination_cities.includes(c.origin_city)
        && amounts(c.resource_config) && positive(c.resource_config);
    }
  }
}
export function validNativeLaunch(value: unknown): boolean {
  return obj(value) && exact(value,["task","config","request_id","confirmed"])
    && value.confirmed === true && typeof value.request_id === "string"
    && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value.request_id)
    && validNativeConfig(value.task,value.config);
}
export type PlayerAccount = {id:string; player?:string; label?:string; name?:string; email?:string|null; world?:string};
const imported = /^Imported IkaBot (?:account|identity)(?: [0-9]+)?$/i;
export function playerName(a: PlayerAccount): string {
  return [a.player,a.label,a.name,a.email,a.id].find(v=>typeof v==="string" && v.trim() && !imported.test(v.trim()))?.trim() ?? a.id;
}
export function playerNames(accounts: PlayerAccount[]): Record<string,string> {
  const counts = new Map<string,number>();
  for (const a of accounts) {const key=playerName(a).toLowerCase();counts.set(key,(counts.get(key)??0)+1);}
  return Object.fromEntries(accounts.map(a=>[a.id,counts.get(playerName(a).toLowerCase())!>1
    ? `${playerName(a)} · ${a.world || "—"} (${a.id})` : playerName(a)]));
}
export type City = {id:number;name:string;coords?:string};
export function scopedCities(value: unknown, account: string): City[] {
  if (!obj(value) || value.account_id !== account || value.synthetic_demo === true || !Array.isArray(value.cities))
    return [];
  const result: City[]=[];
  for (const row of value.cities) {
    if (!obj(row) || !city(row.id) || typeof row.name !== "string" || !row.name.trim()
      || result.some(c=>c.id===row.id)) return [];
    result.push({id:row.id,name:row.name,coords:typeof row.coords==="string"?row.coords:undefined});
  }
  return result;
}
export function readyPreflight(value:unknown,account:string,task:NativeTask):boolean {
  return obj(value) && value.account_id===account && value.task===task && value.ready===true
    && value.unresolved_request===false;
}
