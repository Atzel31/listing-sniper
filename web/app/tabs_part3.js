"use client";
import { useState, useEffect, useRef } from "react";
import {
  T, Badge, Stat, Pulse, EmptyState, ChartEmbed,
  fmtUSD, pct, timeAgo, chainCol, accumColor, accumLabel,
  getLiveAccumData, getWeeklyReport, ACCUMULATION_LIST,
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
function CombosPanel({combos}) {
  if (!combos || !combos.length) return null;
  const sigLabels = {
    prelisting_unconfirmed:"Pre-listing NO confirmado",
    prelisting_confirmed:"Exchange activo",
    multi_exchange:"Multi-exchange",
    insider_buy:"Insider dentro",
    high_pump_prob:"Prob. pump alta",
    whale_convergence:"Convergencia whales",
    exchange_out:"Retiro exchanges",
    vol_accel:"Volumen acelerando",
  };
  return (
    <div style={{background:T.orange+"08",border:"1px solid "+T.orange+"25",borderRadius:10,padding:14,marginBottom:16}}>
      <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
        <span style={{fontSize:12,color:T.orange,fontFamily:"monospace",fontWeight:700}}>🎯 COMBOS ACTIVOS</span>
        <Pulse color={T.orange}/>
        <span style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>senales apiladas en el mismo token</span>
      </div>
      <div style={{display:"flex",flexDirection:"column",gap:6}}>
        {combos.map((c,i)=>(
          <div key={i} style={{background:T.card,border:"1px solid "+(c.n_signals>=3?T.orange+"44":T.border),borderLeft:"3px solid "+(c.score>=7?T.red:T.orange),borderRadius:8,padding:"10px 12px"}}>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:6}}>
              <span style={{fontSize:13,fontWeight:700,color:T.text,fontFamily:"monospace"}}>{c.symbol}</span>
              <Badge color={chainCol(c.chain)} small>{c.chain}</Badge>
              <Badge color={c.score>=7?T.red:T.orange}>{"x"+c.n_signals+" senales"}</Badge>
              <span style={{marginLeft:"auto",fontSize:11,fontWeight:900,color:c.score>=7?T.red:T.orange,fontFamily:"monospace"}}>score {c.score}</span>
            </div>
            <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>
              {c.signals.map(s=><Badge key={s} color={T.purple} small>{sigLabels[s]||s}</Badge>)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── PANEL DE WIN RATE ────────────────────────────────────────────────────────
function WinRatePanel({bySignal, byHour}) {
  const hasSignal = bySignal && bySignal.filter(s=>s.total>=2).length>0;
  const hasHour = byHour && byHour.filter(h=>h.total>=2).length>0;
  if (!hasSignal && !hasHour) return null;
  return (
    <div style={{background:T.cyan+"06",border:"1px solid "+T.cyan+"20",borderRadius:10,padding:14,marginBottom:16}}>
      <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
        <span style={{fontSize:12,color:T.cyan,fontFamily:"monospace",fontWeight:700}}>📊 WIN RATE POR TIPO</span>
        <span style={{fontSize:9,color:T.dim,fontFamily:"monospace"}}>que senales aciertan mas (se afina con el tiempo)</span>
      </div>
      {hasSignal&&(
        <div style={{marginBottom:hasHour?12:0}}>
          <div style={{fontSize:9,color:T.muted,fontFamily:"monospace",marginBottom:6}}>POR SEÑAL</div>
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
      </div>

      {/* Weekly report */}
      <WeeklyBanner weekly={weekly}/>

      {/* Combos activos y win rate por tipo */}
      <CombosPanel combos={liveData?.combos}/>
      <WinRatePanel bySignal={liveData?.winrate_by_signal} byHour={liveData?.winrate_by_hour}/>

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
