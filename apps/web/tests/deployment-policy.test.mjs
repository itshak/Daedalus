import test from 'node:test';
import assert from 'node:assert/strict';
import { shouldDeploy } from '../scripts/vercel-ignore-build.mjs';
const base = {env:'production',ref:'main',previous:'0.1.0-beta.1',current:'0.1.0-beta.2',lock:'0.1.0-beta.2'};
test('only increasing versions on main can deploy automatically',()=>{
  assert.equal(shouldDeploy(base),true);
  assert.equal(shouldDeploy({...base,previous:base.current}),false);
  assert.equal(shouldDeploy({...base,previous:'0.1.0'}),false);
  assert.equal(shouldDeploy({...base,current:'0.1.0',lock:'0.1.0'}),true);
  assert.equal(shouldDeploy({...base,current:'0.2.0-beta.1',lock:'0.2.0-beta.1'}),true);
  assert.equal(shouldDeploy({...base,env:'preview'}),false);
  assert.equal(shouldDeploy({...base,ref:'feature/new-version'}),false);
  assert.equal(shouldDeploy({...base,previous:undefined}),false);
  assert.equal(shouldDeploy({...base,lock:base.previous}),false);
  assert.equal(shouldDeploy({...base,current:'garbage',lock:'garbage'}),false);
});


test('configured ignore command works against real synthetic Git history',async()=>{
  const {mkdtempSync,mkdirSync,writeFileSync,copyFileSync,rmSync}=await import('node:fs');
  const {tmpdir}=await import('node:os');
  const {join}=await import('node:path');
  const {execFileSync}=await import('node:child_process');
  const {fileURLToPath}=await import('node:url');
  const folder=mkdtempSync(join(tmpdir(),'daedalus-vercel-gate-'));
  const web=join(folder,'apps','web');
  const git=(...args)=>execFileSync('git',['-C',folder,...args],{stdio:'ignore'});
  try {
    mkdirSync(join(web,'scripts'),{recursive:true});
    copyFileSync(fileURLToPath(new URL('../scripts/vercel-ignore-build.mjs',import.meta.url)),join(web,'scripts','vercel-ignore-build.mjs'));
    git('init','-q');git('config','user.name','Synthetic test');git('config','user.email','test@example.invalid');
    const commit=(v,lock=v)=>{
      writeFileSync(join(web,'package.json'),JSON.stringify({version:v}));
      writeFileSync(join(web,'package-lock.json'),JSON.stringify({version:lock,packages:{'':{version:lock}}}));
      git('add','.');git('commit','-qm','Synthetic version','--allow-empty');
    };
    const run=(env='production',ref='main')=>execFileSync(process.execPath,['scripts/vercel-ignore-build.mjs'],{cwd:web,encoding:'utf8',env:{...process.env,VERCEL_ENV:env,VERCEL_GIT_COMMIT_REF:ref}}).trim();
    commit('0.1.0-beta.1');assert.equal(run(),'SKIP');
    commit('0.1.0-beta.1');assert.equal(run(),'SKIP');
    commit('0.1.0-beta.2');assert.equal(run(),'DEPLOY');assert.equal(run('preview','feature'),'SKIP');
    commit('0.1.0-beta.3','0.1.0-beta.2');assert.equal(run(),'SKIP');
    commit('0.1.0-beta.2');assert.equal(run(),'SKIP');
  }finally{rmSync(folder,{recursive:true,force:true});}
});
