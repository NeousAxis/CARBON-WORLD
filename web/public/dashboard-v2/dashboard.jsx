// Carbon World — single dashboard, real choropleth map, fully dynamic.
const { useState, useEffect, useRef, useMemo } = React;

// ============================================================
// DATA
// ============================================================
// Country-name → ISO2 lookup for matching topojson `name` properties.
const NAME_TO_ISO = {
  'France':'FR','Germany':'DE','Spain':'ES','Italy':'IT','Portugal':'PT',
  'United Kingdom':'GB','Norway':'NO','Sweden':'SE','Finland':'FI',
  'Belgium':'BE','Netherlands':'NL','Poland':'PL','Greece':'GR',
  'Russia':'RU','Ukraine':'UA','Turkey':'TR',
  'United States of America':'US','Canada':'CA','Mexico':'MX',
  'Brazil':'BR','Argentina':'AR','Colombia':'CO','Chile':'CL','Peru':'PE','Venezuela':'VE',
  'India':'IN','China':'CN','Japan':'JP','South Korea':'KR','Indonesia':'ID',
  'Vietnam':'VN','Thailand':'TH','Philippines':'PH','Malaysia':'MY',
  'Australia':'AU','New Zealand':'NZ',
  'Egypt':'EG','South Africa':'ZA','Kenya':'KE','Nigeria':'NG','Ethiopia':'ET',
  'Morocco':'MA','Algeria':'DZ',
  'Saudi Arabia':'SA','Iran':'IR','Iraq':'IQ','Israel':'IL',
};

// Live event seed — refreshed by simulator.
const SEED_EVENTS = [
  { id:1,  ts:0,  verdict:'MINT',    amount:48, title:'French Senate weakens EU nature restoration enforcement',  src:'Reuters',   country:'FR', frameworks:['PB','SDG-15'],         tx:'5a9f…c0d2' },
  { id:2,  ts:1,  verdict:'BURN',    amount:12, title:'Colombia ratifies Escazú Agreement expanded protections',     src:'El País',   country:'CO', frameworks:['UDHR','UNDRIP'],       tx:'b124…e4c8' },
  { id:3,  ts:2,  verdict:'MINT',    amount:96, title:'Indonesia approves coal-fired plant despite moratorium',      src:'AP',        country:'ID', frameworks:['PB','SDG-7','SDG-13'], tx:'8f2a…a18f' },
  { id:4,  ts:3,  verdict:'BURN',    amount:4,  title:'Portuguese court awards reparations to Roma community',       src:'Público',   country:'PT', frameworks:['UDHR','CRC'],          tx:'c710…8d14' },
  { id:5,  ts:4,  verdict:'NEUTRAL', amount:0,  title:'UN draft resolution on AI rights — pending review',           src:'UN News',   country:'US', frameworks:['UDHR'],                tx:'—', flagged:true },
  { id:6,  ts:5,  verdict:'MINT',    amount:24, title:'Australian mining wins appeal against indigenous land claim', src:'ABC',       country:'AU', frameworks:['UNDRIP','SDG-10'],     tx:'42e1…621a' },
  { id:7,  ts:6,  verdict:'BURN',    amount:8,  title:'EU Parliament strengthens child online safety directive',     src:'Politico',  country:'BE', frameworks:['CRC','UDHR'],          tx:'18fc…c921' },
  { id:8,  ts:7,  verdict:'MINT',    amount:32, title:'Brazil rolls back Amazon deforestation enforcement budget',   src:'Folha',     country:'BR', frameworks:['PB','UNDRIP'],         tx:'9a40…112d' },
  { id:9,  ts:8,  verdict:'BURN',    amount:16, title:'Kenya passes universal basic education funding act',          src:'Nation',    country:'KE', frameworks:['CRC','SDG-4'],         tx:'6e89…aa07' },
  { id:10, ts:9,  verdict:'MINT',    amount:18, title:'Japan extends nuclear plant operational lifetime to 80 yrs',  src:'Asahi',     country:'JP', frameworks:['PB','SDG-7'],          tx:'2c11…fe44' },
  { id:11, ts:10, verdict:'BURN',    amount:6,  title:'Norway sovereign fund divests from labour-violating firms',   src:'NRK',       country:'NO', frameworks:['ILO'],                 tx:'77b3…0a91' },
  { id:12, ts:11, verdict:'MINT',    amount:54, title:'Russia withdraws from Bern animal welfare convention',         src:'TASS',      country:'RU', frameworks:['ANIMAL'],              tx:'30af…ee72' },
  { id:13, ts:12, verdict:'BURN',    amount:14, title:'India launches green hydrogen national mission funding',      src:'Hindu',     country:'IN', frameworks:['PB','SDG-7'],          tx:'a91c…77b0' },
  { id:14, ts:13, verdict:'MINT',    amount:42, title:'China extends coal subsidy program through 2030',             src:'Xinhua',    country:'CN', frameworks:['PB','SDG-13'],         tx:'5d22…c401' },
  { id:15, ts:14, verdict:'BURN',    amount:9,  title:'South Africa ratifies migrant workers convention',             src:'Mail&G.',   country:'ZA', frameworks:['ILO','UDHR'],          tx:'fa18…d29e' },
];

// New event templates the simulator picks from
const EVENT_POOL = [
  { verdict:'MINT', amount:36, title:'Mexico delays single-use plastics ban implementation',  src:'Milenio',   country:'MX', frameworks:['PB','SDG-12'] },
  { verdict:'BURN', amount:11, title:'Germany triples solar deployment subsidy budget',        src:'DW',        country:'DE', frameworks:['PB','SDG-7'] },
  { verdict:'MINT', amount:64, title:'Saudi Arabia announces new megaproject in protected zone',src:'Al Arabiya',country:'SA', frameworks:['PB','UNDRIP'] },
  { verdict:'BURN', amount:7,  title:'Argentina criminalizes cross-border human trafficking',  src:'La Nación', country:'AR', frameworks:['UDHR','ILO'] },
  { verdict:'MINT', amount:28, title:'UK government cuts overseas climate aid by 40%',         src:'BBC',       country:'GB', frameworks:['PB','SDG-13'] },
  { verdict:'BURN', amount:5,  title:'Chile recognizes water as a constitutional human right', src:'Mercurio',  country:'CL', frameworks:['UDHR','PB'] },
  { verdict:'MINT', amount:22, title:'Iran lifts moratorium on offshore drilling',             src:'IRNA',      country:'IR', frameworks:['PB'] },
  { verdict:'BURN', amount:13, title:'Morocco mandates living wage in public procurement',     src:'Le Matin',  country:'MA', frameworks:['ILO','SDG-8'] },
  { verdict:'MINT', amount:38, title:'Nigeria approves new gas flaring exemptions',            src:'Premium',   country:'NG', frameworks:['PB','SDG-13'] },
  { verdict:'BURN', amount:10, title:'Sweden ratifies expanded child-soldier protection',      src:'SVT',       country:'SE', frameworks:['CRC'] },
];

