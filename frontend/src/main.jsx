import React, { lazy, Suspense, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, BarChart3, CheckCircle2, Cpu, FileText, HardDrive, KeyRound, LayoutDashboard, LogOut, Menu, Network, Play, Search, Server, ShieldCheck, Terminal, Users, X, Brain, GitBranch, Siren, ClipboardCheck } from 'lucide-react';
import './styles.css';
import './password-settings.css';

const API = import.meta.env.VITE_API_URL || '/api';
const MetricChart = lazy(() => import('./MetricChart.jsx'));
const nav = [{ id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard }, { id: 'processes', label: 'Processes', icon: Activity }, { id: 'services', label: 'Services', icon: Server }, { id: 'dependencies', label: 'Dependencies', icon: GitBranch }, { id: 'predictions', label: 'Forecasts & models', icon: Brain }, { id: 'root-causes', label: 'Root cause', icon: Search }, { id: 'recommendations', label: 'Recommendations', icon: ClipboardCheck }, { id: 'incidents', label: 'Incidents', icon: Siren }, { id: 'logs', label: 'System logs', icon: FileText }, { id: 'alerts', label: 'Alerts & anomalies', icon: AlertTriangle }, { id: 'admin', label: 'Operations & admin', icon: ShieldCheck }, { id: 'users', label: 'Users', icon: Users }, { id: 'audit', label: 'Audit history', icon: Terminal }];

