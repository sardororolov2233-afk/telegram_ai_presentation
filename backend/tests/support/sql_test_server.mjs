// Test-only PostgREST subset backed by real PostgreSQL in PGlite. Never deploy this server.
import { PGlite } from '@electric-sql/pglite';
import { readFile, readdir } from 'node:fs/promises';
import http from 'node:http';
const db=new PGlite();
await db.exec('create role anon;create role authenticated;create role service_role bypassrls;');
const migrations = new URL('../../supabase/migrations/', import.meta.url);
for (const name of (await readdir(migrations)).filter(name => name.endsWith('.sql')).sort()) {
  await db.exec(await readFile(new URL(name, migrations), 'utf8'));
}
const tables=new Set(['users','payments','statistics','commerce_accounts','commerce_grants','commerce_charges','commerce_jobs']);
const identifier=value=>{if(!/^[a-z_][a-z_0-9]*$/.test(value))throw Error('invalid identifier');return '"'+value+'"'};
const server=http.createServer(async(req,res)=>{
  try {
    const url=new URL(req.url,'http://localhost');
    if(url.pathname==='/health'){res.end('ok');return}
    if(req.headers.apikey!=='test-service-key'){res.writeHead(401);res.end('{}');return}
    const body=await new Promise((resolve,reject)=>{let text='';req.on('data',part=>text+=part);req.on('end',()=>{try{resolve(text?JSON.parse(text):{})}catch(e){reject(e)}})});
    const base=url.pathname.replace(/^\/rest\/v1\//,'');
    let output;
    if(base.startsWith('rpc/')){
      const name=base.slice(4);if(!name.startsWith('commerce_'))throw Error('invalid RPC');
      const args=Object.keys(body), values=Object.values(body);
      const placeholders=args.map((key,i)=>`${identifier(key)} => $${i+1}`).join(',');
      output=(await db.query(`select public.${identifier(name)}(${placeholders}) as result`,values)).rows[0].result;
    } else {
      if(!tables.has(base))throw Error('invalid table');
      const values=[],clauses=[];
      for(const [column,filter] of url.searchParams){
        if(['select','order','limit','offset'].includes(column))continue;
        const point=filter.indexOf('.'),operator=filter.slice(0,point),value=filter.slice(point+1);
        if(operator!=='eq')throw Error('unsupported test filter');
        values.push(value);clauses.push(`${identifier(column)} = $${values.length}`);
      }
      const where=clauses.length?' where '+clauses.join(' and '):'';
      if(req.method==='GET'){
        const columns=url.searchParams.get('select')||'*';
        const selection=columns==='*'?'*':columns.split(',').map(identifier).join(',');
        output=(await db.query(`select ${selection} from ${identifier(base)}${where}`,values)).rows;
      } else if(req.method==='PATCH'){
        const updates=Object.entries(body).map(([column,value])=>{values.push(value);return `${identifier(column)}=$${values.length}`});
        output=(await db.query(`update ${identifier(base)} set ${updates.join(',')}${where} returning *`,values)).rows;
      } else if(req.method==='POST'){
        const columns=Object.keys(body).map(identifier);const rows=Object.values(body);
        output=(await db.query(`insert into ${identifier(base)}(${columns.join(',')}) values(${rows.map((_,i)=>'$'+(i+1)).join(',')}) returning *`,rows)).rows;
      } else throw Error('unsupported method');
      res.setHeader('Content-Range',`0-${Math.max(0,output.length-1)}/${output.length}`);
    }
    res.setHeader('Content-Type','application/json');res.end(JSON.stringify(output,(_,value)=>typeof value==='bigint'?Number(value):value));
  } catch(error){res.writeHead(400,{'Content-Type':'application/json'});res.end(JSON.stringify({message:error.message,code:error.code||'TEST',details:'',hint:''}))}
});
server.listen(Number(process.argv[2]||0),'127.0.0.1',()=>console.log('READY '+server.address().port));
process.on('SIGTERM',()=>server.close(()=>db.close().then(()=>process.exit(0))));
