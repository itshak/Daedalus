/** Working scope is a preference, not an authorization grant. */
export type AccountScope = {mode:"all"} | {mode:"explicit"; ids:string[]};
export const ALL_SCOPE:AccountScope = {mode:"all"};
export function parseScope(raw:string|null):AccountScope {
  if(raw===null)return ALL_SCOPE;
  try {
    const value=JSON.parse(raw);
    if(value?.mode==="all")return ALL_SCOPE;
    if(value?.mode==="explicit" && Array.isArray(value.ids) && value.ids.every((id:unknown)=>typeof id==="string"&&id.length>0))
      return {mode:"explicit",ids:[...new Set<string>(value.ids)]};
  } catch {}
  return {mode:"explicit",ids:[]};
}
export function scopedAccounts<T extends {id:string}>(accounts:T[],scope:AccountScope):T[] {
  if(scope.mode==="all")return accounts;
  const ids=new Set(scope.ids);
  return accounts.filter(a=>ids.has(a.id));
}
export function reconcileScope(scope:AccountScope,ids:string[]):AccountScope {
  if(scope.mode==="all")return scope;
  const authorized=new Set(ids);
  const kept=scope.ids.filter(id=>authorized.has(id));
  return kept.length===scope.ids.length?scope:{mode:"explicit",ids:kept};
}
export function eligibleTarget(ids:string[],chosen:string):string {
  return ids.includes(chosen)?chosen:ids.length===1?ids[0]:"";
}
