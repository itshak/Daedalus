/** Bounded per-instance defence in depth; distributed ingress limits remain required. */
export class TrafficGuard {
  private readonly windows = new Map<string,{start:number;count:number}>();
  private readonly now:()=>number;
  constructor(now:()=>number=Date.now){this.now=now;}
  allow(key:string,limit:number,windowMs:number):boolean {
    const time=this.now();
    for(const [id,entry] of this.windows) if(time-entry.start>=windowMs || time<entry.start)this.windows.delete(id);
    const entry=this.windows.get(key);
    if(entry){if(entry.count>=limit)return false;entry.count++;return true;}
    if(this.windows.size>=4096)return false;
    this.windows.set(key,{start:time,count:1});return true;
  }
}
export const gatewayTraffic=new TrafficGuard();
export const loginTraffic=new TrafficGuard();
