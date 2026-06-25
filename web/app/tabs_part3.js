"use client";
import { useState, useEffect, useRef } from "react";
import {
  T, Badge, Stat, Pulse, EmptyState, ChartEmbed,
  fmtUSD, pct, timeAgo, chainCol, accumColor, accumLabel,
  getLiveAccumData, getWeeklyReport, ACCUMULATION_LIST, copyText, RAILWAY_API,
} from "./shared";

// ─── ACCUMULATION CARD ────────────────────────────────────────────────────────
function AccumCard({token, rank}) {
  const [open, setOpen] = useState(false);
  const score = token.score || 0;
  const color = accumColor(score);
  const chartUrl = token.pair && token.real_chain
    ? "https://dexscreener.com/"+token.real_chain+"/"+token.pair+"?embed=1&theme=dark&trades=0&info=0"
    : null;

  return (
    <div style={{
      background:T.card,
      border:"1px solid "+(open?color+"44":T.border),
      borderLeft:"3px solid "+color,
      borderRadius:10,overflow:"hidden",transition:"border-color 0.2s",
    }}>
      <div onClick={()=>setOpen(o=>!o)} style={{padding:"13px 14px",cursor:"pointer",display:"flex",alignItems:"center",gap:12}}>
        {rank&&(
          <div style={{fontSize:16,fontWeight:900,color:rank<=3?color:T.dim,fontFamily:"monospace",minWidth:24,textAlign:"center"}}>
            #{rank}
          </div>
        )}
        <div style={{display:"flex",flexDirection:"column",gap:4,flexShrink:0}}>
          <Badge color={chainCol(token.chain)}>{token.chain}</Badge>
        </div>
        <div style={{flex:1,minWidth:0}}>
          <div style={{display:"flex",alignItems:"center",gap:6,flexWrap:"wrap",marginBottom:5}}>
            <span style={{fontSize:14,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{token.symbol||token.name}</span>
            {token.price&&parseFloat(token.price)>0&&<span style={{fontSize:10,color:T.muted,fontFamily:"monospace"}}>${parseFloat(token.price)<0.01?parseFloat(token.price).toFixed(8):parseFloat(token.price).toFixed(4)}</span>}
            {token.flow==="OUT"&&<Badge color={T.green}>↑ RETIRO</Badge>}
            {(token.whale_count||0)>0&&<Badge color={T.pink}>{"🐋 x"+token.whale_count}</Badge>}
            {(token.big_buyers||0)>0&&<Badge color={T.orange}>{"+"+token.big_buyers+" compradores"}</Badge>}
          </div>
          <div style={{display:"flex",gap:12,flexWrap:"wrap"}}>
            {token.mcap>0?<Stat label="MCap" value={fmtUSD(token.mcap)}/>:<Stat label="Liq" value={fmtUSD(token.liq)}/>}
            <Stat label="Vol 24h" value={fmtUSD(token.vol)}/>
            <Stat label="24h" value={pct(token.ch24h)} color={parseFloat(token.ch24h||0)>=0?T.green:T.red}/>
            {token.ch7d!==undefined&&token.ch7d!==null&&<Stat label="7d" value={pct(token.ch7d)} color={parseFloat(token.ch7d||0)>=0?T.green:T.red}/>}
          </div>
        </div>
        <div style={{display:"flex",flexDirection:"column",alignItems:"center",flexShrink:0}}>
          <div style={{fontSize:20,fontWeight:900,color,fontFamily:"monospace",lineHeight:1}}>{score}%</div>
          <div style={{fontSize:8,color,fontFamily:"monospace",fontWeight:700,marginTop:2}}>{accumLabel(score)}</div>
        </div>
      </div>

      {open&&(
        <div onClick={e=>e.stopPropagation()} style={{padding:"0 14px 14px",borderTop:"1px solid "+T.border}}>
          {/* Stats grid */}
          <div style={{display:"flex",gap:6,marginTop:12,flexWrap:"wrap",marginBottom:12}}>
            <div style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 10px",flex:1,minWidth:80}}>
              <div style={{fontSize:8,color:T.muted,fontFamily:"monospace",marginBottom:3}}>FLUJO EXCHANGE</div>
              <div style={{fontSize:10,fontWeight:700,fontFamily:"monospace",color:token.flow==="OUT"?T.green:token.flow==="IN"?T.red:T.dim}}>
                {token.flow==="OUT"?"↑ Retiro":token.flow==="IN"?"↓ Deposito":"Neutral"}
              </div>
            </div>
            <div style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 10px",flex:1,minWidth:80}}>
              <div style={{fontSize:8,color:T.muted,fontFamily:"monospace",marginBottom:3}}>BUYS / SELLS</div>
              <div style={{fontSize:10,fontWeight:700,fontFamily:"monospace"}}>
                <span style={{color:T.green}}>{token.buys||0}</span>
                <span style={{color:T.dim}}> / </span>
                <span style={{color:T.red}}>{token.sells||0}</span>
              </div>
            </div>
            {token.ath_change!==undefined&&token.ath_change!==null&&(
              <div style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 10px",flex:1,minWidth:80}}>
                <div style={{fontSize:8,color:T.muted,fontFamily:"monospace",marginBottom:3}}>DESDE ATH</div>
                <div style={{fontSize:10,fontWeight:700,fontFamily:"monospace",color:T.red}}>{pct(token.ath_change)}</div>
              </div>
            )}
            {token.multi_dex&&(
              <div style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"7px 10px",flex:1,minWidth:80}}>
                <div style={{fontSize:8,color:T.muted,fontFamily:"monospace",marginBottom:3}}>MULTI-DEX</div>
                <div style={{fontSize:10,fontWeight:700,fontFamily:"monospace",color:T.blue}}>Si</div>
              </div>
            )}
          </div>

          {/* Score breakdown */}
          {token.reasons&&token.reasons.length>0&&(
            <div style={{marginBottom:12}}>
              <div style={{fontSize:9,color:T.muted,fontFamily:"monospace",marginBottom:6}}>POR QUE ESTE SCORE</div>
              {token.reasons.map((r,i)=>(
                <div key={i} style={{display:"flex",justifyContent:"space-between",fontSize:9,padding:"3px 0",borderBottom:"1px solid "+T.bg}}>
                  <span style={{color:T.muted}}>{r.reason}</span>
                  <span style={{color:r.effect>0?T.green:T.red,fontFamily:"monospace",fontWeight:700}}>{r.effect>0?"+":""}{r.effect}</span>
                </div>
              ))}
              <div style={{display:"flex",justifyContent:"space-between",paddingTop:5}}>
                <span style={{fontSize:10,color:T.muted,fontWeight:700}}>SCORE ACUMULACION</span>
                <span style={{fontSize:12,color,fontWeight:900,fontFamily:"monospace"}}>{score}%</span>
              </div>
            </div>
          )}

          {/* Chart */}
          {chartUrl&&(
            <div style={{marginBottom:10}}>
              <ChartEmbed chartUrl={chartUrl} dexUrl={token.url} name={token.symbol}/>
            </div>
          )}

          {/* Actions */}
          <div style={{display:"flex",gap:6}}>
            {token.buy_url&&(
              <a href={token.buy_url} target="_blank" rel="noopener noreferrer" style={{flex:1,textAlign:"center",background:T.green+"10",border:"1px solid "+T.green+"33",color:T.green,padding:"8px",borderRadius:6,fontSize:10,fontWeight:700,fontFamily:"monospace",textDecoration:"none",display:"block"}}>
                ↗ Comprar
              </a>
            )}
            {token.url&&(
              <a href={token.url} target="_blank" rel="noopener noreferrer" style={{flex:1,textAlign:"center",background:T.bg,border:"1px solid "+T.border,color:T.muted,padding:"8px",borderRadius:6,fontSize:10,fontWeight:700,fontFamily:"monospace",textDecoration:"none",display:"block"}}>
                ↗ {token.chain==="CEX"?"CoinGecko":"DexScreener"}
              </a>
            )}
          </div>

          {token.contract&&token.chain!=="CEX"&&(
            <div style={{marginTop:8,fontSize:8,color:T.dim,fontFamily:"monospace",wordBreak:"break-all"}}>
              {token.contract}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── WEEKLY REPORT BANNER ─────────────────────────────────────────────────────
function WeeklyBanner({weekly}) {
  if (!weekly || !weekly.ranking || !weekly.ranking.length) return null;
  const top3 = weekly.ranking.slice(0,3);
  return (
    <div style={{background:T.cyan+"08",border:"1px solid "+T.cyan+"25",borderRadius:10,padding:14,marginBottom:16}}>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:10,flexWrap:"wrap",gap:6}}>
        <div style={{display:"flex",alignItems:"center",gap:8}}>
          <span style={{fontSize:12,color:T.cyan,fontFamily:"monospace",fontWeight:700}}>📊 ANALISIS SEMANAL</span>
          <span style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>{weekly.week}</span>
        </div>
        <span style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>Generado: {weekly.generated_at}</span>
      </div>
      <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",marginBottom:10}}>
        Mercado: <span style={{color:T.orange,fontWeight:700}}>BAJISTA</span> · {weekly.ranking.length} tokens analizados · {weekly.events_count||0} eventos esta semana
      </div>
      <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
        {top3.map((t,i)=>(
          <div key={t.symbol} style={{flex:1,minWidth:140,background:T.card,border:"1px solid "+T.border,borderRadius:8,padding:"10px 12px"}}>
            <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:6}}>
              <span style={{fontSize:14,fontWeight:900,color:i===0?T.cyan:T.dim,fontFamily:"monospace"}}>#{i+1}</span>
              <span style={{fontSize:12,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{t.symbol}</span>
              <Badge color={chainCol(t.chain)} small>{t.chain}</Badge>
            </div>
            <div style={{fontSize:18,fontWeight:900,color:accumColor(t.score),fontFamily:"monospace",marginBottom:4}}>{t.score}%</div>
            <div style={{fontSize:9,color:T.muted,fontFamily:"monospace",lineHeight:1.5}}>{t.diagnosis}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── WEEK EVENTS LOG ──────────────────────────────────────────────────────────
function WeekEventsLog({events}) {
  if (!events || !events.length) return null;
  const typeColors = {
    pump: T.green, dump: T.red, liq_growth: T.cyan,
    exchange_out: T.green, score_cross: T.purple, smart_money: T.orange,
  };
  const typeLabels = {
    pump: "🚀 Pump", dump: "⚠ Dump", liq_growth: "💧 Liquidez",
    exchange_out: "📤 Retiro exchange", score_cross: "⭐ Score alto", smart_money: "🧠 Smart money",
  };
  return (
    <div style={{marginBottom:16}}>
      <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",marginBottom:8,letterSpacing:1}}>
        EVENTOS RECIENTES ({events.length})
      </div>
      <div style={{display:"flex",flexDirection:"column",gap:5,maxHeight:240,overflowY:"auto"}}>
        {events.slice().reverse().map((e,i)=>(
          <div key={i} style={{background:T.surface,border:"1px solid "+T.border,borderRadius:7,padding:"8px 11px",display:"flex",alignItems:"center",gap:8}}>
            <Badge color={typeColors[e.type]||T.muted} small>{typeLabels[e.type]||e.type}</Badge>
            <span style={{fontSize:11,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{e.token}</span>
            <span style={{fontSize:9,color:T.muted,fontFamily:"monospace",flex:1}}>{e.detail}</span>
            <span style={{fontSize:8,color:T.dim,fontFamily:"monospace",flexShrink:0}}>{timeAgo(e.ts)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── PANEL DE COMBOS ──────────────────────────────────────────────────────────
// ─── PANEL DE POSICIONES (alertas de salida) ─────────────────────────────────
function PositionsPanel({positions, onRefresh}) {
  const [showAdd, setShowAdd] = useState(false);
  const [addr, setAddr] = useState("");
  const [chain, setChain] = useState("ETH");
  const [price, setPrice] = useState("");
  const [adding, setAdding] = useState(false);

  async function addPosition() {
    if (!addr.trim()) return;
    setAdding(true);
    try {
      const p = price.trim() || "auto";
      await fetch(RAILWAY_API+"/api/position/add/"+chain+"/"+addr.trim()+"/"+p);
      setAddr(""); setPrice(""); setShowAdd(false);
      setTimeout(()=>onRefresh&&onRefresh(), 1500);
    } catch {}
    setAdding(false);
  }
  async function removePos(contract) {
    try {
      await fetch(RAILWAY_API+"/api/position/remove/"+contract);
      setTimeout(()=>onRefresh&&onRefresh(), 1000);
    } catch {}
  }

  const pos = positions || [];
  return (
    <div style={{background:T.green+"06",border:"1px solid "+T.green+"22",borderRadius:10,padding:14,marginBottom:16}}>
      <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
        <span style={{fontSize:12,color:T.green,fontFamily:"monospace",fontWeight:700}}>💼 MIS POSICIONES</span>
        <span style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>alertas de salida (x2/x3 y caida tras pico)</span>
        <button onClick={()=>setShowAdd(s=>!s)} style={{marginLeft:"auto",background:T.green+"12",border:"1px solid "+T.green+"33",color:T.green,padding:"3px 10px",borderRadius:5,cursor:"pointer",fontSize:9,fontFamily:"monospace",fontWeight:700}}>{showAdd?"cancelar":"+ estoy dentro"}</button>
      </div>
      {showAdd&&(
        <div style={{background:T.card,border:"1px solid "+T.border,borderRadius:8,padding:10,marginBottom:10}}>
          <div style={{display:"flex",gap:6,marginBottom:8,flexWrap:"wrap"}}>
            {["ETH","BNB","BASE","SOL"].map(c=>(
              <button key={c} onClick={()=>setChain(c)} style={{background:chain===c?T.green+"15":"transparent",border:"1px solid "+(chain===c?T.green+"44":T.border),color:chain===c?T.green:T.muted,padding:"3px 10px",borderRadius:5,cursor:"pointer",fontSize:9,fontFamily:"monospace",fontWeight:700}}>{c}</button>
            ))}
          </div>
          <input value={addr} onChange={e=>setAddr(e.target.value)} placeholder="Contrato del token (0x...)" style={{width:"100%",background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"8px 10px",color:T.text,fontSize:10,fontFamily:"monospace",outline:"none",marginBottom:6,boxSizing:"border-box"}}/>
          <input value={price} onChange={e=>setPrice(e.target.value)} placeholder="Precio de entrada (vacio = precio actual)" style={{width:"100%",background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"8px 10px",color:T.text,fontSize:10,fontFamily:"monospace",outline:"none",marginBottom:8,boxSizing:"border-box"}}/>
          <button onClick={addPosition} disabled={adding} style={{width:"100%",background:T.green+"15",border:"1px solid "+T.green+"44",color:T.green,padding:"8px",borderRadius:6,cursor:"pointer",fontSize:10,fontFamily:"monospace",fontWeight:700}}>{adding?"Agregando...":"Marcar posicion"}</button>
        </div>
      )}
      {pos.length===0?(
        <div style={{fontSize:10,color:T.dim,fontFamily:"monospace",textAlign:"center",padding:"10px"}}>Sin posiciones marcadas. Marca una para recibir alertas de salida.</div>
      ):(
        <div style={{display:"flex",flexDirection:"column",gap:6}}>
          {pos.map((p,i)=>{
            const mc = p.mult>=2?T.green:p.mult>=1?T.cyan:T.red;
            return (
            <div key={i} style={{background:T.card,border:"1px solid "+T.border,borderRadius:8,padding:"10px 12px"}}>
              <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:6}}>
                <span style={{fontSize:13,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{p.symbol}</span>
                <Badge color={chainCol(p.chain)} small>{p.chain}</Badge>
                <span style={{fontSize:14,fontWeight:900,color:mc,fontFamily:"monospace"}}>x{p.mult}</span>
                {p.peak_mult>p.mult&&<span style={{fontSize:8,color:T.dim,fontFamily:"monospace"}}>pico x{p.peak_mult}</span>}
                <button onClick={()=>removePos(p.contract)} style={{marginLeft:"auto",background:"transparent",border:"1px solid "+T.border,color:T.dim,padding:"2px 8px",borderRadius:4,cursor:"pointer",fontSize:8,fontFamily:"monospace"}}>salir</button>
              </div>
              <div style={{display:"flex",gap:10,flexWrap:"wrap"}}>
                <Stat label="Entrada" value={p.entry_price.toPrecision(4)}/>
                <Stat label="Ahora" value={p.last_price.toPrecision(4)} color={mc}/>
                {p.targets_hit&&p.targets_hit.length>0&&<Stat label="Objetivos" value={p.targets_hit.map(t=>"x"+t).join(" ")} color={T.green}/>}
              </div>
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function CombosPanel({combos}) {
  const [copiedIdx, setCopiedIdx] = useState(-1);
  if (!combos || !combos.length) return null;
  const sigLabels = {
    insider_convergence:"CONVERGENCIA INSIDER",
    prelisting_unconfirmed:"Pre-listing NO confirmado",
    prelisting_confirmed:"Exchange activo",
    multi_exchange:"Multi-exchange",
    insider_buy:"Insider dentro",
    high_pump_prob:"Prob. pump alta",
    whale_convergence:"Convergencia whales",
    exchange_out:"Retiro exchanges",
    vol_accel:"Volumen acelerando",
  };
  function doCopy(contract, idx) {
    if (copyText(contract)) { setCopiedIdx(idx); setTimeout(()=>setCopiedIdx(-1), 1500); }
  }
  const dexChain = ch => ch==="ETH"?"ethereum":ch==="BNB"?"bsc":ch==="BASE"?"base":"solana";
  return (
    <div style={{background:T.orange+"08",border:"1px solid "+T.orange+"25",borderRadius:10,padding:14,marginBottom:16}}>
      <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
        <span style={{fontSize:12,color:T.orange,fontFamily:"monospace",fontWeight:700}}>🎯 COMBOS ACTIVOS</span>
        <Pulse color={T.orange}/>
        <span style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>senales apiladas en el mismo token</span>
      </div>
      <div style={{display:"flex",flexDirection:"column",gap:6}}>
        {combos.map((c,i)=>{
          const dexUrl = c.url || (c.contract?("https://dexscreener.com/"+dexChain(c.chain)+"/"+c.contract):"");
          return (
          <div key={i} style={{background:T.card,border:"1px solid "+(c.n_signals>=3?T.orange+"44":T.border),borderLeft:"3px solid "+(c.score>=7?T.red:T.orange),borderRadius:8,padding:"10px 12px"}}>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:6}}>
              <span style={{fontSize:13,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{c.symbol}</span>
              <Badge color={chainCol(c.chain)} small>{c.chain}</Badge>
              <Badge color={c.score>=7?T.red:T.orange}>{"x"+c.n_signals+" senales"}</Badge>
              <span style={{marginLeft:"auto",fontSize:11,fontWeight:900,color:c.score>=7?T.red:T.orange,fontFamily:"monospace"}}>score {c.score}</span>
            </div>
            <div style={{display:"flex",gap:4,flexWrap:"wrap",marginBottom:8}}>
              {c.signals.map(s=><Badge key={s} color={s==="insider_convergence"?T.red:T.purple} small>{sigLabels[s]||s}</Badge>)}
            </div>
            {(c.liq>0||c.pump_prob>0)&&(
              <div style={{display:"flex",gap:10,marginBottom:8}}>
                {c.liq>0&&<Stat label="Liq" value={fmtUSD(c.liq)}/>}
                {c.pump_prob>0&&<Stat label="Pump" value={c.pump_prob+"%"} color={c.pump_prob>=60?T.green:T.yellow}/>}
              </div>
            )}
            {c.contract&&(
              <div style={{display:"flex",gap:5,flexWrap:"wrap"}}>
                {dexUrl&&<a href={dexUrl} target="_blank" rel="noopener noreferrer" style={{flex:1,minWidth:90,textAlign:"center",background:T.cyan+"10",border:"1px solid "+T.cyan+"33",color:T.cyan,padding:"6px",borderRadius:5,fontSize:9,fontWeight:700,fontFamily:"monospace",textDecoration:"none"}}>📊 DexScreener</a>}
                {c.buy_url&&<a href={c.buy_url} target="_blank" rel="noopener noreferrer" style={{flex:1,minWidth:90,textAlign:"center",background:T.green+"10",border:"1px solid "+T.green+"33",color:T.green,padding:"6px",borderRadius:5,fontSize:9,fontWeight:700,fontFamily:"monospace",textDecoration:"none"}}>💰 Comprar</a>}
                <button onClick={()=>doCopy(c.contract,i)} style={{flex:1,minWidth:90,background:copiedIdx===i?T.green+"15":T.purple+"10",border:"1px solid "+(copiedIdx===i?T.green+"44":T.purple+"33"),color:copiedIdx===i?T.green:T.purple,padding:"6px",borderRadius:5,cursor:"pointer",fontSize:9,fontWeight:700,fontFamily:"monospace"}}>{copiedIdx===i?"✓ copiado":"copiar CA"}</button>
              </div>
            )}
          </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── PANEL DE WIN RATE ────────────────────────────────────────────────────────
function WinRatePanel({bySignal, byHour, byCombo}) {
  const hasSignal = bySignal && bySignal.filter(s=>s.total>=2).length>0;
  const hasHour = byHour && byHour.filter(h=>h.total>=2).length>0;
  const hasCombo = byCombo && byCombo.filter(c=>c.total>=2).length>0;
  if (!hasSignal && !hasHour && !hasCombo) return null;
  const comboLabel = k => k.split("+").map(s=>({
    insider_convergence:"conv.insider",prelisting_unconfirmed:"pre-list",prelisting_confirmed:"exch.activo",
    multi_exchange:"multi-ex",insider_buy:"insider",high_pump_prob:"pump-prob",
    whale_convergence:"whales",vol_accel:"vol",exchange_out:"retiro"
  }[s]||s)).join(" + ");
  return (
    <div style={{background:T.cyan+"06",border:"1px solid "+T.cyan+"20",borderRadius:10,padding:14,marginBottom:16}}>
      <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
        <span style={{fontSize:12,color:T.cyan,fontFamily:"monospace",fontWeight:700}}>📊 WIN RATE POR TIPO</span>
        <span style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>que senales aciertan mas (se afina con el tiempo)</span>
      </div>
      {hasCombo&&(
        <div style={{marginBottom:12}}>
          <div style={{fontSize:9,color:T.orange,fontFamily:"monospace",marginBottom:6,fontWeight:700}}>POR COMBINACION (lo mas util)</div>
          {byCombo.filter(c=>c.total>=2).slice(0,6).map((c,i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",gap:8,padding:"4px 0",borderBottom:"1px solid "+T.bg}}>
              <span style={{fontSize:9,color:T.text,fontFamily:"monospace",flex:1}}>{comboLabel(c.combo)}</span>
              <span style={{fontSize:8,color:T.dim,fontFamily:"monospace"}}>{c.total}x</span>
              <span style={{fontSize:8,color:T.green,fontFamily:"monospace"}}>↑x{c.best_mult}</span>
              <span style={{fontSize:10,fontWeight:700,color:c.win_rate>=40?T.green:c.win_rate>=20?T.yellow:T.red,fontFamily:"monospace",minWidth:32,textAlign:"right"}}>{c.win_rate}%</span>
            </div>
          ))}
        </div>
      )}
      {hasSignal&&(
        <div style={{marginBottom:hasHour?12:0}}>
          <div style={{fontSize:9,color:T.muted,fontFamily:"monospace",marginBottom:6}}>POR SEÑAL INDIVIDUAL</div>
          {bySignal.filter(s=>s.total>=2).slice(0,8).map((s,i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",gap:8,padding:"4px 0",borderBottom:"1px solid "+T.bg}}>
              <span style={{fontSize:10,color:T.text,fontFamily:"monospace",flex:1}}>{s.signal}</span>
              <span style={{fontSize:8,color:T.dim,fontFamily:"monospace"}}>{s.total} alertas</span>
              <div style={{width:60,height:4,background:T.dim,borderRadius:2,overflow:"hidden"}}>
                <div style={{width:s.win_rate+"%",height:"100%",background:s.win_rate>=40?T.green:s.win_rate>=20?T.yellow:T.red}}/>
              </div>
              <span style={{fontSize:10,fontWeight:700,color:s.win_rate>=40?T.green:s.win_rate>=20?T.yellow:T.red,fontFamily:"monospace",minWidth:32,textAlign:"right"}}>{s.win_rate}%</span>
            </div>
          ))}
        </div>
      )}
      {hasHour&&(
        <div>
          <div style={{fontSize:9,color:T.muted,fontFamily:"monospace",marginBottom:6}}>MEJORES HORAS (PERU)</div>
          <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
            {byHour.filter(h=>h.total>=2).slice(0,6).map((h,i)=>(
              <div key={i} style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"5px 10px"}}>
                <div style={{fontSize:11,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{String(h.hour_peru).padStart(2,"0")}:00</div>
                <div style={{fontSize:10,fontWeight:700,color:h.win_rate>=40?T.green:T.yellow,fontFamily:"monospace"}}>{h.win_rate}%</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── TAB: ACUMULACIÓN ─────────────────────────────────────────────────────────
export function AccumulationTab({githubRepo}) {
  const [liveData, setLiveData] = useState(null);
  const [weekly, setWeekly] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("ALL");
  const [lastUpdate, setLastUpdate] = useState(null);
  const intRef = useRef(null);

  async function refresh() {
    const [live, week] = await Promise.all([
      getLiveAccumData(),
      getWeeklyReport(githubRepo),
    ]);
    if (live) {
      setLiveData(live);
      setLastUpdate(Date.now());
    }
    if (week) setWeekly(week);
    setLoading(false);
  }

  useEffect(()=>{
    refresh();
    intRef.current = setInterval(refresh, 120000); // cada 2 min
    return ()=>clearInterval(intRef.current);
  },[]);

  const tokens = liveData?.tokens || [];
  const ranking = [...tokens].sort((a,b)=>(b.score||0)-(a.score||0));

  const vis = ranking.filter(t=>{
    if (filter==="DEX") return t.chain!=="CEX";
    if (filter==="GOOD") return (t.score||0)>=50;
    if (filter==="ETH") return t.chain==="ETH";
    if (filter==="SOL") return t.chain==="SOL";
    if (filter==="BNB") return t.chain==="BNB";
    if (filter==="BASE") return t.chain==="BASE";
    return true;
  });

  const avgScore = ranking.length ? Math.round(ranking.reduce((a,t)=>a+(t.score||0),0)/ranking.length) : 0;
  const excellent = ranking.filter(t=>(t.score||0)>=70).length;
  const avoid = ranking.filter(t=>(t.score||0)<30).length;

  return (
    <div>
      {/* Info banner */}
      <div style={{background:T.purple+"08",border:"1px solid "+T.purple+"20",borderRadius:8,padding:"10px 14px",marginBottom:14}}>
        <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4,flexWrap:"wrap"}}>
          <span style={{fontSize:11,color:T.purple,fontFamily:"monospace",fontWeight:700}}>📈 Asesor de Acumulacion</span>
          {liveData&&<Pulse color={T.green}/>}
          {lastUpdate&&<span style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>actualizado {timeAgo(Math.floor(lastUpdate/1000))}</span>}
        </div>
        <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",lineHeight:1.6}}>
          Datos en vivo desde Railway · {ACCUMULATION_LIST.length} tokens en seguimiento · ETH, SOL, BNB, BASE + CEX (CoinGecko)
        </div>
        {liveData?.market_context&&(
          <div style={{display:"flex",alignItems:"center",gap:6,marginTop:8,padding:"6px 10px",background:T.bg,border:"1px solid "+T.border,borderRadius:6}}>
            <span style={{fontSize:10}}>{liveData.market_context.emoji||"⚪"}</span>
            <span style={{fontSize:10,color:T.muted,fontFamily:"monospace"}}>Mercado:</span>
            <span style={{fontSize:10,fontWeight:700,color:liveData.market_context.status==="verde"?T.green:liveData.market_context.status==="rojo"?T.red:T.dim,fontFamily:"monospace"}}>BTC {liveData.market_context.ch24h>=0?"+":""}{liveData.market_context.ch24h}% 24h</span>
            <span style={{fontSize:8,color:T.dim,fontFamily:"monospace",marginLeft:"auto"}}>{liveData.market_context.status==="rojo"?"cuidado con pumps aislados":liveData.market_context.status==="verde"?"viento a favor":"lateral"}</span>
          </div>
        )}
      </div>

      {/* Weekly report */}
      <WeeklyBanner weekly={weekly}/>

      {/* Mis posiciones (alertas de salida) */}
      <PositionsPanel positions={liveData?.positions} onRefresh={refresh}/>

      {/* Combos activos y win rate por tipo */}
      <CombosPanel combos={liveData?.combos}/>
      <WinRatePanel bySignal={liveData?.winrate_by_signal} byHour={liveData?.winrate_by_hour} byCombo={liveData?.winrate_by_combo}/>

      {!liveData&&loading&&(
        <div style={{padding:"30px 20px",textAlign:"center"}}>
          <div style={{width:24,height:24,border:"2px solid "+T.purple+"22",borderTop:"2px solid "+T.purple,borderRadius:"50%",margin:"0 auto 12px",animation:"spin 1s linear infinite"}}/>
          <div style={{fontSize:11,color:T.muted,fontFamily:"monospace"}}>Conectando con Railway...</div>
        </div>
      )}

      {!liveData&&!loading&&(
        <EmptyState icon="📈" text="Sin conexion con el bot" sub="Verifica que Railway este corriendo y que /api/live responda"/>
      )}

      {liveData&&(
        <>
          {/* Stats summary */}
          <div style={{display:"flex",gap:8,marginBottom:14,flexWrap:"wrap"}}>
            <div style={{background:T.bg,border:"1px solid "+T.border,borderRadius:6,padding:"8px 14px",flex:1,minWidth:90}}>
              <div style={{fontSize:8,color:T.muted,fontFamily:"monospace",marginBottom:3}}>SCORE PROMEDIO</div>
              <div style={{fontSize:18,fontWeight:900,color:accumColor(avgScore),fontFamily:"monospace"}}>{avgScore}%</div>
            </div>
            <div style={{background:T.green+"0a",border:"1px solid "+T.green+"22",borderRadius:6,padding:"8px 14px",flex:1,minWidth:90}}>
              <div style={{fontSize:8,color:T.green,fontFamily:"monospace",marginBottom:3}}>EXCELENTES</div>
              <div style={{fontSize:18,fontWeight:900,color:T.green,fontFamily:"monospace"}}>{excellent}</div>
            </div>
            <div style={{background:T.red+"0a",border:"1px solid "+T.red+"22",borderRadius:6,padding:"8px 14px",flex:1,minWidth:90}}>
              <div style={{fontSize:8,color:T.red,fontFamily:"monospace",marginBottom:3}}>EVITAR</div>
              <div style={{fontSize:18,fontWeight:900,color:T.red,fontFamily:"monospace"}}>{avoid}</div>
            </div>
          </div>

          {/* Events */}
          <WeekEventsLog events={liveData.events}/>

          {/* Filters */}
          <div style={{display:"flex",gap:4,marginBottom:12,flexWrap:"wrap"}}>
            {[["ALL","Todos"],["GOOD","≥50%"],["DEX","Solo DEX"],["ETH","ETH"],["SOL","SOL"],["BNB","BNB"],["BASE","BASE"]].map(([k,l])=>(
              <button key={k} onClick={()=>setFilter(k)} style={{background:filter===k?T.purple+"0d":"transparent",border:"1px solid "+(filter===k?T.purple+"33":T.border),color:filter===k?T.purple:T.muted,padding:"4px 10px",borderRadius:5,cursor:"pointer",fontSize:10,fontFamily:"monospace",fontWeight:filter===k?700:400}}>{l}</button>
            ))}
            <span style={{marginLeft:"auto",fontSize:10,color:T.dim,fontFamily:"monospace",alignSelf:"center"}}>{vis.length} tokens</span>
          </div>

          {/* Ranking */}
          <div style={{fontSize:10,color:T.muted,fontFamily:"monospace",marginBottom:8,letterSpacing:1}}>
            RANKING — MEJOR OPCION PARA ACUMULAR
          </div>
          <div style={{display:"flex",flexDirection:"column",gap:6}}>
            {vis.map((t,i)=><AccumCard key={t.symbol} token={t} rank={ranking.indexOf(t)+1}/>)}
          </div>
        </>
      )}
    </div>
  );
}
