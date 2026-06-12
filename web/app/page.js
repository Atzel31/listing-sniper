"use client";
import { useState, useEffect, useRef } from "react";
import {
  T, Pulse, sleep, fmtUSD, pct,
  getDex, getBoosted, getNewPairs, getEthTxs, getEarlyBuyers, sendNtfy, calcScore,
  EX_ETH,
} from "./shared";
import { Setup, SniperTab, NewPairsTab, InsidersTab } from "./tabs_part1";
import { WatchlistTab, WhalesTab } from "./tabs_part2";
import { AccumulationTab } from "./tabs_part3";

// ─── HEADER ───────────────────────────────────────────────────────────────────
function Header({running,scanning,countdown,keys,onSetup,onToggleRun,tab,setTab,alerts,newPairsCount}) {
  const TABS = [
    {label:"Sniper",     icon:"◈",  count:alerts.length, color:T.green},
    {label:"Nuevos",     icon:"⚡",  count:newPairsCount, color:T.cyan},
    {label:"Insiders",   icon:"🎯", count:null,          color:T.orange},
    {label:"Watchlist",  icon:"◉",  count:null,          color:T.purple},
    {label:"Whales",     icon:"🐋", count:null,          color:T.pink},
    {label:"Acumulacion",icon:"📈", count:null,          color:T.cyan},
  ];
  return (
    <div style={{background:T.bg,borderBottom:"1px solid "+T.border,position:"sticky",top:0,zIndex:50}}>
      <div style={{maxWidth:840,margin:"0 auto",padding:"12px 16px 0"}}>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:10,marginBottom:12,flexWrap:"wrap"}}>
          <div style={{display:"flex",alignItems:"center",gap:10}}>
            <span style={{fontSize:15,fontWeight:700,color:T.text,letterSpacing:0.5}}>Alpha Terminal</span>
            <Pulse color={scanning?T.yellow:running?T.green:T.dim}/>
            <span style={{fontSize:10,color:T.muted,fontFamily:"monospace"}}>
              {scanning?"escaneando":running?"activo · "+countdown+"s":"inactivo"}
            </span>
          </div>
          <div style={{display:"flex",gap:6,alignItems:"center"}}>
            {keys.ntfyTopic&&<span style={{fontSize:9,color:T.green,border:"1px solid "+T.green+"22",padding:"2px 7px",borderRadius:4,fontFamily:"monospace"}}>🔔 {keys.ntfyTopic}</span>}
            <button onClick={onSetup} style={{background:"transparent",border:"1px solid "+T.border,color:T.dim,padding:"5px 9px",borderRadius:5,cursor:"pointer",fontSize:11}}>⚙</button>
            <button onClick={onToggleRun} style={{background:running?T.red+"10":T.green+"10",border:"1px solid "+(running?T.red+"33":T.green+"33"),color:running?T.red:T.green,padding:"5px 16px",borderRadius:5,cursor:"pointer",fontSize:10,fontWeight:700,transition:"all 0.2s"}}>
              {running?"Stop":"Start"}
            </button>
          </div>
        </div>
        <div style={{display:"flex",gap:0,overflowX:"auto"}}>
          {TABS.map((t,i)=>(
            <button key={i} onClick={()=>setTab(i)} style={{
              background:"transparent",border:"none",
              borderBottom:"2px solid "+(tab===i?t.color:"transparent"),
              color:tab===i?T.text:T.muted,
              padding:"7px 12px",cursor:"pointer",fontSize:10,
              fontWeight:tab===i?700:400,transition:"all 0.2s",
              marginBottom:-1,whiteSpace:"nowrap",
              display:"flex",alignItems:"center",gap:5,
            }}>
              <span>{t.icon}</span>
              <span>{t.label}</span>
              {t.count!==null&&t.count>0&&(
                <span style={{background:t.color+"20",color:t.color,fontSize:8,padding:"1px 5px",borderRadius:10,fontFamily:"monospace",fontWeight:900}}>{t.count}</span>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
let gId=1;
const gSeen=new Set();
const gNewSeen=new Set();

export default function App() {
  const [setup,setSetup]           = useState(false);
  const [keys,setKeys]             = useState({ethKey:"",ntfyTopic:"listingsniper-atzel",pumpThreshold:30,githubRepo:"Atzel31/listing-sniper"});
  const [running,setRunning]       = useState(false);
  const [scanning,setScanning]     = useState(false);
  const [alerts,setAlerts]         = useState([]);
  const [newPairs,setNewPairs]     = useState([]);
  const [insiderAlerts,setInsiderAlerts] = useState([]);
  const [tab,setTab]               = useState(5); // Inicia en Acumulacion
  const [scanLog,setScanLog]       = useState([]);
  const [scanCount,setScanCount]   = useState(0);
  const [countdown,setCountdown]   = useState(45);
  const [externalAddWhale,setExternalAddWhale] = useState(null);
  const [mounted, setMounted] = useState(false);

  const runRef  = useRef(false);
  const scanRef = useRef(false);
  const tickRef = useRef(null);
  const cdRef   = useRef(45);
  const keysRef = useRef(keys);
  const pumpAnalyzedRef = useRef(new Set());
  const insiderAlertsRef = useRef([]);
  useEffect(()=>{ keysRef.current=keys; },[keys]);

  // Cargar preferencias guardadas (localStorage solo en cliente)
  useEffect(()=>{
    setMounted(true);
    try {
      const saved = localStorage.getItem("alpha-terminal-keys");
      if (saved) setKeys(JSON.parse(saved));
    } catch {}
  },[]);

  function saveKeys(k) {
    setKeys(k);
    try { localStorage.setItem("alpha-terminal-keys", JSON.stringify(k)); } catch {}
  }

  function log(msg){setScanLog(p=>["["+new Date().toLocaleTimeString()+"] "+msg,...p].slice(0,15));}

  function pushAlert(a){
    const full={...a,id:gId++};
    setAlerts(p=>[full,...p].slice(0,100));
    const e=a.score>=70?"🟢":a.score>=45?"🟡":"🔴";
    log(e+" "+a.name+" ("+a.chain+") — "+a.score+"/100");
    if (a.source!=="WATCHLIST"){
      const t=keysRef.current.ntfyTopic;
      sendNtfy(t,e+" "+a.name+" ("+a.chain+") — "+a.score+"/100","Fuente: "+a.source+" | Liq: "+fmtUSD(a.liq)+" | 1h: "+pct(a.ch1h)+"\n"+(a.dexScreen||""),a.score>=70?"urgent":a.score>=45?"high":"default");
    }
  }

  async function analyzeInsiders(contract, chain, dex) {
    if (pumpAnalyzedRef.current.has(contract)) return;
    pumpAnalyzedRef.current.add(contract);
    log("🎯 Analizando insiders: "+dex.name);
    const apiKey=keysRef.current.ethKey||"YourApiKeyToken";
    const earlyBuyers=await getEarlyBuyers(contract,apiKey);
    if (!earlyBuyers.length) return;
    const prevAddresses=new Set(insiderAlertsRef.current.flatMap(a=>(a.earlyBuyers||[]).map(b=>b.address.toLowerCase())));
    const buyers=earlyBuyers.map(b=>({...b,appearsInMultiple:prevAddresses.has(b.address.toLowerCase())}));
    const insiderAlert={
      id:Date.now(),name:dex.name,contract,chain,
      liq:dex.liq,vol:dex.vol,ch1h:dex.ch1h,
      earlyBuyers:buyers,knownWhales:[],
      ts:Math.floor(Date.now()/1000),
      dexUrl:dex.dexUrl,
    };
    insiderAlertsRef.current=[insiderAlert,...insiderAlertsRef.current].slice(0,20);
    setInsiderAlerts([...insiderAlertsRef.current]);
  }

  async function runCycle() {
    if (scanRef.current) return;
    scanRef.current=true; setScanning(true);
    setScanCount(c=>c+1);
    log("Iniciando ciclo...");
    const apiKey=keysRef.current.ethKey||"YourApiKeyToken";
    const pumpTh=keysRef.current.pumpThreshold||30;

    try {
      for (const w of EX_ETH) {
        if (!runRef.current) break;
        log("ETH: "+w.ex+" "+w.address.slice(0,8)+"...");
        try {
          const txs=await getEthTxs(w.address,apiKey);
          await sleep(300);
          const now=Date.now()/1000;
          const recent=txs.filter(tx=>now-parseInt(tx.timeStamp)<14400);
          const contracts=[...new Set(recent.map(tx=>tx.contractAddress).filter(Boolean))];
          for (const contract of contracts) {
            if (gSeen.has(contract)) continue;
            const dex=await getDex(contract,"ETH");
            await sleep(400);
            if (!dex||dex.liq<5000) continue;
            gSeen.add(contract);
            const multi=EX_ETH.filter(x=>x.ex!==w.ex).some(x=>recent.some(tx=>tx.from?.toLowerCase()===x.address.toLowerCase()||tx.to?.toLowerCase()===x.address.toLowerCase()));
            const {score,factors}=calcScore({...dex,src:w.ex,chain:"ETH",wc:0,flow:"NEUTRAL",accum:false,liqG:0,multi});
            pushAlert({chain:"ETH",name:dex.name,contract,source:w.ex,multi,score,factors,ts:Math.floor(now),...dex,wc:0,flow:"NEUTRAL",accum:false,liqG:0,dexLink:"https://app.uniswap.org/#/swap?outputCurrency="+contract,dexScreen:dex.dexUrl||"https://dexscreener.com/ethereum/"+contract});
            if (parseFloat(dex.ch1h||0)>=pumpTh) await analyzeInsiders(contract,"ETH",dex);
            await sleep(400);
          }
        } catch {}
        await sleep(300);
      }

      if (runRef.current) {
        log("Nuevos pares ETH...");
        const pairs=await getNewPairs("ethereum");
        for (const p of pairs) {
          const addr=p.tokenAddress||p.baseToken?.address;
          if (!addr||gNewSeen.has(addr)) continue;
          gNewSeen.add(addr);
          const dex=await getDex(addr,"ETH");
          await sleep(400);
          if (!dex||dex.liq<3000) continue;
          const {score,factors}=calcScore({...dex,src:"NEW_PAIR",chain:"ETH",wc:0,flow:"NEUTRAL",accum:false,liqG:0,multi:false});
          const newItem={id:gId++,chain:"ETH",name:dex.name,contract:addr,source:"NEW_PAIR",score,factors,ts:Math.floor(Date.now()/1000),...dex,isNew:true,wc:0,flow:"NEUTRAL",accum:false,liqG:0,dexLink:"https://app.uniswap.org/#/swap?outputCurrency="+addr,dexScreen:dex.dexUrl||"https://dexscreener.com/ethereum/"+addr};
          setNewPairs(prev=>[newItem,...prev].slice(0,80));
          if (score>=65) pushAlert(newItem);
          if (parseFloat(dex.ch1h||0)>=pumpTh) await analyzeInsiders(addr,"ETH",dex);
          await sleep(300);
        }
      }

      if (runRef.current) {
        log("Nuevos pares SOL...");
        const pairs=await getNewPairs("solana");
        for (const p of pairs) {
          const addr=p.tokenAddress||p.baseToken?.address;
          if (!addr||gNewSeen.has(addr)) continue;
          gNewSeen.add(addr);
          const dex=await getDex(addr,"SOL");
          await sleep(400);
          if (!dex||dex.liq<2000) continue;
          const {score,factors}=calcScore({...dex,src:"NEW_PAIR",chain:"SOL",wc:0,flow:"NEUTRAL",accum:false,liqG:0,multi:false});
          const newItem={id:gId++,chain:"SOL",name:dex.name,contract:addr,source:"NEW_PAIR",score,factors,ts:Math.floor(Date.now()/1000),...dex,isNew:true,wc:0,flow:"NEUTRAL",accum:false,liqG:0,dexLink:"https://jup.ag/swap/SOL-"+addr,dexScreen:dex.dexUrl||"https://dexscreener.com/solana/"+addr};
          setNewPairs(prev=>[newItem,...prev].slice(0,80));
          if (score>=65) pushAlert(newItem);
          await sleep(300);
        }
      }

      if (runRef.current) {
        log("DexScreener boosted ETH...");
        const boosted=await getBoosted("ethereum");
        for (const t of boosted) {
          if (!t.tokenAddress||gSeen.has(t.tokenAddress)) continue;
          const dex=await getDex(t.tokenAddress,"ETH");
          await sleep(400);
          if (!dex||dex.liq<5000) continue;
          gSeen.add(t.tokenAddress);
          const {score,factors}=calcScore({...dex,src:"DEXSCREENER",chain:"ETH",wc:0,flow:"NEUTRAL",accum:false,liqG:0,multi:false});
          pushAlert({chain:"ETH",name:dex.name,contract:t.tokenAddress,source:"DEXSCREENER",score,factors,ts:Math.floor(Date.now()/1000),...dex,wc:0,dexLink:"https://app.uniswap.org/#/swap?outputCurrency="+t.tokenAddress,dexScreen:dex.dexUrl||"https://dexscreener.com/ethereum/"+t.tokenAddress});
          if (parseFloat(dex.ch1h||0)>=pumpTh) await analyzeInsiders(t.tokenAddress,"ETH",dex);
          await sleep(400);
        }
      }

      if (runRef.current) {
        log("DexScreener boosted SOL...");
        const boosted=await getBoosted("solana");
        for (const t of boosted) {
          if (!t.tokenAddress||gSeen.has(t.tokenAddress)) continue;
          const dex=await getDex(t.tokenAddress,"SOL");
          await sleep(400);
          if (!dex||dex.liq<3000) continue;
          gSeen.add(t.tokenAddress);
          const {score,factors}=calcScore({...dex,src:"DEXSCREENER",chain:"SOL",wc:0,flow:"NEUTRAL",accum:false,liqG:0,multi:false});
          pushAlert({chain:"SOL",name:dex.name,contract:t.tokenAddress,source:"DEXSCREENER",score,factors,ts:Math.floor(Date.now()/1000),...dex,wc:0,dexLink:"https://jup.ag/swap/SOL-"+t.tokenAddress,dexScreen:dex.dexUrl||"https://dexscreener.com/solana/"+t.tokenAddress});
          await sleep(400);
        }
      }
    } catch(e){log("Error: "+e.message);}

    log("Ciclo completo.");
    scanRef.current=false; setScanning(false);
    cdRef.current=45; setCountdown(45);
  }

  useEffect(()=>{
    if (running){
      runRef.current=true;
      runCycle();
      tickRef.current=setInterval(()=>{
        cdRef.current-=1; setCountdown(cdRef.current);
        if (cdRef.current<=0&&!scanRef.current&&runRef.current){cdRef.current=45;setCountdown(45);runCycle();}
      },1000);
    } else {
      runRef.current=false;
      clearInterval(tickRef.current);
      setScanning(false); cdRef.current=45; setCountdown(45);
    }
    return ()=>{runRef.current=false;clearInterval(tickRef.current);};
  },[running]);

  if (!mounted) {
    return <div style={{minHeight:"100vh",background:T.bg}}/>;
  }

  return (
    <div style={{minHeight:"100vh",background:T.bg,color:T.text,fontFamily:"-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",paddingBottom:60}}>
      <style>{`
        @keyframes slideDown{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:translateY(0)}}
        @keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
        *{box-sizing:border-box;margin:0;padding:0}
        input::placeholder{color:#2a2a2a!important}
        select option{background:#101010;color:#f0f0f0}
        ::-webkit-scrollbar{width:3px}
        ::-webkit-scrollbar-thumb{background:#222;border-radius:4px}
        a{transition:opacity 0.15s} a:hover{opacity:0.8}
        button:hover{opacity:0.85}
      `}</style>

      {setup&&<Setup initial={keys} onSave={k=>{saveKeys(k);setSetup(false);}}/>}

      <Header
        running={running} scanning={scanning} countdown={countdown}
        keys={keys} onSetup={()=>setSetup(true)}
        onToggleRun={()=>setRunning(r=>!r)}
        tab={tab} setTab={setTab}
        alerts={alerts} newPairsCount={newPairs.length}
      />

      <div style={{maxWidth:840,margin:"0 auto",padding:"20px 16px 0"}}>
        {tab===0&&<SniperTab alerts={alerts} running={running} scanning={scanning} countdown={countdown} scanLog={scanLog}/>}
        {tab===1&&<NewPairsTab newPairs={newPairs} running={running} scanning={scanning}/>}
        {tab===2&&<InsidersTab insiderAlerts={insiderAlerts} onAddWhale={(address,chain,label)=>setExternalAddWhale({address,chain,label})} pumpThreshold={keys.pumpThreshold||30}/>}
        {tab===3&&<WatchlistTab running={running} keys={keys} ntfyTopic={keys.ntfyTopic} onNewAlert={pushAlert}/>}
        {tab===4&&<WhalesTab running={running} ntfyTopic={keys.ntfyTopic} onNewAlert={pushAlert} externalAddWhale={externalAddWhale} setExternalAddWhale={setExternalAddWhale}/>}
        {tab===5&&<AccumulationTab githubRepo={keys.githubRepo}/>}

        <div style={{marginTop:24,padding:"10px 12px",background:T.surface,border:"1px solid "+T.border,borderRadius:7,fontSize:9,color:T.dim,fontFamily:"monospace",lineHeight:1.8}}>
          No es consejo financiero. Score orientativo. Verifica siempre antes de operar.
        </div>
      </div>
    </div>
  );
}
