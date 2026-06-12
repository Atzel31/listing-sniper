"use client";
import { useState, useEffect, useRef } from "react";

// ─── CONFIG ───────────────────────────────────────────────────────────────────
// URL del bot en Railway — endpoint Flask /api/live
export const RAILWAY_API = "https://listing-sniper-production.up.railway.app";

// ─── UTILS ────────────────────────────────────────────────────────────────────
export const sleep = ms => new Promise(r => setTimeout(r, ms));
export const fmtUSD = n => {
  if (!n || isNaN(n)) return "$0";
  if (n >= 1e9) return "$" + (n/1e9).toFixed(2) + "B";
  if (n >= 1e6) return "$" + (n/1e6).toFixed(2) + "M";
  if (n >= 1e3) return "$" + (n/1e3).toFixed(1) + "K";
  return "$" + Number(n).toFixed(2);
};
export const pct = n => (parseFloat(n||0) >= 0 ? "+" : "") + parseFloat(n||0).toFixed(1) + "%";
export const shortAddr = a => a ? a.slice(0,5)+"..."+a.slice(-4) : "—";
export const timeAgo = ts => {
  const d = Math.floor(Date.now()/1000 - ts);
  if (d < 60) return d+"s";
  if (d < 3600) return Math.floor(d/60)+"m";
  if (d < 86400) return Math.floor(d/3600)+"h";
  return Math.floor(d/86400)+"d";
};
export const scoreColor = s => s>=70?"#22c55e":s>=45?"#eab308":"#ef4444";
export const scoreLabel = s => s>=70?"Bajo riesgo":s>=45?"Riesgo medio":"Alto riesgo";
export const accumColor = s => s>=70?"#22c55e":s>=50?"#06b6d4":s>=30?"#eab308":"#ef4444";
export const accumLabel = s => s>=70?"Excelente":s>=50?"Bueno":s>=30?"Neutral":"Evitar";
export const chainCol = c => ({SOL:"#9945ff",ETH:"#6366f1",BNB:"#f0b90b",BASE:"#0052ff",CEX:"#888"})[c]||"#666";

// ─── EXCHANGE WALLETS (para referencia visual) ────────────────────────────────
export const EX_ETH = [
  {address:"0x75e89d5979E4f6Fba9F97c104c2F0AFB3F1dcB88",ex:"MEXC"},
  {address:"0x6cc5f688a315f3dc28a7781717a9a798a59fda7b",ex:"MEXC"},
  {address:"0xd24400ae8BfEBb18cA49Be86258a3C749cf46853",ex:"MEXC"},
  {address:"0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23",ex:"BITGET"},
  {address:"0x0d0707963952f2fba59dd06f2b425ace40b492fe",ex:"BITGET"},
  {address:"0xf89d7b9c864f589bbf53a82105107622b35eaa40",ex:"BYBIT"},
  {address:"0xbaed383ede0e5d9d72430661f3285daa77e9439f",ex:"BYBIT"},
  {address:"0xf977814e90da44bfa03b6295a0616a897441acec",ex:"BINANCE"},
  {address:"0x161ba15a5f335c9f06bb5bbb0a9ce14076fbb645",ex:"BINANCE"},
  {address:"0x4b4e14a3773ee558b6597070797fd51eb48606e5",ex:"OKX"},
];

// ─── WATCHLIST PRESET ─────────────────────────────────────────────────────────
export const PRESET_WATCH = [
  {id:1,contract:"9AvytnUKsLxPxFHFqS6VLxaxt5p6BhYNr53SD2Chpump",chain:"SOL",name:"67"},
  {id:2,contract:"Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk", chain:"SOL",name:"USELESS"},
  {id:3,contract:"63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9", chain:"SOL",name:"GIGA"},
  {id:4,contract:"BFgdzMkTPdKKJeTipv2njtDEwhKxkgFueJQfJGt1jups", chain:"SOL",name:"URANUS"},
  {id:5,contract:"8wXtPeU6557ETkp9WHFY1n1EcU6NxDvbAggHGsMYiHsB", chain:"SOL",name:"GME"},
  {id:6,contract:"0xE0f63A424a4439cBE457D80E4f4b51aD25b2c56C",    chain:"ETH",name:"SPX6900"},
];

