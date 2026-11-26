export const WAREHOUSE_TTL_MS = 120_000;
export const DASHBOARD_PAGES = ["overview", "accounts", "warehouses", "automations", "military", "activity", "settings"] as const;
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
/** Private, mounted-dashboard memory only. No browser storage or offline replay. */
export class WarehouseCache {
  private entries = new Map<string, {value: WarehouseResult; at: number}>();
  private pending = new Map<string, Promise<WarehouseResult>>();
  private generation = 0;
  private readonly now: () => number;
  constructor(now: () => number = Date.now) { this.now = now; }
  fresh(key: string) {
    const entry = this.entries.get(key);
    if (entry && this.now() - entry.at < WAREHOUSE_TTL_MS) return entry;
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
      if (value.account_id !== accountId || !Array.isArray(value.cities) || value.cities.some(city => city.account_id !== accountId)) throw new Error("Warehouse response unavailable");
      if (this.generation === generation) this.entries.set(key, {value, at: this.now()});
      return value;
    }).finally(() => { if (this.pending.get(key) === request) this.pending.delete(key); });
    this.pending.set(key, request);
    return request;
  }
}
