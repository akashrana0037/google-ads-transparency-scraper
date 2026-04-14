import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  ShieldCheck, Terminal, Ghost, Cpu, XCircle, ChevronRight,
  Download, Loader2, Play, Sun, Moon, Database, Zap, Activity,
  Target, Globe, Mail, Phone, ArrowUp, RefreshCcw, Plus,
  TrendingUp, Crosshair, BarChart3, Lock, Search
} from 'lucide-react';

const API_BASE = '/api';

/* ─── ECG Monitor ────────────────────────────────────────────────────────── */
const ECGMonitor = ({ className, status }) => {
  const isRunning = ['running','scraping_serp','harvesting_contacts','verifying_ads','discovering_keywords','awaiting_approval'].includes(status);
  const color = isRunning ? "var(--accent-main)" : "var(--text-muted)";
  return (
    <svg viewBox="0 0 120 30" className={className} preserveAspectRatio="none">
      <path
        d="M0 15 L18 15 L23 6 L28 24 L33 15 L60 15 L65 3 L70 27 L75 15 L120 15"
        fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round"
        className={isRunning ? 'heartbeat-active heartbeat-path' : 'heartbeat-idle heartbeat-path'}
      />
    </svg>
  );
};

/* ─── Logo ───────────────────────────────────────────────────────────────── */
const VectorEyeLogo = ({ className }) => (
  <svg className={className} viewBox="0 0 36 36" fill="none">
    <circle cx="18" cy="18" r="16" stroke="var(--accent-main)" strokeWidth="1.2" strokeDasharray="3 2" opacity="0.4"/>
    <circle cx="18" cy="18" r="9" fill="var(--accent-mute)" stroke="var(--accent-main)" strokeWidth="1.4"/>
    <circle cx="18" cy="18" r="3.5" fill="var(--accent-main)"/>
    <circle cx="18" cy="18" r="1.2" fill="white"/>
    <line x1="2" y1="18" x2="9" y2="18" stroke="var(--accent-main)" strokeWidth="1.4" strokeLinecap="round"/>
    <line x1="27" y1="18" x2="34" y2="18" stroke="var(--accent-main)" strokeWidth="1.4" strokeLinecap="round"/>
  </svg>
);

/* ─── Result Type Badge ──────────────────────────────────────────────────── */
const TypeBadge = ({ type }) => {
  if (type === 'Ad') return (
    <span className="badge-ad">
      <span style={{width:5,height:5,borderRadius:'50%',background:'var(--ad-color)',display:'inline-block'}}/>
      Paid Ad
    </span>
  );
  if (type === 'Local') return (
    <span className="badge-local">
      <span style={{width:5,height:5,borderRadius:'50%',background:'var(--local-color)',display:'inline-block'}}/>
      Local
    </span>
  );
  return (
    <span className="badge-organic">
      <span style={{width:5,height:5,borderRadius:'50%',background:'var(--organic-color)',display:'inline-block'}}/>
      Organic
    </span>
  );
};