export const SEED_WHALES = [
  {address:"0xab5801a7d398351b8be11c439e05c5b3259aec9b",label:"Vitalik.eth",chain:"ETH",pinned:true,hits:5,trust:92},
  {address:"0x220866B1A2219f40e72f5c628B65D54268cA3A9D",label:"ETH Alpha",chain:"ETH",pinned:false,hits:3,trust:71},
  {address:"DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",label:"SOL Smart Money",chain:"SOL",pinned:true,hits:7,trust:89},
  {address:"9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",label:"SOL Whale",chain:"SOL",pinned:false,hits:2,trust:61},
];

// ─── ACCUMULATION LIST (referencia, los datos reales vienen de Railway) ──────
export const ACCUMULATION_LIST = [
  {contract:"0x57e114B691Db790C35207b2e685D4A43181e6061",chain:"ETH",name:"ENA"},
  {contract:"0xfAbA6f8e4a5E8Ab82F62fe7C39859FA577269BE3",chain:"ETH",name:"ONDO"},
  {contract:"0x6982508145454Ce325dDbE47a25d4ec3d2311933",chain:"ETH",name:"PEPE"},
  {contract:"0xE0f63A424a4439cBE457D80E4f4b51aD25b2c56C",chain:"ETH",name:"SPX6900"},
  {contract:"0x1495bc9e44af1f8bcb62278d2bec4540cf0c05ea",chain:"ETH",name:"DEAI"},
  {contract:"0x54991328ab43c7d5d31c19d1b9fa048e77b5cd16",chain:"ETH",name:"SOIL"},
  {contract:"0x1865dc79a9e4b5751531099057d7ee801033d268",chain:"ETH",name:"LKI"},
  {contract:"4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",chain:"SOL",name:"RAY"},
  {contract:"5UUH9RTDiSpq6HKS6bp4NdU9PNJpXRXuiw6ShBTBhgH2",chain:"SOL",name:"TROLL"},
  {contract:"63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9",chain:"SOL",name:"GIGA"},
  {contract:"GtDZKAqvMZMnti46ZewMiXCa4oXF4bZxwQPoKzXPFxZn",chain:"SOL",name:"NUB"},
  {contract:"Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk", chain:"SOL",name:"USELESS"},
  {contract:"BFgdzMkTPdKKJeTipv2njtDEwhKxkgFueJQfJGt1jups", chain:"SOL",name:"URANUS"},
  {contract:"9AvytnUKsLxPxFHFqS6VLxaxt5p6BhYNr53SD2Chpump",chain:"SOL",name:"67"},
  {contract:"EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", chain:"SOL",name:"WIF"},
  {contract:"0xf4c8e32eadec4bfe97e0f595add0f4450a863a11",chain:"BNB", name:"THE"},
  {contract:"0x0A43fC31a73013089DF59194872Ecae4cAe14444",chain:"BNB", name:"4"},
  {contract:"0xAC1Bd2486aAf3B5C0fc3Fd868558b082a531B2B4",chain:"BASE",name:"TOSHI"},
  {contract:"0x532f27101965dd16442E59d40670FaF5eBB142E4",chain:"BASE",name:"BRETT"},
  {contract:"ronin",  chain:"CEX", name:"RON"},
  {contract:"arweave",chain:"CEX", name:"AR"},
];

