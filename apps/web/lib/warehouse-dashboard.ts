export const WAREHOUSE_TTL_MS = 120_000;
export const DASHBOARD_PAGES = ["overview", "accounts", "warehouses", "production", "automations", "military", "activity", "settings"] as const;
export type DashboardPage = typeof DASHBOARD_PAGES[number];
export function savedPage(value: string | null): DashboardPage {
  return DASHBOARD_PAGES.find(page => page === value) ?? "overview";
}
export const WAREHOUSE_RESOURCES = ["wood", "wine", "marble", "glass", "sulfur"] as const;
export type WarehouseResource = typeof WAREHOUSE_RESOURCES[number];
export type WarehouseCity = {account_id: string; city_id: number; city_name: string; island?: string | null; captured_at?: string; resources: {unsecured: Record<string, number | null>; total?: Record<string, number | null>; capacity?: number | null}};
export type WarehouseResult = {account_id: string; cities: WarehouseCity[]; synthetic_demo?: boolean};
export function warehouseIsland(city: WarehouseCity, world: string): string {
  return city.island ? `${world} · ${city.island}` : "";
}
export function filterWarehouseRows(rows: WarehouseCity[], filters: {query: string; island: string; resource: WarehouseResource | "all"; minimum: number; onlyLarge: boolean}, account: (id: string) => {name: string; world: string}): WarehouseCity[] {
  const query = filters.query.trim().toLocaleLowerCase();
  return rows.filter(city => {
    const identity = account(city.account_id);
    if (filters.island !== "all" && warehouseIsland(city, identity.world) !== filters.island) return false;
    if (query && ![city.city_name, city.island, identity.name, identity.world].some(value => value?.toLocaleLowerCase().includes(query))) return false;
    if (filters.resource !== "all") {
      const amount = city.resources?.unsecured?.[filters.resource];
      if (typeof amount !== "number" || amount < Math.max(1, filters.minimum)) return false;
    }
    if (filters.onlyLarge) {
      const values = WAREHOUSE_RESOURCES.map(resource => city.resources?.unsecured?.[resource]);
      if (values.every(value => typeof value === "number") && values.reduce<number>((sum, value) => sum + (value ?? 0), 0) < 220_000) return false;
    }
    return true;
  });
}
const record=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==="object"&&!Array.isArray(v);
const amount=(v:unknown):v is number|null=>v===null||(typeof v==="number"&&Number.isSafeInteger(v)&&v>=0);
function resourceMap(v:unknown):Record<string,number|null>{
  if(!record(v)||!WAREHOUSE_RESOURCES.every(k=>amount(v[k])))throw new Error("Warehouse response unavailable");
  return Object.fromEntries(WAREHOUSE_RESOURCES.map(k=>[k,v[k] as number|null]));
}
/** Project only the fixed warehouse DTO. Never render malformed numbers or cross-account rows. */
export function parseWarehouseResult(value:unknown,accountId:string):WarehouseResult{
  if(!record(value)||value.account_id!==accountId||!Array.isArray(value.cities)||value.cities.length>100)throw new Error("Warehouse response unavailable");
  const seen=new Set<number>();
  const cities=value.cities.map((row:unknown):WarehouseCity=>{
    if(!record(row)||row.account_id!==accountId||typeof row.city_id!=="number"||!Number.isSafeInteger(row.city_id)||row.city_id<=0||seen.has(row.city_id)||typeof row.city_name!=="string"||!row.city_name.trim()||row.city_name.length>120||!record(row.resources)||!amount(row.resources.capacity))throw new Error("Warehouse response unavailable");
    if(row.island!==undefined&&row.island!==null&&(typeof row.island!=="string"||!/^(?:[0-9]{1,3}:[0-9]{1,3}|\[[0-9]{1,3}:[0-9]{1,3}\])$/.test(row.island)))throw new Error("Warehouse response unavailable");
    if(row.captured_at!==undefined&&(typeof row.captured_at!=="string"||row.captured_at.length>64||!Number.isFinite(Date.parse(row.captured_at))))throw new Error("Warehouse response unavailable");
    seen.add(row.city_id);
    return {account_id:accountId,city_id:row.city_id,city_name:row.city_name,island:row.island as string|null|undefined,captured_at:row.captured_at as string|undefined,resources:{unsecured:resourceMap(row.resources.unsecured),capacity:row.resources.capacity,...(row.resources.total===undefined?{}:{total:resourceMap(row.resources.total)})}};
  });
  return {account_id:accountId,cities,synthetic_demo:value.synthetic_demo===true};
}
/** Private, mounted-dashboard memory only. No browser storage or offline replay. */
export class WarehouseCache {
  private entries = new Map<string, {value: WarehouseResult; at: number}>();
  private pending = new Map<string, Promise<WarehouseResult>>();
  private generation = 0;
  private readonly now: () => number;
  constructor(now: () => number = Date.now) { this.now = now; }
  fresh(key: string) {
    const entry = this.entries.get(key);
    if (entry && this.now() >= entry.at && this.now() - entry.at < WAREHOUSE_TTL_MS) return entry;
    if (entry) this.entries.delete(key);
    return undefined;
  }
  clear() { this.generation++; this.entries.clear(); this.pending.clear(); }
  async read(key: string, accountId: string, fetcher: () => Promise<WarehouseResult>): Promise<WarehouseResult> {
    const existing = this.fresh(key);
    if (existing) return existing.value;
    const inFlight = this.pending.get(key);
    if (inFlight) return inFlight;
    this.entries.delete(key);
    const generation = this.generation;
    const request = Promise.resolve().then(fetcher).then(value => {
      if(this.generation!==generation)throw new Error("Warehouse response unavailable");
      const parsed=parseWarehouseResult(value,accountId);
      this.entries.set(key,{value:parsed,at:this.now()});
      return parsed;
    }).finally(() => { if (this.pending.get(key) === request) this.pending.delete(key); });
    this.pending.set(key, request);
    return request;
  }
}