// ============================================================
// I18N
// ============================================================
const I18N = {
  EN: { dashboard:'Dashboard', events:'Events', sources:'Sources', frameworks:'Frameworks', review:'Review queue', api:'API', partners:'Partners', about:'About',
        decisionMonitor:'Decision monitor', tagline:'A scientific reading of how today’s decisions impact the living world.',
        supply:'CBWD supply', minted24:'Minted · 24h', burned24:'Burned · 24h', queue:'Review queue', flagged:'Flagged',
        worldwide:'Verdicts worldwide', today:'Today', sevenDays:'7 days', thirtyDays:'30 days',
        topCountries:'Top countries · 24h', mintCount:'mint', burnCount:'burn',
        eventLog:'Live event log', supplyCurve:'Supply curve · 30 days', frameworkActivity:'Framework activity · 7 days',
        time:'Time', verdict:'Verdict', decision:'Decision', tx:'Solana tx', mainnet:'Solana · mainnet',
        nextRead:'Next read', search:'Search events, sources, tx…', breadcrumb:'Home · Dashboard',
        seeAll:'See all events', viewSolana:'View on Solana', live:'Live' },
  FR: { dashboard:'Tableau de bord', events:'Événements', sources:'Sources', frameworks:'Cadres', review:'File de revue', api:'API', partners:'Partenaires', about:'À propos',
        decisionMonitor:'Moniteur de décisions', tagline:'Une lecture scientifique de l’impact des décisions sur le vivant.',
        supply:'Offre CBWD', minted24:'Émis · 24h', burned24:'Brûlés · 24h', queue:'File de revue', flagged:'Signalés',
        worldwide:'Verdicts dans le monde', today:'Aujourd’hui', sevenDays:'7 jours', thirtyDays:'30 jours',
        topCountries:'Top pays · 24h', mintCount:'mint', burnCount:'burn',
        eventLog:'Journal en direct', supplyCurve:'Courbe de l’offre · 30 jours', frameworkActivity:'Activité par cadre · 7 jours',
        time:'Heure', verdict:'Verdict', decision:'Décision', tx:'Tx Solana', mainnet:'Solana · mainnet',
        nextRead:'Prochaine lecture', search:'Rechercher événements, sources, tx…', breadcrumb:'Accueil · Tableau de bord',
        seeAll:'Voir tous les événements', viewSolana:'Voir sur Solana', live:'En direct' },
};
const fmtNum = (n, locale) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, locale==='FR'?' ':',');

// ============================================================
// LOGO
// ============================================================
function Reticle({ size = 22 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" style={{ color:'var(--cw-accent)' }}>
      <g stroke="currentColor" strokeWidth="1.5" strokeLinecap="square">
        <circle cx="16" cy="16" r="10" />
        <circle cx="16" cy="16" r="2.5" fill="currentColor" stroke="none" />
        <line x1="16" y1="2" x2="16" y2="8" /><line x1="16" y1="24" x2="16" y2="30" />
        <line x1="2" y1="16" x2="8" y2="16" /><line x1="24" y1="16" x2="30" y2="16" />
      </g>
    </svg>
  );
}

// ============================================================
// SIDEBAR
// ============================================================
function Sidebar({ active, locale, onNav }) {
  const t = I18N[locale];
  const items = [
    { id:'dashboard', label:t.dashboard, glyph:'▦' },
    { id:'events',    label:t.events,    glyph:'◇' },
    { id:'sources',   label:t.sources,   glyph:'≡' },
    { id:'frameworks',label:t.frameworks,glyph:'◯' },
    { id:'review',    label:t.review,    glyph:'⊘', badge:12 },
    { id:'api',       label:t.api,       glyph:'⌘' },
    { id:'partners',  label:t.partners,  glyph:'✕' },
    { id:'about',     label:t.about,     glyph:'ⁱ' },
  ];
  return (
    <aside style={{ width:220, flex:'0 0 220px', background:'var(--cw-bg-0)', borderRight:'1px solid var(--cw-line)', display:'flex', flexDirection:'column', height:'100vh', position:'sticky', top:0 }}>
      <div style={{ height:56, display:'flex', alignItems:'center', gap:10, padding:'0 16px', borderBottom:'1px solid var(--cw-line)' }}>
        <Reticle size={22}/>
        <span style={{ fontSize:12, fontWeight:500, letterSpacing:'0.06em', color:'var(--cw-fg-0)' }}>CARBON.WORLD</span>
      </div>
      <div style={{ padding:'14px 16px 8px' }}><span className="cw-label" style={{ color:'var(--cw-fg-3)' }}>v1.4 · live</span></div>
      <nav style={{ flex:1, padding:'4px 8px', display:'flex', flexDirection:'column', gap:2 }}>
        {items.map(it => {
          const on = active === it.id;
          return (
            <a key={it.id} href="#" onClick={e => { e.preventDefault(); onNav?.(it.id); }} style={{
              display:'flex', alignItems:'center', gap:12, padding:'11px 12px', textDecoration:'none',
              color:on?'var(--cw-fg-0)':'var(--cw-fg-2)', background:on?'var(--cw-bg-2)':'transparent',
              borderLeft:on?'2px solid var(--cw-accent)':'2px solid transparent',
              fontSize:12, letterSpacing:'0.04em', textTransform:'uppercase',
            }}>
              <span style={{ width:16, textAlign:'center', color:on?'var(--cw-accent)':'var(--cw-fg-3)', fontSize:13 }}>{it.glyph}</span>
              <span style={{ flex:1 }}>{it.label}</span>
              {it.badge && <span style={{ fontSize:10, padding:'2px 5px', background:'var(--cw-accent)', color:'#111', fontWeight:700 }}>{it.badge}</span>}
            </a>
          );
        })}
      </nav>
      <div style={{ borderTop:'1px solid var(--cw-line)', padding:'12px 16px', fontSize:10, color:'var(--cw-fg-3)', lineHeight:1.6 }}>
        <div>OPEN SOURCE · NO PRE-MINE</div>
        <div>github/carbonworld</div>
      </div>
    </aside>
  );
}

