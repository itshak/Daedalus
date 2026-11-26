import { NextRequest, NextResponse } from "next/server";
import { createHash } from "node:crypto";
import { serverSupabase, operatorRole } from "@/lib/supabase";
import { readBoundedBody } from "@/lib/bounded-body";
import { loginTraffic } from "@/lib/traffic-guard";
import { z } from "zod";
export const runtime="nodejs";
const headers={"Cache-Control":"private, no-store, max-age=0","Pragma":"no-cache"};
const draft=z.object({email:z.email().max(254),password:z.string().min(1).max(1024)}).strict();
const denied=()=>NextResponse.json({error:"Unable to sign in"},{status:401,headers});
export async function POST(request:NextRequest){
  if(request.headers.get("origin")!==new URL(request.url).origin)return NextResponse.json({error:"Invalid origin"},{status:403,headers});
  if(!loginTraffic.allow("global",60,60_000))return NextResponse.json({error:"Try again later"},{status:429,headers:{...headers,"Retry-After":"60"}});
  try{
    if(Number(request.headers.get("content-length")??0)>8192)return denied();
    const raw=await readBoundedBody(request.body,8192);
    const parsed=draft.safeParse(JSON.parse(raw));if(!parsed.success)return denied();
    const key=createHash("sha256").update(parsed.data.email.trim().toLowerCase()).digest("hex");
    if(!loginTraffic.allow(key,8,60_000))return NextResponse.json({error:"Try again later"},{status:429,headers:{...headers,"Retry-After":"60"}});
    const supabase=await serverSupabase();if(!supabase)return denied();
    const {data,error}=await supabase.auth.signInWithPassword(parsed.data);
    if(error||!data.user)return denied();
    // Valid provider credentials alone do not confer membership. Do not report
    // success or retain a session for an uninvited or disabled operator.
    let role: string|null = null;
    try { role = await operatorRole(supabase, data.user.id); } catch { /* fail closed */ }
    if(!role){ await supabase.auth.signOut({scope:"local"}); return denied(); }
    // Never return Supabase access/refresh tokens to JavaScript. Operator
    // membership is checked on every privileged request by authorizedOperator.
    return NextResponse.json({signedIn:true},{headers});
  }catch{return denied();}
}
