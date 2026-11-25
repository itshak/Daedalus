export type ChallengeMode="stop"|"notify_and_stop";
export type ChallengePolicy={account_id:string;mode:ChallengeMode;notification_ready:boolean};
const obj=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==="object"&&!Array.isArray(v);
const mode=(v:unknown):v is ChallengeMode=>v==="stop"||v==="notify_and_stop";
export function challengeRoute(parts:string[]):boolean{return parts.length===3&&parts[0]==="accounts"&&parts[2]==="challenge-policy";}
export function validChallengeDraft(v:unknown):boolean{return obj(v)&&Object.keys(v).length===3&&mode(v.mode)&&mode(v.expected_mode)&&v.confirmed===true;}
export function parseChallengePolicy(v:unknown,account:string):ChallengePolicy{
  if(!obj(v)||Object.keys(v).length!==3||v.account_id!==account||!mode(v.mode)||typeof v.notification_ready!=="boolean")throw new Error("Invalid human challenge policy");
  return v as unknown as ChallengePolicy;
}
