const fs=require('node:fs');
const {chromium}=require('/home/ra/.npm/_npx/9833c18b2d85bc59/node_modules/playwright');
(async()=>{
 const out='/tmp/rsf29-qa-browser';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
 const context=await browser.newContext();const page=await context.newPage();
 try {
  const load=name=>fs.readFileSync('/home/ra/Documents/ro-sprite-forge/tests/browser/'+name,'utf8').replace("evidence=root+'/docs/verification/rsf-29'","evidence='/tmp/rsf29-qa-browser'").trim().replace(/;$/,'');
  for(const [name,file] of [['primary','rsf29-mcp.js'],['workflow','rsf29-workflow-mcp.js']]){
   const result=await eval('('+load(file)+')')(page);fs.writeFileSync(out+'/'+name+'.json',JSON.stringify(result,null,2));console.log(name,JSON.stringify(result));
  }
 }finally{await context.close();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