async function request(path, options = {}, token) {
	let response;
	try {
		response = await fetch(`${API}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(options.headers || {}) } });
	} catch (error) {
		if (error instanceof TypeError) throw new Error('Cannot reach the API. Start the backend, then try again.');
		throw error;
	}
	if (response.status === 401 && token) {
		localStorage.removeItem('lap-session');
		window.dispatchEvent(new Event('lap-session-expired'));
		throw new Error('Your session expired. Please sign in again.');
	}
	if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `Request failed (${response.status})`);
	return response.json();
}

function Login({ onLogin, notice = '' }) { const [form, setForm] = useState({ username: 'admin', password: '' }); const [error, setError] = useState(''); const submit = async e => { e.preventDefault(); try { const data = await request('/auth/login', { method: 'POST', body: JSON.stringify(form) }); onLogin(data); } catch (err) { setError(err.message); } }; return <main className="login-shell"><div className="login-panel"><div className="brand-mark"><ShieldCheck size={22} /></div><p className="eyebrow">LINUX ADMIN INTELLIGENCE PLATFORM</p><h1>Know what your system is doing.</h1><p className="muted">Live telemetry, controlled operations, and evidence-backed alerts for Ubuntu.</p><form onSubmit={submit}><label>Username<input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} /></label><label>Password<input type="password" autoComplete="current-password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} /></label>{error && <p className="error">{error}</p>}<button className="primary full">Sign in <ShieldCheck size={16} /></button></form>{notice && <p className="password-updated" role="status">{notice}</p>}</div><div className="login-aside"><div><span className="signal-dot" /> LIVE SYSTEM OBSERVABILITY</div><h2>From signal<br />to confident action.</h2><p>Monitor the host, inspect the cause, and keep every administrative decision accountable.</p></div></main> }

function Stat({ icon: Icon, label, value, unit, tone = 'blue' }) { return <div className="stat"><div className={`stat-icon ${tone}`}><Icon size={18} /></div><div><span>{label}</span><strong>{value}{unit && <small>{unit}</small>}</strong></div></div> }
function Dashboard({ token }) {
	const [data, setData] = useState(null); const [info, setInfo] = useState(null); const [health, setHealth] = useState(null); const [diskInfo, setDiskInfo] = useState(null); const [collector, setCollector] = useState(null); const [error, setError] = useState(''); const [refreshing, setRefreshing] = useState(false); const [rangeHours, setRangeHours] = useState(24);
	const load = async () => {
		setRefreshing(true);
		try {
			const start = new Date(Date.now() - rangeHours * 60 * 60 * 1000).toISOString();
			const [metrics, history, system, hostHealth, disk, collectorHealth] = await Promise.all([request('/system/metrics', {}, token), request(`/system/metrics/history?start=${encodeURIComponent(start)}&limit=5000`, {}, token), request('/system/info', {}, token), request('/system/health', {}, token), request('/system/disk', {}, token), request('/health', {}, token)]);
			setData({ ...metrics, history }); setInfo(system); setHealth(hostHealth); setDiskInfo(disk); setCollector(collectorHealth); setError('');
		} catch (err) { setError(err.message); } finally { setRefreshing(false); }
	};
	useEffect(() => { load(); const timer = setInterval(load, 15000); return () => clearInterval(timer); }, [token, rangeHours]);
	if (error && !data) return <div className="error-block"><p>{error}</p><button className="primary" onClick={load}>Try again</button></div>;
	if (!data) return <Loading />;
	const m = data.latest; const interfaces = Object.entries(m.interface_stats || {}).map(([name, value]) => ({ name, ...value }));
	return <><header className="page-head"><div><p className="eyebrow">SYSTEM OVERVIEW</p><h1>Good morning, operator.</h1><p className="muted">{info?.hostname} · {info?.os}</p></div><div className="dashboard-actions"><div className={data.stale ? 'live-badge warning' : 'live-badge'}><span className="signal-dot" /> {data.stale ? 'Stale observation' : 'Live · refreshed every 15s'} · {new Date(m.timestamp).toLocaleTimeString()}</div><select className="filter-select" aria-label="Telemetry time range" value={rangeHours} onChange={event => setRangeHours(Number(event.target.value))}><option value={1}>Last hour</option><option value={6}>Last 6 hours</option><option value={24}>Last 24 hours</option><option value={168}>Last 7 days</option></select><button className="primary" disabled={refreshing} onClick={load}>{refreshing ? 'Refreshing…' : 'Refresh now'}</button></div></header>
		{error && <div className="error-block inline-error">{error}</div>}
		<section className="stats-grid"><Stat icon={Cpu} label="CPU usage" value={m.cpu_usage.toFixed(1)} unit="%" tone="orange" /><Stat icon={Activity} label="Memory usage" value={m.memory_usage.toFixed(1)} unit="%" tone="blue" /><Stat icon={HardDrive} label="Disk usage" value={m.disk_usage.toFixed(1)} unit="%" tone="green" /><Stat icon={Network} label="Network receive rate" value={formatBytes(m.network_received_rate)} unit="/s" tone="purple" /><Stat icon={Terminal} label="System uptime" value={formatUptime(info?.uptime_seconds)} tone="slate" /><Stat icon={Users} label="Processes observed" value={m.process_count} tone="orange" /></section>
		<Suspense fallback={<div className="loading">Loading telemetry chart…</div>}><MetricChart history={data.history} /></Suspense>
		<section className="lower-grid"><div className="panel"><div className="section-heading"><div><p className="eyebrow">HOST CONTEXT</p><h2>Runtime details</h2></div><CheckCircle2 className={health?.status === 'healthy' ? 'success' : 'muted'} size={20} /></div><dl className="details"><dt>Host health</dt><dd>{health?.status || 'unknown'} · {health?.open_alert_count || 0} open alerts · {health?.failed_service_count || 0} failed services</dd><dt>Collector</dt><dd>{collector?.collector?.status || 'unknown'} · last success {collector?.collector?.last_success_at || 'not yet'}</dd><dt>Linux integration</dt><dd>{collector?.linux_integration ? 'systemd available' : 'unavailable on this host'}</dd><dt>Memory available</dt><dd>{formatBytes(m.memory_available)}</dd><dt>Filesystem capacity</dt><dd>{formatBytes(m.disk_used_bytes)} used of {formatBytes(m.disk_total_bytes)}</dd><dt>Kernel</dt><dd>{info?.kernel}</dd><dt>Architecture</dt><dd>{info?.architecture}</dd><dt>Python runtime</dt><dd>{info?.python}</dd></dl></div><div className="panel alert-panel"><div className="section-heading"><div><p className="eyebrow">FILESYSTEMS</p><h2>Mount capacity</h2></div><HardDrive size={20} /></div><DataTable rows={diskInfo?.partitions || []} columns={[{ key: 'mountpoint', label: 'Mount' }, { key: 'filesystem', label: 'Type' }, { key: 'percent', label: 'Used', render: row => row.percent.toFixed(1) + '%' }, { key: 'free_bytes', label: 'Free', render: row => formatBytes(row.free_bytes) }]} empty="No filesystem capacity records are available." /></div></section>
		<section className="panel"><div className="section-heading"><div><p className="eyebrow">NETWORK INTERFACES</p><h2>Interface state and counters</h2></div></div><DataTable rows={interfaces} columns={[{ key: 'name', label: 'Interface' }, { key: 'is_up', label: 'State', render: row => row.is_up == null ? 'unknown' : row.is_up ? 'up' : 'down' }, { key: 'speed_mbps', label: 'Speed', render: row => row.speed_mbps ? row.speed_mbps + ' Mbps' : 'unknown' }, { key: 'bytes_received', label: 'Received', render: row => formatBytes(row.bytes_received) }, { key: 'bytes_sent', label: 'Sent', render: row => formatBytes(row.bytes_sent) }]} empty="Network interface counters are unavailable." /></section>
	</>;
}function formatBytes(bytes) { const units = ['B', 'KB', 'MB', 'GB', 'TB']; let value = bytes || 0; let index = 0; while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; } return `${value.toFixed(1)} ${units[index]}`; } function formatUptime(seconds = 0) { const days = Math.floor(seconds / 86400); const hours = Math.floor((seconds % 86400) / 3600); return `${days}d ${hours}h`; } function Loading() { return <div className="loading"><span className="spinner" /> Collecting live system data…</div> }
function DataTable({ columns, rows, empty = 'No records collected yet.' }) { return rows.length ? <div className="table-scroll"><table><thead><tr>{columns.map(col => <th key={col.key}>{col.label}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={row.id || row.pid || row.name || index}>{columns.map(col => <td key={col.key}>{col.render ? col.render(row) : row[col.key]}</td>)}</tr>)}</tbody></table></div> : <div className="empty">{empty}</div> }
function Processes({ token }) {
	const [rows, setRows] = useState([]); const [query, setQuery] = useState(''); const [error, setError] = useState(''); const [selected, setSelected] = useState(null);
	const load = async () => { try { setRows(await request('/processes', {}, token)); setError(''); } catch (err) { setError(err.message); } };
	useEffect(() => { load(); }, [token]);
	const inspect = async pid => { try { setSelected(await request(`/processes/${pid}`, {}, token)); } catch (err) { setError(err.message); } };
	const filtered = rows.filter(row => `${row.name} ${row.pid} ${row.user}`.toLowerCase().includes(query.toLowerCase()));
	return <Page title="Processes" kicker="PROCESS INTELLIGENCE" action={<><div className="search"><Search size={16} /><input placeholder="Search processes" value={query} onChange={e => setQuery(e.target.value)} /></div><button className="primary" onClick={load}>Refresh</button></>}>
		{error && <div className="error-block">{error}</div>}<DataTable rows={filtered} columns={[{ key: 'pid', label: 'PID', render: row => <button className="text-button" onClick={() => inspect(row.pid)}>{row.pid}</button> }, { key: 'name', label: 'Process' }, { key: 'cpu_usage', label: 'CPU', render: row => `${row.cpu_usage.toFixed(1)}%` }, { key: 'memory_usage', label: 'Memory', render: row => `${row.memory_usage.toFixed(1)}%` }, { key: 'status', label: 'Status', render: row => <span className="pill neutral">{row.status}</span> }, { key: 'user', label: 'User' }, { key: 'command', label: 'Command', render: row => <span className="command">{row.command || '—'}</span> }]} />
		{selected && <section className="process-detail"><div className="section-heading"><div><p className="eyebrow">PROCESS DETAIL</p><h2>{selected.name} · PID {selected.pid}</h2></div><button className="text-button" onClick={() => setSelected(null)}>Close</button></div><dl className="details"><dt>User</dt><dd>{selected.user}</dd><dt>State</dt><dd>{selected.status}</dd><dt>Started</dt><dd>{new Date(selected.start_time).toLocaleString()}</dd><dt>Command</dt><dd>{selected.command || '—'}</dd></dl></section>}
	</Page>;
}
function Services({ token }) {
	const [rows, setRows] = useState([]); const [query, setQuery] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(''); const [notice, setNotice] = useState('');
	const load = async () => { try { setRows(await request('/services', {}, token)); setError(''); } catch (err) { setError(err.message); } };
	useEffect(() => { load(); }, [token]);
	const restart = async name => {
		let assessment;
		try { assessment = await request('/impact/' + encodeURIComponent(name) + '?operation=restart', {}, token); }
		catch (err) { setNotice('Could not assess impact: ' + err.message); return; }
		const impact = assessment.impact; const risk = assessment.risk;
		const summary = 'Impact: ' + impact.classification + ' (' + impact.potentially_affected_services.length + ' dependent services). Risk: ' + risk.score + '/100 ' + risk.band + '. Unknowns: ' + (risk.unknowns.join(' ') || 'none reported') + '. Continue to create an approval request?';
		if (!window.confirm(summary)) return;
		const reason = window.prompt('Explain why you are requesting a restart of ' + name + ':');
		if (!reason) return;
		setBusy(name); setNotice('');
		try { const result = await request('/actions', { method: 'POST', body: JSON.stringify({ action_type: 'restart', target: name, reason }) }, token); setNotice(`${name}: request ${result.id} is ${result.state}. Waiting for administrator review.`); await load(); }
		catch (err) { setNotice(`${name}: ${err.message}`); }
		finally { setBusy(''); }
	};
	const filtered = rows.filter(row => `${row.name} ${row.description}`.toLowerCase().includes(query.toLowerCase()));
	return <Page title="Services" kicker="SYSTEMD INVENTORY" action={<><div className="search"><Search size={16} /><input placeholder="Search services" value={query} onChange={e => setQuery(e.target.value)} /></div><span className="live-badge">{rows.length} observed</span></>}>
		{error && <div className="error-block">{error} <button className="text-button" onClick={load}>Retry</button></div>}{notice && <p className="operation-notice" role="status">{notice}</p>}
		<DataTable rows={filtered} columns={[{ key: 'name', label: 'Service' }, { key: 'active', label: 'Active state', render: row => <span className={`pill ${row.active === 'active' ? 'good' : 'neutral'}`}>{row.active}</span> }, { key: 'status', label: 'Sub-state' }, { key: 'unit_file_state', label: 'Enablement' }, { key: 'description', label: 'Description' }, { key: 'name', label: 'Action', render: row => <button className="icon-button" disabled={Boolean(busy) || !row.allowed || row.active === 'unavailable'} title={`Restart ${row.name}`} aria-label={`Restart ${row.name}`} onClick={() => restart(row.name)}>{busy === row.name ? '…' : <Play size={15} />}</button> }]} empty="No services match this search, or systemd is unavailable on this host." />
	</Page>;
}
function Logs({ token }) {
	const [rows, setRows] = useState([]); const [query, setQuery] = useState(''); const [severity, setSeverity] = useState(''); const [error, setError] = useState('');
	useEffect(() => { const params = new URLSearchParams({ limit: '200' }); if (severity) params.set('severity', severity); request(`/logs?${params}`, {}, token).then(setRows).catch(err => setError(err.message)); }, [token, severity]);
	const filtered = rows.filter(row => `${row.source} ${row.message}`.toLowerCase().includes(query.toLowerCase()));
	return <Page title="System logs" kicker="JOURNAL STREAM" action={<><div className="search"><Search size={16} /><input placeholder="Search log messages" value={query} onChange={e => setQuery(e.target.value)} /></div><select className="filter-select" aria-label="Filter by severity" value={severity} onChange={e => setSeverity(e.target.value)}><option value="">All severity</option>{['emergency','alert','critical','error','warning','notice','info','debug'].map(item => <option key={item}>{item}</option>)}</select></>}>
		{error && <div className="error-block">{error}</div>}<DataTable rows={filtered} columns={[{ key: 'timestamp', label: 'Timestamp' }, { key: 'source', label: 'Source' }, { key: 'severity', label: 'Severity', render: row => <span className={`pill ${['error','critical','alert','emergency'].includes(row.severity) ? 'bad' : 'neutral'}`}>{row.severity}</span> }, { key: 'message', label: 'Message' }]} empty="No journal entries are available. Run this backend on Ubuntu with journalctl access." />
	</Page>;
}
function Alerts({ token, role }) {
	const [alerts, setAlerts] = useState([]); const [anomalies, setAnomalies] = useState([]); const [error, setError] = useState(''); const [busy, setBusy] = useState(null);
	const load = async () => { try { const [a, b] = await Promise.all([request('/alerts', {}, token), request('/anomalies?status_filter=open', {}, token)]); setAlerts(a); setAnomalies(b); setError(''); } catch (err) { setError(err.message); } };
	useEffect(() => { load(); }, [token]);
	const acknowledge = async id => { setBusy(id); try { await request(`/alerts/${id}/acknowledge`, { method: 'PATCH' }, token); await load(); } catch (err) { setError(err.message); } finally { setBusy(null); } };
	const resolveAnomaly = async id => { setBusy(id); try { await request('/anomalies/' + id + '?state=resolved', { method: 'PATCH' }, token); await load(); } catch (err) { setError(err.message); } finally { setBusy(null); } }; return <Page title="Alerts & anomalies" kicker="INTELLIGENCE LAYER" action={<button className="primary" onClick={load}>Refresh</button>}>
		{error && <div className="error-block">{error}</div>}<div className="alert-list">{alerts.map(alert => <div className={`alert-item ${alert.status !== 'open' ? 'acknowledged' : ''}`} key={alert.id}><div className="alert-icon"><AlertTriangle size={17} /></div><div><strong>{alert.alert_type.replaceAll('_', ' ')}</strong><p>{alert.message}</p><small>{new Date(alert.timestamp).toLocaleString()} · {alert.source}</small></div><span className={`pill ${alert.severity === 'high' ? 'bad' : 'neutral'}`}>{alert.status === 'open' ? alert.severity : alert.status}</span>{role === 'administrator' && alert.status === 'open' && <button className="text-button" disabled={busy === alert.id} onClick={() => acknowledge(alert.id)}>{busy === alert.id ? 'Saving…' : 'Acknowledge'}</button>}</div>)}{anomalies.map(row => <div className="alert-item anomaly" key={`a-${row.id}`}><div className="alert-icon"><BarChart3 size={17} /></div><div><strong>Metric anomaly detected</strong><p>{row.explanation}</p><small>{new Date(row.timestamp || row.created_at).toLocaleString()} · Historical baseline</small></div><span className="pill bad">{row.status}</span>{role === 'administrator' && <button className="text-button" disabled={busy === row.id} onClick={() => resolveAnomaly(row.id)}>Resolve</button>}</div>)}{!alerts.length && !anomalies.length && <div className="empty">No alerts yet. Threshold alerts and historical anomalies will appear here.</div>}</div>
	</Page>;
}
function PasswordSettings({ token, onPasswordChanged }) {
	const [currentPassword, setCurrentPassword] = useState('');
	const [newPassword, setNewPassword] = useState('');
	const [confirmPassword, setConfirmPassword] = useState('');
	const [error, setError] = useState('');
	const [saving, setSaving] = useState(false);

	const submit = async event => {
		event.preventDefault();
		setError('');
		if (newPassword !== confirmPassword) {
			setError('New passwords do not match.');
			return;
		}
		setSaving(true);
		try {
			await request('/auth/change-password', {
				method: 'POST',
				body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
			}, token);
			onPasswordChanged();
		} catch (err) {
			setError(err.message);
			setSaving(false);
		}
	};

	return <section className="security-settings">
		<div className="section-heading"><div><p className="eyebrow">ACCOUNT SECURITY</p><h2>Change admin password</h2></div><KeyRound size={19} /></div>
		<form className="password-form" onSubmit={submit}>
			<label>Current password<input autoComplete="current-password" type="password" required value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} /></label>
			<label>New password<input autoComplete="new-password" type="password" minLength={12} required value={newPassword} onChange={event => setNewPassword(event.target.value)} /></label>
			<label>Confirm new password<input autoComplete="new-password" type="password" minLength={12} required value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} /></label>
			{error && <p className="error" role="alert">{error}</p>}
			<button className="primary" disabled={saving}>{saving ? 'Updating…' : 'Update password'} <KeyRound size={15} /></button>
		</form>
	</section>;
}

function Admin({ token, role, onPasswordChanged }) {
	const [actions, setActions] = useState([]); const [error, setError] = useState(''); const [config, setConfig] = useState(null); const [notice, setNotice] = useState('');
	const load = async () => { try { const queue = await request('/actions', {}, token); setActions(queue); if (role === 'administrator') setConfig(await request('/config', {}, token)); setError(''); } catch (err) { setError(err.message); } };
	useEffect(() => { load(); }, [token]);
	const decide = async (id, decision) => { const reason = window.prompt(`${decision} this operation. Enter the review rationale:`); if (!reason) return; try { await request(`/actions/${id}/decision`, { method: 'POST', body: JSON.stringify({ decision, reason }) }, token); setNotice(`Request ${id} ${decision}d.`); await load(); } catch (err) { setError(err.message); } };
	const execute = async id => { try { const result = await request(`/actions/${id}/execute`, { method: 'POST' }, token); setNotice(`Request ${id}: ${result.state} — ${result.result || ''}`); await load(); } catch (err) { setError(err.message); } };
	const cancel = async id => { try { await request(`/actions/${id}/cancel`, { method: 'POST' }, token); setNotice(`Request ${id} cancelled.`); await load(); } catch (err) { setError(err.message); } };
	const saveConfig = async event => { event.preventDefault(); try { await request('/config', { method: 'PUT', body: JSON.stringify({ cpu_alert_threshold: Number(config.cpu_alert_threshold), memory_alert_threshold: Number(config.memory_alert_threshold), disk_alert_threshold: Number(config.disk_alert_threshold) }) }, token); setNotice('Alert thresholds saved.'); await load(); } catch (err) { setError(err.message); } };
	return <Page title="Administration" kicker="APPROVALS & CONFIGURATION" action={<button className="primary" onClick={load}>Refresh</button>}>
		{error && <div className="error-block">{error}</div>}{notice && <p className="operation-notice" role="status">{notice}</p>}
		<div className="section-heading"><div><p className="eyebrow">HUMAN REVIEW</p><h2>Service operation requests</h2></div></div>
		<DataTable rows={actions} columns={[{ key: 'id', label: 'Request' }, { key: 'action_type', label: 'Operation' }, { key: 'target', label: 'Service' }, { key: 'requested_by', label: 'Requested by' }, { key: 'reason', label: 'Reason' }, { key: 'state', label: 'State' }, { key: 'risk', label: 'Impact and risk', render: row => <details><summary>{row.risk.score}/100 · {row.risk.band}</summary><pre>{JSON.stringify({ impact: row.impact, risk: row.risk }, null, 2)}</pre></details> }, { key: 'id', label: 'Review', render: row => <div className="inline-actions">{role === 'administrator' && row.state === 'PENDING_APPROVAL' && <><button className="text-button" onClick={() => decide(row.id, 'approve')}>Approve</button><button className="text-button" onClick={() => decide(row.id, 'reject')}>Reject</button></>}{role === 'administrator' && row.state === 'APPROVED' && <button className="text-button" onClick={() => execute(row.id)}>Execute approved request</button>}{['PENDING_APPROVAL','APPROVED'].includes(row.state) && <button className="text-button" onClick={() => cancel(row.id)}>Cancel</button>}</div> }]} empty="No service operation requests are waiting for review." />
		{config && <form className="password-form threshold-form" onSubmit={saveConfig}><h2>Alert thresholds (%)</h2>{['cpu_alert_threshold','memory_alert_threshold','disk_alert_threshold'].map(key => <label key={key}>{key.replace('_alert_threshold','').toUpperCase()}<input type="number" min="1" max="100" step="1" value={config[key]} onChange={event => setConfig({ ...config, [key]: event.target.value })} /></label>)}<button className="primary">Save thresholds</button><small>Collector interval: {config.collector_interval_seconds}s · retention: {config.retention_days} days</small></form>}
		{role === 'administrator' && <PasswordSettings token={token} onPasswordChanged={onPasswordChanged} />}
	</Page>;
}
function Audit({ token }) { const [rows, setRows] = useState([]); const [error, setError] = useState(''); useEffect(() => { request('/audit', {}, token).then(setRows).catch(err => setError(err.message)); }, [token]); return <Page title="Audit history" kicker="ACCOUNTABILITY" action={<span className="live-badge">{rows.length} recent events</span>}>{error && <div className="error-block">{error}</div>}<DataTable rows={rows} columns={[{ key: 'username', label: 'User' }, { key: 'action', label: 'Action' }, { key: 'target', label: 'Target' }, { key: 'timestamp', label: 'Time', render: row => new Date(row.timestamp || row.created_at).toLocaleString() }, { key: 'result', label: 'Result' }]} empty="No administrative actions have been recorded." /></Page> }
function UserManagement({ token, role }) {
	const [rows, setRows] = useState([]); const [form, setForm] = useState({ username: '', password: '', role: 'operator' }); const [error, setError] = useState(''); const [notice, setNotice] = useState('');
	const load = async () => { try { setRows(await request('/users', {}, token)); setError(''); } catch (err) { setError(err.message); } };
	useEffect(() => { load(); }, [token]);
	const submit = async event => { event.preventDefault(); setError(''); try { await request('/users', { method: 'POST', body: JSON.stringify(form) }, token); setNotice(`Account ${form.username} created.`); setForm({ username: '', password: '', role: 'operator' }); await load(); } catch (err) { setError(err.message); } };
	return <Page title="User management" kicker="ROLE-BASED ACCESS">{role !== 'administrator' && <div className="error-block">Administrator access is required to manage accounts.</div>}{error && <div className="error-block">{error}</div>}{notice && <p className="operation-notice">{notice}</p>}<DataTable rows={rows} columns={[{ key: 'username', label: 'Account' }, { key: 'role', label: 'Role' }, { key: 'created_at', label: 'Created' }]} empty="No accounts found." />{role === 'administrator' && <form className="password-form threshold-form" onSubmit={submit}><h2>Create account</h2><label>Username<input minLength="3" required pattern="[A-Za-z0-9_.-]+" value={form.username} onChange={event => setForm({ ...form, username: event.target.value })} /></label><label>Temporary password<input minLength="12" required type="password" value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} /></label><label>Role<select value={form.role} onChange={event => setForm({ ...form, role: event.target.value })}><option value="operator">Operator</option><option value="administrator">Administrator</option></select></label><button className="primary">Create user</button></form>}</Page>;
}
function InsightPage({ page, token, role }) {
	const [rows, setRows] = useState([]); const [extra, setExtra] = useState(null); const [error, setError] = useState(''); const [notice, setNotice] = useState(''); const [selected, setSelected] = useState(null); const [detail, setDetail] = useState(null); const [assignees, setAssignees] = useState([]); const [filter, setFilter] = useState(''); const [pageNumber, setPageNumber] = useState(0); const [hasMore, setHasMore] = useState(false);
	const definitions = { dependencies: ['Service dependencies', 'SYSTEMD RELATIONSHIPS', '/dependencies', 'edges'], predictions: ['Resource forecasts', 'PREDICTIVE MONITORING', '/forecasts', null], 'root-causes': ['Evidence-ranked hypotheses', 'DIAGNOSTIC SUPPORT', '/root-causes', null], recommendations: ['Recommendations', 'HUMAN-REVIEWED GUIDANCE', '/recommendations', null], incidents: ['Incident management', 'TRACKED EVENTS', '/incidents', null] };
	const [title, kicker, endpoint, key] = definitions[page] || definitions.predictions;
	const load = async () => { try {
		const paginated = ['incidents', 'recommendations'].includes(page); const params = new URLSearchParams(); if (filter && paginated) params.set('status_filter', filter); if (paginated) { params.set('limit', '51'); params.set('offset', String(pageNumber * 50)); } const query = params.toString() ? '?' + params.toString() : '';
		const data = await request(endpoint + query, {}, token); const fetchedRows = key ? data[key] || [] : data; const resultRows = paginated ? fetchedRows.slice(0, 50) : fetchedRows; setRows(resultRows); setHasMore(paginated && fetchedRows.length > 50);
		if (page === 'predictions') { const [history, model] = await Promise.all([request('/predictions?limit=12', {}, token), request('/models/status', {}, token)]); setExtra({ history, model }); }
		else if (page === 'dependencies') setExtra(data); else setExtra(null);
		if (page === 'incidents' && role === 'administrator') setAssignees(await request('/users', {}, token));
		setError('');
	} catch (err) { setError(err.message); } };
	useEffect(() => { setSelected(null); setDetail(null); load(); }, [page, token, filter, pageNumber]);
	const openIncident = async row => { setSelected(row); try { setDetail(await request('/incidents/' + row.id, {}, token)); } catch (err) { setError(err.message); } };
	const changeIncident = async (row, nextStatus, assignedTo) => {
		const resolution_notes = ['resolved', 'closed'].includes(nextStatus) ? window.prompt('Resolution notes:') : null;
		if (['resolved', 'closed'].includes(nextStatus) && !resolution_notes) return;
		try { await request('/incidents/' + row.id, { method: 'PATCH', body: JSON.stringify({ status: nextStatus, resolution_notes, assigned_to: assignedTo || undefined }) }, token); setNotice('Incident ' + row.id + ' updated.'); await load(); if (selected && selected.id === row.id) await openIncident(row); }
		catch (err) { setError(err.message); }
	};
	const changeRecommendation = async (row, nextStatus) => { try { await request('/recommendations/' + row.id, { method: 'PATCH', body: JSON.stringify({ status: nextStatus }) }, token); setNotice('Recommendation marked ' + nextStatus + '.'); await load(); } catch (err) { setError(err.message); } };
	const columns = page === 'dependencies' ? [{ key: 'source_service', label: 'From' }, { key: 'relationship', label: 'Relationship' }, { key: 'target_service', label: 'To' }, { key: 'observed_at', label: 'Observed' }]
		: page === 'predictions' ? [{ key: 'metric', label: 'Resource' }, { key: 'status', label: 'Forecast' }, { key: 'observed_value', label: 'Current', render: row => row.observed_value == null ? '—' : row.observed_value.toFixed(1) + '%' }, { key: 'predicted_value', label: 'Estimate', render: row => row.predicted_value == null ? row.explanation : row.predicted_value.toFixed(1) + '% in ' + row.horizon_hours + 'h' }, { key: 'estimated_hours_to_threshold', label: 'Threshold crossing', render: row => row.estimated_hours_to_threshold == null ? 'Not estimated' : row.estimated_hours_to_threshold.toFixed(1) + 'h' }, { key: 'method', label: 'Method' }, { key: 'confidence_score', label: 'Data score', render: row => row.confidence_score == null ? '—' : row.confidence_score.toFixed(0) + '%' }]
		: page === 'root-causes' ? [{ key: 'component', label: 'Component' }, { key: 'hypothesis', label: 'Hypothesis' }, { key: 'confidence', label: 'Evidence score' }, { key: 'confidence_definition', label: 'Meaning' }, { key: 'evidence', label: 'Evidence', render: row => (row.evidence || []).join(' · ') }, { key: 'alternatives', label: 'Alternatives', render: row => (row.alternatives || []).join(' · ') }, { key: 'diagnostics', label: 'Diagnostics', render: row => (row.diagnostics || []).join(' · ') }]
		: page === 'incidents' ? [{ key: 'id', label: 'ID', render: row => <button className="text-button" onClick={() => openIncident(row)}>{row.id}</button> }, { key: 'title', label: 'Incident' }, { key: 'severity', label: 'Severity' }, { key: 'component', label: 'Component' }, { key: 'status', label: 'Status' }, { key: 'assignee', label: 'Assignee' }, { key: 'updated_at', label: 'Updated' }, { key: 'id', label: 'Manage', render: row => role === 'administrator' ? <div className="inline-actions"><select aria-label={'Incident ' + row.id + ' status'} value={row.status} onChange={event => changeIncident(row, event.target.value, row.assigned_to)}><option value="open">Open</option><option value="investigating">Investigating</option><option value="resolved">Resolved</option><option value="closed">Closed</option></select><select aria-label={'Incident ' + row.id + ' assignee'} value={row.assigned_to || ''} onChange={event => changeIncident(row, row.status, Number(event.target.value))}><option value="">Assign to…</option>{assignees.map(person => <option key={person.id} value={person.id}>{person.username}</option>)}</select></div> : '—' }]
		: [{ key: 'title', label: 'Recommendation' }, { key: 'category', label: 'Category' }, { key: 'problem', label: 'Evidence' }, { key: 'proposed_action', label: 'Suggested review' }, { key: 'expected_benefit', label: 'Expected benefit' }, { key: 'potential_impact', label: 'Impact' }, { key: 'risk_score', label: 'Risk', render: row => row.risk_score + '/100 · ' + (row.requires_approval ? 'approval required' : 'read only') }, { key: 'risk_factors', label: 'Risk factors', render: row => JSON.stringify(row.risk_factors) }, { key: 'status', label: 'Status' }, { key: 'id', label: 'Review', render: row => <div className="inline-actions"><button className="text-button" onClick={() => changeRecommendation(row, 'dismissed')}>Dismiss</button><button className="text-button" onClick={() => changeRecommendation(row, 'resolved')}>Resolve</button></div> }];
	return <Page title={title} kicker={kicker} action={<><select className="filter-select" value={filter} onChange={event => { setPageNumber(0); setFilter(event.target.value); }} aria-label="Filter records"><option value="">All records</option>{page === 'incidents' && ['open','investigating','resolved','closed'].map(value => <option key={value}>{value}</option>)}{page === 'recommendations' && ['active','dismissed','resolved'].map(value => <option key={value}>{value}</option>)}</select><button className="primary" onClick={load}>Refresh</button></>}>
		{error && <div className="error-block">{error}</div>}{notice && <p className="operation-notice">{notice}</p>}
		{page === 'dependencies' ? <><p className="muted">Coverage: {extra?.coverage || 'unknown'}. Ordering edges represent sequence, not functional dependency.</p><div className="dependency-graph" aria-label="Observed service dependency graph">{(extra?.edges || []).map((edge, index) => <div className="dependency-edge" key={edge.source_service + edge.relationship + index}><strong>{edge.source_service}</strong><span>{edge.relationship} →</span><strong>{edge.target_service}</strong><small>{edge.source}</small></div>)}</div></> : <DataTable rows={rows} columns={columns} empty={page === 'predictions' ? 'Collect at least 12 actual observations to produce a resource trend estimate. This is not a failure probability.' : 'No data is available yet for this view.'} />}
		<div className="inline-actions pagination">{['incidents','recommendations'].includes(page) && <><button className="text-button" disabled={pageNumber === 0} onClick={() => setPageNumber(Math.max(0,pageNumber-1))}>Previous</button><span>Page {pageNumber+1}</span><button className="text-button" disabled={!hasMore} onClick={() => setPageNumber(pageNumber+1)}>Next</button></>}</div>{page === 'incidents' && selected && detail && <section className="panel inner-panel"><div className="section-heading"><div><p className="eyebrow">INCIDENT DETAIL</p><h2>#{selected.id} {detail.incident.title}</h2></div><button className="text-button" onClick={() => { setSelected(null); setDetail(null); }}>Close</button></div><p>{detail.incident.description}</p><p className="muted">Created {detail.incident.created_at} · Updated {detail.incident.updated_at} · Resolution: {detail.incident.resolution_notes || 'pending'}</p>{[['Linked alert',detail.alert],['Root-cause findings',detail.root_cause_findings],['Anomalies',detail.anomalies],['Predictions',detail.predictions],['Actions',detail.actions],['Impact',detail.impact_assessments],['Risk',detail.risk_assessments],['Audit events',detail.audit_events]].map(([label,value]) => <details key={label}><summary>{label} ({Array.isArray(value) ? value.length : value ? 1 : 0})</summary><pre>{JSON.stringify(value,null,2)}</pre></details>)}</section>}
		{extra?.model && <section className="panel inner-panel"><h2>Model and evaluation status</h2><p>{extra.model.forecast_model}</p><p>Stored observations: {extra.model.observation_count}</p><DataTable rows={extra.history} columns={[{ key: 'created_at', label: 'Computed at' }, { key: 'metric', label: 'Resource' }, { key: 'method', label: 'Method' }, { key: 'walk_forward_mae', label: 'Walk-forward MAE' }, { key: 'baseline_mae', label: 'Baseline MAE' }, { key: 'sample_count', label: 'Samples' }]} empty="Forecast history will appear after enough observations have been collected." /></section>}
	</Page>;
}
function Page({ title, kicker, action, children }) { return <><header className="page-head compact"><div><p className="eyebrow">{kicker}</p><h1>{title}</h1></div>{action}</header><section className="panel page-panel">{children}</section></> }
function App() {
	const [session, setSession] = useState(() => { try { return JSON.parse(localStorage.getItem('lap-session') || 'null'); } catch { localStorage.removeItem('lap-session'); return null; } });
	const [page, setPage] = useState('dashboard');
	const [mobile, setMobile] = useState(false);
	const [passwordChanged, setPasswordChanged] = useState(false);
	useEffect(() => {
		const handleSessionExpired = () => setSession(null);
		window.addEventListener('lap-session-expired', handleSessionExpired);
		return () => window.removeEventListener('lap-session-expired', handleSessionExpired);
	}, []);
	const logout = async () => {
		try { if (session?.token) await request('/auth/logout', { method: 'POST' }, session.token); }
		catch { /* Local sign-out must still work if the API is unavailable. */ }
		finally { localStorage.removeItem('lap-session'); setSession(null); }
	};
	const finishPasswordChange = () => {
		logout();
		setPasswordChanged(true);
	};
	if (!session) return <Login notice={passwordChanged ? 'Password changed. Sign in with your new password.' : ''} onLogin={data => { localStorage.setItem('lap-session', JSON.stringify(data)); setSession(data); setPasswordChanged(false); }} />;
	const content = { dashboard: <Dashboard token={session.token} />, processes: <Processes token={session.token} />, services: <Services token={session.token} />, dependencies: <InsightPage page={page} token={session.token} role={session.user.role} />, predictions: <InsightPage page={page} token={session.token} role={session.user.role} />, 'root-causes': <InsightPage page={page} token={session.token} role={session.user.role} />, recommendations: <InsightPage page={page} token={session.token} role={session.user.role} />, incidents: <InsightPage page={page} token={session.token} role={session.user.role} />, logs: <Logs token={session.token} />, alerts: <Alerts token={session.token} role={session.user.role} />, admin: <Admin token={session.token} role={session.user.role} onPasswordChanged={finishPasswordChange} />, users: <UserManagement token={session.token} role={session.user.role} />, audit: <Audit token={session.token} /> }[page];
	return <div className="app-shell"><aside className={mobile ? 'open' : ''}><div className="side-brand"><div className="brand-mark"><ShieldCheck size={19} /></div><span>LAI <b>Platform</b></span></div><div className="side-label">OPERATIONS</div><nav>{nav.map(item => { const Icon = item.icon; return <button className={page === item.id ? 'active' : ''} key={item.id} onClick={() => { setPage(item.id); setMobile(false); }}><Icon size={17} />{item.label}</button>; })}</nav><div className="side-footer"><div className="user-chip"><div className="avatar">{session.user.username[0].toUpperCase()}</div><div><strong>{session.user.username}</strong><small>{session.user.role}</small></div><button className="logout" title="Sign out" onClick={logout}><LogOut size={15} /></button></div></div></aside><main><button className="mobile-menu" onClick={() => setMobile(!mobile)}>{mobile ? <X /> : <Menu />}</button>{content}</main></div>;
}
createRoot(document.getElementById('root')).render(<App />);
