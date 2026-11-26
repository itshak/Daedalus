import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {WarehouseCache, WAREHOUSE_TTL_MS, savedPage, filterWarehouseRows, parseWarehouseResult} from "../lib/warehouse-dashboard.ts";
const city=(id,account,wood,island="[1:2]")=>({account_id:account,city_id:id,city_name:id===1?"Athens":"Sparta",island,resources:{unsecured:{wood,wine:0,marble:0,glass:0,sulfur:0},capacity:300000}});
const response={account_id:"alpha",cities:[city(1,"alpha",250000)]};
const identity=id=>({name:id,world:id==="alpha"?"s1":"s2"});
const filters={query:"",island:"all",resource:"all",minimum:0,onlyLarge:false};
test("safe saved navigation restores only recognized pages",()=>{
  assert.equal(savedPage("military"),"military");assert.equal(savedPage("warehouses"),"warehouses");assert.equal(savedPage("https://other.example"),"overview");assert.equal(savedPage(null),"overview");
});
test("warehouse filters distinguish worlds, numeric resource thresholds and unknown stock",()=>{
  const rows=[city(1,"alpha",250000),city(2,"beta",5),city(3,"alpha",null),city(4,"alpha",0)];
  assert.deepEqual(filterWarehouseRows(rows,{...filters,island:"s2 · [1:2]"},identity).map(r=>r.city_id),[2]);
  assert.deepEqual(filterWarehouseRows(rows,{...filters,resource:"wood",minimum:10},identity).map(r=>r.city_id),[1]);
  assert.deepEqual(filterWarehouseRows(rows,{...filters,onlyLarge:true},identity).map(r=>r.city_id),[1,3]);
  assert.deepEqual(filterWarehouseRows(rows,{...filters,query:"ATHENS"},identity).map(r=>r.city_id),[1]);
});
test("warehouse cache deduplicates requests and expires after two minutes",async()=>{
  let now=100, calls=0;const cache=new WarehouseCache(()=>now);const fetch=async()=>{calls++;return response;};
  await Promise.all([cache.read("alpha-world","alpha",fetch),cache.read("alpha-world","alpha",fetch)]);assert.equal(calls,1);
  now+=WAREHOUSE_TTL_MS-1;await cache.read("alpha-world","alpha",fetch);assert.equal(calls,1);
  now+=1;await cache.read("alpha-world","alpha",fetch);assert.equal(calls,2);
  cache.clear();await cache.read("alpha-world","alpha",fetch);assert.equal(calls,3);
});
test("wrong accounts, failed fetches, and late responses after clear never populate cache",async()=>{
  const cache=new WarehouseCache();
  await assert.rejects(cache.read("beta","beta",async()=>response));assert.equal(cache.fresh("beta"),undefined);
  await assert.rejects(cache.read("alpha","alpha",async()=>{throw Error("offline")}));assert.equal(cache.fresh("alpha"),undefined);
  let resolve;const pending=cache.read("alpha","alpha",()=>new Promise(r=>{resolve=r;}));await Promise.resolve();cache.clear();resolve(response);await assert.rejects(pending);assert.equal(cache.fresh("alpha"),undefined);
});
test("dashboard renders TanStack sorted rows and persists navigation, not warehouse payloads",()=>{
  const source=readFileSync(new URL("../components/control-center.tsx",import.meta.url),"utf8");
  assert.match(source,/useReactTable\(/);assert.match(source,/getSortedRowModel\(\)/);assert.match(source,/getToggleSortingHandler\(\)/);assert.match(source,/warehouseTable.getRowModel\(\).rows.map/);assert.match(source,/localStorage.setItem\("daedalus-page",target\)/);assert.ok(!source.includes('localStorage.setItem("warehouseMap"'));
});


test("TanStack numeric sorting is numeric and unknown values sort last", async()=>{
  const {createTable,getCoreRowModel,getSortedRowModel}=await import("@tanstack/react-table");
  const rows=[city(1,"alpha",2),city(2,"alpha",100),city(3,"alpha",null),city(4,"alpha",10)];
  const table=createTable({data:rows,columns:[{id:"wood",accessorFn:r=>r.resources.unsecured.wood??undefined,sortUndefined:"last"}],state:{sorting:[{id:"wood",desc:true}]},onStateChange:()=>{},renderFallbackValue:null,getCoreRowModel:getCoreRowModel(),getSortedRowModel:getSortedRowModel()});
  assert.deepEqual(table.getRowModel().rows.map(r=>r.original.city_id),[2,4,1,3]);
});


test("warehouse projection rejects malformed resource values, duplicate cities and cross-account rows",()=>{
  assert.equal(parseWarehouseResult(response,"alpha").cities[0].resources.unsecured.wood,250000);
  for(const bad of [{...response,cities:[city(1,"beta",12)]},{...response,cities:[city(1,"alpha",1),city(1,"alpha",2)]},{...response,cities:[city(1,"alpha",-1)]},{...response,cities:[city(1,"alpha","100")]}])assert.throws(()=>parseWarehouseResult(bad,"alpha"));
  const projected=parseWarehouseResult({...response,unwanted:"synthetic extra",cities:[{...city(1,"alpha",null),unwanted:"synthetic extra"}]},"alpha");
  assert.equal(projected.cities[0].resources.unsecured.wood,null);assert.equal(projected.unwanted,undefined);assert.equal(projected.cities[0].unwanted,undefined);
});
