/** Project the account-bound controller DTO into visible city/unit rows. */
export type MilitaryRow = {cityId: number; city: string; unit: string | null; amount: number};
export type MilitaryInventory = {troops: MilitaryRow[]; fleet: MilitaryRow[]; observedAt: number};
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function positiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}
export function militaryInventory(value: unknown, accountId: string): MilitaryInventory | null {
  if (!record(value) || value.account_id !== accountId || !positiveInteger(value.observed_at)
      || !Array.isArray(value.cities) || value.cities.length > 100) return null;
  const result: MilitaryInventory = {troops: [], fleet: [], observedAt: value.observed_at};
  const seen = new Set<number>();
  for (const city of value.cities) {
    if (!record(city) || !positiveInteger(city.city_id) || seen.has(city.city_id)
        || typeof city.city_name !== "string" || !city.city_name.trim()) return null;
    seen.add(city.city_id);
    for (const group of ["troops", "fleet"] as const) {
      const units = city[group];
      if (!Array.isArray(units) || units.length > 100) return null;
      if (!units.length) result[group].push({cityId: city.city_id, city: city.city_name, unit: null, amount: 0});
      for (const unit of units) {
        if (!record(unit) || typeof unit.unit !== "string" || !unit.unit.trim()
            || typeof unit.amount !== "number" || !Number.isSafeInteger(unit.amount)
            || unit.amount < 0 || unit.amount > 10**10) return null;
        result[group].push({cityId: city.city_id, city: city.city_name, unit: unit.unit, amount: unit.amount});
      }
    }
  }
  return result;
}
