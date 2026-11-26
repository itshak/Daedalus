import { NextRequest, NextResponse } from "next/server";
import { serverSupabase } from "@/lib/supabase";
export async function POST(request: NextRequest) {
  const u = new URL(request.url);
  if (request.headers.get("origin") !== u.origin)
    return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  const supabase = await serverSupabase();
  if(supabase){
    const {error}=await supabase.auth.signOut({scope:"local"});
    if(error)return NextResponse.json({error:"Sign out unavailable"},{status:503,headers:{"Cache-Control":"no-store"}});
  }
  if(request.headers.get("content-type")?.includes("application/x-www-form-urlencoded"))return NextResponse.redirect(new URL("/login",request.url),303);
  return NextResponse.json({ signedOut: true }, { headers: { "Cache-Control": "no-store" } });
}
