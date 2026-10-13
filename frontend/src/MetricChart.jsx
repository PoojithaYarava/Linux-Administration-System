import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export default function MetricChart({ history }) {
	const data = history.map(item => ({
		time: new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
		cpu: item.cpu_usage,
		memory: item.memory_usage,
	}));

	return <div className="chart-wrap">
		<div className="section-heading">
			<div><p className="eyebrow">TELEMETRY</p><h2>Resource pressure</h2></div>
			<span className="legend"><i className="cpu" /> CPU <i className="memory" /> Memory</span>
		</div>
		<ResponsiveContainer width="100%" height={240}>
			<AreaChart data={data}>
				<defs>
					<linearGradient id="cpu" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ef8354" stopOpacity=".28" /><stop offset="100%" stopColor="#ef8354" stopOpacity="0" /></linearGradient>
					<linearGradient id="memory" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3e92cc" stopOpacity=".22" /><stop offset="100%" stopColor="#3e92cc" stopOpacity="0" /></linearGradient>
				</defs>
				<CartesianGrid strokeDasharray="3 3" stroke="#d8e0e7" vertical={false} />
				<XAxis dataKey="time" tick={{ fontSize: 11 }} />
				<YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
				<Tooltip />
				<Area type="monotone" dataKey="cpu" stroke="#ef8354" fill="url(#cpu)" strokeWidth={2} name="CPU %" />
				<Area type="monotone" dataKey="memory" stroke="#3e92cc" fill="url(#memory)" strokeWidth={2} name="Memory %" />
			</AreaChart>
		</ResponsiveContainer>
	</div>;
}
