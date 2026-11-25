export const TRAINING_RESOURCES=["wood","wine","marble","crystal","sulfur","citizens"] as const;
export type TrainingUnit={unit_type_id:number;cantidad:number};
export type TrainingDraft={city_ids:number[];train_troops:boolean;rounds:TrainingUnit[][];cycles:number};
export type ObservedUnit=TrainingUnit&{local_name:string;costs:Record<string,number>};
export type TrainingCity={city_id:number;city_name:string;position:number;rounds:ObservedUnit[][];stock:number[];round_costs:number[][];total_costs:number[];ready:boolean};
export type TrainingPlan=TrainingDraft&{account_id:string;cities:TrainingCity[];ready:boolean;preview_id:string|null;expires_in:number|null};
const obj=(v:unknown):v is Record<string,unknown>=>typeof v==="object"&&v!==null&&!Array.isArray(v);
const int=(v:unknown,min:number,max:number):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&v>=min&&v<=max;
const exact=(v:Record<string,unknown>,keys:string[])=>Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const number=(v:unknown,max:number):v is number=>typeof v==="number"&&Number.isFinite(v)&&v>=0&&v<=max;
export function validTrainingDraft(v:unknown,origin?:number):v is TrainingDraft{
  if(!obj(v)||!exact(v,["city_ids","train_troops","rounds","cycles"])||typeof v.train_troops!=="boolean"||
    !int(v.cycles,1,10)||!Array.isArray(v.city_ids)||v.city_ids.length<1||v.city_ids.length>32||
    !v.city_ids.every(id=>int(id,1,999_999_999_999))||new Set(v.city_ids).size!==v.city_ids.length||
    (origin!==undefined&&v.city_ids[0]!==origin)||!Array.isArray(v.rounds)||v.rounds.length<1||v.rounds.length>10||
    v.city_ids.length*v.rounds.length*v.cycles>200)return false;
  return v.rounds.every(group=>Array.isArray(group)&&group.length>=1&&group.length<=50&&
    group.every(u=>obj(u)&&exact(u,["unit_type_id","cantidad"])&&int(u.unit_type_id,1,9_999_999)&&int(u.cantidad,1,100000))&&
    new Set(group.map(u=>u.unit_type_id)).size===group.length);
}
function sameNumbers(v:unknown,expected:number[]):boolean{
  return Array.isArray(v)&&v.length===expected.length&&v.every((n,i)=>number(n,1e15)&&Math.abs(n-expected[i])<=Math.max(1e-6,Math.abs(expected[i])*1e-12));
}
export function scopedTrainingPlan(v:unknown,account:string,draft:TrainingDraft,owned:number[]):TrainingPlan{
  if(!validTrainingDraft(draft)||!draft.city_ids.every(id=>owned.includes(id))||!obj(v)||v.account_id!==account||
    !validTrainingDraft({city_ids:v.city_ids,train_troops:v.train_troops,rounds:v.rounds,cycles:v.cycles})||
    JSON.stringify(v.city_ids)!==JSON.stringify(draft.city_ids)||v.train_troops!==draft.train_troops||v.cycles!==draft.cycles||
    !Array.isArray(v.rounds)||v.rounds.length!==draft.rounds.length||
    !v.rounds.every((g,i)=>g.length===draft.rounds[i].length&&g.every((u:TrainingUnit,j:number)=>u.unit_type_id===draft.rounds[i][j].unit_type_id&&u.cantidad===draft.rounds[i][j].cantidad))||
    !Array.isArray(v.cities)||v.cities.length!==draft.city_ids.length)throw new Error("Invalid recruitment scope");
  for(const [i,r] of v.cities.entries()){
    if(!obj(r)||r.city_id!==draft.city_ids[i]||typeof r.city_name!=="string"||!r.city_name||r.city_name.length>100||
      !int(r.position,0,80)||!Array.isArray(r.rounds)||r.rounds.length!==draft.rounds.length||
      !Array.isArray(r.stock)||r.stock.length!==6||!r.stock.every(n=>int(n,0,1e15))||
      !Array.isArray(r.round_costs)||r.round_costs.length!==draft.rounds.length)throw new Error("Invalid recruiting city");
    const sums:number[][]=[];
    for(const [j,g] of r.rounds.entries()){
      if(!Array.isArray(g)||g.length!==draft.rounds[j].length)throw new Error("Invalid round");
      const sumsForRound=TRAINING_RESOURCES.map(()=>0);
      for(const [k,u] of g.entries()){
        if(!obj(u)||u.unit_type_id!==draft.rounds[j][k].unit_type_id||u.cantidad!==draft.rounds[j][k].cantidad||
          typeof u.local_name!=="string"||!u.local_name||u.local_name.length>100||!obj(u.costs)||
          Object.entries(u.costs).some(([key,n])=>![...TRAINING_RESOURCES,"upkeep","completiontime"].includes(key)&&true||!number(n,1e9)))throw new Error("Invalid unit");
        const costs=u.costs as Record<string,number>;
        TRAINING_RESOURCES.forEach((key,n)=>{sumsForRound[n]+=(costs[key]??0)*draft.rounds[j][k].cantidad;});
      }
      if(!sameNumbers(r.round_costs[j],sumsForRound))throw new Error("Invalid round costs");
      sums.push(sumsForRound);
    }
    const total=TRAINING_RESOURCES.map((_,k)=>sums.reduce((n,g)=>n+g[k],0)*draft.cycles);
    if(!sameNumbers(r.total_costs,total)||r.ready!==sums[0].every((n,j)=>n<=(r.stock as number[])[j]))throw new Error("Invalid recruitment costs");
  }
  if(v.ready!==v.cities.every(r=>r.ready===true)||
     (v.ready&&(typeof v.preview_id!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(v.preview_id)||!int(v.expires_in,1,120)))||
     (!v.ready&&(v.preview_id!==null||v.expires_in!==null)))throw new Error("Invalid recruitment ticket");
  return v as unknown as TrainingPlan;
}