// ============================================================
// TOPBAR
// ============================================================
function Topbar({ locale, onLocale }) {
  const t = I18N[locale];
  const [now, setNow] = useState(new Date());
  useEffect(() => { const id = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(id); }, []);
  const pad = n => String(n).padStart(2,'0');
  const time = `${now.getUTCFullYear()}-${pad(now.getUTCMonth()+1)}-${pad(now.getUTCDate())} ${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())} UTC`;
  return (
    <header style={{ height:56, display:'flex', alignItems:'center', gap:16, padding:'0 24px', borderBottom:'1px solid var(--cw-line)', background:'var(--cw-bg-0)', position:'sticky', top:0, zIndex:5 }}>
      <span className="cw-meta" style={{ color:'var(--cw-fg-3)' }}>{t.breadcrumb}</span>
      <div style={{ marginLeft:24, flex:'1 1 460px', maxWidth:460, display:'flex', alignItems:'center', gap:8, background:'var(--cw-bg-1)', border:'1px solid var(--cw-line)', height:32, padding:'0 12px' }}>
        <span style={{ color:'var(--cw-fg-3)', fontSize:12 }}>⌕</span>
        <input placeholder={t.search} style={{ flex:1, background:'transparent', border:'none', outline:'none', color:'var(--cw-fg-1)', fontFamily:'var(--cw-font-mono)', fontSize:12 }}/>
        <span className="cw-meta" style={{ border:'1px solid var(--cw-line)', padding:'1px 4px', fontSize:10 }}>⌘K</span>
      </div>
      <div style={{ marginLeft:'auto', display:'flex', alignItems:'center', gap:16 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <span className="cw-dot cw-dot--burn" style={{ animation:'cw-pulse 2s ease-in-out infinite' }}/>
          <span className="cw-meta">{t.mainnet}</span>
        </div>
        <span className="cw-meta" style={{ fontVariantNumeric:'tabular-nums' }}>{time}</span>
        <button onClick={() => onLocale(locale==='EN'?'FR':'EN')} style={{ background:'transparent', border:'1px solid var(--cw-line)', color:'var(--cw-fg-2)', padding:'4px 10px', fontFamily:'var(--cw-font-mono)', fontSize:11, letterSpacing:'0.08em', cursor:'pointer' }}>
          <span style={{ color:locale==='FR'?'var(--cw-fg-0)':'var(--cw-fg-3)' }}>FR</span>
          <span style={{ color:'var(--cw-fg-3)', margin:'0 4px' }}>·</span>
          <span style={{ color:locale==='EN'?'var(--cw-fg-0)':'var(--cw-fg-3)' }}>EN</span>
        </button>
      </div>
    </header>
  );
}

// ============================================================
// CARD
// ============================================================
function Card({ title, meta, action, children, style, noPad }) {
  return (
    <div style={{ background:'var(--cw-bg-1)', border:'1px solid var(--cw-line)', display:'flex', flexDirection:'column', minWidth:0, ...style }}>
      {(title || action) && (
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'14px 18px', borderBottom:'1px solid var(--cw-line)', gap:16, minHeight:52 }}>
          <div style={{ display:'flex', flexDirection:'column', gap:3, minWidth:0, flex:1 }}>
            {title && <span style={{ fontSize:13, fontWeight:500, color:'var(--cw-fg-0)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{title}</span>}
            {meta && <span className="cw-meta" style={{ whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{meta}</span>}
          </div>
          {action && <div style={{ flexShrink:0 }}>{action}</div>}
        </div>
      )}
      <div style={{ padding:noPad?0:'18px', flex:1, minWidth:0 }}>{children}</div>
    </div>
  );
}

// ============================================================
// ANIMATED COUNTER
// ============================================================
function useAnimatedNumber(target, dur=800) {
  const [val, setVal] = useState(target);
  const fromRef = useRef(target);
  const startRef = useRef(performance.now());
  useEffect(() => {
    fromRef.current = val;
    startRef.current = performance.now();
    let raf;
    const tick = (t) => {
      const e = Math.min(1, (t - startRef.current) / dur);
      const eased = 1 - Math.pow(1-e, 3);
      setVal(fromRef.current + (target - fromRef.current) * eased);
      if (e < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return val;
}

// ============================================================
// KPI
// ============================================================
function KPI({ label, value, locale, delta, deltaTone, sparkline, sub, tone }) {
  const animated = useAnimatedNumber(value);
  const valueColor = tone==='mint'?'var(--cw-mint)':tone==='burn'?'var(--cw-burn)':'var(--cw-fg-0)';
  const dColor = deltaTone==='mint'?'var(--cw-mint)':deltaTone==='burn'?'var(--cw-burn)':'var(--cw-fg-2)';
  return (
    <div style={{ background:'var(--cw-bg-1)', border:'1px solid var(--cw-line)', padding:'18px 20px', display:'flex', flexDirection:'column', gap:10, minHeight:140 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <span className="cw-label">{label}</span>
        {delta && <span className="mono" style={{ fontSize:11, color:dColor, padding:'2px 6px', border:`1px solid ${dColor}` }}>{delta}</span>}
      </div>
      <div style={{ display:'flex', alignItems:'baseline', gap:6, marginTop:4 }}>
        <span className="mono" style={{ fontSize:38, fontWeight:500, color:valueColor, letterSpacing:'-0.01em', fontVariantNumeric:'tabular-nums', lineHeight:1 }}>
          {tone==='mint'?'+':tone==='burn'?'−':''}{fmtNum(Math.abs(animated), locale)}
        </span>
      </div>
      {sub && <span className="cw-meta">{sub}</span>}
      {sparkline && <div style={{ marginTop:'auto' }}>{sparkline}</div>}
    </div>
  );
}

// ============================================================
// SPARKLINE — animates path
// ============================================================
function Sparkline({ data, color, height=32, fill=false }) {
  const w=200, h=height, pad=2;
  const min=Math.min(...data), max=Math.max(...data);
  const x = i => pad + (i/(data.length-1))*(w-pad*2);
  const y = v => pad + (1-(v-min)/((max-min)||1))*(h-pad*2);
  const d = data.map((p,i) => `${i===0?'M':'L'}${x(i).toFixed(1)},${y(p).toFixed(1)}`).join(' ');
  const area = d + ` L${x(data.length-1)},${h} L${x(0)},${h} Z`;
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ display:'block' }}>
      {fill && <path d={area} fill={color} opacity="0.18"/>}
      <path d={d} fill="none" stroke={color} strokeWidth="1.4" style={{ transition:'all 600ms cubic-bezier(.4,0,.2,1)' }}/>
    </svg>
  );
}

// ============================================================
// SUPPLY CHART (animated)
// ============================================================
function SupplyChart({ data, locale, height=260 }) {
  const w=1200, h=height, padL=64, padR=16, padT=20, padB=32;
  const min=Math.min(...data), max=Math.max(...data);
  const x = i => padL + (i/(data.length-1))*(w-padL-padR);
  const y = v => padT + (1-(v-min)/((max-min)||1))*(h-padT-padB);
  const d = data.map((p,i) => `${i===0?'M':'L'}${x(i).toFixed(1)},${y(p).toFixed(1)}`).join(' ');
  const area = d + ` L${x(data.length-1)},${h-padB} L${x(0)},${h-padB} Z`;
  const ticks = 5;
  const yTicks = Array.from({length:ticks}, (_,i) => min + (max-min)*(i/(ticks-1)));
  const labels = locale==='FR' ? ['Avr 03','Avr 10','Avr 17','Avr 24','Mai 01'] : ['Apr 03','Apr 10','Apr 17','Apr 24','May 01'];
  const last = data[data.length-1];
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ display:'block' }}>
      {yTicks.map((v,i) => (
        <g key={i}>
          <line x1={padL} x2={w-padR} y1={y(v)} y2={y(v)} stroke="var(--cw-line)" strokeDasharray="2 4"/>
          <text x={padL-8} y={y(v)+3} textAnchor="end" fontSize="10" fill="var(--cw-fg-3)" fontFamily="var(--cw-font-mono)">{fmtNum(v, locale)}</text>
        </g>
      ))}
      {labels.map((l,i) => {
        const xc = padL + (i/(labels.length-1))*(w-padL-padR);
        return <text key={i} x={xc} y={h-12} textAnchor="middle" fontSize="10" fill="var(--cw-fg-3)" fontFamily="var(--cw-font-mono)">{l}</text>;
      })}
      <path d={area} fill="var(--cw-accent)" opacity="0.10"/>
      <path d={d} fill="none" stroke="var(--cw-accent)" strokeWidth="1.6" style={{ transition:'all 600ms cubic-bezier(.4,0,.2,1)' }}/>
      <circle cx={x(data.length-1)} cy={y(last)} r="3.5" fill="var(--cw-accent)"/>
      <circle cx={x(data.length-1)} cy={y(last)} r="9" fill="var(--cw-accent)" opacity="0.25">
        <animate attributeName="r" values="6;14;6" dur="2.4s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.4;0;0.4" dur="2.4s" repeatCount="indefinite"/>
      </circle>
    </svg>
  );
}

// ============================================================
// CHOROPLETH WORLD MAP — uses real country SVG paths
// ============================================================
function WorldMap({ countryStats, height=440, locale='EN', range='today', onRange, focused, onHover }) {
  const t = I18N[locale];
  const W = 1000, H = 500;
  // Crop to drop most of antarctica
  const viewH = 420, viewY = 30;
  const countries = window.WORLD_COUNTRIES || [];

  // Compute color scale
  const max = Math.max(1, ...Object.values(countryStats).map(s => s.mint + s.burn));
  const intensity = (iso) => {
    const s = countryStats[iso];
    if (!s) return 0;
    return Math.min(1, (s.mint + s.burn) / max);
  };
  const colorFor = (iso) => {
    const s = countryStats[iso];
    if (!s) return 'var(--cw-bg-2)';
    const dom = s.mint > s.burn ? 'mint' : 'burn';
    const i = intensity(iso);
    if (i === 0) return 'var(--cw-bg-2)';
    // Use accent for mint-dominant (orange), burn-green for burn-dominant
    const baseR = dom==='mint' ? [255,132,0] : [182,255,206];
    const r = Math.round(baseR[0] * (0.35 + i*0.65));
    const g = Math.round(baseR[1] * (0.35 + i*0.65));
    const b = Math.round(baseR[2] * (0.35 + i*0.65));
    return `rgb(${r},${g},${b})`;
  };

  return (
    <div style={{ position:'relative', background:'var(--cw-bg-1)' }}>
      {/* Header overlay */}
      <div style={{ position:'absolute', top:14, left:18, right:18, display:'flex', justifyContent:'space-between', alignItems:'center', zIndex:2, pointerEvents:'none' }}>
        <div>
          <span style={{ fontSize:13, fontWeight:500, color:'var(--cw-fg-0)' }}>{t.worldwide}</span>
          <div className="cw-meta" style={{ marginTop:3 }}>{Object.keys(countryStats).length} countries · live</div>
        </div>
        <div style={{ display:'flex', gap:0, pointerEvents:'auto' }}>
          {[
            { id:'today',  l:t.today },
            { id:'7d',     l:t.sevenDays },
            { id:'30d',    l:t.thirtyDays },
          ].map((r,i,arr) => (
            <button key={r.id} onClick={() => onRange?.(r.id)} style={{
              background: range===r.id?'var(--cw-bg-2)':'transparent',
              color: range===r.id?'var(--cw-fg-0)':'var(--cw-fg-2)',
              border:'1px solid var(--cw-line-bright)',
              borderLeft: i>0 ? 'none' : '1px solid var(--cw-line-bright)',
              padding:'5px 12px', fontSize:11, letterSpacing:'0.08em', textTransform:'uppercase',
              fontFamily:'var(--cw-font-mono)', cursor:'pointer',
            }}>{r.l}</button>
          ))}
        </div>
      </div>

      <svg width="100%" viewBox={`0 ${viewY} ${W} ${viewH}`} preserveAspectRatio="xMidYMid meet" style={{ display:'block', height }}>
        <defs>
          <pattern id="cw-map-grid" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M20 0H0V20" stroke="var(--cw-line)" strokeWidth="0.5" fill="none" opacity="0.35"/>
          </pattern>
        </defs>
        <rect x="0" y={viewY} width={W} height={viewH} fill="url(#cw-map-grid)"/>

        {/* Countries */}
        {countries.map(c => {
          const iso = NAME_TO_ISO[c.name];
          const fill = colorFor(iso);
          const isFocused = iso && focused === iso;
          return (
            <path
              key={c.id}
              d={c.d}
              fill={fill}
              stroke={isFocused?'var(--cw-fg-0)':'var(--cw-line-bright)'}
              strokeWidth={isFocused?1.2:0.5}
              style={{ cursor: iso?'pointer':'default', transition:'fill 400ms linear' }}
              onMouseEnter={() => iso && onHover?.(iso)}
              onMouseLeave={() => onHover?.(null)}
            />
          );
        })}

        {/* Pulse rings on countries with activity */}
        {Object.entries(countryStats).map(([iso, s]) => {
          // Find centroid via the country path bounding box
          const country = countries.find(c => NAME_TO_ISO[c.name] === iso);
          if (!country) return null;
          // Quick centroid: parse first M command
          const m = country.d.match(/M([\d.\-]+),([\d.\-]+)/);
          if (!m) return null;
          const cx = parseFloat(m[1]), cy = parseFloat(m[2]);
          const dom = s.mint > s.burn ? 'var(--cw-mint)' : 'var(--cw-burn)';
          const size = Math.min(8, 3 + (s.mint + s.burn) / 30);
          return (
            <g key={iso}>
              <circle cx={cx} cy={cy} r={size} fill={dom} opacity="0.85"/>
              <circle cx={cx} cy={cy} r={size} fill="none" stroke={dom} strokeWidth="1">
                <animate attributeName="r" values={`${size};${size*3};${size}`} dur="2.2s" repeatCount="indefinite"/>
                <animate attributeName="opacity" values="0.7;0;0.7" dur="2.2s" repeatCount="indefinite"/>
              </circle>
            </g>
          );
        })}
      </svg>

      {/* Footer legend */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4, 1fr)', borderTop:'1px solid var(--cw-line)' }}>
        {[
          { l:'Mint-dominant', c:'var(--cw-mint)' },
          { l:'Burn-dominant', c:'var(--cw-burn)' },
          { l:'Inactive',      c:'var(--cw-bg-2)' },
          { l:'Live read every 15 min', c:null },
        ].map((it,i,arr) => (
          <div key={i} style={{ padding:'10px 14px', borderRight: i<arr.length-1 ? '1px solid var(--cw-line)' : 'none', display:'flex', alignItems:'center', gap:8 }}>
            {it.c && <span style={{ width:10, height:10, background:it.c }}/>}
            {!it.c && <span className="cw-dot cw-dot--burn" style={{ animation:'cw-pulse 2s infinite' }}/>}
            <span className="cw-label" style={{ color:'var(--cw-fg-2)' }}>{it.l}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// FRAMEWORK BAR
// ============================================================
function FrameworkBar({ code, positive, negative }) {
  const total = positive + negative;
  const pPct = total ? (positive/total)*100 : 50;
  return (
    <div style={{ display:'grid', gridTemplateColumns:'70px 1fr 110px', gap:12, alignItems:'center', padding:'10px 0', borderBottom:'1px solid var(--cw-line)' }}>
      <span className="mono" style={{ fontSize:12, color:'var(--cw-fg-1)' }}>{code}</span>
      <div style={{ position:'relative', height:8, background:'var(--cw-bg-2)', display:'flex' }}>
        <div style={{ width:`${pPct}%`, background:'var(--cw-burn)', transition:'width 600ms cubic-bezier(.4,0,.2,1)' }}/>
        <div style={{ flex:1, background:'var(--cw-mint)' }}/>
      </div>
      <div style={{ textAlign:'right' }}>
        <span className="mono" style={{ fontSize:11, color:'var(--cw-burn)' }}>+{positive}</span>
        <span className="mono" style={{ fontSize:11, color:'var(--cw-fg-3)' }}> / </span>
        <span className="mono" style={{ fontSize:11, color:'var(--cw-mint)' }}>−{negative}</span>
      </div>
    </div>
  );
}

// ============================================================
// EVENT ROW (with entry animation)
// ============================================================
function EventRow({ ev, isNew }) {
  const [entered, setEntered] = useState(!isNew);
  useEffect(() => { if (isNew) requestAnimationFrame(() => setEntered(true)); }, [isNew]);
  const vColor = ev.verdict==='MINT'?'var(--cw-mint)':ev.verdict==='BURN'?'var(--cw-burn)':'var(--cw-neutral)';
  const sign = ev.verdict==='MINT'?'+':ev.verdict==='BURN'?'−':'·';
  return (
    <div style={{
      display:'grid', gridTemplateColumns:'58px 26px 102px 1fr 124px 60px',
      gap:14, alignItems:'center', padding:'12px 0', borderBottom:'1px solid var(--cw-line)',
      opacity: entered?1:0, transform:`translateY(${entered?0:-8}px)`, transition:'all 320ms cubic-bezier(.4,0,.2,1)',
      background: isNew && !entered ? 'var(--cw-accent-dim)' : 'transparent',
    }}>
      <span className="mono" style={{ fontSize:11, color:'var(--cw-fg-3)' }}>{ev.t}</span>
      <span style={{ width:20, height:20, background:'var(--cw-bg-2)', display:'inline-flex', alignItems:'center', justifyContent:'center', fontSize:9, color:'var(--cw-fg-1)', letterSpacing:'0.06em' }}>{ev.country}</span>
      <div style={{ display:'flex', alignItems:'center', gap:8 }}>
        <span style={{ width:6, height:6, background:vColor }}/>
        <span className="mono" style={{ fontSize:11, fontWeight:500, color:vColor, letterSpacing:'0.08em' }}>{ev.verdict}</span>
        <span className="mono" style={{ fontSize:12, color:'var(--cw-fg-0)' }}>{sign}{ev.amount}</span>
      </div>
      <div style={{ minWidth:0 }}>
        <div className="mono" style={{ fontSize:13, color:'var(--cw-fg-0)', lineHeight:1.35, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{ev.title}</div>
        <div className="cw-meta" style={{ marginTop:2 }}>
          {ev.src} · {ev.frameworks.join(' · ')}
          {ev.flagged && <span style={{ color:'var(--cw-accent)' }}> · FLAGGED</span>}
        </div>
      </div>
      <span className="mono" style={{ fontSize:11, color:'var(--cw-fg-3)' }}>{ev.tx}</span>
      <span className="cw-meta" style={{ textAlign:'right' }}>{ev.frameworks.length} fw</span>
    </div>
  );
}

// ============================================================
// SCROLLING TICKER
// ============================================================
function Ticker({ events, locale }) {
  const t = I18N[locale];
  const items = events.slice(0, 8).map((e,i) => {
    const c = e.verdict==='MINT'?'var(--cw-mint)':e.verdict==='BURN'?'var(--cw-burn)':'var(--cw-neutral)';
    return (
      <span key={i}>
        <span style={{ color:'var(--cw-fg-3)', padding:'0 14px' }}>│</span>
        <span style={{ color:c, fontWeight:500 }}>{e.verdict}</span>
        <span style={{ padding:'0 6px', color:'var(--cw-fg-0)' }}>{e.verdict==='MINT'?'+':e.verdict==='BURN'?'−':'·'}{e.amount}</span>
        <span style={{ color:'var(--cw-fg-2)' }}>{e.country} · {e.title.slice(0, 50)}{e.title.length>50?'…':''}</span>
      </span>
    );
  });
  return (
    <div className="cw-ticker">
      <div className="cw-ticker__track" style={{ animationDuration:'80s' }}>{items}{items}</div>
    </div>
  );
}

// ============================================================
// LIVE DATA HOOK — fetches /data/export.json and polls every 30 s
// ============================================================
//
// Replaces the original simulator with a real-data fetcher tied to the
// production export.json (the same file the home dashboard reads). When
// the fetch fails or returns nothing, falls back to SEED_EVENTS so the
// preview never renders blank during dev.
//
// Mapping CarbonEvent (DB) → mockup event shape:
//   - id              → id
//   - decision        → verdict ('BURN' / 'MINT' / 'NEUTRAL')
//   - amount_crbn / 1000 (rounded) → amount  (K CBWD, mockup convention)
//   - event_title     → title
//   - event_source    → src
//   - country (canonical English name) → ISO-2 via NAME_TO_ISO
//   - frameworks      → flat list of strings from positive+negative aspects
//   - tx_hash         → 'xxxx…yyyy' truncation, or '—' when null
//   - created_at      → t (HH:MM UTC)

function timeAgoFromDate(d) {
  return `${String(d.getUTCHours()).padStart(2,'0')}:${String(d.getUTCMinutes()).padStart(2,'0')}`;
}

function truncateTx(hash) {
  if (!hash) return '—';
  if (hash.length <= 10) return hash;
  return hash.slice(0, 4) + '…' + hash.slice(-4);
}

function extractFrameworks(carbonEvent) {
  const out = new Set();
  for (const key of ['positive_aspects_json', 'negative_aspects_json']) {
    const raw = carbonEvent[key];
    if (!raw) continue;
    try {
      const list = JSON.parse(raw);
      if (Array.isArray(list)) {
        for (const aspect of list) {
          if (Array.isArray(aspect.frameworks)) {
            for (const f of aspect.frameworks) out.add(f);
          }
        }
      }
    } catch {/* ignore parse errors, leave frameworks empty */}
  }
  return Array.from(out);
}

function mapCarbonEvent(e) {
  return {
    id: e.id,
    ts: new Date(e.created_at).getTime() || 0,
    verdict: e.decision,
    amount: Math.max(0, Math.round((e.amount_crbn || 0) / 1000)),
    title: e.event_title || '',
    src: e.event_source || '',
    country: e.country ? (NAME_TO_ISO[e.country] || null) : null,
    frameworks: extractFrameworks(e),
    tx: truncateTx(e.tx_hash),
    flagged: !e.tx_hash,
    t: timeAgoFromDate(new Date(e.created_at)),
    _isNew: false,
  };
}

function buildSupplySeries(events, totalMinted, totalBurned) {
  // Build a 180-point cumulative supply curve from the chronological events.
  // Newest event last. If we have fewer than 180 events, pad the start with
  // the initial supply so the chart still renders smoothly.
  const sorted = [...events].sort((a, b) => a.ts - b.ts);
  const target = (totalMinted - totalBurned) / 1000;
  const series = [];
  let v = target;
  for (let i = sorted.length - 1; i >= 0; i--) {
    const e = sorted[i];
    series.unshift(v);
    const delta = e.verdict === 'MINT' ? e.amount : e.verdict === 'BURN' ? -e.amount : 0;
    v -= delta;
  }
  while (series.length < 180) series.unshift(series[0] ?? target);
  return series.slice(-180);
}

async function fetchLiveSnapshot() {
  const url = `/data/export.json?t=${Date.now()}`;
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`fetch /data/export.json failed: ${res.status}`);
  const data = await res.json();
  const rawEvents = Array.isArray(data.events) ? data.events : [];
  const mapped = rawEvents.map(mapCarbonEvent).slice(0, 60);
  const totalMinted = data.total_minted || 0;
  const totalBurned = data.total_burned || 0;
  return {
    events: mapped,
    supply: Math.round((totalMinted - totalBurned) / 1000),
    supplySeries: buildSupplySeries(mapped, totalMinted, totalBurned),
    generatedAt: data.generated_at || null,
  };
}

function useLiveSim() {
  // Initial state: empty events; the first fetch populates within 1 frame.
  // SEED_EVENTS are kept as fallback only if the fetch fails or returns 0.
  const [events, setEvents] = useState([]);
  const [supply, setSupply] = useState(0);
  const [supplySeries, setSupplySeries] = useState(() => {
    // Stub series so charts render before the first fetch lands
    return Array.from({ length: 180 }, () => 0);
  });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let previousTopId = null;

    async function refresh() {
      try {
        const snap = await fetchLiveSnapshot();
        if (cancelled) return;
        // Mark the very first new event _isNew so the row pulses
        const newTopId = snap.events[0]?.id;
        const decoratedEvents = snap.events.map(e => ({
          ...e,
          _isNew: previousTopId !== null && e.id === newTopId && newTopId !== previousTopId,
        }));
        previousTopId = newTopId ?? previousTopId;
        setEvents(decoratedEvents);
        setSupply(snap.supply);
        setSupplySeries(snap.supplySeries);
        setTick(v => v + 1);
      } catch (err) {
        // Fallback to SEED_EVENTS on first failure so the preview is never blank
        if (cancelled) return;
        if (events.length === 0) {
          const seeded = SEED_EVENTS.map(e => ({ ...e, t: '00:00', _isNew: false }));
          setEvents(seeded);
        }
        // Surface the error in the console for diagnosis but don't break the UI
        console.warn('[dashboard-v2] live fetch failed, falling back:', err);
      }
    }

    refresh(); // initial
    const id = setInterval(refresh, 30_000); // poll every 30 s (cron is */30 min on VPS)
    return () => { cancelled = true; clearInterval(id); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { events, supply, supplySeries, tick };
}

// ============================================================
// DASHBOARD
// ============================================================
function Dashboard() {
  const [locale, setLocale] = useState('EN');
  const [active, setActive] = useState('dashboard');
  const [mapRange, setMapRange] = useState('today');
  const [hoverIso, setHoverIso] = useState(null);
  const { events, supply, supplySeries } = useLiveSim();
  const t = I18N[locale];

  // Aggregate per country across selected range
  const countryStats = useMemo(() => {
    const slice = events.slice(0, mapRange==='today'?24:mapRange==='7d'?60:120);
    const agg = {};
    slice.forEach(e => {
      if (!agg[e.country]) agg[e.country] = { mint:0, burn:0, count:0 };
      if (e.verdict==='MINT') agg[e.country].mint += e.amount;
      if (e.verdict==='BURN') agg[e.country].burn += e.amount;
      agg[e.country].count++;
    });
    return agg;
  }, [events, mapRange]);

  // Sparklines
  const mintSpark = useMemo(() => Array.from({length:30}, (_,i) => 40+Math.cos(i/3)*15+Math.random()*8), []);
  const burnSpark = useMemo(() => Array.from({length:30}, (_,i) => 30+Math.sin(i/2.5)*10+Math.random()*5), []);

  // KPI totals (rolling 24h-ish)
  const recent = events.slice(0, 14);
  const minted24 = recent.filter(e => e.verdict==='MINT').reduce((s,e) => s+e.amount, 0);
  const burned24 = recent.filter(e => e.verdict==='BURN').reduce((s,e) => s+e.amount, 0);
  const flagged = events.filter(e => e.flagged).length + 11;

  // Top countries
  const topCountries = useMemo(() => {
    return Object.entries(countryStats)
      .map(([iso, s]) => ({ iso, ...s, total: s.mint + s.burn }))
      .sort((a,b) => b.total - a.total).slice(0, 6);
  }, [countryStats]);

  return (
    <div style={{ display:'flex', minHeight:'100vh', background:'var(--cw-bg-0)', color:'var(--cw-fg-1)', fontFamily:'var(--cw-font-mono)' }}>
      <Sidebar active={active} locale={locale} onNav={setActive}/>
      <div style={{ flex:1, minWidth:0 }}>
        <Topbar locale={locale} onLocale={setLocale}/>
        <Ticker events={events} locale={locale}/>

        <div style={{ padding:'24px 28px 64px', display:'flex', flexDirection:'column', gap:20 }}>
          {/* Header */}
          <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', gap:24, flexWrap:'wrap' }}>
            <div>
              <h1 style={{ fontSize:28, fontWeight:500, color:'var(--cw-fg-0)', letterSpacing:'0.02em', margin:0 }}>{t.decisionMonitor}</h1>
              <div style={{ marginTop:6, fontFamily:'var(--cw-font-serif)', fontSize:16, color:'var(--cw-fg-2)', maxWidth:680, lineHeight:1.5 }}>{t.tagline}</div>
            </div>
            <div style={{ display:'flex', gap:10 }}>
              <button style={btnGhost}>{t.viewSolana}</button>
              <button style={btnPrimary}>{t.seeAll} →</button>
            </div>
          </div>

          {/* KPI strip */}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:14 }}>
            <KPI label={t.supply + ' · CBWD'} value={supply} locale={locale} delta="↑ 0.03%"
              sparkline={<Sparkline data={supplySeries.slice(-60)} color="var(--cw-accent)" fill height={32}/>}
              sub="Net today: +412 CBWD"/>
            <KPI label={t.minted24} value={minted24} locale={locale} tone="mint" delta="↑ 12.4%" deltaTone="mint"
              sparkline={<Sparkline data={mintSpark} color="var(--cw-mint)" height={32}/>}
              sub={`${recent.filter(e => e.verdict==='MINT').length} events`}/>
            <KPI label={t.burned24} value={burned24} locale={locale} tone="burn" delta="↓ 4.1%" deltaTone="burn"
              sparkline={<Sparkline data={burnSpark} color="var(--cw-burn)" height={32}/>}
              sub={`${recent.filter(e => e.verdict==='BURN').length} events`}/>
            <KPI label={t.queue} value={flagged} locale={locale} delta="↑ 3"
              sparkline={<MiniBars/>}
              sub="Cleared 24h: 38 · avg 02h 14m"/>
          </div>

          {/* Map (huge) + side column */}
          <div style={{ display:'grid', gridTemplateColumns:'minmax(0, 2.2fr) minmax(0, 1fr)', gap:14 }}>
            <Card noPad style={{ overflow:'hidden' }}>
              <WorldMap
                countryStats={countryStats}
                locale={locale}
                range={mapRange}
                onRange={setMapRange}
                focused={hoverIso}
                onHover={setHoverIso}
                height={500}
              />
            </Card>

            <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
              <Card title={t.topCountries} meta={`${Object.keys(countryStats).length} active · live`}>
                {topCountries.length === 0 && <div className="cw-meta">No activity yet…</div>}
                {topCountries.map(c => (
                  <div key={c.iso}
                    onMouseEnter={() => setHoverIso(c.iso)}
                    onMouseLeave={() => setHoverIso(null)}
                    style={{
                      display:'grid', gridTemplateColumns:'30px 1fr 70px', gap:12, alignItems:'center',
                      padding:'10px 0', borderBottom:'1px solid var(--cw-line)', cursor:'pointer',
                      background: hoverIso===c.iso ? 'var(--cw-bg-2)' : 'transparent', transition:'background 120ms',
                    }}>
                    <span style={{ width:24, height:24, background:'var(--cw-bg-2)', display:'inline-flex', alignItems:'center', justifyContent:'center', fontSize:10, color:'var(--cw-fg-0)', letterSpacing:'0.06em' }}>{c.iso}</span>
                    <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                      <div style={{ flex:1, height:6, background:'var(--cw-bg-2)', position:'relative' }}>
                        <div style={{ position:'absolute', inset:0, width: `${(c.total / topCountries[0].total) * 100}%`, background: c.mint > c.burn ? 'var(--cw-mint)' : 'var(--cw-burn)', transition:'width 600ms cubic-bezier(.4,0,.2,1)' }}/>
                      </div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <span className="mono" style={{ fontSize:11, color:'var(--cw-mint)' }}>+{c.mint}</span>
                      <span className="mono" style={{ fontSize:11, color:'var(--cw-fg-3)' }}> / </span>
                      <span className="mono" style={{ fontSize:11, color:'var(--cw-burn)' }}>−{c.burn}</span>
                    </div>
                  </div>
                ))}
              </Card>

              <Card title={t.frameworkActivity} meta="+ positive · − negative">
                <FrameworkBar code="SDG"    positive={48} negative={72}/>
                <FrameworkBar code="UDHR"   positive={62} negative={38}/>
                <FrameworkBar code="ILO"    positive={24} negative={31}/>
                <FrameworkBar code="CRC"    positive={18} negative={9}/>
                <FrameworkBar code="UNDRIP" positive={12} negative={28}/>
                <FrameworkBar code="ANIMAL" positive={8}  negative={22}/>
                <FrameworkBar code="PB"     positive={14} negative={88}/>
              </Card>
            </div>
          </div>

          {/* Supply chart full width */}
          <Card title={t.supplyCurve} meta="hourly · UTC · live" noPad action={<ChartTabs/>}>
            <SupplyChart data={supplySeries} locale={locale} height={260}/>
          </Card>

          {/* Live event log */}
          <Card title={t.eventLog} meta={`${events.length} of 128 today · next read 15:00 UTC`} action={
            <div style={{ display:'flex', gap:0 }}>
              {['ALL','MINT','BURN','FLAGGED'].map((f,i,arr) => (
                <button key={f} style={{
                  background: i===0?'var(--cw-bg-2)':'transparent', color: i===0?'var(--cw-fg-0)':'var(--cw-fg-2)',
                  border:'1px solid var(--cw-line-bright)', borderLeft: i>0?'none':'1px solid var(--cw-line-bright)',
                  padding:'5px 12px', fontSize:11, letterSpacing:'0.08em', fontFamily:'var(--cw-font-mono)', cursor:'pointer',
                }}>{f}</button>
              ))}
            </div>
          }>
            <div style={{ display:'grid', gridTemplateColumns:'58px 26px 102px 1fr 124px 60px', gap:14, paddingBottom:8, borderBottom:'1px solid var(--cw-line-bright)' }}>
              <span className="cw-label">{t.time}</span><span className="cw-label">CC</span>
              <span className="cw-label">{t.verdict}</span><span className="cw-label">{t.decision}</span>
              <span className="cw-label">{t.tx}</span><span className="cw-label" style={{ textAlign:'right' }}>FW</span>
            </div>
            {events.slice(0, 12).map(e => <EventRow key={e.id} ev={e} isNew={e._isNew}/>)}
          </Card>
        </div>
      </div>
    </div>
  );
}

function ChartTabs() {
  const [sel, setSel] = useState('30D');
  return (
    <div style={{ display:'flex', gap:0 }}>
      {['1D','7D','30D','90D','1Y','ALL'].map((p,i) => (
        <button key={p} onClick={() => setSel(p)} style={{
          background: sel===p?'var(--cw-bg-2)':'transparent', color: sel===p?'var(--cw-fg-0)':'var(--cw-fg-2)',
          border:'1px solid var(--cw-line-bright)', borderLeft: i>0?'none':'1px solid var(--cw-line-bright)',
          padding:'5px 12px', fontSize:11, letterSpacing:'0.08em', fontFamily:'var(--cw-font-mono)', cursor:'pointer',
        }}>{p}</button>
      ))}
    </div>
  );
}

function MiniBars() {
  const bars = [3,6,4,9,7,12,5,8,12];
  const max = Math.max(...bars);
  return (
    <svg width="100%" height="32" viewBox="0 0 200 32" preserveAspectRatio="none" style={{ display:'block' }}>
      {bars.map((v,i) => (
        <rect key={i} x={i*22+2} y={32-(v/max)*30} width="18" height={(v/max)*30} fill="var(--cw-accent)" opacity={i===bars.length-1?1:0.5}/>
      ))}
    </svg>
  );
}

const btnPrimary = { background:'var(--cw-accent)', color:'#111', border:0, padding:'10px 16px', fontFamily:'var(--cw-font-mono)', fontSize:11, fontWeight:500, letterSpacing:'0.08em', textTransform:'uppercase', cursor:'pointer' };
const btnGhost = { background:'transparent', color:'var(--cw-fg-0)', border:'1px solid var(--cw-line-bright)', padding:'10px 16px', fontFamily:'var(--cw-font-mono)', fontSize:11, fontWeight:500, letterSpacing:'0.08em', textTransform:'uppercase', cursor:'pointer' };

ReactDOM.createRoot(document.getElementById('root')).render(<Dashboard/>);