// ─── SCORE ENGINE (sniper, replicado del bot para consistencia visual) ──────
export function calcScore(d) {
  let s = 50; const f = [];
  const add = (l,v,p) => { s+=v; f.push({l,v:(v>0?"+":"")+v,p}); };
  if (d.liq>200000)      add("Liquidez muy alta",18,true);
  else if (d.liq>80000)  add("Liquidez alta",12,true);
  else if (d.liq>20000)  add("Liquidez media",5,true);
  else                   add("Liquidez baja",-18,false);
  if (d.vol>500000)      add("Volumen muy alto",12,true);
  else if (d.vol>100000) add("Volumen alto",6,true);
  else if (d.vol>10000)  add("Volumen medio",2,true);
  else                   add("Volumen bajo",-8,false);
  if (d.txns>1000)       add("Actividad muy alta",10,true);
  else if (d.txns>300)   add("Actividad alta",5,true);
  else if (d.txns<30)    add("Actividad baja",-8,false);
  const pc=parseFloat(d.ch1h||0);
  if (pc>50)       add("Pump extremo 1h",-10,false);
  else if (pc>20)  add("Pump fuerte 1h",-4,false);
  else if (pc>5)   add("Momentum positivo",6,true);
  else if (pc<-20) add("Caida fuerte",-6,false);
  if ((d.wc||0)>=3)      add(d.wc+" whales compraron",d.wc*5,true);
  else if ((d.wc||0)>=2) add("2 whales compraron",10,true);
  else if ((d.wc||0)===1)add("1 whale compro",5,true);
  if (d.flow==="OUT")    add("Retiro de exchanges",12,true);
  else if (d.flow==="IN")add("Deposito a exchanges",-10,false);
  if (d.accum)           add("Acumulacion silenciosa",14,true);
  if ((d.liqG||0)>50)   add("Liquidez +50% en 2h",12,true);
  else if ((d.liqG||0)>25) add("Liquidez creciendo",6,true);
  if (d.bp>70)           add("Presion compradora alta",8,true);
  else if (d.bp<30)      add("Presion vendedora",-8,false);
  const bon={MEXC:8,BITGET:5,BYBIT:6,BINANCE:4,OKX:4,DEXSCREENER:2,WHALE:8,NEW_PAIR:3};
  if (bon[d.src])        add("Fuente: "+d.src,bon[d.src],true);
  if (d.chain==="SOL")   add("Solana (listings rapidos)",4,true);
  if (d.multi)           add("Multi-exchange",10,true);
  return {score:Math.max(5,Math.min(95,Math.round(s))),factors:f};
}

// ─── DEXSCREENER (cliente, para Sniper/Watchlist/Whales) ─────────────────────
export async function getDex(address, chain) {
  const chainId = chain==="SOL"?"solana":chain==="BNB"?"bsc":chain==="BASE"?"base":"ethereum";
  const base = "https://api.dexscreener.com/latest/dex/tokens/"+address;
  const urls = [base,"https://corsproxy.io/?"+base,"https://api.allorigins.win/raw?url="+encodeURIComponent(base)];
  for (const url of urls) {
    try {
      const r = await fetch(url,{headers:{Accept:"application/json"}});
      if (!r.ok) continue;
      const data = JSON.parse(await r.text());
      if (!data.pairs?.length) continue;
      let pairs = data.pairs.filter(p=>p.chainId===chainId);
      if (!pairs.length) pairs = data.pairs;
      if (!pairs.length) continue;
      const best = pairs.sort((a,b)=>(b.liquidity?.usd||0)-(a.liquidity?.usd||0))[0];
      const buys=best.txns?.h24?.buys||0, sells=best.txns?.h24?.sells||0, total=buys+sells;
      const rc=best.chainId||chainId, pair=best.pairAddress||"";
      const createdAt = best.pairCreatedAt ? Math.floor(best.pairCreatedAt/1000) : null;
      return {
        name:best.baseToken?.symbol||"UNKNOWN",
        liq:best.liquidity?.usd||0,
        vol:best.volume?.h24||0,
        vol5m:best.volume?.m5||0,
        ch1h:best.priceChange?.h1||0,
        ch6h:best.priceChange?.h6||0,
        ch24h:best.priceChange?.h24||0,
        txns:total,buys,sells,
        bp:total>0?Math.round((buys/total)*100):50,
        price:best.priceUsd||"0",
        fdv:best.fdv||0,
        mcap:best.marketCap||0,
        pair,realChain:rc,
        createdAt,
        ageHours: createdAt ? Math.floor((Date.now()/1000-createdAt)/3600) : null,
        chartUrl: pair?"https://dexscreener.com/"+rc+"/"+pair+"?embed=1&theme=dark&trades=0&info=0":null,
        dexUrl:   pair?"https://dexscreener.com/"+rc+"/"+pair:"https://dexscreener.com/"+chainId+"/"+address,
      };
    } catch { continue; }
  }
  return null;
}

