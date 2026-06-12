"use client";
import { useState, useEffect, useRef } from "react";
import { TokenCard } from "./tabs_part1";
import {
  T, Badge, Stat, Pulse, EmptyState, ChartEmbed,
  fmtUSD, pct, shortAddr, timeAgo, scoreColor, chainCol,
  getDex, getEthTxs, sendNtfy, calcScore, sleep,
  PRESET_WATCH, SEED_WHALES,
} from "./shared";

// ─── TAB: WATCHLIST ───────────────────────────────────────────────────────────
export function WatchlistTab({running,keys,ntfyTopic,onNewAlert}) {
  const [tokens,setTokens]=useState(PRESET_WATCH.map(t=>({...t,addedAt:Date.now()/1000})));
  const [data,setData]=useState({});
  const [prevLiq,setPrevLiq]=useState({});
  const [contract,setContract]=useState("");
  const [chain,setChain]=useState("SOL");
  const [adding,setAdding]=useState(false);
  const [refreshing,setRefreshing]=useState(false);
  const [loadingIds,setLoadingIds]=useState([]);
  const alertedRef=useRef(new Set());
  const intRef=useRef(null);
  const tokensRef = useRef(tokens);
  useEffect(()=>{ tokensRef.current=tokens; },[tokens]);

  async function loadOne(token) {
    setLoadingIds(ids=>[...ids,token.id]);
    const dex=await getDex(token.contract,token.chain);
    setLoadingIds(ids=>ids.filter(i=>i!==token.id));
    if (!dex) return;
    const prev=prevLiq[token.contract]||dex.liq;
    const liqG=prev>0?((dex.liq-prev)/prev)*100:0;
    const flow=dex.buys>dex.sells*1.3?"OUT":dex.sells>dex.buys*1.3?"IN":"NEUTRAL";
    const accum=Math.abs(parseFloat(dex.ch1h||0))<3&&dex.txns>100&&dex.vol>3000;
    const {score,factors}=calcScore({...dex,src:"WATCHLIST",chain:token.chain,wc:0,flow,accum,liqG,multi:false});
    setData(p=>({...p,[token.contract]:{...dex,flow,accum,liqG,score,factors}}));
    setPrevLiq(p=>({...p,[token.contract]:dex.liq}));
    if (dex.name&&dex.name!=="UNKNOWN") setTokens(p=>p.map(t=>t.contract===token.contract?{...t,name:dex.name}:t));
    const key=token.contract+"-"+Math.floor(Date.now()/300000);
    if (!alertedRef.current.has(key)&&(liqG>25||accum||flow==="OUT")) {
      alertedRef.current.add(key);
      const emoji=score>=70?"🟢":score>=45?"🟡":"🔴";
      const reason=liqG>25?"Liquidez +"+liqG.toFixed(0)+"%":accum?"Acumulacion silenciosa":"Retiro de exchanges";
      onNewAlert({id:Date.now(),chain:token.chain,name:dex.name||token.name,contract:token.contract,source:"WATCHLIST",score,factors,ts:Math.floor(Date.now()/1000),...dex,wc:0,flow,accum,liqG,multi:false});
      sendNtfy(ntfyTopic,emoji+" "+(dex.name||token.name)+": "+reason,"Score: "+score+"/100 | Liq: "+fmtUSD(dex.liq)+" | 1h: "+pct(dex.ch1h),score>=70?"urgent":"high");
    }
  }

  async function loadAll() {
    setRefreshing(true);
    for (const t of tokensRef.current) { await loadOne(t); await sleep(600); }
    setRefreshing(false);
  }

  useEffect(()=>{ loadAll(); },[]);
  useEffect(()=>{
    if (!running) { clearInterval(intRef.current); return; }
    intRef.current=setInterval(loadAll,90000);
    return ()=>clearInterval(intRef.current);
  },[running]);

  async function addToken() {
    const c=contract.trim();
    if (!c||tokens.find(t=>t.contract.toLowerCase()===c.toLowerCase())) return;
    setAdding(true);
    const dex=await getDex(c,chain);
    const name=dex?.name||shortAddr(c);
    const tok={id:Date.now(),contract:c,chain,name,addedAt:Date.now()/1000};
    setTokens(p=>[...p,tok]);
    if (dex) {
      const flow="NEUTRAL",accum=false;
      const {score,factors}=calcScore({...dex,src:"WATCHLIST",chain,wc:0,flow,accum,liqG:0,multi:false});
      setData(p=>({...p,[c]:{...dex,flow,accum,liqG:0,score,factors}}));
    }
    setContract(""); setAdding(false);
  }

  return (
    <div>
      <div style={{background:T.bg,border:"1px solid "+T.border,borderRadius:8,padding:"10px 14px",marginBottom:14}}>
        <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",lineHeight:1.7}}>
          Monitoreo continuo de tokens especificos. Detecta liquidez, flujo de exchanges y acumulacion.
        </div>
        <div style={{display:"flex",gap:10,marginTop:8,alignItems:"center"}}>
          <span style={{fontSize:10,color:T.dim,fontFamily:"monospace"}}>{tokens.length} tokens · refresh 90s</span>
          <button onClick={loadAll} disabled={refreshing} style={{background:"transparent",border:"1px solid "+T.border,color:T.muted,padding:"3px 8px",borderRadius:4,cursor:"pointer",fontSize:9,fontFamily:"monospace"}}>
            {refreshing?"Actualizando...":"↻ Actualizar"}
          </button>
        </div>
      </div>
      <div style={{background:T.surface,border:"1px solid "+T.border,borderRadius:8,padding:12,marginBottom:14}}>
        <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",marginBottom:8}}>AGREGAR TOKEN</div>
        <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:6}}>
          <input value={contract} onChange={e=>setContract(e.target.value)} placeholder="Pega el contrato..." style={{flex:1,minWidth:180,background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 10px",color:T.text,fontFamily:"monospace",fontSize:10,outline:"none"}}/>
          <select value={chain} onChange={e=>setChain(e.target.value)} style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 10px",color:T.text,fontFamily:"monospace",fontSize:10,outline:"none"}}>
            <option value="SOL">SOL</option>
            <option value="ETH">ETH</option>
            <option value="BNB">BNB</option>
            <option value="BASE">BASE</option>
          </select>
          <button onClick={addToken} disabled={adding||!contract.trim()} style={{background:T.purple+"15",border:"1px solid "+T.purple+"33",color:T.purple,padding:"7px 14px",borderRadius:6,cursor:"pointer",fontSize:10,fontWeight:700,fontFamily:"monospace",opacity:adding?0.5:1}}>
            {adding?"...":"+ Add"}
          </button>
        </div>
      </div>
      <div style={{display:"flex",flexDirection:"column",gap:6}}>
        {tokens.map(token=>{
          const d=data[token.contract];
          const isLoading=loadingIds.includes(token.id);
          const item=d?{...token,...d}:{...token,liq:0,vol:0,ch1h:0,ch24h:0,txns:0,bp:50,buys:0,sells:0,score:0,factors:[],flow:"NEUTRAL",accum:false,liqG:0};
          if (isLoading&&!d) return (
            <div key={token.id} style={{background:T.card,border:"1px solid "+T.border,borderRadius:8,padding:"14px 16px",display:"flex",alignItems:"center",gap:10}}>
              <Badge color={chainCol(token.chain)}>{token.chain}</Badge>
              <span style={{fontSize:12,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{token.name}</span>
              <span style={{fontSize:10,color:T.dim,fontFamily:"monospace",marginLeft:"auto"}}>Cargando...</span>
              <div style={{width:16,height:16,border:"2px solid "+T.green+"22",borderTop:"2px solid "+T.green,borderRadius:"50%",animation:"spin 1s linear infinite"}}/>
            </div>
          );
          return <TokenCard key={token.id} item={item} onRemove={()=>setTokens(p=>p.filter(t=>t.id!==token.id))} accent={T.purple}/>;
        })}
      </div>
    </div>
  );
}

// ─── TAB: WHALES ──────────────────────────────────────────────────────────────
export function WhalesTab({running,ntfyTopic,onNewAlert,externalAddWhale,setExternalAddWhale}) {
  const [whales,setWhales]=useState(SEED_WHALES);
  const [activity,setActivity]=useState([]);
  const [conv,setConv]=useState([]);
  const [addr,setAddr]=useState("");
  const [chain,setChain]=useState("ETH");
  const [label,setLabel]=useState("");
  const [subTab,setSubTab]=useState("wallets");
  const buysRef=useRef({});
  const seenRef=useRef(new Set());
  const intRef=useRef(null);
  const whalesRef = useRef(whales);
  useEffect(()=>{ whalesRef.current=whales; },[whales]);

  useEffect(()=>{
    if (!externalAddWhale) return;
    const {address,chain:c,label:l}=externalAddWhale;
    if (!whales.find(w=>w.address===address)) {
      setWhales(p=>[...p,{address,label:l||shortAddr(address),chain:c,pinned:false,hits:0,trust:50,discovered:true}]);
    }
    setExternalAddWhale(null);
  },[externalAddWhale]);

  function addWhale() {
    const a=addr.trim();
    if (!a||whales.find(w=>w.address===a)) return;
    setWhales(p=>[...p,{address:a,label:label||shortAddr(a),chain,pinned:false,hits:0,trust:50}]);
    setAddr(""); setLabel("");
  }

  async function scanWhale(whale) {
    if (whale.chain!=="ETH") return;
    try {
      const txs=await getEthTxs(whale.address,"");
      const now=Date.now()/1000;
      const recent=txs.filter(tx=>now-parseInt(tx.timeStamp)<10800);
      for (const tx of recent.slice(0,3)) {
        const contract=tx.contractAddress;
        if (!contract) continue;
        const k=whale.address+"-"+contract;
        if (seenRef.current.has(k)) continue;
        const dex=await getDex(contract,"ETH");
        await sleep(300);
        if (!dex||dex.liq<5000) continue;
        seenRef.current.add(k);
        if (!buysRef.current[contract]) buysRef.current[contract]=new Set();
        buysRef.current[contract].add(whale.address);
        const wc=buysRef.current[contract].size;
        const act={id:Date.now()+Math.random(),whale:whale.label,wAddr:whale.address,chain:"ETH",token:dex.name,contract,liq:dex.liq,vol:dex.vol,ch1h:dex.ch1h,bp:dex.bp,ts:parseInt(tx.timeStamp),wc,dexLink:"https://app.uniswap.org/#/swap?outputCurrency="+contract,dexScreen:dex.dexUrl||"https://dexscreener.com/ethereum/"+contract,chartUrl:dex.chartUrl};
        setActivity(p=>[act,...p].slice(0,50));
        setWhales(p=>p.map(w=>w.address===whale.address?{...w,hits:(w.hits||0)+1,trust:Math.min(100,(w.trust||50)+2)}:w));
        if (wc>=2) {
          const ck="conv-"+contract;
          if (!seenRef.current.has(ck)) {
            seenRef.current.add(ck);
            setConv(p=>[act,...p.filter(c=>c.contract!==contract)].slice(0,15));
            const {score,factors}=calcScore({...dex,src:"WHALE",chain:"ETH",wc,flow:"NEUTRAL",accum:false,liqG:0,multi:false});
            onNewAlert({id:Date.now(),chain:"ETH",name:dex.name,contract,source:"WHALE",score,factors,ts:Math.floor(now),...dex,wc,dexLink:act.dexLink,dexScreen:act.dexScreen,chartUrl:dex.chartUrl});
            sendNtfy(ntfyTopic,"🐋 x"+wc+" "+dex.name+" — "+wc+" whales compraron","Liq: "+fmtUSD(dex.liq)+" | 1h: "+pct(dex.ch1h)+"\n"+act.dexScreen,"urgent");
          }
        }
      }
    } catch {}
  }

  async function scanAll() {
    for (const w of whalesRef.current) { await scanWhale(w); await sleep(350); }
  }

  useEffect(()=>{
    if (!running){clearInterval(intRef.current);return;}
    scanAll();
    intRef.current=setInterval(scanAll,120000);
    return ()=>clearInterval(intRef.current);
  },[running]);

  const sorted=[...whales].sort((a,b)=>(b.pinned?1:0)-(a.pinned?1:0)||(b.trust||0)-(a.trust||0));

  return (
    <div>
      {conv.length>0&&(
        <div style={{background:T.pink+"08",border:"1px solid "+T.pink+"20",borderRadius:8,padding:12,marginBottom:14}}>
          <div style={{fontSize:10,color:T.pink,fontFamily:"monospace",fontWeight:700,marginBottom:8,display:"flex",alignItems:"center",gap:6}}>
            <Pulse color={T.pink}/> <span>Compras Convergentes — {conv.length} detectadas</span>
          </div>
          {conv.slice(0,2).map(c=>(
            <div key={c.id} style={{background:T.card,border:"1px solid "+T.border,borderRadius:7,padding:"10px 12px",marginBottom:6}}>
              <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:6}}>
                <span style={{fontSize:13,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{c.token}</span>
                <Badge color={T.pink}>{"x"+c.wc+" whales"}</Badge>
                <span style={{marginLeft:"auto",fontSize:9,color:T.dim,fontFamily:"monospace"}}>{timeAgo(c.ts)}</span>
              </div>
              <div style={{display:"flex",gap:12,marginBottom:8}}>
                <Stat label="Liq" value={fmtUSD(c.liq)}/>
                <Stat label="Vol" value={fmtUSD(c.vol)}/>
                <Stat label="1h" value={pct(c.ch1h)} color={parseFloat(c.ch1h||0)>=0?T.green:T.red}/>
              </div>
              {c.chartUrl&&<div style={{marginBottom:8}}><ChartEmbed chartUrl={c.chartUrl} dexUrl={c.dexScreen} name={c.token}/></div>}
              <div style={{display:"flex",gap:5}}>
                <a href={c.dexLink} target="_blank" rel="noopener noreferrer" style={{flex:1,textAlign:"center",background:T.pink+"10",border:"1px solid "+T.pink+"30",color:T.pink,padding:"6px",borderRadius:5,fontSize:9,fontWeight:700,fontFamily:"monospace",textDecoration:"none",display:"block"}}>↗ Comprar</a>
                <a href={c.dexScreen} target="_blank" rel="noopener noreferrer" style={{flex:1,textAlign:"center",background:T.bg,border:"1px solid "+T.border,color:T.muted,padding:"6px",borderRadius:5,fontSize:9,fontWeight:700,fontFamily:"monospace",textDecoration:"none",display:"block"}}>↗ Chart</a>
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{display:"flex",borderBottom:"1px solid "+T.border,marginBottom:12}}>
        {[["wallets","Wallets"],["activity","Actividad"]].map(([k,l])=>(
          <button key={k} onClick={()=>setSubTab(k)} style={{background:"transparent",border:"none",borderBottom:"2px solid "+(subTab===k?T.pink:"transparent"),color:subTab===k?T.pink:T.muted,padding:"7px 14px",cursor:"pointer",fontSize:10,fontWeight:700,fontFamily:"monospace",marginBottom:-1}}>
            {l}<span style={{marginLeft:4,fontSize:9,color:T.dim}}>({k==="wallets"?whales.length:activity.length})</span>
          </button>
        ))}
      </div>

      {subTab==="wallets"&&(
        <>
          <div style={{background:T.surface,border:"1px solid "+T.border,borderRadius:8,padding:12,marginBottom:12}}>
            <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",marginBottom:8}}>AGREGAR WALLET</div>
            <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:6}}>
              <input value={addr} onChange={e=>setAddr(e.target.value)} placeholder="Direccion de wallet..." style={{flex:1,minWidth:160,background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 10px",color:T.text,fontFamily:"monospace",fontSize:10,outline:"none"}}/>
              <select value={chain} onChange={e=>setChain(e.target.value)} style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 10px",color:T.text,fontFamily:"monospace",fontSize:10,outline:"none"}}>
                <option value="ETH">ETH</option>
                <option value="SOL">SOL</option>
              </select>
            </div>
            <div style={{display:"flex",gap:6}}>
              <input value={label} onChange={e=>setLabel(e.target.value)} placeholder="Etiqueta..." style={{flex:1,background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 10px",color:T.text,fontFamily:"monospace",fontSize:10,outline:"none"}}/>
              <button onClick={addWhale} disabled={!addr.trim()} style={{background:T.pink+"10",border:"1px solid "+T.pink+"30",color:T.pink,padding:"7px 14px",borderRadius:6,cursor:"pointer",fontSize:10,fontWeight:700,fontFamily:"monospace"}}>+ Fijar</button>
            </div>
          </div>

          <div style={{display:"flex",flexDirection:"column",gap:5}}>
            {sorted.map(w=>(
              <div key={w.address} style={{background:T.card,border:"1px solid "+(w.pinned?T.pink+"30":w.discovered?T.orange+"20":T.border),borderLeft:"2px solid "+(w.pinned?T.pink:w.discovered?T.orange:T.dim),borderRadius:8,padding:"10px 13px",display:"flex",alignItems:"center",gap:10}}>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{display:"flex",alignItems:"center",gap:6,flexWrap:"wrap",marginBottom:2}}>
                    <span style={{fontSize:12,fontWeight:700,color:w.pinned?T.pink:T.text,fontFamily:"monospace"}}>{w.label}</span>
                    <Badge color={chainCol(w.chain)}>{w.chain}</Badge>
                    {w.discovered&&<Badge color={T.orange} small>AUTO</Badge>}
                    {w.hits>0&&(
                      <div style={{display:"flex",alignItems:"center",gap:4}}>
                        <span style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>{w.hits} hits</span>
                        <div style={{width:40,height:3,background:T.dim,borderRadius:2,overflow:"hidden"}}>
                          <div style={{width:(w.trust||50)+"%",height:"100%",background:scoreColor(w.trust||50),transition:"width 0.5s"}}/>
                        </div>
                        <span style={{fontSize:8,color:scoreColor(w.trust||50),fontFamily:"monospace"}}>{w.trust||50}%</span>
                      </div>
                    )}
                  </div>
                  <div style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>{shortAddr(w.address)}</div>
                </div>
                <div style={{display:"flex",gap:4,flexShrink:0}}>
                  <button onClick={()=>setWhales(p=>p.map(x=>x.address===w.address?{...x,pinned:!x.pinned}:x))} style={{background:w.pinned?T.pink+"15":"transparent",border:"1px solid "+(w.pinned?T.pink+"33":T.border),color:w.pinned?T.pink:T.dim,padding:"4px 7px",borderRadius:4,cursor:"pointer",fontSize:11}}>
                    {w.pinned?"📌":"📍"}
                  </button>
                  <a href={w.chain==="SOL"?"https://solscan.io/account/"+w.address:"https://etherscan.io/address/"+w.address} target="_blank" rel="noopener noreferrer" style={{background:"transparent",border:"1px solid "+T.border,color:T.dim,padding:"4px 7px",borderRadius:4,fontSize:10,textDecoration:"none",display:"flex",alignItems:"center"}}>↗</a>
                  <button onClick={()=>setWhales(p=>p.filter(x=>x.address!==w.address))} style={{background:"transparent",border:"1px solid "+T.border,color:T.dim,padding:"4px 7px",borderRadius:4,cursor:"pointer",fontSize:13}}>×</button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {subTab==="activity"&&(
        <div>
          {activity.length===0?(
            <EmptyState icon="🐋" text={running?"Esperando actividad on-chain...":"Inicia el bot para rastrear"}/>
          ):(
            <div style={{display:"flex",flexDirection:"column",gap:5}}>
              {activity.slice(0,20).map(a=>(
                <div key={a.id} style={{background:T.card,border:"1px solid "+T.border,borderRadius:8,padding:"10px 12px"}}>
                  <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:6}}>
                    <span style={{fontSize:11,fontWeight:700,color:T.pink,fontFamily:"monospace"}}>{a.whale}</span>
                    <span style={{fontSize:10,color:T.dim}}>→</span>
                    <span style={{fontSize:12,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{a.token}</span>
                    {a.wc>=2&&<Badge color={T.pink}>{"x"+a.wc}</Badge>}
                    <span style={{marginLeft:"auto",fontSize:9,color:T.dim,fontFamily:"monospace"}}>{timeAgo(a.ts)}</span>
                  </div>
                  <div style={{display:"flex",gap:12,marginBottom:7}}>
                    <Stat label="Liq" value={fmtUSD(a.liq)}/>
                    <Stat label="Vol" value={fmtUSD(a.vol)}/>
                    <Stat label="1h" value={pct(a.ch1h)} color={parseFloat(a.ch1h||0)>=0?T.green:T.red}/>
                  </div>
                  <div style={{display:"flex",gap:5}}>
                    <a href={a.dexLink} target="_blank" rel="noopener noreferrer" style={{flex:1,textAlign:"center",background:T.green+"0d",border:"1px solid "+T.green+"22",color:T.green,padding:"6px",borderRadius:5,fontSize:9,fontWeight:700,fontFamily:"monospace",textDecoration:"none",display:"block"}}>↗ Comprar</a>
                    <a href={a.dexScreen} target="_blank" rel="noopener noreferrer" style={{flex:1,textAlign:"center",background:T.bg,border:"1px solid "+T.border,color:T.muted,padding:"6px",borderRadius:5,fontSize:9,fontWeight:700,fontFamily:"monospace",textDecoration:"none",display:"block"}}>↗ Chart</a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
