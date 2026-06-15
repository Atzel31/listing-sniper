"use client";
import { useState, useEffect, useRef } from "react";
import {
  T, Badge, Stat, ScoreRing, Pulse, ChartEmbed, EmptyState,
  fmtUSD, pct, shortAddr, timeAgo, scoreColor, scoreLabel, chainCol, sendNtfy,
  pumpColor, pumpLabel, multStr, getLiveAccumData,
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
      <div onClick={()=>setOpen(o=>!o)} style={{padding:"12px 14px",cursor:"pointer",display:"flex",alignItems:"center",gap:12}}>
        <div style={{display:"flex",flexDirection:"column",gap:4,flexShrink:0}}>
          <Badge color={chainCol(item.chain)}>{item.chain}</Badge>
          {item.source&&item.source!=="WATCHLIST"&&<Badge color="#555" small>{item.source}</Badge>}
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
export function SniperTab({alerts,running,scanning,countdown,scanLog}) {
  const [filter,setFilter]=useState("ALL");
  const vis=alerts.filter(a=>{
    if(filter==="ETH") return a.chain==="ETH";
    if(filter==="SOL") return a.chain==="SOL";
    if(filter==="HIGH") return a.score>=70;
    if(filter==="WHALE") return (a.wc||0)>=1;
    return true;
  });
  const hc=alerts.filter(a=>a.score>=70).length;
  const mc=alerts.filter(a=>a.score>=45&&a.score<70).length;
  const lc=alerts.filter(a=>a.score<45).length;
  return (
    <div>
      <div style={{display:"flex",gap:8,marginBottom:14,flexWrap:"wrap",alignItems:"center"}}>
        {[[hc,"Bajo riesgo",T.green],[mc,"Medio",T.yellow],[lc,"Alto",T.red]].map(([n,l,c])=>(
          <div key={l} style={{background:c+"0d",border:"1px solid "+c+"22",borderRadius:6,padding:"5px 12px",display:"flex",alignItems:"center",gap:8}}>
            <span style={{fontSize:18,fontWeight:700,color:c,fontFamily:"monospace"}}>{n}</span>
            <span style={{fontSize:10,color:c,fontFamily:"monospace"}}>{l}</span>
          </div>
        ))}
        <span style={{marginLeft:"auto",fontSize:10,fontFamily:"monospace",color:scanning?T.yellow:running?T.green:T.muted}}>
          {scanning?"Escaneando...":running?("Prox. "+countdown+"s"):"Inactivo"}
        </span>
      </div>
      <div style={{display:"flex",gap:4,marginBottom:12,flexWrap:"wrap"}}>
        {[["ALL","Todas"],["ETH","ETH"],["SOL","SOL"],["HIGH","Bajo riesgo"],["WHALE","Whales"]].map(([k,l])=>(
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
export function NewPairsTab({newPairs,running,scanning}) {
  const [filter,setFilter]=useState("ALL");
  const vis=newPairs.filter(p=>{
    if(filter==="ETH") return p.chain==="ETH";
    if(filter==="SOL") return p.chain==="SOL";
    if(filter==="HOT") return parseFloat(p.ch1h||0)>20;
    return true;
  });
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
        {[["ALL","Todos"],["ETH","ETH"],["SOL","SOL"],["HOT","🔥 Pump >20%"]].map(([k,l])=>(
          <button key={k} onClick={()=>setFilter(k)} style={{background:filter===k?T.cyan+"0d":"transparent",border:"1px solid "+(filter===k?T.cyan+"33":T.border),color:filter===k?T.cyan:T.muted,padding:"4px 10px",borderRadius:5,cursor:"pointer",fontSize:10,fontFamily:"monospace",fontWeight:filter===k?700:400}}>{l}</button>
        ))}
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
export function InsidersTab({insiderAlerts,onAddWhale,pumpThreshold}) {
  return (
    <div>
      <div style={{background:T.orange+"08",border:"1px solid "+T.orange+"20",borderRadius:8,padding:"10px 14px",marginBottom:14}}>
        <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4}}>
          <span style={{fontSize:11,color:T.orange,fontFamily:"monospace",fontWeight:700}}>🎯 Detector de Insiders</span>
        </div>
        <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",lineHeight:1.6}}>
          Cuando un token sube mas de +{pumpThreshold}% en 1h, se analiza quien compro antes del pump.
        </div>
      </div>
      {insiderAlerts.length===0?(
        <EmptyState icon="🎯" text={"Esperando tokens con pump >+"+pumpThreshold+"%"} sub="El analisis se ejecuta automaticamente"/>
      ):(
        <div style={{display:"flex",flexDirection:"column",gap:10}}>
          {insiderAlerts.map(alert=>(
            <div key={alert.id} style={{background:T.card,border:"1px solid "+T.orange+"33",borderLeft:"2px solid "+T.orange,borderRadius:10,overflow:"hidden"}}>
              <div style={{padding:"12px 14px",borderBottom:"1px solid "+T.border}}>
                <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:6}}>
                  <span style={{fontSize:14,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{alert.name}</span>
                  <Badge color={chainCol(alert.chain)}>{alert.chain}</Badge>
                  <span style={{background:T.orange+"15",border:"1px solid "+T.orange+"33",color:T.orange,fontSize:9,padding:"1px 7px",borderRadius:4,fontFamily:"monospace",fontWeight:700}}>
                    +{parseFloat(alert.ch1h||0).toFixed(0)}% en 1h
                  </span>
                  <span style={{marginLeft:"auto",fontSize:9,color:T.dim,fontFamily:"monospace"}}>{timeAgo(alert.ts)}</span>
                </div>
                <div style={{display:"flex",gap:12}}>
                  <Stat label="Liq" value={fmtUSD(alert.liq)}/>
                  <Stat label="Vol" value={fmtUSD(alert.vol)}/>
                  <Stat label="Pump 1h" value={pct(alert.ch1h)} color={T.orange}/>
                  {alert.earlyBuyers&&<Stat label="Compradores" value={alert.earlyBuyers.length} color={T.orange}/>}
                </div>
              </div>
              <div style={{padding:"10px 14px"}}>
                <div style={{fontSize:9,color:T.orange,fontFamily:"monospace",fontWeight:700,marginBottom:8}}>COMPRADORES ANTES DEL PUMP</div>
                {(alert.earlyBuyers||[]).map((b,i)=>(
                  <div key={b.address} style={{display:"flex",alignItems:"center",gap:8,padding:"5px 0",borderBottom:"1px solid "+T.border}}>
                    <span style={{fontSize:10,color:T.dim,fontFamily:"monospace",minWidth:20}}>#{i+1}</span>
                    <a href={"https://etherscan.io/address/"+b.address} target="_blank" rel="noopener noreferrer"
                      style={{fontSize:10,color:T.orange,fontFamily:"monospace",textDecoration:"none",flex:1}}>
                      {shortAddr(b.address)}
                    </a>
                    <span style={{fontSize:9,color:T.muted,fontFamily:"monospace"}}>{b.txCount} txns</span>
                    <div style={{display:"flex",gap:4}}>
                      {b.appearsInMultiple&&<Badge color={T.pink} small>RECURRENTE</Badge>}
                      <button onClick={()=>onAddWhale(b.address,"ETH","Insider #"+b.address.slice(-4))} style={{background:T.pink+"10",border:"1px solid "+T.pink+"30",color:T.pink,padding:"2px 7px",borderRadius:4,cursor:"pointer",fontSize:8,fontFamily:"monospace",fontWeight:700}}>
                        + Seguir
                      </button>
                    </div>
                  </div>
                ))}
                <div style={{display:"flex",gap:5,marginTop:10}}>
                  <a href={alert.dexUrl||"https://dexscreener.com"} target="_blank" rel="noopener noreferrer"
                    style={{flex:1,textAlign:"center",background:T.orange+"10",border:"1px solid "+T.orange+"33",color:T.orange,padding:"7px",borderRadius:6,fontSize:9,fontWeight:700,fontFamily:"monospace",textDecoration:"none",display:"block"}}>
                    ↗ Ver chart
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
