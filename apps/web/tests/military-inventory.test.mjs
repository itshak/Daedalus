import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {militaryInventory} from "../lib/military-inventory.ts";
const sample = {account_id:"alpha", observed_at:1795160000, cities:[
  {city_id:42,city_name:"Athens",troops:[{unit:"Swordsman",amount:17},{unit:"Hoplite",amount:8}],fleet:[{unit:"Ballista Ship",amount:3}]},
  {city_id:43,city_name:"Sparta",troops:[],fleet:[]} ]};
test("nested city inventory becomes real unit rows and verified empty cities",()=>{
  const result=militaryInventory(sample,"alpha");
  assert.deepEqual(result.troops.map(x=>[x.city,x.unit,x.amount]),[["Athens","Swordsman",17],["Athens","Hoplite",8],["Sparta",null,0]]);
  assert.deepEqual(result.fleet.map(x=>[x.city,x.unit,x.amount]),[["Athens","Ballista Ship",3],["Sparta",null,0]]);
});
test("wrong account, missing lists and bad counts are not zero inventory",()=>{
  assert.equal(militaryInventory(sample,"beta"),null);
  assert.equal(militaryInventory({...sample,cities:[{...sample.cities[0],troops:undefined}]},"alpha"),null);
  assert.equal(militaryInventory({...sample,cities:[{...sample.cities[0],fleet:[{unit:"Ship",amount:"3"}]}]},"alpha"),null);
  assert.equal(militaryInventory({...sample,cities:[sample.cities[0],sample.cities[0]]},"alpha"),null);
});
test("military page uses dedicated unit rendering instead of generic nested table",()=>{
  const source=readFileSync(new URL("../components/control-center.tsx",import.meta.url),"utf8");
  assert.match(source,/militaryTab==="troops"\?<MilitaryInventoryDetails data=\{militaryData\[id\]\} accountId=\{id\}/);
  assert.match(source,/formatNumber\(row.amount, locale\)/);
  assert.match(source,/unitsTable\(inventory.troops, "troops"\)/);
  assert.match(source,/unitsTable\(inventory.fleet, "fleet"\)/);
});