export async function getNewPairs(chainId) {
  const urls = [
    "https://api.dexscreener.com/token-profiles/latest/v1",
    "https://corsproxy.io/?https://api.dexscreener.com/token-profiles/latest/v1",
  ];
  for (const url of urls) {
    try {
      const r = await fetch(url,{headers:{Accept:"application/json"}});
      if (!r.ok) continue;
      const data = await r.json();
      const items = Array.isArray(data) ? data : [];
      return items.filter(t=>t.chainId===chainId).slice(0,15);
    } catch { continue; }
  }
  try {
    const r = await fetch("https://api.dexscreener.com/token-boosts/latest/v1");
    if (!r.ok) return [];
    const data = await r.json();
    return (Array.isArray(data)?data:[]).filter(t=>t.chainId===chainId).slice(0,10);
  } catch { return []; }
}

export async function getBoosted(chainId) {
  try {
    const r = await fetch("https://api.dexscreener.com/token-boosts/latest/v1");
    if (!r.ok) return [];
    const data = await r.json();
    return (Array.isArray(data)?data:[]).filter(t=>t.chainId===chainId).slice(0,8);
  } catch { return []; }
}

export async function getEthTxs(address, key) {
  try {
    const k = key||"YourApiKeyToken";
    const r = await fetch("https://api.etherscan.io/api?module=account&action=tokentx&address="+address+"&sort=desc&page=1&offset=25&apikey="+k);
    const d = await r.json();
    return d.status==="1"?(d.result||[]):[];
  } catch { return []; }
}

export async function getEarlyBuyers(contract, apiKey) {
  try {
    const k = apiKey||"YourApiKeyToken";
    const r = await fetch("https://api.etherscan.io/api?module=account&action=tokentx&contractaddress="+contract+"&sort=asc&page=1&offset=30&apikey="+k);
    const d = await r.json();
    if (d.status!=="1") return [];
    const txs = d.result||[];
    const buyers = {};
    txs.forEach(tx => {
      const addr = tx.to?.toLowerCase();
      if (!addr) return;
      if (!buyers[addr]) buyers[addr] = {address:tx.to,txCount:0,firstBuy:parseInt(tx.timeStamp)};
      buyers[addr].txCount++;
    });
    return Object.values(buyers).sort((a,b)=>a.firstBuy-b.firstBuy).slice(0,10);
  } catch { return []; }
}

export async function sendNtfy(topic, title, body, priority) {
  if (!topic) return;
  try {
    await fetch("https://ntfy.sh/"+topic,{
      method:"POST",mode:"no-cors",
      headers:{"Content-Type":"text/plain"},
      body:title+"\n"+body,
    });
  } catch {}
}

