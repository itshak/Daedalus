export const WORLD_COLUMNS=["x","y","island_id","resource_type","miracle_type","wood_level","luxury_level","occupied_slots"] as const;
type Meta={report_id:string;completed_at:number;shallow:boolean;partial:boolean;island_count:number};
export type WorldReports={account_id:string;reports:Meta[]};
type Page=Meta&{account_id:string;offset:number;rows:(number|null)[][];next_offset:number|null};
const obj=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==="object"&&!Array.isArray(v);
const integer=(v:unknown,lo:number,hi:number):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&lo<=v&&v<=hi;
const id=(v:unknown):v is string=>typeof v==="string"&&/^[a-f0-9]{24}$/.test(v);
const meta=(v:Record<string,unknown>):v is Record<string,unknown>&Meta=>id(v.report_id)&&integer(v.completed_at,1,1e11)&&typeof v.shallow==="boolean"&&typeof v.partial==="boolean"&&integer(v.island_count,0,10201);
export function parseWorldReports(v:unknown,account:string):WorldReports{
  if(!obj(v)||Object.keys(v).length!==2||v.account_id!==account||!Array.isArray(v.reports)||v.reports.length>20||
    !v.reports.every(r=>obj(r)&&Object.keys(r).length===5&&meta(r))||
    new Set(v.reports.map(r=>r.report_id)).size!==v.reports.length)throw new Error("Invalid aggregate report inventory");
  return v as WorldReports;
}
export function parseWorldPage(v:unknown,account:string,reportId:string,offset:number):Page{
  if(!obj(v)||Object.keys(v).length!==9||v.account_id!==account||v.report_id!==reportId||v.offset!==offset||!integer(offset,0,10201)||!meta(v)||!Array.isArray(v.rows)||
     offset>v.island_count||v.rows.length!==Math.min(1000,v.island_count-offset))throw new Error("Invalid aggregate report page");
  const end=offset+v.rows.length;
  if(v.next_offset!==(end<v.island_count?end:null))throw new Error("Invalid report continuation");
  const coords=new Set<string>(),ids=new Set<number>();
  for(const row of v.rows){
    if(!Array.isArray(row)||row.length!==8||!integer(row[0],0,100)||!integer(row[1],0,100)||!integer(row[2],1,1e12-1)||
       !integer(row[3],0,4)||!integer(row[4],0,8)||!integer(row[5],0,150)||
       (row[6]!==null&&!integer(row[6],0,150))||(v.shallow&&row[6]!==null)||!integer(row[7],0,100)||
       coords.has(row[0]+":"+row[1])||ids.has(row[2]))throw new Error("Invalid aggregate report row");
    coords.add(row[0]+":"+row[1]);ids.add(row[2]);
  }
  return v as Page;
}
export async function collectWorldCsv(reader:(offset:number)=>Promise<unknown>,account:string,reportId:string){
  let offset=0,expected:string|null=null,total=0;
  const rows:(number|null)[][]=[];
  for(let i=0;i<11;i++){
    const page=parseWorldPage(await reader(offset),account,reportId,offset);
    const fingerprint=JSON.stringify([page.report_id,page.completed_at,page.shallow,page.partial,page.island_count]);
    if(expected!==null&&fingerprint!==expected)throw new Error("Report changed");
    expected=fingerprint;total=page.island_count;rows.push(...page.rows);
    if(page.next_offset===null)break;
    offset=page.next_offset;
  }
  if(expected===null||rows.length!==total||new Set(rows.map(r=>r[0]+":"+r[1])).size!==total||new Set(rows.map(r=>r[2])).size!==total)
    throw new Error("Incomplete report");
  return WORLD_COLUMNS.join(",")+"\r\n"+rows.map(r=>r.map(n=>n===null?"":String(n)).join(",")).join("\r\n")+"\r\n";
}