/* ─── Stat Card ──────────────────────────────────────────────────────────── */
const StatCard = ({ label, value, icon: Icon, accentColor, subtext }) => (
  <div className="stat-card" style={{ '--stat-accent': accentColor }}>
    <div>
      <p className="section-label mb-1">{label}</p>
      <div className="text-3xl font-[900] text-[var(--text-primary)] tracking-tight leading-none">{value}</div>
      {subtext && <p className="text-[10px] text-[var(--text-muted)] mt-1">{subtext}</p>}
    </div>
    <div className="p-2.5 rounded-xl" style={{background: `${accentColor}14`}}>
      <Icon className="w-5 h-5" style={{color: accentColor, opacity: 0.8}} />
    </div>
  </div>
);
/* ─── CSV Download Button with TTL Countdown ────────────────────────────── */
const CsvDownloadButton = ({ href, secondsLeft }) => {
  const isExpired = secondsLeft === 0;
  const mins = Math.floor(secondsLeft / 60);
  const secs = secondsLeft % 60;
  const timeStr = secondsLeft !== null ? `${mins}:${secs.toString().padStart(2,'0')}` : null;
  const urgency = secondsLeft !== null && secondsLeft < 120 ? 'var(--danger)' : secondsLeft !== null && secondsLeft < 360 ? 'var(--warning)' : 'var(--success)';

  if (isExpired) return (
    <div className="flex items-center gap-2 w-full py-2.5 px-4 rounded-full border border-[var(--danger)]/20 bg-[var(--danger-mute)] text-[var(--danger)] text-[10px] font-extrabold uppercase tracking-widest opacity-60 cursor-not-allowed justify-center">
      <XCircle className="w-3.5 h-3.5" /> Report Expired
    </div>
  );

  return (
    <a href={href}
      className="flex items-center justify-between gap-3 w-full py-2.5 px-4 rounded-full border transition-all group"
      style={{ borderColor: `${urgency}30`, background: `${urgency}0D`, color: urgency }}
    >
      <div className="flex items-center gap-2 text-[10px] font-extrabold uppercase tracking-widest">
        <Download className="w-3.5 h-3.5" /> Export CSV Report
      </div>
      {timeStr && (
        <div className="flex items-center gap-1.5 mono text-[9px] font-bold" style={{ color: urgency }}>
          <span className="w-1.5 h-1.5 rounded-full animate-pulse flex-shrink-0" style={{ background: urgency }} />
          {timeStr} left
        </div>
      )}
    </a>
  );
};

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('ve_theme') || 'dark');
  const [keywords, setKeywords] = useState('');
  const [location, setLocation] = useState('India');
  const [pages, setPages] = useState(1);
  const [headless, setHeadless] = useState(true);
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [status, setStatus] = useState(null);
  const [customKeyword, setCustomKeyword] = useState('');
  const [editableKeywords, setEditableKeywords] = useState([]);
  const [csvSecondsLeft, setCsvSecondsLeft] = useState(null); // null = no CSV yet
  const statusRef = useRef(null);
  const elapsedRef = useRef(null);
  const csvExpiryRef = useRef(null);
  const csvCountdownRef = useRef(null);
  const logEndRef = useRef(null);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('ve_theme', theme);
  }, [theme]);

  useEffect(() => {
    const savedTask = localStorage.getItem('ve_task_id');
    if (savedTask) setTaskId(savedTask);
  }, []);

  useEffect(() => {
    if (!taskId) return;
    const poll = async () => {
      try {
        const [statusRes, resultsRes] = await Promise.all([
          axios.get(`${API_BASE}/status/${taskId}`),
          axios.get(`${API_BASE}/results/${taskId}`)
        ]);
        const s = statusRes.data;
        setTaskStatus(s);
        setStatus(s.status);
        setResults(resultsRes.data || []);

        // Start CSV countdown the moment csv_available flips true
        if (s.csv_available && !csvExpiryRef.current) {
          const expiresAt = Date.now() + 15 * 60 * 1000; // 15 min from now
          csvExpiryRef.current = expiresAt;
          csvCountdownRef.current = setInterval(() => {
            const left = Math.max(0, Math.floor((csvExpiryRef.current - Date.now()) / 1000));
            setCsvSecondsLeft(left);
            if (left === 0) clearInterval(csvCountdownRef.current);
          }, 1000);
          setCsvSecondsLeft(15 * 60);
        }
      } catch (err) {
        if (err.response?.status === 404) {
          setTaskId(null);
          localStorage.removeItem('ve_task_id');
        }
      }
    };
    poll();
    statusRef.current = setInterval(poll, 3000);
    return () => clearInterval(statusRef.current);
  }, [taskId]);

  useEffect(() => {
    if (!taskStatus?.start_time) return;
    if (['completed','failed','aborted','interrupted'].includes(taskStatus?.status)) {
      clearInterval(elapsedRef.current);
      return;
    }
    const start = new Date(taskStatus.start_time).getTime();
    elapsedRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(elapsedRef.current);
  }, [taskStatus?.start_time, taskStatus?.status]);

  const discoveredKeywords = taskStatus?.discovered_keywords || [];
  useEffect(() => {
    if (discoveredKeywords.length > 0 && editableKeywords.length === 0) {
      setEditableKeywords([...discoveredKeywords]);
    }
  }, [discoveredKeywords]);

  const formatElapsed = (s) => {
    const m = Math.floor(s / 60), sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${s}s`;
  };

  const handleStart = async () => {
    if (!keywords.trim() || isMissionActive) return;
    setLoading(true); setError(null); setResults([]); setElapsed(0); setEditableKeywords([]);
    try {
      const res = await axios.post(`${API_BASE}/scrape`, null, { params: { keywords, location, pages, headless } });
      const newTaskId = res.data.task_id;
      setTaskId(newTaskId);
      localStorage.setItem('ve_task_id', newTaskId);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start. Is the engine online?');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (approvedKeywords) => {
    if (!taskId) return;
    try { await axios.post(`${API_BASE}/confirm/${taskId}`, approvedKeywords); }
    catch (err) { console.error('Confirm failed:', err); }
  };

  const handleSyncManual = async () => {
    if (!taskId) return;
    setLoading(true);
    try {
      const [statusRes, resultsRes] = await Promise.all([
        axios.get(`${API_BASE}/status/${taskId}`),
        axios.get(`${API_BASE}/results/${taskId}`)
      ]);
      setTaskStatus(statusRes.data); setStatus(statusRes.data.status);
      setResults(resultsRes.data || []);
    } catch (err) { console.error('Sync failed:', err); }
    finally { setLoading(false); }
  };

  const handleAbort = async () => {
    if (!taskId) return;
    try { await axios.post(`${API_BASE}/abort/${taskId}`); }
    catch (err) { console.error('Abort failed:', err); }
  };

  const handleReset = () => {
    setTaskId(null); setStatus(null); setTaskStatus(null); setResults([]);
    setElapsed(0); setLoading(false); setError(null);
    setKeywords(''); setLocation('India'); setPages(1); setEditableKeywords([]);
    setCsvSecondsLeft(null);
    csvExpiryRef.current = null;
    if (csvCountdownRef.current) clearInterval(csvCountdownRef.current);
    localStorage.removeItem('ve_task_id');
  };

  const awaitingApproval = taskStatus?.status === 'awaiting_approval';

  const getStatusLabel = (s) => ({
    queued:'Queued', running:'Scanning...', scraping_serp:'SERP Extraction',
    harvesting_contacts:'Harvesting Intel', verifying_ads:'Ad Verification',
    awaiting_approval:'Keyword Approval', completed:'Mission Complete',
    failed:'System Failure', aborted:'Aborted', interrupted:'Offline/Halted'
  })[s] || s || 'Standby';

  const getStatusColor = (s) => {
    if (s === 'completed') return 'var(--success)';
    if (['failed','aborted'].includes(s)) return 'var(--danger)';
    if (['running','scraping_serp','harvesting_contacts','verifying_ads','discovering_keywords'].includes(s)) return 'var(--accent-main)';
    if (s === 'awaiting_approval') return 'var(--warning)';
    return 'var(--text-muted)';
  };

  const calcProgress = () => {
    const s = taskStatus?.status;
    if (!s || s === 'queued') return 0;
    const phases = { running:5, discovering_keywords:15, awaiting_approval:40, scraping_serp:60, harvesting_contacts:80, verifying_ads:95, completed:100, failed:100, aborted:100, interrupted:100 };
    const base = phases[s] || 0;
    const extra = s === 'scraping_serp' ? Math.min((taskStatus?.results_count || 0) * 2, 18) : 0;
    return Math.min(base + extra, 99.9).toFixed(1);
  };

  const isMissionActive = taskId && !['completed','failed','aborted','interrupted'].includes(taskStatus?.status);
  const adCount = results.filter(r => r.result_type === 'Ad').length;
  const organicCount = results.filter(r => r.result_type === 'Organic').length;
  const localCount = results.filter(r => r.result_type === 'Local').length;

  return (
    <div className="min-h-screen" style={{background:'var(--bg-color)'}}>
      <div className="aurora-bg" />

      {/* ── TOP NAV ── */}
      <nav className="sticky top-0 z-50 border-b border-[var(--card-border)] backdrop-blur-xl"
        style={{background:'rgba(var(--bg-rgb),0.82)'}}>
        <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <VectorEyeLogo className="w-7 h-7" />
            <div className="flex items-baseline gap-2">
              <span className="text-base font-[900] tracking-tight text-[var(--text-primary)]">
                Vector<span className="text-[var(--accent-main)]">Eye</span>
              </span>
              <span className="text-[9px] mono font-bold px-1.5 py-0.5 rounded bg-[var(--accent-mute)] text-[var(--accent-main)] border border-[var(--accent-main)]/20">
                PRO v5.2
              </span>
            </div>
            <div className="hidden md:flex items-center gap-1 ml-4 pl-4 border-l border-[var(--card-border)]">
              <span className="section-label">Sector Intelligence Commander</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* New Mission — always visible */}
            <button
              onClick={handleReset}
              title="Clear all and start a new mission"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest bg-[var(--accent-mute)] text-[var(--accent-main)] border border-[var(--accent-main)]/20 hover:bg-[var(--accent-main)] hover:text-white transition-all">
              <Plus className="w-3 h-3" /> New Mission
            </button>
            <div className="flex items-center gap-0.5 p-1 rounded-lg bg-[var(--input-bg)] border border-[var(--card-border)]">
              <button onClick={() => setTheme('light')}
                className={`p-1.5 rounded-md transition-all ${theme==='light' ? 'bg-[var(--accent-main)] text-white' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`}>
                <Sun className="w-3.5 h-3.5" />
              </button>
              <button onClick={() => setTheme('dark')}
                className={`p-1.5 rounded-md transition-all ${theme==='dark' ? 'bg-[var(--accent-main)] text-white' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`}>
                <Moon className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-[1400px] mx-auto px-4 md:px-6 py-6 space-y-5">

        {/* ── MAIN GRID: Left Control | Right Status ── */}
        <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-5 items-stretch">

          {/* ════ LEFT: MISSION CONTROL ════ */}
          <aside className="hud-panel border-beam p-6 flex flex-col gap-5 h-full">

            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-1.5 h-4 rounded-full bg-[var(--accent-main)]" />
                <h2 className="text-xs font-black uppercase tracking-widest text-[var(--text-primary)]">Mission Parameters</h2>
              </div>

              <div className="space-y-3">
                <div className="elite-input-wrapper">
                  <Crosshair className="elite-input-icon" />
                  <input id="sector-input" type="text" value={keywords}
                    onChange={e => setKeywords(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleStart()}
                    placeholder="Target sector — e.g. Dentist, Law Firm..."
                    className="elite-input w-full" disabled={isMissionActive}
                  />
                </div>
                <div className="elite-input-wrapper">
                  <Globe className="elite-input-icon" />
                  <input id="location-input" type="text" value={location}
                    onChange={e => setLocation(e.target.value)}
                    placeholder="Region — e.g. India, Dubai, London..."
                    className="elite-input w-full" disabled={isMissionActive}
                  />
                </div>
              </div>
            </div>

            {/* Page depth */}
            <div>
              <div className="flex items-center justify-between mb-2.5">
                <span className="section-label">Scan Depth</span>
                <span className="text-[10px] font-bold text-[var(--accent-main)] bg-[var(--accent-mute)] px-2 py-0.5 rounded-full border border-[var(--accent-main)]/20">
                  {pages} {pages === 1 ? 'Page' : 'Pages'} · ~{pages * 10} results
                </span>
              </div>
              <div className="segmented-container">
                <div className="segmented-slider"
                  style={{ left:`calc(${([1,2,5,10].indexOf(pages)/4)*100}% + 3px)`, width:'calc(25% - 6px)' }}
                />
                {[1,2,5,10].map(p => (
                  <button key={p} onClick={() => setPages(p)}
                    className={`segmented-btn ${pages===p?'active':''}`}
                    disabled={isMissionActive}>
                    {p}P
                  </button>
                ))}
              </div>
            </div>

            {/* Browser mode */}
            <div>
              <div className="flex items-center justify-between mb-2.5">
                <span className="section-label">Browser Mode</span>
                <span className="section-label text-[var(--accent-main)]">{headless ? 'STEALTH' : 'VISIBLE'}</span>
              </div>
              <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[var(--input-bg)] border border-[var(--card-border)]">
                {[
                  { val:true, icon: Ghost, label: 'Stealth', desc:'Headless — faster & silent' },
                  { val:false, icon: Cpu, label: 'Visual', desc:'Visible — for CAPTCHA solve' },
                ].map(({ val, icon: Icon, label, desc }) => (
                  <button key={String(val)} onClick={() => setHeadless(val)}
                    title={desc} disabled={isMissionActive}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-[10px] font-extrabold uppercase tracking-widest transition-all duration-200 ${
                      headless === val
                        ? 'bg-[var(--accent-main)] text-white shadow-sm'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--accent-mute)]'
                    }`}>
                    <Icon className="w-3.5 h-3.5" />{label}
                  </button>
                ))}
              </div>
            </div>

            {/* CTA */}
            <div className="space-y-2.5 pt-1 mt-auto">
              <button id="initiate-engine-btn" onClick={handleStart}
                disabled={isMissionActive || loading || !keywords.trim()}
                className="btn-mission w-full">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                {loading ? 'Initializing...' : 'Launch Intelligence Scan'}
              </button>

              {isMissionActive && (
                <button onClick={handleAbort}
                  className="flex items-center justify-center gap-2 w-full py-2.5 rounded-full border border-[var(--danger)]/25 bg-[var(--danger-mute)] text-[var(--danger)] text-[10px] font-extrabold uppercase tracking-widest hover:bg-[var(--danger)]/12 transition-all">
                  <XCircle className="w-3.5 h-3.5" /> Terminate Mission
                </button>
              )}

              {taskStatus?.csv_available && (
                <CsvDownloadButton href={`${API_BASE}/download/${taskId}`} secondsLeft={csvSecondsLeft} />
              )}
            </div>

            {error && (
              <div className="p-3 rounded-xl border border-[var(--danger)]/20 bg-[var(--danger-mute)] text-[var(--danger)] text-xs font-semibold">
                {error}
              </div>
            )}

            {/* Mission info footer */}
            {taskId && (
              <div className="pt-2 border-t border-[var(--card-border)] flex items-center justify-between">
                <span className="section-label">Mission ID</span>
                <span className="mono text-[9px] text-[var(--text-muted)] bg-[var(--input-bg)] px-2 py-1 rounded-md border border-[var(--card-border)]">
                  #{taskId}
                </span>
              </div>
            )}
          </aside>

          {/* ════ RIGHT: STATUS HUD ════ */}
          <div className="flex flex-col gap-5 h-full">

            {/* Status banner — with Mission Flow + System Readiness */}
            <div className="hud-panel border-beam p-5 flex-1 flex flex-col gap-0">

              {/* ── Header ── */}
              <div className="flex items-center justify-between gap-4 mb-3">
                <div>
                  <p className="section-label mb-1.5">Pipeline Status</p>
                  <div className="text-2xl font-[900] tracking-tight transition-all duration-500"
                    style={{ color: getStatusColor(taskStatus?.status), fontFamily:"'Plus Jakarta Sans',sans-serif" }}>
                    {getStatusLabel(taskStatus?.status)}
                  </div>
                  {taskStatus?.active_variant && isMissionActive && (
                    <p className="text-[10px] mono text-[var(--text-muted)] mt-0.5 truncate max-w-[340px]">
                      ⟶ {taskStatus.active_variant}
                    </p>
                  )}
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="section-label mb-1.5">Elapsed</p>
                  <div className="text-2xl font-[900] mono text-[var(--text-primary)]">{formatElapsed(elapsed)}</div>
                </div>
              </div>

              <ECGMonitor className="w-full h-7 mb-2" status={taskStatus?.status} />

              <div className="mb-5">
                <div className="w-full bg-[var(--card-border)] rounded-full h-1.5 overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${calcProgress()}%`,
                      background: `linear-gradient(90deg, var(--accent-main), var(--accent-pulse))`,
                      boxShadow: `0 0 8px rgba(var(--accent-rgb),0.45)`
                    }}
                  />
                </div>
                <div className="flex justify-between mt-1">
                  <span className="section-label">Overall Progress</span>
                  <span className="mono text-[9px] font-bold" style={{color:'var(--accent-main)'}}>{calcProgress()}%</span>
                </div>
              </div>

              {/* ── Divider ── */}
              <div className="h-px bg-[var(--card-border)] mb-5" />

              {/* ── Mission Flow Pipeline ── */}
              <div className="mb-5">
                <p className="section-label mb-4">Mission Flow</p>
                {(() => {
                  const s = taskStatus?.status;
                  const phases = [
                    {
                      id: 'discover',
                      label: 'Keyword Discovery',
                      sub: 'Google Autocomplete + Intent Templates',
                      icon: Search,
                      active: ['discovering_keywords','running','queued','awaiting_approval','scraping_serp','harvesting_contacts','verifying_ads','completed'].includes(s),
                      current: ['discovering_keywords','running','queued'].includes(s),
                      done: ['awaiting_approval','scraping_serp','harvesting_contacts','verifying_ads','completed'].includes(s),
                    },
                    {
                      id: 'approve',
                      label: 'Keyword Approval',
                      sub: 'Review & authorize targets',
                      icon: ShieldCheck,
                      active: ['awaiting_approval','scraping_serp','harvesting_contacts','verifying_ads','completed'].includes(s),
                      current: s === 'awaiting_approval',
                      done: ['scraping_serp','harvesting_contacts','verifying_ads','completed'].includes(s),
                    },
                    {
                      id: 'serp',
                      label: 'SERP Extraction',
                      sub: 'Ads · Organic · Local pack',
                      icon: Crosshair,
                      active: ['scraping_serp','harvesting_contacts','verifying_ads','completed'].includes(s),
                      current: s === 'scraping_serp',
                      done: ['harvesting_contacts','verifying_ads','completed'].includes(s),
                    },
                    {
                      id: 'harvest',
                      label: 'Contact Harvest',
                      sub: 'Emails · Phones · Socials',
                      icon: Database,
                      active: ['harvesting_contacts','verifying_ads','completed'].includes(s),
                      current: ['harvesting_contacts','verifying_ads'].includes(s),
                      done: s === 'completed',
                    },
                  ];
                  return (
                    <div className="flex flex-col gap-0">
                      {phases.map((phase, idx) => {
                        const Icon = phase.icon;
                        const color = phase.done ? 'var(--success)' : phase.current ? 'var(--accent-main)' : phase.active ? 'var(--accent-main)' : 'var(--text-muted)';
                        const bgColor = phase.done ? 'var(--success-mute)' : phase.current ? 'var(--accent-mute-strong)' : 'var(--input-bg)';
                        const borderColor = phase.done ? 'rgba(52,211,153,0.3)' : phase.current ? 'rgba(var(--accent-rgb),0.4)' : 'var(--card-border)';
                        return (
                          <div key={phase.id} className="flex items-stretch gap-4">
                            {/* Icon + Line Column */}
                            <div className="flex flex-col items-center flex-shrink-0 w-8">
                              <div className="w-8 h-8 rounded-lg flex items-center justify-center border transition-all duration-500 flex-shrink-0"
                                style={{ background: bgColor, borderColor, boxShadow: phase.current ? `0 0 12px rgba(var(--accent-rgb),0.25)` : 'none' }}>
                                {phase.done ? (
                                  <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none">
                                    <path d="M2.5 7L5.5 10L11.5 4" stroke="var(--success)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                  </svg>
                                ) : (
                                  <Icon className="w-3.5 h-3.5 transition-all duration-500" style={{ color, opacity: phase.active ? 1 : 0.35 }} />
                                )}
                              </div>
                              {idx < phases.length - 1 && (
                                <div className="w-px flex-1 my-1 rounded-full transition-all duration-700"
                                  style={{ background: phase.done ? 'var(--success)' : 'var(--card-border)', opacity: phase.done ? 0.5 : 0.4, minHeight: '16px' }}
                                />
                              )}
                            </div>
                            {/* Text Column */}
                            <div className="flex-1 pb-4">
                              <div className="flex items-center gap-2">
                                <p className="text-[11px] font-bold transition-all duration-500"
                                  style={{ color: phase.active ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                                  {phase.label}
                                </p>
                                {phase.current && (
                                  <span className="flex items-center gap-1 text-[8px] font-black uppercase tracking-widest text-[var(--accent-main)] bg-[var(--accent-mute)] px-1.5 py-0.5 rounded-full border border-[var(--accent-main)]/20">
                                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-main)] animate-pulse inline-block" />
                                    Running
                                  </span>
                                )}
                                {phase.done && (
                                  <span className="text-[8px] font-black uppercase tracking-widest text-[var(--success)] bg-[var(--success-mute)] px-1.5 py-0.5 rounded-full border border-[var(--success)]/20">
                                    Done
                                  </span>
                                )}
                              </div>
                              <p className="text-[9px] text-[var(--text-muted)] mt-0.5 opacity-70">{phase.sub}</p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}
              </div>

              {/* ── Divider ── */}
              <div className="h-px bg-[var(--card-border)] mb-5" />

              {/* ── System Readiness ── */}
              <div className="mt-auto">
                <p className="section-label mb-3">System Readiness</p>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: 'API', status: 'online', color: 'var(--success)' },
                    { label: 'Playwright', status: 'ready', color: 'var(--success)' },
                    { label: 'Stealth', status: 'active', color: 'var(--accent-main)' },
                    { label: 'Scraper', status: isMissionActive ? 'busy' : 'idle', color: isMissionActive ? 'var(--warning)' : 'var(--text-muted)' },
                    { label: 'Security', status: 'encrypted', color: 'var(--success)' },
                    { label: 'Output', status: '15m TTL', color: 'var(--text-muted)' },
                  ].map(({ label, status, color }) => (
                    <div key={label} className="flex flex-col gap-1 p-2.5 rounded-xl bg-[var(--input-bg)] border border-[var(--card-border)]">
                      <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }} />
                        <span className="section-label" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                      </div>
                      <span className="mono text-[9px] font-semibold" style={{ color }}>{status}</span>
                    </div>
                  ))}
                </div>
              </div>

            </div>

            {/* ── KEYWORD APPROVAL PANEL ── */}
            {awaitingApproval && (
              <div className="hud-panel shine-border p-5 animate-in" style={{borderRadius:'1.5rem',background:'rgba(245,158,11,0.04)'}}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="relative">
                      <div className="w-2.5 h-2.5 rounded-full bg-[var(--warning)]" />
                      <div className="w-2.5 h-2.5 rounded-full bg-[var(--warning)] absolute top-0 animate-ping opacity-60" />
                    </div>
                    <h3 className="text-xs font-black uppercase tracking-widest text-[var(--warning)]">
                      Keyword Intelligence Map
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="mono text-[9px] font-bold bg-[var(--warning-mute)] text-[var(--warning)] px-2 py-1 rounded-full border border-[var(--warning)]/25">
                      {editableKeywords.length}/{discoveredKeywords.length} selected
                    </span>
                  </div>
                </div>

                <p className="text-[11px] text-[var(--text-secondary)] mb-3 leading-relaxed">
                  Select keywords to scan. Each becomes a separate SERP query.
                  <span className="text-[var(--warning)] font-semibold"> Optimal: 8–15 targets.</span>
                </p>

                {/* Controls */}
                <div className="flex items-center gap-2 mb-3">
                  <button onClick={() => setEditableKeywords([...discoveredKeywords])}
                    className="text-[9px] font-black uppercase tracking-widest px-2.5 py-1.5 rounded-lg bg-[var(--accent-mute)] border border-[var(--accent-main)]/20 text-[var(--accent-main)] hover:bg-[var(--accent-main)] hover:text-white transition-all">
                    ✓ All
                  </button>
                  <button onClick={() => setEditableKeywords([])}
                    className="text-[9px] font-black uppercase tracking-widest px-2.5 py-1.5 rounded-lg bg-[var(--danger-mute)] border border-[var(--danger)]/20 text-[var(--danger)] hover:bg-[var(--danger)] hover:text-white transition-all">
                    ✕ None
                  </button>
                  <div className="ml-auto flex items-center gap-2">
                    <div className="w-20 bg-[var(--card-border)] rounded-full h-1 overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-500"
                        style={{
                          width:`${Math.min((editableKeywords.length/Math.max(discoveredKeywords.length,1))*100,100)}%`,
                          background:'linear-gradient(90deg, var(--accent-main), var(--warning))'
                        }}
                      />
                    </div>
                    <span className="section-label">{Math.round((editableKeywords.length/Math.max(discoveredKeywords.length,1))*100)}%</span>
                  </div>
                </div>

                {/* Chip grid */}
                <div className="overflow-y-auto custom-scrollbar mb-3" style={{maxHeight:'200px',minHeight:'60px'}}>
                  <div className="flex flex-wrap gap-1.5 pr-1 pb-1">
                    {discoveredKeywords.length === 0 ? (
                      <div className="w-full text-center py-5 section-label opacity-50">Scanning keywords...</div>
                    ) : discoveredKeywords.map((kw, i) => {
                      const isSelected = editableKeywords.includes(kw);
                      return (
                        <button key={i} onClick={() => setEditableKeywords(prev =>
                          isSelected ? prev.filter(k => k !== kw) : [...prev, kw]
                        )} className="keyword-chip" data-selected={isSelected} title={kw}>
                          <span className="keyword-chip-dot" style={{
                            background: isSelected ? 'var(--warning)' : 'var(--text-muted)',
                            opacity: isSelected ? 1 : 0.4
                          }} />
                          <span className="keyword-chip-text">{kw}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Manual inject */}
                <div className="relative mb-3">
                  <Zap className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--warning)] pointer-events-none" />
                  <input type="text" value={customKeyword} onChange={e => setCustomKeyword(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && customKeyword.trim()) {
                        setEditableKeywords(prev => [...prev, customKeyword.trim()]);
                        setCustomKeyword('');
                      }
                    }}
                    placeholder="Add custom keyword and press Enter..."
                    className="elite-input w-full !py-2 !pl-9 !text-xs !rounded-xl"
                  />
                </div>

                {/* Confirm */}
                <div className="flex gap-2.5">
                  <button onClick={() => handleConfirm(editableKeywords)} disabled={editableKeywords.length === 0}
                    className="flex-1 btn-mission !py-2.5 !text-[11px]">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    Authorize {editableKeywords.length} Keyword{editableKeywords.length !== 1 ? 's' : ''} → Launch
                  </button>
                  <button onClick={handleAbort}
                    className="px-4 py-2.5 rounded-full border border-[var(--danger)]/25 bg-[var(--danger-mute)] text-[var(--danger)] text-[10px] font-extrabold uppercase tracking-widest hover:bg-[var(--danger)]/15 transition-all">
                    Abort
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── STAT CARDS ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Total Leads" value={results.length} icon={Database}
            accentColor="var(--accent-main)" subtext="across all keywords" />
          <StatCard label="Paid Ads" value={adCount} icon={TrendingUp}
            accentColor="var(--ad-color)" subtext="actively advertising" />
          <StatCard label="Organic" value={organicCount} icon={Search}
            accentColor="var(--organic-color)" subtext="unpaid rankings" />
          <StatCard label="Local Pack" value={localCount} icon={Globe}
            accentColor="var(--local-color)" subtext="maps & places" />
        </div>

        {/* ── RESULTS TABLE ── */}
        <section className="hud-panel border-beam overflow-hidden" style={{display:'flex',flexDirection:'column',height:'520px'}}>
          {/* Table header */}
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--card-border)] flex-shrink-0"
            style={{background:'var(--surface-raised)'}}>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2.5">
                <div className="w-1.5 h-5 rounded-full bg-[var(--accent-main)] opacity-80" />
                <h2 className="text-xs font-black uppercase tracking-widest text-[var(--text-primary)]">
                  Intelligence Grid
                </h2>
                {results.length > 0 && (
                  <span className="mono text-[9px] font-bold px-2 py-0.5 rounded-full bg-[var(--accent-mute)] text-[var(--accent-main)] border border-[var(--accent-main)]/20">
                    {results.length} leads
                  </span>
                )}
              </div>
              {taskId && !isMissionActive && (
                <button onClick={handleReset}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[var(--accent-mute)] border border-[var(--accent-main)]/20 text-[var(--accent-main)] hover:bg-[var(--accent-main)] hover:text-white transition-all text-[9px] font-black uppercase tracking-widest">
                  <Plus className="w-3 h-3" /> New
                </button>
              )}
              {taskId && (
                <button onClick={handleSyncManual} disabled={loading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[var(--card-bg)] border border-[var(--card-border)] text-[var(--text-secondary)] hover:text-[var(--accent-main)] transition-all text-[9px] font-black uppercase tracking-widest disabled:opacity-30">
                  <RefreshCcw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                  Sync
                </button>
              )}
            </div>
            <div className="flex items-center gap-3">
              {taskStatus?.csv_available && csvSecondsLeft !== null && (
                csvSecondsLeft === 0 ? (
                  <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--danger-mute)] border border-[var(--danger)]/20 text-[var(--danger)] text-[9px] font-black uppercase tracking-widest opacity-60">
                    <XCircle className="w-3 h-3" /> Expired
                  </span>
                ) : (
                  <a href={`${API_BASE}/download/${taskId}`}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg border text-[9px] font-black uppercase tracking-widest transition-all"
                    style={{
                      borderColor: csvSecondsLeft < 120 ? 'rgba(239,68,68,0.3)' : csvSecondsLeft < 360 ? 'rgba(245,158,11,0.3)' : 'rgba(16,185,129,0.25)',
                      background: csvSecondsLeft < 120 ? 'rgba(239,68,68,0.08)' : csvSecondsLeft < 360 ? 'rgba(245,158,11,0.08)' : 'rgba(16,185,129,0.07)',
                      color: csvSecondsLeft < 120 ? 'var(--danger)' : csvSecondsLeft < 360 ? 'var(--warning)' : 'var(--success)'
                    }}>
                    <Download className="w-3 h-3" /> Export CSV
                    <span className="mono opacity-70">
                      {Math.floor(csvSecondsLeft/60)}:{(csvSecondsLeft%60).toString().padStart(2,'0')}
                    </span>
                  </a>
                )
              )}
              <span className="mono text-[9px] text-[var(--text-muted)] opacity-40">GOLIATH_v7.0</span>
            </div>
          </div>

          {/* Table body */}
          <div className="overflow-auto flex-1 custom-scrollbar">
            <table className="w-full text-left border-collapse min-w-[780px]">
              <thead className="sticky top-0 z-10" style={{background:'var(--surface-raised)'}}>
                <tr>
                  {['Company / Domain','Type','Ad Headline','Keywords','Contacts'].map((h,i) => (
                    <th key={h} className={`px-5 py-3 section-label border-b border-[var(--card-border)] ${i===4?'text-right':''}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {results.length > 0 ? results.map((res, i) => (
                  <tr key={res.domain + i} className="data-row group">
                    {/* Company */}
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-black uppercase flex-shrink-0 border"
                          style={{
                            background: res.result_type==='Ad' ? 'var(--ad-mute)' : res.result_type==='Local' ? 'var(--local-mute)' : 'var(--organic-mute)',
                            borderColor: res.result_type==='Ad' ? 'rgba(52,211,153,0.2)' : res.result_type==='Local' ? 'rgba(245,158,11,0.2)' : 'rgba(99,102,241,0.18)',
                            color: res.result_type==='Ad' ? 'var(--ad-color)' : res.result_type==='Local' ? 'var(--local-color)' : 'var(--organic-color)'
                          }}>
                          {res.company_name?.[0] || '?'}
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-bold text-[var(--text-primary)] truncate max-w-[200px] group-hover:text-[var(--accent-main)] transition-colors leading-tight">
                            {res.company_name}
                          </p>
                          <a href={`https://${res.domain}`} target="_blank" rel="noopener noreferrer"
                            className="text-[10px] text-[var(--text-muted)] hover:text-[var(--accent-main)] flex items-center gap-1 mt-0.5 transition-colors w-fit">
                            <Globe className="w-2.5 h-2.5 flex-shrink-0" />
                            <span className="truncate max-w-[160px]">{res.domain}</span>
                          </a>
                        </div>
                      </div>
                    </td>

                    {/* Type badge */}
                    <td className="px-5 py-3.5">
                      <TypeBadge type={res.result_type} />
                    </td>

                    {/* Ad headline / description */}
                    <td className="px-5 py-3.5 max-w-[220px]">
                      {res.ad_headline ? (
                        <div>
                          <p className="text-[11px] font-semibold text-[var(--text-primary)] truncate">{res.ad_headline}</p>
                          {res.ad_description && (
                            <p className="text-[10px] text-[var(--text-muted)] truncate mt-0.5">{res.ad_description}</p>
                          )}
                        </div>
                      ) : (
                        <span className="text-[10px] text-[var(--text-muted)] opacity-40">—</span>
                      )}
                    </td>

                    {/* Keywords cluster */}
                    <td className="px-5 py-3.5">
                      <div className="flex flex-wrap gap-1">
                        {res.matched_keywords?.slice(0,2).map((k,j) => (
                          <span key={j} className="text-[9px] font-medium px-1.5 py-0.5 rounded-md bg-[var(--input-bg)] text-[var(--text-muted)] border border-[var(--card-border)] truncate max-w-[100px]">
                            {k}
                          </span>
                        ))}
                        {(res.matched_keywords?.length || 0) > 2 && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-md bg-[var(--accent-mute)] text-[var(--accent-main)] border border-[var(--accent-main)]/20">
                            +{res.matched_keywords.length - 2}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Contacts */}
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {res.contacts?.emails?.length > 0 && (
                          <span title={res.contacts.emails[0]} className="flex items-center gap-1 text-[9px] font-bold text-[var(--success)] bg-[var(--success-mute)] px-1.5 py-0.5 rounded-md border border-[var(--success)]/20">
                            <Mail className="w-2.5 h-2.5" /> {res.contacts.emails.length}
                          </span>
                        )}
                        {res.contacts?.phones?.length > 0 && (
                          <span className="flex items-center gap-1 text-[9px] font-bold text-[var(--accent-main)] bg-[var(--accent-mute)] px-1.5 py-0.5 rounded-md border border-[var(--accent-main)]/20">
                            <Phone className="w-2.5 h-2.5" /> {res.contacts.phones.length}
                          </span>
                        )}
                        {!res.contacts?.emails?.length && !res.contacts?.phones?.length && (
                          <span className="text-[9px] text-[var(--text-muted)] opacity-30">—</span>
                        )}
                      </div>
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan="5" className="px-5 py-20 text-center">
                      <div className="flex flex-col items-center gap-4 opacity-40">
                        <div className="w-14 h-14 rounded-2xl border border-[var(--card-border)] bg-[var(--input-bg)] flex items-center justify-center">
                          <Activity className="w-6 h-6 text-[var(--accent-main)]" />
                        </div>
                        <div>
                          <p className="text-sm font-bold text-[var(--text-secondary)]">Awaiting Intelligence Stream</p>
                          <p className="section-label mt-1">Launch a mission to begin data collection</p>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── GHOST FEED / TERMINAL ── */}
        <section className="hud-panel p-5" style={{background:'var(--surface)'}}>
          <div className="flex items-center gap-2.5 mb-3 pb-3 border-b border-[var(--card-border)]">
            <Terminal className="w-3.5 h-3.5 text-[var(--accent-main)]" />
            <span className="text-[10px] font-black uppercase tracking-widest text-[var(--text-secondary)]">
              Ghost Feed — Live Telemetry
            </span>
            <div className="ml-auto flex items-center gap-2">
              {isMissionActive && <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent-main)] animate-pulse" />}
              <span className="section-label">{isMissionActive ? 'LIVE' : 'IDLE'}</span>
            </div>
          </div>
          <div className="space-y-1 max-h-36 overflow-y-auto pr-1 custom-scrollbar">
            {(taskStatus?.logs || []).slice().reverse().map((log, i) => (
              <div key={i} className="flex items-start gap-2 animate-in">
                <ChevronRight className="w-3 h-3 text-[var(--accent-pulse)] mt-0.5 flex-shrink-0 opacity-50" />
                <p className="mono text-[10px] text-[var(--text-secondary)] leading-snug">{log}</p>
              </div>
            ))}
            {(!taskStatus?.logs || taskStatus.logs.length === 0) && (
              <p className="mono text-[10px] text-[var(--text-muted)] opacity-30 italic">
                Engine offline — awaiting mission initialization...
              </p>
            )}
            <div ref={logEndRef} />
          </div>
        </section>

      </div>
    </div>
  );
}