// Fetch de datos en vivo desde Railway
export async function getLiveAccumData() {
  try {
    const r = await fetch(RAILWAY_API+"/api/live",{headers:{Accept:"application/json"}});
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

// Fetch del reporte semanal desde GitHub (raw)
export async function getWeeklyReport(githubRepo) {
  if (!githubRepo) return null;
  try {
    const r = await fetch("https://raw.githubusercontent.com/"+githubRepo+"/main/data/weekly.json?t="+Date.now());
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

// ─── DESIGN SYSTEM ────────────────────────────────────────────────────────────
export const T = {
  bg:       "#080808",
  surface:  "#101010",
  card:     "#141414",
  border:   "#1e1e1e",
  borderHi: "#2a2a2a",
  text:     "#f0f0f0",
  muted:    "#606060",
  dim:      "#2a2a2a",
  green:    "#22c55e",
  yellow:   "#eab308",
  red:      "#ef4444",
  purple:   "#a855f7",
  pink:     "#ec4899",
  blue:     "#6366f1",
  orange:   "#f97316",
  cyan:     "#06b6d4",
};

// ─── BASE COMPONENTS ──────────────────────────────────────────────────────────
export function Badge({children, color="#666", small}) {
  return (
    <span style={{
      background:color+"18", border:"1px solid "+color+"33",
      color, fontSize:small?8:9, fontWeight:700,
      padding:small?"1px 4px":"1px 6px", borderRadius:4,
      fontFamily:"monospace", whiteSpace:"nowrap",
    }}>{children}</span>
  );
}

export function Stat({label,value,color}) {
  return (
    <div style={{display:"flex",flexDirection:"column",gap:2}}>
      <span style={{fontSize:9,color:T.muted,fontFamily:"monospace"}}>{label}</span>
      <span style={{fontSize:11,fontWeight:700,color:color||T.text,fontFamily:"monospace"}}>{value}</span>
    </div>
  );
}

export function ScoreRing({score,size=54,color}) {
  const c = color || scoreColor(score);
  const r=size/2-6; const C=2*Math.PI*r;
  return (
    <div style={{display:"flex",flexDirection:"column",alignItems:"center",flexShrink:0}}>
      <svg width={size} height={size} style={{transform:"rotate(-90deg)"}}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#1a1a1a" strokeWidth={5}/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={c} strokeWidth={5}
          strokeDasharray={C} strokeDashoffset={C-(score/100)*C} strokeLinecap="round"
          style={{transition:"all 0.8s ease"}}/>
      </svg>
      <div style={{marginTop:-(size-14),zIndex:1,textAlign:"center",marginBottom:size-20}}>
        <div style={{fontSize:size>50?13:10,fontWeight:900,color:c,lineHeight:1}}>{score}</div>
      </div>
    </div>
  );
}

export function Pulse({color}) {
  return (
    <span style={{display:"inline-block",width:6,height:6,borderRadius:"50%",
      background:color,boxShadow:"0 0 6px "+color,animation:"pulse 1.5s infinite"}}/>
  );
}

export function ChartEmbed({chartUrl, dexUrl, name}) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <button onClick={()=>setShow(s=>!s)} style={{
        width:"100%",background:show?T.green+"0d":T.bg,
        border:"1px solid "+(show?T.green+"33":T.border),
        color:show?T.green:T.muted,padding:"7px",borderRadius:6,
        cursor:"pointer",fontSize:9,fontFamily:"monospace",fontWeight:700,
        marginBottom:show?8:0,transition:"all 0.2s",
        display:"flex",alignItems:"center",justifyContent:"center",gap:6,
      }}>
        <span>{show?"▲":"▼"}</span>
        <span>{show?"Ocultar chart":"Ver chart en vivo — "+name}</span>
      </button>
      {show && (
        <div style={{borderRadius:8,overflow:"hidden",border:"1px solid "+T.border}}>
          {chartUrl ? (
            <iframe src={chartUrl} style={{width:"100%",height:320,border:"none",display:"block"}} title={name}/>
          ) : (
            <a href={dexUrl} target="_blank" rel="noopener noreferrer" style={{
              display:"block",padding:"20px",textAlign:"center",
              background:T.bg,color:T.muted,fontSize:10,fontFamily:"monospace",textDecoration:"none",
            }}>Ver en DexScreener ↗</a>
          )}
          <a href={dexUrl} target="_blank" rel="noopener noreferrer" style={{
            display:"block",textAlign:"center",background:T.bg,borderTop:"1px solid "+T.border,
            color:T.muted,padding:"6px",fontSize:9,fontFamily:"monospace",textDecoration:"none",
          }}>Abrir completo en DexScreener ↗</a>
        </div>
      )}
    </div>
  );
}

export function EmptyState({icon, text, sub}) {
  return (
    <div style={{padding:"48px 20px",textAlign:"center"}}>
      <div style={{fontSize:32,marginBottom:12,opacity:0.15}}>{icon}</div>
      <div style={{fontSize:13,color:T.muted,fontFamily:"monospace"}}>{text}</div>
      {sub&&<div style={{fontSize:10,color:T.dim,fontFamily:"monospace",marginTop:6}}>{sub}</div>}
    </div>
  );
}
