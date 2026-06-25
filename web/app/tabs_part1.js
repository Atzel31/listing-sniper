"use client";
import { useState, useEffect, useRef } from "react";
import {
  T, Badge, Stat, ScoreRing, Pulse, ChartEmbed, EmptyState,
  fmtUSD, pct, shortAddr, timeAgo, scoreColor, scoreLabel, chainCol, sendNtfy,
  pumpColor, pumpLabel, multStr, getLiveAccumData, copyText, RAILWAY_API,
} from "./shared";

// ─── PANEL DE RENDIMIENTO (tracking post-notificacion) ───────────────────────
export function PerformancePanel() {
  const [data, setData] = useState(null);
  const intRef = useRef(null);
  async function refresh() {
    const live = await getLiveAccumData();
    if (live) setData(live);
  }
  useEffect(()=>{
    refresh();
    intRef.current = setInterval(refresh, 120000);
    return ()=>clearInterval(intRef.current);
  },[]);

  if (!data) return null;
  const tracking = data.tracking || [];
  const rugged = data.rugged || [];
  if (!tracking.length && !rugged.length) return null;

  const pumped = tracking.filter(t=>t.max_mult>=1.3);
  const active = tracking.filter(t=>t.status==="tracking");
  const winRate = tracking.length ? Math.round((pumped.length/tracking.length)*100) : 0;
  const best = tracking.reduce((a,t)=>(t.max_mult>(a?.max_mult||0)?t:a), null);

  return (
    <div style={{background:T.green+"06",border:"1px solid "+T.green+"20",borderRadius:8,padding:"12px 14px",marginBottom:14}}>
      <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10,flexWrap:"wrap"}}>
        <span style={{fontSize:11,color:T.green,fontFamily:"monospace",fontWeight:700}}>📊 Rendimiento de alertas</span>
        <Pulse color={T.green}/>
      </div>
      <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:tracking.length?10:0}}>
        <div style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 12px",flex:1,minWidth:75}}>
          <div style={{fontSize:8,color:T.muted,fontFamily:"monospace"}}>TRACKEADOS</div>
          <div style={{fontSize:16,fontWeight:900,color:T.text,fontFamily:"monospace"}}>{tracking.length}</div>
        </div>
        <div style={{background:T.green+"0a",border:"1px solid "+T.green+"22",borderRadius:6,padding:"7px 12px",flex:1,minWidth:75}}>
          <div style={{fontSize:8,color:T.green,fontFamily:"monospace"}}>PUMPEARON</div>
          <div style={{fontSize:16,fontWeight:900,color:T.green,fontFamily:"monospace"}}>{pumped.length}</div>
        </div>
        <div style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 12px",flex:1,minWidth:75}}>
          <div style={{fontSize:8,color:T.muted,fontFamily:"monospace"}}>WIN RATE</div>
          <div style={{fontSize:16,fontWeight:900,color:pumpColor(winRate),fontFamily:"monospace"}}>{winRate}%</div>
        </div>
        <div style={{background:T.red+"0a",border:"1px solid "+T.red+"22",borderRadius:6,padding:"7px 12px",flex:1,minWidth:75}}>
          <div style={{fontSize:8,color:T.red,fontFamily:"monospace"}}>RUGPULLS</div>
          <div style={{fontSize:16,fontWeight:900,color:T.red,fontFamily:"monospace"}}>{rugged.length}</div>
        </div>
      </div>
      {best&&best.max_mult>1.05&&(
        <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",marginBottom:8}}>
          Mejor resultado: <span style={{color:T.green,fontWeight:700}}>{best.symbol} {multStr(best.max_mult)}</span>
          {" "}(prob. era {best.pump_prob}%)
        </div>
      )}
      {tracking.length>0&&(
        <div style={{maxHeight:200,overflowY:"auto"}}>
          {tracking.slice(0,12).map((t,i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",gap:8,padding:"5px 0",borderBottom:"1px solid "+T.bg}}>
              <Badge color={chainCol(t.chain)} small>{t.chain}</Badge>
              <span style={{fontSize:10,fontWeight:700,color:T.text,fontFamily:"monospace",flex:1}}>{t.symbol}</span>
              {t.status==="rugged"
                ? <Badge color={T.red} small>RUG</Badge>
                : <span style={{fontSize:10,fontWeight:700,fontFamily:"monospace",color:t.max_mult>=1.3?T.green:t.max_mult>=1?T.muted:T.red}}>{multStr(t.max_mult||1)}</span>
              }
              <span style={{fontSize:8,color:T.dim,fontFamily:"monospace"}}>prob {t.pump_prob}%</span>
            </div>
          ))}
        </div>
      )}
      {rugged.length>0&&(
        <div style={{marginTop:10}}>
          <div style={{fontSize:9,color:T.red,fontFamily:"monospace",fontWeight:700,marginBottom:5}}>RUGPULLS DETECTADOS</div>
          {rugged.slice(0,5).map((r,i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",gap:8,padding:"3px 0"}}>
              <Badge color={chainCol(r.chain)} small>{r.chain}</Badge>
              <span style={{fontSize:10,color:T.muted,fontFamily:"monospace",flex:1}}>{r.symbol}</span>
              <span style={{fontSize:9,color:T.red,fontFamily:"monospace"}}>-{r.liq_drop_pct}% liq</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ─── TOKEN CARD ───────────────────────────────────────────────────────────────
export function TokenCard({item, onRemove, accent}) {
  const [open,setOpen]=useState(false);
  const [copied,setCopied]=useState(false);
  const sc=item.score||0, color=scoreColor(sc);
  const borderColor = accent||color;
  const isNew = item.ts&&(Date.now()/1000-item.ts)<90;
  const pc1h=parseFloat(item.ch1h||0), pc24h=parseFloat(item.ch24h||0);
  const buyLink = item.chain==="SOL"?"https://jup.ag/swap/SOL-"+item.contract:"https://app.uniswap.org/#/swap?outputCurrency="+item.contract;
  const dexLink = item.dexUrl||("https://dexscreener.com/"+(item.chain==="SOL"?"solana":"ethereum")+"/"+item.contract);
  function copy(){navigator.clipboard.writeText(item.contract).then(()=>{setCopied(true);setTimeout(()=>setCopied(false),2000)});}

  return (
    <div style={{
      background:T.card,
      border:"1px solid "+(open?borderColor+"44":T.border),
      borderLeft:"2px solid "+(sc>0?borderColor:T.dim),
      borderRadius:10,overflow:"hidden",transition:"border-color 0.2s",
      animation:isNew?"slideDown 0.3s ease":"none",
    }}>
      <div onClick={()=>setOpen(o=>!o)} style={{padding:"12px 14px",cursor:"pointer",display:"flex",alignItems:"center",gap:12,opacity:item.status==="rugged"?0.5:1}}>
        <div style={{display:"flex",flexDirection:"column",gap:4,flexShrink:0}}>
          <Badge color={chainCol(item.chain)}>{item.chain}</Badge>
          {item.source==="DEXSCREENER"
            ? <Badge color={T.orange} small>💰 BOOSTED</Badge>
            : item.source&&item.source!=="WATCHLIST"&&item.source!=="NEW_PAIR"
              ? <Badge color={T.green} small>{item.source}</Badge>
              : item.source==="NEW_PAIR"&&<Badge color="#555" small>NUEVO PAR</Badge>}
        </div>
        <div style={{flex:1,minWidth:0}}>
          <div style={{display:"flex",alignItems:"center",gap:5,flexWrap:"wrap",marginBottom:5}}>
            <span style={{fontSize:14,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{item.name||"—"}</span>
            {item.price&&parseFloat(item.price)>0&&<span style={{fontSize:10,color:T.muted,fontFamily:"monospace"}}>${parseFloat(item.price).toFixed(6)}</span>}
            {isNew&&<Badge color={T.green}>NUEVO</Badge>}
            {item.isNew&&<Badge color={T.cyan}>PAR NUEVO</Badge>}
            {(item.wc||0)>1&&<Badge color={T.pink}>{"🐋 x"+item.wc}</Badge>}
            {(item.insiders||0)>0&&<Badge color={T.orange}>{"🎯 "+item.insiders+" insiders"}</Badge>}
            {item.accum&&<Badge color={T.purple}>ACUM</Badge>}
            {item.flow==="OUT"&&<Badge color={T.green}>↑ RETIRO</Badge>}
            {item.multi&&<Badge color={T.blue}>MULTI-EX</Badge>}
            {item.pump_prob!==undefined&&item.pump_prob!==null&&(
              <Badge color={item.pump_prob>=70?T.green:item.pump_prob>=45?T.yellow:T.red}>
                {"⚡ Pump "+item.pump_prob+"%"}
              </Badge>
            )}
            {item.status==="rugged"&&<Badge color={T.red}>💀 RUGPULL</Badge>}
            {(item.status==="pumped"||item.max_mult>=1.3)&&item.max_mult&&(
              <Badge color={T.green}>{"📈 "+(item.max_mult>=2?"x"+item.max_mult.toFixed(1):"+"+((item.max_mult-1)*100).toFixed(0)+"%")}</Badge>
            )}
          </div>
          <div style={{display:"flex",gap:12,flexWrap:"wrap"}}>
            <Stat label="Liq" value={fmtUSD(item.liq)}/>
            <Stat label="Vol 24h" value={fmtUSD(item.vol)}/>
            <Stat label="1h" value={pct(item.ch1h)} color={pc1h>=0?T.green:T.red}/>
            <Stat label="24h" value={pct(item.ch24h)} color={pc24h>=0?T.green:T.red}/>
            {item.txns>0&&<Stat label="Txns" value={item.txns}/>}
            {item.ageHours!==null&&item.ageHours!==undefined&&<Stat label="Edad" value={item.ageHours+"h"}/>}
          </div>
        </div>
        {sc>0&&<ScoreRing score={sc}/>}
        {onRemove&&(
          <button onClick={e=>{e.stopPropagation();onRemove();}} style={{background:"transparent",border:"none",color:T.dim,cursor:"pointer",fontSize:16,padding:"4px",flexShrink:0}}>×</button>
        )}
      </div>

      {open&&(
        <div onClick={e=>e.stopPropagation()} style={{padding:"0 14px 14px",borderTop:"1px solid "+T.border}}>
          <div style={{display:"flex",gap:6,marginTop:12,flexWrap:"wrap",marginBottom:12}}>
            {[
              {l:"FLUJO EX",v:item.flow==="OUT"?"↑ Retiro":item.flow==="IN"?"↓ Deposito":"Neutral",c:item.flow==="OUT"?T.green:item.flow==="IN"?T.red:T.dim},
              {l:"ACUMULACION",v:item.accum?"Detectada":"No",c:item.accum?T.purple:T.dim},
              {l:"BUYS / SELLS",v:(item.buys||0)+" / "+(item.sells||0),c:T.text},
              {l:"FDV",v:fmtUSD(item.fdv),c:T.muted},
            ].map(s=>(
              <div key={s.l} style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 10px",flex:1,minWidth:70}}>
                <div style={{fontSize:8,color:T.muted,fontFamily:"monospace",marginBottom:3}}>{s.l}</div>
                <div style={{fontSize:10,fontWeight:700,color:s.c,fontFamily:"monospace"}}>{s.v}</div>
              </div>
            ))}
          </div>

          {item.earlyBuyers&&item.earlyBuyers.length>0&&(
            <div style={{background:T.orange+"08",border:"1px solid "+T.orange+"22",borderRadius:8,padding:"10px 12px",marginBottom:12}}>
              <div style={{fontSize:9,color:T.orange,fontFamily:"monospace",fontWeight:700,marginBottom:8,display:"flex",alignItems:"center",gap:6}}>
                <span>🎯</span><span>COMPRADORES TEMPRANOS (pre-pump)</span>
              </div>
              {item.earlyBuyers.slice(0,5).map((b,i)=>(
                <div key={b.address} style={{display:"flex",alignItems:"center",gap:8,padding:"4px 0",borderBottom:"1px solid "+T.border}}>
                  <span style={{fontSize:9,color:T.dim,fontFamily:"monospace",minWidth:16}}>#{i+1}</span>
                  <a href={"https://etherscan.io/address/"+b.address} target="_blank" rel="noopener noreferrer"
                    style={{fontSize:9,color:T.orange,fontFamily:"monospace",textDecoration:"none",flex:1}}>
                    {shortAddr(b.address)}
                  </a>
                  <span style={{fontSize:9,color:T.muted,fontFamily:"monospace"}}>{b.txCount} txns</span>
                  <span style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>{timeAgo(b.firstBuy)}</span>
                  {item.knownWhales&&item.knownWhales.includes(b.address.toLowerCase())&&(
                    <Badge color={T.pink} small>WHALE</Badge>
                  )}
                </div>
              ))}
            </div>
          )}

          {item.factors&&item.factors.length>0&&(
            <div style={{marginBottom:12}}>
              <div style={{fontSize:9,color:T.muted,fontFamily:"monospace",marginBottom:6}}>SCORE BREAKDOWN</div>
              {item.factors.map((f,i)=>(
                <div key={i} style={{display:"flex",justifyContent:"space-between",fontSize:9,padding:"2px 0",borderBottom:"1px solid "+T.bg}}>
                  <span style={{color:T.muted}}>{f.l}</span>
                  <span style={{color:f.p?T.green:T.red,fontFamily:"monospace",fontWeight:700}}>{f.v}</span>
                </div>
              ))}
              <div style={{display:"flex",justifyContent:"space-between",paddingTop:5}}>
                <span style={{fontSize:10,color:T.muted,fontWeight:700}}>TOTAL</span>
                <span style={{fontSize:12,color:scoreColor(sc),fontWeight:900,fontFamily:"monospace"}}>{sc}/100</span>
              </div>
            </div>
          )}

          <div style={{marginBottom:10}}>
            <ChartEmbed chartUrl={item.chartUrl} dexUrl={dexLink} name={item.name||"token"}/>
          </div>

          <div style={{marginBottom:10}}>
            <div style={{fontSize:8,color:T.muted,fontFamily:"monospace",marginBottom:5}}>CONTRATO</div>
            <div style={{display:"flex",gap:6,alignItems:"center"}}>
              <code style={{flex:1,fontSize:9,color:T.dim,fontFamily:"monospace",wordBreak:"break-all",background:T.bg,border:"1px solid "+T.border,borderRadius:5,padding:"6px 8px"}}>{item.contract}</code>
              <button onClick={copy} style={{background:copied?T.green+"15":"transparent",border:"1px solid "+(copied?T.green+"44":T.border),color:copied?T.green:T.muted,padding:"6px 10px",borderRadius:5,cursor:"pointer",fontSize:9,fontWeight:700,fontFamily:"monospace",flexShrink:0,transition:"all 0.2s"}}>
                {copied?"✓":"Copiar"}
              </button>
            </div>
          </div>

          <div style={{display:"flex",gap:6}}>
            <a href={buyLink} target="_blank" rel="noopener noreferrer" style={{flex:1,textAlign:"center",background:T.green+"10",border:"1px solid "+T.green+"33",color:T.green,padding:"8px",borderRadius:6,fontSize:10,fontWeight:700,fontFamily:"monospace",textDecoration:"none",display:"block"}}>
              {item.chain==="SOL"?"↗ Jupiter":"↗ Uniswap"}
            </a>
            <a href={dexLink} target="_blank" rel="noopener noreferrer" style={{flex:1,textAlign:"center",background:T.bg,border:"1px solid "+T.border,color:T.muted,padding:"8px",borderRadius:6,fontSize:10,fontWeight:700,fontFamily:"monospace",textDecoration:"none",display:"block"}}>
              ↗ DexScreener
            </a>
          </div>
          {item.ts&&<div style={{marginTop:8,fontSize:8,color:T.dim,fontFamily:"monospace",textAlign:"right"}}>detectado {timeAgo(item.ts)}</div>}
        </div>
      )}
    </div>
  );
}

// ─── SETUP ────────────────────────────────────────────────────────────────────
export function Setup({onSave,initial}) {
  const [ethKey,setEthKey]=useState(initial?.ethKey||"");
  const [topic,setTopic]=useState(initial?.ntfyTopic||"");
  const [githubRepo,setGithubRepo]=useState(initial?.githubRepo||"Atzel31/listing-sniper");
  const [pumpThreshold,setPumpThreshold]=useState(initial?.pumpThreshold||30);
  const [state,setState]=useState("idle");
  async function test(){
    setState("sending");
    await sendNtfy(topic,"Alpha Terminal conectado","Notificaciones funcionando correctamente.","high");
    setState("sent"); setTimeout(()=>setState("idle"),4000);
  }
  const inp={width:"100%",background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"8px 10px",color:T.text,fontFamily:"monospace",fontSize:11,outline:"none",boxSizing:"border-box"};
  return (
    <div style={{position:"fixed",inset:0,zIndex:300,background:"rgba(0,0,0,0.97)",display:"flex",alignItems:"center",justifyContent:"center",padding:20,overflowY:"auto"}}>
      <div style={{background:T.surface,border:"1px solid "+T.border,borderRadius:12,padding:28,width:"100%",maxWidth:400,margin:"auto"}}>
        <div style={{fontSize:18,fontWeight:700,color:T.text,marginBottom:4}}>Alpha Terminal</div>
        <div style={{fontSize:11,color:T.muted,fontFamily:"monospace",marginBottom:24}}>Configuracion</div>

        <div style={{marginBottom:16}}>
          <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",marginBottom:6}}>CANAL NTFY</div>
          <input style={inp} value={topic} onChange={e=>setTopic(e.target.value.trim())} placeholder="ej: listingsniper-atzel"/>
          {topic&&<button onClick={test} style={{marginTop:8,width:"100%",background:state==="sent"?T.green+"15":"transparent",border:"1px solid "+(state==="sent"?T.green+"44":T.border),color:state==="sent"?T.green:T.muted,padding:"7px",borderRadius:6,cursor:"pointer",fontSize:10,fontFamily:"monospace",fontWeight:700}}>
            {state==="sending"?"Enviando...":(state==="sent"?"✓ Revisa tu celular":"Probar notificacion")}
          </button>}
        </div>

        <div style={{marginBottom:16}}>
          <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",marginBottom:6,display:"flex",justifyContent:"space-between"}}>
            <span>ETHERSCAN API KEY <span style={{color:T.dim}}>(opcional)</span></span>
            <a href="https://etherscan.io/apis" target="_blank" rel="noopener noreferrer" style={{color:T.dim,fontSize:9,textDecoration:"none"}}>gratis →</a>
          </div>
          <input style={inp} value={ethKey} onChange={e=>setEthKey(e.target.value)} placeholder="Mejora el scan de ETH"/>
        </div>

        <div style={{marginBottom:16}}>
          <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",marginBottom:6}}>
            REPO GITHUB <span style={{color:T.dim}}>(para reporte semanal)</span>
          </div>
          <input style={inp} value={githubRepo} onChange={e=>setGithubRepo(e.target.value)} placeholder="usuario/repo"/>
        </div>

        <div style={{marginBottom:20}}>
          <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",marginBottom:6,display:"flex",justifyContent:"space-between"}}>
            <span>UMBRAL DE PUMP PARA INSIDERS</span>
            <span style={{color:T.orange,fontWeight:700}}>+{pumpThreshold}%</span>
          </div>
          <input type="range" min={10} max={100} step={5} value={pumpThreshold}
            onChange={e=>setPumpThreshold(Number(e.target.value))}
            style={{width:"100%",accentColor:T.orange}}/>
        </div>

        <div style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"8px 10px",marginBottom:16,fontSize:9,color:T.dim,fontFamily:"monospace",lineHeight:1.7}}>
          Keys en memoria local del navegador. El modulo de Acumulacion lee datos en vivo de Railway.
        </div>

        <button onClick={()=>onSave({ethKey,ntfyTopic:topic,pumpThreshold,githubRepo})} style={{width:"100%",background:T.green+"15",border:"1px solid "+T.green+"44",color:T.green,padding:"10px",borderRadius:7,cursor:"pointer",fontSize:11,fontWeight:700,fontFamily:"monospace"}}>
          Iniciar
        </button>
      </div>
    </div>
  );
}

// ─── TAB: SNIPER ──────────────────────────────────────────────────────────────
export function SniperTab({alerts,running,scanning,countdown,scanLog,ruggedSet={}}) {
  const [filter,setFilter]=useState("ALL");
  // Marcar las que ruggearon segun el bot
  const marked = alerts.map(a=>{
    const rug = a.contract && ruggedSet[a.contract.toLowerCase()];
    return rug ? {...a, status:"rugged", rugData:rug} : a;
  });
  const vis=marked.filter(a=>{
    if(filter==="ETH") return a.chain==="ETH";
    if(filter==="SOL") return a.chain==="SOL";
    if(filter==="HIGH") return a.score>=70 && a.status!=="rugged";
    if(filter==="WHALE") return (a.wc||0)>=1;
    if(filter==="BOOSTED") return a.source==="DEXSCREENER";
    if(filter==="HIDE_RUG") return a.status!=="rugged";
    return true;
  }).sort((x,y)=>{
    // Rugpulls siempre al fondo
    if((x.status==="rugged")!==(y.status==="rugged")) return x.status==="rugged"?1:-1;
    return 0;
  });
  const hc=alerts.filter(a=>a.score>=70).length;
  const mc=alerts.filter(a=>a.score>=45&&a.score<70).length;
  const lc=alerts.filter(a=>a.score<45).length;
  const rugCount=marked.filter(a=>a.status==="rugged").length;
  return (
    <div>
      <div style={{display:"flex",gap:8,marginBottom:14,flexWrap:"wrap",alignItems:"center"}}>
        {[[hc,"Bajo riesgo",T.green],[mc,"Medio",T.yellow],[lc,"Alto",T.red]].map(([n,l,c])=>(
          <div key={l} style={{background:c+"0d",border:"1px solid "+c+"22",borderRadius:6,padding:"5px 12px",display:"flex",alignItems:"center",gap:8}}>
            <span style={{fontSize:18,fontWeight:700,color:c,fontFamily:"monospace"}}>{n}</span>
            <span style={{fontSize:10,color:c,fontFamily:"monospace"}}>{l}</span>
          </div>
        ))}
        {rugCount>0&&(
          <div style={{background:T.red+"0d",border:"1px solid "+T.red+"22",borderRadius:6,padding:"5px 12px",display:"flex",alignItems:"center",gap:8}}>
            <span style={{fontSize:18,fontWeight:700,color:T.red,fontFamily:"monospace"}}>{rugCount}</span>
            <span style={{fontSize:10,color:T.red,fontFamily:"monospace"}}>💀 rug</span>
          </div>
        )}
        <span style={{marginLeft:"auto",fontSize:10,fontFamily:"monospace",color:scanning?T.yellow:running?T.green:T.muted}}>
          {scanning?"Escaneando...":running?("Prox. "+countdown+"s"):"Inactivo"}
        </span>
      </div>
      <div style={{display:"flex",gap:4,marginBottom:12,flexWrap:"wrap"}}>
        {[["ALL","Todas"],["ETH","ETH"],["SOL","SOL"],["HIGH","Bajo riesgo"],["WHALE","Whales"],["BOOSTED","💰 Boosted"],["HIDE_RUG","Ocultar rugs"]].map(([k,l])=>(
          <button key={k} onClick={()=>setFilter(k)} style={{background:filter===k?T.green+"0d":"transparent",border:"1px solid "+(filter===k?T.green+"33":T.border),color:filter===k?T.green:T.muted,padding:"4px 10px",borderRadius:5,cursor:"pointer",fontSize:10,fontFamily:"monospace",fontWeight:filter===k?700:400}}>{l}</button>
        ))}
        {vis.length>0&&<span style={{marginLeft:"auto",fontSize:10,color:T.dim,fontFamily:"monospace",alignSelf:"center"}}>{vis.length} alertas</span>}
      </div>
      {running&&scanLog.length>0&&(
        <div style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 10px",marginBottom:12,maxHeight:56,overflowY:"auto"}}>
          {scanLog.slice(0,3).map((l,i)=><div key={i} style={{fontSize:8,color:i===0?T.dim:"#1a1a1a",fontFamily:"monospace",lineHeight:1.8}}>{l}</div>)}
        </div>
      )}
      {vis.length===0?(
        <EmptyState icon="◈" text={scanning?"Consultando APIs...":running?"Esperando siguiente ciclo":"Presiona Start para comenzar"}/>
      ):(
        <div style={{display:"flex",flexDirection:"column",gap:6}}>
          {vis.map(a=><TokenCard key={a.id} item={a}/>)}
        </div>
      )}
    </div>
  );
}

// ─── TAB: NUEVOS TOKENS ───────────────────────────────────────────────────────
export function NewPairsTab({newPairs,running,scanning,ruggedSet={}}) {
  const [filter,setFilter]=useState("ALL");
  const marked = newPairs.map(p=>{
    const rug = p.contract && ruggedSet[p.contract.toLowerCase()];
    return rug ? {...p, status:"rugged", rugData:rug} : p;
  });
  const vis=marked.filter(p=>{
    if(filter==="ETH") return p.chain==="ETH";
    if(filter==="SOL") return p.chain==="SOL";
    if(filter==="HOT") return parseFloat(p.ch1h||0)>20 && p.status!=="rugged";
    if(filter==="PUMP") return (p.pump_prob||0)>=60 && p.status!=="rugged";
    if(filter==="HIDE_RUG") return p.status!=="rugged";
    return true;
  }).sort((x,y)=>{
    if((x.status==="rugged")!==(y.status==="rugged")) return x.status==="rugged"?1:-1;
    return 0;
  });
  const rugCount=marked.filter(p=>p.status==="rugged").length;
  return (
    <div>
      <div style={{background:T.cyan+"08",border:"1px solid "+T.cyan+"20",borderRadius:8,padding:"10px 14px",marginBottom:14}}>
        <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4}}>
          <span style={{fontSize:11,color:T.cyan,fontFamily:"monospace",fontWeight:700}}>⚡ Scanner de Tokens Nuevos</span>
          {running&&<Pulse color={T.cyan}/>}
        </div>
        <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",lineHeight:1.6}}>
          Pares nuevos en ETH y SOL con filtros reforzados. Cada alerta incluye probabilidad de pump y se trackea su rendimiento.
        </div>
      </div>
      <PerformancePanel/>
      <div style={{display:"flex",gap:4,marginBottom:12,flexWrap:"wrap"}}>
        {[["ALL","Todos"],["ETH","ETH"],["SOL","SOL"],["HOT","🔥 Pump >20%"],["PUMP","⚡ Prob alta"],["HIDE_RUG","Ocultar rugs"]].map(([k,l])=>(
          <button key={k} onClick={()=>setFilter(k)} style={{background:filter===k?T.cyan+"0d":"transparent",border:"1px solid "+(filter===k?T.cyan+"33":T.border),color:filter===k?T.cyan:T.muted,padding:"4px 10px",borderRadius:5,cursor:"pointer",fontSize:10,fontFamily:"monospace",fontWeight:filter===k?700:400}}>{l}</button>
        ))}
        {rugCount>0&&<span style={{fontSize:9,color:T.red,fontFamily:"monospace",alignSelf:"center"}}>{rugCount} 💀</span>}
        {vis.length>0&&<span style={{marginLeft:"auto",fontSize:10,color:T.dim,fontFamily:"monospace",alignSelf:"center"}}>{vis.length} pares</span>}
      </div>
      {vis.length===0?(
        <EmptyState icon="⚡" text={scanning?"Buscando pares nuevos...":running?"Esperando siguiente ciclo":"Presiona Start para comenzar"}/>
      ):(
        <div style={{display:"flex",flexDirection:"column",gap:6}}>
          {vis.map(p=><TokenCard key={p.id} item={p} accent={T.cyan}/>)}
        </div>
      )}
    </div>
  );
}

// ─── TAB: INSIDERS ────────────────────────────────────────────────────────────
// ─── CARD DE WALLET (con copiar direccion y portfolio expandible) ────────────
function WalletCard({w, rank, tagInfo}) {
  const [copied, setCopied] = useState(false);
  const [showPort, setShowPort] = useState(false);
  const [port, setPort] = useState(null);
  const [loadingPort, setLoadingPort] = useState(false);
  const ti = tagInfo[w.tag] || tagInfo.smart;
  const explorer = w.chain==="ETH"?"https://etherscan.io/address/":w.chain==="BNB"?"https://bscscan.com/address/":w.chain==="BASE"?"https://basescan.org/address/":"https://solscan.io/account/";

  function doCopy(e) {
    e.stopPropagation();
    if (copyText(w.address)) { setCopied(true); setTimeout(()=>setCopied(false), 1500); }
  }
  async function togglePort(e) {
    e.stopPropagation();
    if (showPort) { setShowPort(false); return; }
    setShowPort(true);
    if (port===null && w.chain!=="SOL") {
      setLoadingPort(true);
      try {
        const r = await fetch(RAILWAY_API+"/api/portfolio/"+w.chain+"/"+w.address);
        const d = await r.json();
        setPort(d.holdings||[]);
      } catch { setPort([]); }
      setLoadingPort(false);
    }
  }

  return (
    <div style={{background:T.card,border:"1px solid "+(w.tag==="insider_activo"?T.red+"33":T.border),borderLeft:"3px solid "+ti.color,borderRadius:10,padding:"12px 14px"}}>
      <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:8}}>
        <div style={{fontSize:15,fontWeight:900,color:rank<=3?ti.color:T.dim,fontFamily:"monospace",minWidth:24}}>#{rank}</div>
        <div style={{flex:1,minWidth:0}}>
          <div style={{display:"flex",alignItems:"center",gap:6,flexWrap:"wrap",marginBottom:3}}>
            <Badge color={ti.color}>{ti.label}</Badge>
            <Badge color={chainCol(w.chain)} small>{w.chain}</Badge>
            {w.tracked&&<Badge color={T.green} small>SIGUIENDO</Badge>}
            {w.forensic&&<Badge color={T.orange} small>📜 FORENSE</Badge>}
          </div>
          <div style={{display:"flex",alignItems:"center",gap:6}}>
            <a href={explorer+w.address} target="_blank" rel="noopener noreferrer" style={{fontSize:10,color:T.muted,fontFamily:"monospace",textDecoration:"none"}}>{shortAddr(w.address)} ↗</a>
            <button onClick={doCopy} style={{background:copied?T.green+"15":"transparent",border:"1px solid "+(copied?T.green+"44":T.border),color:copied?T.green:T.dim,padding:"1px 6px",borderRadius:4,cursor:"pointer",fontSize:8,fontFamily:"monospace"}}>{copied?"✓ copiado":"copiar"}</button>
            {w.chain!=="SOL"&&<button onClick={togglePort} style={{background:showPort?T.purple+"15":"transparent",border:"1px solid "+(showPort?T.purple+"44":T.border),color:showPort?T.purple:T.dim,padding:"1px 6px",borderRadius:4,cursor:"pointer",fontSize:8,fontFamily:"monospace"}}>portfolio</button>}
          </div>
        </div>
        <div style={{textAlign:"center",flexShrink:0}}>
          <div style={{fontSize:18,fontWeight:900,color:ti.color,fontFamily:"monospace",lineHeight:1}}>{w.insider_score}</div>
          <div style={{fontSize:7,color:T.muted,fontFamily:"monospace"}}>SCORE</div>
        </div>
      </div>
      <div style={{display:"flex",gap:10,flexWrap:"wrap",marginBottom:8}}>
        <Stat label="Coincidencias" value={w.n_tokens+" tokens"} color={ti.color}/>
        {w.total_usd>0&&<Stat label="Dinero movido" value={fmtUSD(w.total_usd)} color={T.green}/>}
        <Stat label="Compras" value={w.buys}/>
        {w.last_seen>0&&<Stat label="Ultima vez" value={timeAgo(w.last_seen)}/>}
      </div>
      {w.tokens&&w.tokens.length>0&&(
        <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>
          {w.tokens.map(t=><Badge key={t} color={T.purple} small>{t}</Badge>)}
        </div>
      )}
      {showPort&&(
        <div style={{marginTop:10,paddingTop:10,borderTop:"1px solid "+T.border}}>
          <div style={{fontSize:8,color:T.purple,fontFamily:"monospace",fontWeight:700,marginBottom:6}}>PORTFOLIO ACTUAL (tokens que tiene)</div>
          {loadingPort&&<div style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>Consultando...</div>}
          {!loadingPort&&port&&port.length===0&&<div style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>Sin holdings visibles con datos gratuitos</div>}
          {!loadingPort&&port&&port.length>0&&(
            <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>
              {port.map((h,i)=>(
                <a key={i} href={"https://dexscreener.com/"+(w.chain==="ETH"?"ethereum":w.chain==="BNB"?"bsc":"base")+"/"+h.contract} target="_blank" rel="noopener noreferrer" style={{textDecoration:"none"}}>
                  <Badge color={T.cyan} small>{h.symbol} ↗</Badge>
                </a>
              ))}
            </div>
          )}
          <div style={{fontSize:7,color:T.dim,fontFamily:"monospace",marginTop:6}}>Vista superficial via transferencias. No es valoracion exacta.</div>
        </div>
      )}
    </div>
  );
}

// ─── EXAMINADOR MANUAL DE WALLETS ─────────────────────────────────────────────
function WalletExaminer() {
  const [open, setOpen] = useState(false);
  const [addr, setAddr] = useState("");
  const [chain, setChain] = useState("ETH");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);

  const vColors = {red:T.red, gray:T.dim, green:T.green, yellow:T.yellow};

  async function examine() {
    if (!addr.trim()) return;
    setLoading(true); setResult(null); setAdded(false);
    try {
      const r = await fetch(RAILWAY_API+"/api/examine/"+chain+"/"+addr.trim());
      const d = await r.json();
      setResult(d);
    } catch { setResult({error:"No se pudo conectar con Railway"}); }
    setLoading(false);
  }
  async function addToTracking() {
    setAdding(true);
    try {
      const r = await fetch(RAILWAY_API+"/api/add_wallet/"+chain+"/"+addr.trim());
      const d = await r.json();
      if (d.status==="added") setAdded(true);
    } catch {}
    setAdding(false);
  }

  return (
    <div style={{background:T.purple+"08",border:"1px solid "+T.purple+"25",borderRadius:10,marginBottom:14,overflow:"hidden"}}>
      <div onClick={()=>setOpen(o=>!o)} style={{padding:"10px 14px",cursor:"pointer",display:"flex",alignItems:"center",gap:8}}>
        <span style={{fontSize:11,color:T.purple,fontFamily:"monospace",fontWeight:700}}>🔬 Examinar wallet manualmente</span>
        <span style={{marginLeft:"auto",fontSize:12,color:T.purple}}>{open?"−":"+"}</span>
      </div>
      {open&&(
        <div style={{padding:"0 14px 14px"}}>
          <div style={{fontSize:9,color:T.muted,fontFamily:"monospace",marginBottom:10,lineHeight:1.5}}>
            Pega una direccion y el bot la analiza: comportamiento, coincidencias con tu lista, portfolio y un veredicto. Solo ETH/BNB/BASE.
          </div>
          <div style={{display:"flex",gap:6,marginBottom:8,flexWrap:"wrap"}}>
            {["ETH","BNB","BASE"].map(c=>(
              <button key={c} onClick={()=>setChain(c)} style={{background:chain===c?T.purple+"15":"transparent",border:"1px solid "+(chain===c?T.purple+"44":T.border),color:chain===c?T.purple:T.muted,padding:"3px 10px",borderRadius:5,cursor:"pointer",fontSize:9,fontFamily:"monospace",fontWeight:700}}>{c}</button>
            ))}
          </div>
          <div style={{display:"flex",gap:6,marginBottom:10}}>
            <input value={addr} onChange={e=>setAddr(e.target.value)} placeholder="0x..." style={{flex:1,background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"8px 10px",color:T.text,fontSize:10,fontFamily:"monospace",outline:"none"}}/>
            <button onClick={examine} disabled={loading} style={{background:T.purple+"15",border:"1px solid "+T.purple+"44",color:T.purple,padding:"8px 14px",borderRadius:6,cursor:"pointer",fontSize:10,fontFamily:"monospace",fontWeight:700}}>{loading?"...":"Examinar"}</button>
          </div>

          {result&&result.error&&(
            <div style={{background:T.red+"0d",border:"1px solid "+T.red+"33",borderRadius:6,padding:"8px 10px",fontSize:10,color:T.red,fontFamily:"monospace"}}>{result.error}</div>
          )}
          {result&&!result.error&&(
            <div style={{background:T.card,border:"1px solid "+(vColors[result.verdict_color]||T.border)+"44",borderRadius:8,padding:"12px"}}>
              <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                <Badge color={vColors[result.verdict_color]||T.dim}>{result.verdict}</Badge>
                {result.already_tracked&&<Badge color={T.green} small>YA EN SEGUIMIENTO</Badge>}
                <span style={{marginLeft:"auto",fontSize:14,fontWeight:900,color:vColors[result.verdict_color]||T.dim,fontFamily:"monospace"}}>~{result.est_score}</span>
              </div>
              <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",lineHeight:1.5,marginBottom:10}}>{result.verdict_detail}</div>
              <div style={{display:"flex",gap:10,flexWrap:"wrap",marginBottom:10}}>
                <Stat label="Comportamiento" value={result.behavior}/>
                <Stat label="Txs (muestra)" value={result.n_txs_sample}/>
                <Stat label="Tokens distintos" value={result.distinct_tokens}/>
                <Stat label="Coincidencias" value={result.n_matches} color={result.n_matches>0?T.green:T.dim}/>
              </div>
              {result.matches&&result.matches.length>0&&(
                <div style={{marginBottom:10}}>
                  <div style={{fontSize:8,color:T.green,fontFamily:"monospace",marginBottom:4}}>COINCIDE CON TU LISTA:</div>
                  <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>
                    {result.matches.map(m=><Badge key={m} color={T.green} small>{m}</Badge>)}
                  </div>
                </div>
              )}
              {result.portfolio&&result.portfolio.length>0&&(
                <div style={{marginBottom:10}}>
                  <div style={{fontSize:8,color:T.cyan,fontFamily:"monospace",marginBottom:4}}>PORTFOLIO ACTUAL:</div>
                  <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>
                    {result.portfolio.map((h,i)=>(
                      <a key={i} href={"https://dexscreener.com/"+(chain==="ETH"?"ethereum":chain==="BNB"?"bsc":"base")+"/"+h.contract} target="_blank" rel="noopener noreferrer" style={{textDecoration:"none"}}>
                        <Badge color={T.cyan} small>{h.symbol} ↗</Badge>
                      </a>
                    ))}
                  </div>
                </div>
              )}
              {/* Boton agregar: solo si paso el filtro y no esta ya en seguimiento */}
              {result.is_quality && !result.already_tracked && result.n_matches>0 && (
                added ? (
                  <div style={{fontSize:10,color:T.green,fontFamily:"monospace",fontWeight:700}}>✓ Agregada a seguimiento</div>
                ) : (
                  <button onClick={addToTracking} disabled={adding} style={{width:"100%",background:T.green+"12",border:"1px solid "+T.green+"44",color:T.green,padding:"8px",borderRadius:6,cursor:"pointer",fontSize:10,fontFamily:"monospace",fontWeight:700}}>
                    {adding?"Agregando...":"+ Agregar a seguimiento"}
                  </button>
                )
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function InsidersTab({pumpThreshold}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [forcing, setForcing] = useState(false);
  const [filter, setFilter] = useState("ALL");
  const intRef = useRef(null);

  async function refresh() {
    const live = await getLiveAccumData();
    if (live) setData(live);
    setLoading(false);
  }
  useEffect(()=>{
    refresh();
    intRef.current = setInterval(refresh, 120000);
    return ()=>clearInterval(intRef.current);
  },[]);

  async function forceForensic() {
    setForcing(true);
    try { await fetch("https://listing-sniper-production.up.railway.app/api/forensic"); } catch {}
    setTimeout(()=>{ setForcing(false); refresh(); }, 5000);
  }

  const wallets = data?.smart_wallets || [];
  const alerts = data?.insider_alerts || [];
  const convergences = data?.insider_convergences || [];
  const sells = data?.insider_sells || [];
  const trackedCount = data?.tracked_whales || 0;

  const tagInfo = {
    insider_activo:    {label:"INSIDER ACTIVO",    color:T.red},
    insider_historico: {label:"INSIDER HISTORICO", color:T.orange},
    smart:             {label:"SMART",             color:T.cyan},
  };

  const vis = wallets.filter(w=>{
    if (filter==="ACTIVO") return w.tag==="insider_activo";
    if (filter==="TRACKED") return w.tracked;
    if (filter==="FORENSIC") return w.forensic;
    return true;
  });

  return (
    <div>
      <div style={{background:T.orange+"08",border:"1px solid "+T.orange+"20",borderRadius:8,padding:"10px 14px",marginBottom:14}}>
        <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4,flexWrap:"wrap"}}>
          <span style={{fontSize:11,color:T.orange,fontFamily:"monospace",fontWeight:700}}>🎯 Detector de Insiders y Smart Money</span>
          {data&&<Pulse color={T.green}/>}
        </div>
        <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",lineHeight:1.6}}>
          Wallets que compran 2+ monedas de tu lista, rankeadas por dinero, coincidencias y actividad. Filtra bots automaticamente. El forense busca quien compro antes de pumps pasados.
        </div>
        <div style={{display:"flex",gap:8,marginTop:8,alignItems:"center",flexWrap:"wrap"}}>
          <span style={{fontSize:10,color:T.dim,fontFamily:"monospace"}}>{wallets.length} smart wallets · {trackedCount} en seguimiento activo</span>
          <button onClick={forceForensic} disabled={forcing} style={{background:forcing?T.orange+"15":"transparent",border:"1px solid "+T.orange+"33",color:T.orange,padding:"4px 10px",borderRadius:5,cursor:"pointer",fontSize:9,fontFamily:"monospace",fontWeight:700}}>
            {forcing?"Analizando...":"🔍 Forzar forense"}
          </button>
        </div>
      </div>

      {/* Examinador manual de wallets */}
      <WalletExaminer/>

      {/* CONVERGENCIA DE INSIDERS — la señal mas fuerte */}
      {convergences.length>0&&(
        <div style={{background:T.red+"0c",border:"1px solid "+T.red+"33",borderRadius:10,padding:12,marginBottom:14}}>
          <div style={{fontSize:11,color:T.red,fontFamily:"monospace",fontWeight:700,marginBottom:8,display:"flex",alignItems:"center",gap:6}}>
            <Pulse color={T.red}/> <span>🎯 CONVERGENCIA INSIDER ({convergences.length})</span>
          </div>
          <div style={{fontSize:9,color:T.muted,fontFamily:"monospace",marginBottom:8}}>2+ insiders distintos en la misma moneda. La señal mas fuerte del sistema.</div>
          {convergences.map((c,i)=>(
            <div key={i} style={{background:T.card,border:"1px solid "+T.red+"33",borderRadius:8,padding:"10px 12px",marginBottom:6}}>
              <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4}}>
                <span style={{fontSize:13,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{c.symbol}</span>
                <Badge color={chainCol(c.chain)} small>{c.chain}</Badge>
                <Badge color={T.red}>{c.n_insiders+" insiders"}</Badge>
                <span style={{marginLeft:"auto",fontSize:10,color:T.red,fontFamily:"monospace",fontWeight:700}}>score prom {c.avg_score}</span>
              </div>
              <div style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>Wallets: {(c.holders||[]).join(", ")}</div>
              <div style={{fontSize:8,color:T.green,fontFamily:"monospace",marginTop:3}}>✓ En seguimiento automatico · {timeAgo(c.detected_at)}</div>
            </div>
          ))}
        </div>
      )}

      {/* INSIDERS VENDIENDO */}
      {sells.length>0&&(
        <div style={{background:T.yellow+"0a",border:"1px solid "+T.yellow+"25",borderRadius:10,padding:12,marginBottom:14}}>
          <div style={{fontSize:10,color:T.yellow,fontFamily:"monospace",fontWeight:700,marginBottom:8,display:"flex",alignItems:"center",gap:6}}>
            <span>⚠️ Insiders vendiendo ({sells.length})</span>
          </div>
          <div style={{fontSize:9,color:T.muted,fontFamily:"monospace",marginBottom:6}}>Dinero inteligente saliendo. Puede ser toma de ganancias o salida anticipada.</div>
          {sells.slice(0,6).map((s,i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",gap:8,padding:"5px 0",borderBottom:"1px solid "+T.bg}}>
              <Badge color={chainCol(s.chain)} small>{s.chain}</Badge>
              <span style={{fontSize:10,color:T.muted,fontFamily:"monospace"}}>{shortAddr(s.wallet)}</span>
              <span style={{fontSize:9,color:T.dim}}>vendio</span>
              <span style={{fontSize:11,fontWeight:700,color:T.yellow,fontFamily:"monospace",flex:1}}>{s.token}</span>
              <span style={{fontSize:8,color:T.dim,fontFamily:"monospace"}}>{timeAgo(s.ts)}</span>
            </div>
          ))}
        </div>
      )}

      {alerts.length>0&&(
        <div style={{background:T.green+"08",border:"1px solid "+T.green+"20",borderRadius:8,padding:12,marginBottom:14}}>
          <div style={{fontSize:10,color:T.green,fontFamily:"monospace",fontWeight:700,marginBottom:8,display:"flex",alignItems:"center",gap:6}}>
            <Pulse color={T.green}/> <span>Compras recientes de insiders ({alerts.length})</span>
          </div>
          {alerts.slice(0,6).map((a,i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",gap:8,padding:"6px 0",borderBottom:"1px solid "+T.bg}}>
              <Badge color={chainCol(a.chain)} small>{a.chain}</Badge>
              <a href={(a.chain==="ETH"?"https://etherscan.io/address/":a.chain==="BNB"?"https://bscscan.com/address/":"https://basescan.org/address/")+a.wallet} target="_blank" rel="noopener noreferrer" style={{fontSize:10,color:tagInfo[a.tag]?.color||T.muted,fontFamily:"monospace",textDecoration:"none"}}>{shortAddr(a.wallet)}</a>
              <span style={{fontSize:10,color:T.dim}}>compro</span>
              <span style={{fontSize:11,fontWeight:700,color:T.text,fontFamily:"monospace",flex:1}}>{a.token}</span>
              {a.tag==="insider_activo"&&<Badge color={T.red} small>ACTIVO</Badge>}
              <span style={{fontSize:8,color:T.dim,fontFamily:"monospace"}}>{timeAgo(a.ts)}</span>
            </div>
          ))}
        </div>
      )}

      <div style={{display:"flex",gap:4,marginBottom:12,flexWrap:"wrap"}}>
        {[["ALL","Todas"],["ACTIVO","🔴 Insiders activos"],["TRACKED","En seguimiento"],["FORENSIC","Forense"]].map(([k,l])=>(
          <button key={k} onClick={()=>setFilter(k)} style={{background:filter===k?T.orange+"0d":"transparent",border:"1px solid "+(filter===k?T.orange+"33":T.border),color:filter===k?T.orange:T.muted,padding:"4px 10px",borderRadius:5,cursor:"pointer",fontSize:10,fontFamily:"monospace",fontWeight:filter===k?700:400}}>{l}</button>
        ))}
        {vis.length>0&&<span style={{marginLeft:"auto",fontSize:10,color:T.dim,fontFamily:"monospace",alignSelf:"center"}}>{vis.length} wallets</span>}
      </div>

      {loading&&!data&&(
        <div style={{padding:"30px",textAlign:"center"}}>
          <div style={{width:24,height:24,border:"2px solid "+T.orange+"22",borderTop:"2px solid "+T.orange,borderRadius:"50%",margin:"0 auto 12px",animation:"spin 1s linear infinite"}}/>
          <div style={{fontSize:11,color:T.muted,fontFamily:"monospace"}}>Conectando con Railway...</div>
        </div>
      )}

      {!loading&&vis.length===0&&(
        <EmptyState icon="🎯" text="Aun no hay smart wallets detectadas" sub="El forense corre al inicio y cada dia a las 7am. Puedes forzarlo arriba."/>
      )}

      <div style={{display:"flex",flexDirection:"column",gap:6}}>
        {vis.map((w,i)=>(
          <WalletCard key={w.address} w={w} rank={wallets.indexOf(w)+1} tagInfo={tagInfo}/>
        ))}
      </div>
    </div>
  );
}
