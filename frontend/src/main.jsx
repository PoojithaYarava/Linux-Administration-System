import React, { lazy, Suspense, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, BarChart3, CheckCircle2, Cpu, FileText, HardDrive, KeyRound, LayoutDashboard, LogOut, Menu, Network, Play, Search, Server, ShieldCheck, Terminal, Users, X } from 'lucide-react';
import './styles.css';
import './password-settings.css';

const API = import.meta.env.VITE_API_URL || '/api';
const MetricChart = lazy(() => import('./MetricChart.jsx'));
const nav = [{ id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard }, { id: 'processes', label: 'Processes', icon: Activity }, { id: 'services', label: 'Services', icon: Server }, { id: 'logs', label: 'System logs', icon: FileText }, { id: 'alerts', label: 'Alerts & anomalies', icon: AlertTriangle }, { id: 'admin', label: 'Administration', icon: ShieldCheck }, { id: 'audit', label: 'Audit history', icon: Terminal }];

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
	const [data, setData] = useState(null);
	const [info, setInfo] = useState(null);
	const [error, setError] = useState('');
	const [refreshing, setRefreshing] = useState(false);
	const load = async () => {
		setRefreshing(true);
		try {
			const [metrics, system] = await Promise.all([request('/system/metrics', {}, token), request('/system/info', {}, token)]);
			setData(metrics);
			setInfo(system);
			setError('');
		} catch (err) { setError(err.message); }
		finally { setRefreshing(false); }
	};
	useEffect(() => { load(); const timer = setInterval(load, 15000); return () => clearInterval(timer); }, [token]);
	if (error && !data) return <div className="error-block"><p>{error}</p><button className="primary" onClick={load}>Try again</button></div>;
	if (!data) return <Loading />;
	const m = data.latest;
	return <><header className="page-head"><div><p className="eyebrow">SYSTEM OVERVIEW</p><h1>Good morning, operator.</h1><p className="muted">{info?.hostname} · {info?.os}</p></div><div className="dashboard-actions"><div className="live-badge"><span className="signal-dot" /> Live · refreshed every 15s</div><button className="primary" disabled={refreshing} onClick={load}>{refreshing ? 'Refreshing…' : 'Refresh now'}</button></div></header>{error && <div className="error-block inline-error">{error}</div>}<section className="stats-grid"><Stat icon={Cpu} label="CPU usage" value={m.cpu_usage.toFixed(1)} unit="%" tone="orange" /><Stat icon={Activity} label="Memory usage" value={m.memory_usage.toFixed(1)} unit="%" tone="blue" /><Stat icon={HardDrive} label="Disk usage" value={m.disk_usage.toFixed(1)} unit="%" tone="green" /><Stat icon={Network} label="Network received" value={formatBytes(m.network_received)} tone="purple" /><Stat icon={Terminal} label="System uptime" value={formatUptime(info?.uptime_seconds)} tone="slate" /><Stat icon={Users} label="CPU cores" value={info?.cpu_count || '—'} tone="orange" /></section><Suspense fallback={<div className="loading">Loading telemetry chart…</div>}><MetricChart history={data.history} /></Suspense><section className="lower-grid"><div className="panel"><div className="section-heading"><div><p className="eyebrow">HOST CONTEXT</p><h2>Runtime details</h2></div><CheckCircle2 className="success" size={20} /></div><dl className="details"><dt>Kernel</dt><dd>{info?.kernel}</dd><dt>Architecture</dt><dd>{info?.architecture}</dd><dt>CPU cores</dt><dd>{info?.cpu_count}</dd><dt>Python runtime</dt><dd>{info?.python}</dd></dl></div><div className="panel alert-panel"><div className="section-heading"><div><p className="eyebrow">NEXT STEP</p><h2>Keep investigating</h2></div><BarChart3 size={20} /></div><p className="muted">Open Processes to connect resource pressure to the process responsible. Threshold alerts and historical anomalies are available in Alerts.</p></div></section></>;
}
function formatBytes(bytes) { const units = ['B', 'KB', 'MB', 'GB', 'TB']; let value = bytes || 0; let index = 0; while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; } return `${value.toFixed(1)} ${units[index]}`; } function formatUptime(seconds = 0) { const days = Math.floor(seconds / 86400); const hours = Math.floor((seconds % 86400) / 3600); return `${days}d ${hours}h`; } function Loading() { return <div className="loading"><span className="spinner" /> Collecting live system data…</div> }
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
		if (!window.confirm(`Restart ${name}? This will run a system service operation on the monitored host.`)) return;
		setBusy(name); setNotice('');
		try { const result = await request(`/services/${encodeURIComponent(name)}/restart`, { method: 'POST' }, token); setNotice(`${name}: ${result.status}. ${result.command_output || result.verified_state || ''}`); await load(); }
		catch (err) { setNotice(`${name}: ${err.message}`); }
		finally { setBusy(''); }
	};
	const filtered = rows.filter(row => `${row.name} ${row.description}`.toLowerCase().includes(query.toLowerCase()));
	return <Page title="Services" kicker="SYSTEMD INVENTORY" action={<><div className="search"><Search size={16} /><input placeholder="Search services" value={query} onChange={e => setQuery(e.target.value)} /></div><span className="live-badge">{rows.length} observed</span></>}>
		{error && <div className="error-block">{error} <button className="text-button" onClick={load}>Retry</button></div>}{notice && <p className="operation-notice" role="status">{notice}</p>}
		<DataTable rows={filtered} columns={[{ key: 'name', label: 'Service' }, { key: 'active', label: 'Active state', render: row => <span className={`pill ${row.active === 'active' ? 'good' : 'neutral'}`}>{row.active}</span> }, { key: 'status', label: 'Sub-state' }, { key: 'description', label: 'Description' }, { key: 'name', label: 'Action', render: row => <button className="icon-button" disabled={Boolean(busy) || row.active === 'unavailable' || row.name === 'linux-only'} title={`Restart ${row.name}`} aria-label={`Restart ${row.name}`} onClick={() => restart(row.name)}>{busy === row.name ? '…' : <Play size={15} />}</button> }]} empty="No services match this search, or systemd is unavailable on this host." />
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
function Alerts({ token }) {
	const [alerts, setAlerts] = useState([]); const [anomalies, setAnomalies] = useState([]); const [error, setError] = useState(''); const [busy, setBusy] = useState(null);
	const load = async () => { try { const [a, b] = await Promise.all([request('/alerts', {}, token), request('/anomalies', {}, token)]); setAlerts(a); setAnomalies(b.filter(row => row.is_anomaly)); setError(''); } catch (err) { setError(err.message); } };
	useEffect(() => { load(); }, [token]);
	const acknowledge = async id => { setBusy(id); try { await request(`/alerts/${id}/acknowledge`, { method: 'PATCH' }, token); await load(); } catch (err) { setError(err.message); } finally { setBusy(null); } };
	return <Page title="Alerts & anomalies" kicker="INTELLIGENCE LAYER" action={<button className="primary" onClick={load}>Refresh</button>}>
		{error && <div className="error-block">{error}</div>}<div className="alert-list">{alerts.map(alert => <div className={`alert-item ${alert.status !== 'open' ? 'acknowledged' : ''}`} key={alert.id}><div className="alert-icon"><AlertTriangle size={17} /></div><div><strong>{alert.alert_type.replaceAll('_', ' ')}</strong><p>{alert.message}</p><small>{new Date(alert.timestamp).toLocaleString()} · {alert.source}</small></div><span className={`pill ${alert.severity === 'high' ? 'bad' : 'neutral'}`}>{alert.status === 'open' ? alert.severity : alert.status}</span>{alert.status === 'open' && <button className="text-button" disabled={busy === alert.id} onClick={() => acknowledge(alert.id)}>{busy === alert.id ? 'Saving…' : 'Acknowledge'}</button>}</div>)}{anomalies.map(row => <div className="alert-item anomaly" key={`a-${row.id}`}><div className="alert-icon"><BarChart3 size={17} /></div><div><strong>Metric anomaly detected</strong><p>{row.explanation}</p><small>{new Date(row.timestamp).toLocaleString()} · Historical baseline</small></div><span className="pill bad">Anomaly</span></div>)}{!alerts.length && !anomalies.length && <div className="empty">No alerts yet. Threshold alerts and historical anomalies will appear here.</div>}</div>
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

function Admin({ token, onPasswordChanged }) {
	const [name, setName] = useState('');
	const [result, setResult] = useState(null);
	const submit = async () => {
		try {
			setResult(await request(`/services/${name}/restart`, { method: 'POST' }, token));
		} catch (err) {
			setResult({ status: 'failed', command_output: err.message });
		}
	};
	return <Page title="Administration" kicker="CONTROLLED OPERATIONS">
		<div className="admin-flow">
			<div className="flow-step"><span>01</span><div><strong>Choose an allowlisted service</strong><p>Only services configured in <code>ALLOWED_SERVICES</code> can be operated.</p><select value={name} onChange={event => setName(event.target.value)}><option value="">Select service</option><option value="ssh">ssh</option><option value="cron">cron</option><option value="systemd-journald">systemd-journald</option></select></div></div>
			<div className="flow-step"><span>02</span><div><strong>Validate and restart</strong><p>The backend executes a fixed systemctl operation, verifies state, then writes actions and audit_logs.</p><button className="primary" disabled={!name} onClick={submit}><Play size={15} /> Restart service</button></div></div>
			{result && <div className={`result ${result.status}`}><strong>{result.status.toUpperCase()}</strong><p>Verified state: {result.verified_state || 'not available'}</p><code>{result.command_output}</code></div>}
		</div>
		<PasswordSettings token={token} onPasswordChanged={onPasswordChanged} />
	</Page>;
}
function Audit({ token }) { const [rows, setRows] = useState([]); const [error, setError] = useState(''); useEffect(() => { request('/audit', {}, token).then(setRows).catch(err => setError(err.message)); }, [token]); return <Page title="Audit history" kicker="ACCOUNTABILITY" action={<span className="live-badge">{rows.length} recent events</span>}>{error && <div className="error-block">{error}</div>}<DataTable rows={rows} columns={[{ key: 'username', label: 'User' }, { key: 'action', label: 'Action' }, { key: 'target', label: 'Target' }, { key: 'timestamp', label: 'Time', render: row => new Date(row.timestamp).toLocaleString() }, { key: 'result', label: 'Result' }]} empty="No administrative actions have been recorded." /></Page> }
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
	const content = { dashboard: <Dashboard token={session.token} />, processes: <Processes token={session.token} />, services: <Services token={session.token} />, logs: <Logs token={session.token} />, alerts: <Alerts token={session.token} />, admin: <Admin token={session.token} onPasswordChanged={finishPasswordChange} />, audit: <Audit token={session.token} /> }[page];
	return <div className="app-shell"><aside className={mobile ? 'open' : ''}><div className="side-brand"><div className="brand-mark"><ShieldCheck size={19} /></div><span>LAI <b>Platform</b></span></div><div className="side-label">OPERATIONS</div><nav>{nav.map(item => { const Icon = item.icon; return <button className={page === item.id ? 'active' : ''} key={item.id} onClick={() => { setPage(item.id); setMobile(false); }}><Icon size={17} />{item.label}</button>; })}</nav><div className="side-footer"><div className="user-chip"><div className="avatar">{session.user.username[0].toUpperCase()}</div><div><strong>{session.user.username}</strong><small>{session.user.role}</small></div><button className="logout" title="Sign out" onClick={logout}><LogOut size={15} /></button></div></div></aside><main><button className="mobile-menu" onClick={() => setMobile(!mobile)}>{mobile ? <X /> : <Menu />}</button>{content}</main></div>;
}
createRoot(document.getElementById('root')).render(<App />);
