"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type AlertRow = { id: number; created_at: string; device_id: string; window_start: string; score: number; acknowledged: boolean; acc_mag_max: number | null; acc_mag_mean: number | null; gyro_mag_mean: number | null; sample_count: number | null };
type Point = { time: string; device_id: string; acc_mag_max: number; prediction: string; score: number; sample_count: number; fall_samples: number };
type Dashboard = { summary: { windows_15m: number; devices: number; latest_window: string | null; latest_ingested: string | null; open_alerts: number; alerts_15m: number; latest: { device_id: string } | null }; alerts: AlertRow[]; timeline: Point[] };
type Device = { device_id: string; display_name: string; location: string | null; assigned_to: string | null; active: boolean; last_seen: string | null; window_count: number; connected: boolean };
type Model = { version: string; file: string; sha256?: string; features?: string[]; metrics: Record<string, unknown>; active: boolean; registered: boolean; created_at?: string };
type Tab = "overview" | "devices" | "models";

const fmt = (v?: string | null) => v ? new Date(v).toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—";
const n = (v: unknown, digits = 0) => Number(v ?? 0).toLocaleString("vi-VN", { maximumFractionDigits: digits });

function Sparkline({ rows }: { rows: Point[] }) {
  if (!rows.length) return <div className="chart-empty">Chưa có dữ liệu cửa sổ. Hãy khởi chạy Spark và producer.</div>;
  const W = 820, H = 265, L = 48, R = 18, T = 16, B = 32;
  const vals = rows.map(r => Number(r.acc_mag_max) || 0), max = Math.max(10, Math.ceil(Math.max(...vals) / 10) * 10);
  const x = (i: number) => L + (rows.length < 2 ? (W - L - R) / 2 : i * (W - L - R) / (rows.length - 1));
  const y = (v: number) => T + H - T - B - v / max * (H - T - B);
  const line = rows.map((r, i) => `${i ? "L" : "M"}${x(i)},${y(vals[i])}`).join(" ");
  const area = `${line} L${x(rows.length - 1)},${H - B} L${x(0)},${H - B} Z`;
  return <svg className="chart-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Gia tốc cực đại theo thời gian">
    <defs><linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#74a8ff" stopOpacity=".25"/><stop offset="1" stopColor="#74a8ff" stopOpacity="0"/></linearGradient></defs>
    {[0, 1, 2, 3, 4].map(i => { const value = max * i / 4, yy = y(value); return <g key={i}><line x1={L} y1={yy} x2={W - R} y2={yy} className="chart-grid"/><text x={L - 10} y={yy + 4} textAnchor="end" className="chart-label">{Math.round(value)}</text></g>; })}
    <path d={area} fill="url(#chartFill)"/><path d={line} className="chart-line"/>
    {rows.map((row, i) => <circle key={`${row.time}-${i}`} cx={x(i)} cy={y(vals[i])} r={row.prediction === "FALL" ? 4.5 : 3} className={row.prediction === "FALL" ? "point-fall" : "point-adl"}><title>{fmt(row.time)} · {row.prediction} · {n(vals[i], 2)} m/s² · score {n(row.score, 2)}</title></circle>)}
    <text x={L} y={H - 6} className="chart-label">{fmt(rows[0].time)}</text><text x={W - R} y={H - 6} textAnchor="end" className="chart-label">{fmt(rows[rows.length - 1].time)}</text><text x={W - R} y={T + 8} textAnchor="end" className="chart-label">m/s²</text>
  </svg>;
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("overview");
  const [data, setData] = useState<Dashboard | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [services, setServices] = useState({ database: false, models: false, devices: false });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState<"open" | "all">("open");
  const [selected, setSelected] = useState<AlertRow | null>(null);
  const [toast, setToast] = useState("");
  const [clock, setClock] = useState("--:--:--");

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString("vi-VN"));
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, []);

  const loadDashboard = useCallback(async () => {
    try {
      const res = await fetch("/api/dashboard", { cache: "no-store" });
      const body = await res.json();
      if (!res.ok || !body.ok) throw new Error(body.error || "Không kết nối được PostgreSQL");
      setData(body); setServices(s => ({ ...s, database: true })); setError("");
    } catch (e) { setServices(s => ({ ...s, database: false })); setError(e instanceof Error ? e.message : "Lỗi kết nối"); }
  }, []);

  const loadAdmin = useCallback(async () => {
    const [d, m] = await Promise.allSettled([fetch("/api/devices", { cache: "no-store" }), fetch("/api/models", { cache: "no-store" })]);
    if (d.status === "fulfilled" && d.value.ok) { const b = await d.value.json(); setDevices(b.devices || []); setServices(s => ({ ...s, devices: true })); } else setServices(s => ({ ...s, devices: false }));
    if (m.status === "fulfilled" && m.value.ok) { const b = await m.value.json(); setModels(b.models || []); setServices(s => ({ ...s, models: true })); } else setServices(s => ({ ...s, models: false }));
  }, []);

  useEffect(() => { void loadDashboard(); void loadAdmin(); const timer = setInterval(() => { void loadDashboard(); if (tab !== "overview") void loadAdmin(); }, 5000); return () => clearInterval(timer); }, [loadDashboard, loadAdmin, tab]);
  const visibleAlerts = useMemo(() => (data?.alerts || []).filter(a => filter === "all" || !a.acknowledged), [data, filter]);

  async function acknowledge(id: number) {
    setBusy(true);
    try { const res = await fetch(`/api/alerts/${id}/acknowledge`, { method: "POST" }); const body = await res.json(); if (!res.ok || !body.ok) throw new Error(body.error || "Không cập nhật được cảnh báo"); setSelected(null); setToast("Đã ghi nhận: người theo dõi đã kiểm tra cảnh báo."); setTimeout(() => setToast(""), 3500); await loadDashboard(); }
    catch (e) { setToast(e instanceof Error ? e.message : "Lỗi cập nhật"); setTimeout(() => setToast(""), 3500); }
    finally { setBusy(false); }
  }

  async function saveDevice(device: Device, patch: Partial<Device>) {
    setBusy(true);
    try { const res = await fetch(`/api/devices/${encodeURIComponent(device.device_id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }); const body = await res.json(); if (!res.ok) throw new Error(body.detail || "Không cập nhật được thiết bị"); await loadAdmin(); setToast("Đã lưu cấu hình thiết bị."); setTimeout(() => setToast(""), 2500); }
    catch (e) { setToast(e instanceof Error ? e.message : "Lỗi lưu thiết bị"); setTimeout(() => setToast(""), 3500); }
    finally { setBusy(false); }
  }

  async function registerModel(model: Model) {
    setBusy(true);
    try { const res = await fetch("/api/models/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ version: model.version, file: model.file, metrics: model.metrics || {} }) }); const body = await res.json(); if (!res.ok) throw new Error(body.detail || "Không đăng ký được model"); await loadAdmin(); setToast(`Đã đăng ký model ${model.version}.`); setTimeout(() => setToast(""), 2500); }
    catch (e) { setToast(e instanceof Error ? e.message : "Lỗi đăng ký model"); setTimeout(() => setToast(""), 3500); }
    finally { setBusy(false); }
  }

  async function activateModel(model: Model) {
    setBusy(true);
    try { const res = await fetch(`/api/models/${encodeURIComponent(model.version)}/activate`, { method: "POST" }); const body = await res.json(); if (!res.ok) throw new Error(body.detail || "Không kích hoạt được model"); await loadAdmin(); setToast(`Model ${model.version} đang hoạt động.`); setTimeout(() => setToast(""), 2500); }
    catch (e) { setToast(e instanceof Error ? e.message : "Lỗi kích hoạt model"); setTimeout(() => setToast(""), 3500); }
    finally { setBusy(false); }
  }

  const pageTitle = tab === "overview" ? "Tổng quan an toàn" : tab === "devices" ? "Quản lý thiết bị" : "Model Registry";
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><div className="brand-mark">F</div><div><b>FALLALLD</b><small>SAFETY PLATFORM</small></div></div>
      <div className="side-label">WORKSPACE</div><button className={`nav-item ${tab === "overview" ? "selected" : ""}`} onClick={() => setTab("overview")}><span>◫</span> Tổng quan</button><button className={`nav-item ${tab === "devices" ? "selected" : ""}`} onClick={() => setTab("devices")}><span>⌁</span> Thiết bị <em>{devices.length}</em></button><button className={`nav-item ${tab === "models" ? "selected" : ""}`} onClick={() => setTab("models")}><span>◈</span> Mô hình AI</button>
      <div className="side-bottom"><div className="side-label">SERVICES</div><Service name="PostgreSQL" ok={services.database}/><Service name="Model Registry API" ok={services.models}/><Service name="Device Manager API" ok={services.devices}/><div className="side-foot">FallAllD · Local demo<br/>Dữ liệu nghiên cứu, không phải thiết bị y tế.</div></div>
    </aside>
    <main className="main"><header className="topbar"><div><div className="breadcrumb">FallAllD <span>/</span> {pageTitle}</div><h1>{pageTitle}</h1></div><div className="top-actions"><span className={`system-pill ${error ? "offline" : "online"}`}><i/> {error ? "Cần kiểm tra kết nối" : "Giám sát đang hoạt động"}</span><button className="button secondary" onClick={() => { void loadDashboard(); void loadAdmin(); }}>↻ Làm mới</button></div></header>
      {error && <div className="notice error"><b>Chưa đọc được dữ liệu:</b> {error}<span> Kiểm tra PostgreSQL và FALL_POSTGRES_URL.</span></div>}
      {tab === "overview" && <>
        <section className="intro"><div><div className="eyebrow">LIVE SAFETY MONITORING</div><h2>Phát hiện sớm. Phản hồi kịp thời.</h2><p>Chuyển động cổ tay → phân tích AI → người theo dõi xử lý cảnh báo.</p></div><div className="last-update">Cập nhật tự động mỗi 5 giây<br/><b>{clock}</b></div></section>
        <section className="kpis"><Kpi label="Cần người theo dõi kiểm tra" value={n(data?.summary.open_alerts)} hint="Cảnh báo chưa được xác nhận" icon="!" tone="red"/><Kpi label="Cửa sổ phân tích · 15 phút" value={n(data?.summary.windows_15m)} hint="Gom mẫu cảm biến theo thời gian" icon="▥" tone="blue"/><Kpi label="Cảnh báo mới · 15 phút" value={n(data?.summary.alerts_15m)} hint="Dự đoán FALL gần đây" icon="◉" tone="amber"/><Kpi label="Thiết bị ghi nhận" value={n(data?.summary.devices)} hint={data?.summary.latest?.device_id ? `Gần nhất: ${data.summary.latest.device_id}` : "Chưa có thiết bị gửi dữ liệu"} icon="⌁" tone="green"/></section>
        <section className="content-grid"><article className="panel chart-panel"><div className="panel-heading"><div><h2>Hoạt động cảm biến</h2><p>Gia tốc cực đại theo cửa sổ · đỏ = FALL, xanh = ADL</p></div><span className="chip">60 cửa sổ gần nhất</span></div><div className="chart-wrap"><Sparkline rows={data?.timeline || []}/></div><div className="legend"><span><i className="legend-blue"/> Gia tốc tối đa</span><span><i className="legend-red"/> FALL</span><span><i className="legend-green"/> ADL</span></div></article>
        <article className="panel alert-panel"><div className="panel-heading"><div><h2>Hàng đợi cảnh báo</h2><p>Chọn sự kiện để xem lý do và ghi nhận xử lý</p></div><span className="chip">Random Forest</span></div><div className="filter-row"><button className={filter === "open" ? "filter active" : "filter"} onClick={() => setFilter("open")}>Cần xử lý ({data?.summary.open_alerts ?? 0})</button><button className={filter === "all" ? "filter active" : "filter"} onClick={() => setFilter("all")}>Gần đây</button></div><div className="alert-stack">{visibleAlerts.length ? visibleAlerts.map(a => <button className="alert-row" key={a.id} onClick={() => setSelected(a)}><span className="alert-symbol">!</span><span className="alert-copy"><b>{a.device_id} <i className="fall-badge">FALL</i></b><small>{fmt(a.created_at)} · độ tin cậy {Math.round(Number(a.score) * 100)}%</small></span><span className="row-arrow">›</span></button>) : <div className="empty-state">{data?.alerts.length ? "Không còn cảnh báo cần xử lý trong danh sách gần đây." : "Chưa ghi nhận cảnh báo nào. Khi mô hình phát hiện FALL, sự kiện sẽ xuất hiện ở đây."}</div>}</div><div className="howto"><b>Quy trình:</b> mở cảnh báo → xác minh người đeo → ghi nhận đã kiểm tra.</div></article></section>
        <section className="panel flow-panel"><div className="panel-heading"><div><h2>Từ cảm biến đến hành động</h2><p>Đây là cách pipeline hỗ trợ người chăm sóc — không tự thay thế quyết định của con người.</p></div><span className="chip">END-TO-END</span></div><div className="flow">{[["01","Cảm biến","Gia tốc + con quay hồi chuyển"],["02","Kafka","Truyền bản tin cảm biến"],["03","Spark","Tạo cửa sổ và đặc trưng"],["04","Random Forest","Phân loại FALL / ADL"],["05","Người theo dõi","Xem, xác minh, ghi nhận"]].map(([num,title,desc]) => <div className="flow-step" key={num}><span>{num}</span><b>{title}</b><small>{desc}</small></div>)}</div></section>
      </>}
      {tab === "devices" && <section className="admin-page"><div className="page-intro"><div><h2>Thiết bị đang gửi dữ liệu</h2><p>Đặt tên dễ nhận biết, gán vị trí/người đeo và bật hoặc tạm ngưng theo dõi trong giao diện.</p></div><span className="chip">{devices.length} thiết bị</span></div>{!services.devices ? <div className="notice error">Device Manager API chưa kết nối. Khởi động API ở cổng 8001.</div> : devices.length === 0 ? <div className="empty-large">Chưa phát hiện thiết bị. Hãy chạy producer để dữ liệu đi qua Kafka và Spark.</div> : <div className="device-grid">{devices.map(d => <DeviceCard key={d.device_id} device={d} busy={busy} onSave={saveDevice}/>)}</div>}</section>}
      {tab === "models" && <section className="admin-page"><div className="page-intro"><div><h2>Phiên bản mô hình</h2><p>Đăng ký artifact đã huấn luyện, xem metrics và chọn phiên bản đang hoạt động.</p></div><span className="chip">{models.length} artifacts</span></div>{!services.models ? <div className="notice error">Model Registry API chưa kết nối. Khởi động API ở cổng 8000.</div> : models.length === 0 ? <div className="empty-large">Chưa tìm thấy model trong thư mục models/.</div> : <div className="model-grid">{models.map(m => <ModelCard key={`${m.version}-${m.file}`} model={m} busy={busy} onRegister={registerModel} onActivate={activateModel}/>)}</div>}</section>}
      <footer>FallAllD research demo · Luôn xác minh trực tiếp sau cảnh báo · Không thay thế dịch vụ cấp cứu</footer>
    </main>
    {selected && <div className="modal-back" onMouseDown={e => { if (e.target === e.currentTarget) setSelected(null); }}><section className="modal-card"><div className="modal-title"><div><div className="eyebrow">INCIDENT REVIEW</div><h2>{selected.device_id} <i className="fall-badge">FALL</i></h2><p>{fmt(selected.created_at)} · Cửa sổ {fmt(selected.window_start)}</p></div><button className="icon-button" onClick={() => setSelected(null)}>×</button></div><div className="confidence"><div><span>Khả năng FALL theo mô hình</span><b>{Math.round(Number(selected.score) * 100)}%</b></div><div className="meter"><i style={{ width: `${Math.min(100, Math.max(0, Number(selected.score) * 100))}%` }}/></div></div><div className="detail-metrics"><Metric label="Gia tốc cực đại" value={selected.acc_mag_max == null ? "—" : `${n(selected.acc_mag_max, 2)} m/s²`}/><Metric label="Gia tốc trung bình" value={selected.acc_mag_mean == null ? "—" : `${n(selected.acc_mag_mean, 2)} m/s²`}/><Metric label="Con quay hồi chuyển" value={selected.gyro_mag_mean == null ? "—" : n(selected.gyro_mag_mean, 2)}/><Metric label="Mẫu trong cửa sổ" value={n(selected.sample_count)}/></div><div className="advice"><b>Hành động của người theo dõi</b><p>Kiểm tra trực tiếp tình trạng người đeo. Nếu người đó cần trợ giúp, liên hệ người thân hoặc dịch vụ phù hợp theo quy trình của bạn. Nút xác nhận chỉ ghi nhận trạng thái xử lý trong demo.</p></div><div className="modal-actions"><button className="button secondary" onClick={() => setSelected(null)}>Đóng</button><button className="button primary" disabled={busy || selected.acknowledged} onClick={() => void acknowledge(selected.id)}>{selected.acknowledged ? "✓ Đã ghi nhận" : busy ? "Đang lưu…" : "✓ Ghi nhận đã kiểm tra"}</button></div></section></div>}
    {toast && <div className="toast">{toast}</div>}
  </div>;
}

function Service({ name, ok }: { name: string; ok: boolean }) { return <div className="service"><i className={ok ? "service-dot good" : "service-dot"}/><span>{name}</span><small>{ok ? "ONLINE" : "OFFLINE"}</small></div>; }
function Kpi({ label, value, hint, icon, tone }: { label: string; value: string; hint: string; icon: string; tone: string }) { return <article className={`kpi-card ${tone}`}><div className="kpi-top"><span>{label}</span><i>{icon}</i></div><strong>{value}</strong><small>{hint}</small></article>; }
function Metric({ label, value }: { label: string; value: string }) { return <div className="metric"><small>{label}</small><b>{value}</b></div>; }
function DeviceCard({ device, busy, onSave }: { device: Device; busy: boolean; onSave: (d: Device, p: Partial<Device>) => void }) {
  const [name, setName] = useState(device.display_name || ""); const [location, setLocation] = useState(device.location || ""); const [assigned, setAssigned] = useState(device.assigned_to || "");
  return <article className="panel device-card"><div className="device-card-head"><div className="device-icon">⌁</div><div><h3>{device.display_name || device.device_id}</h3><small>{device.device_id}</small></div><span className={`status-chip ${device.connected ? "connected" : "disconnected"}`}>{device.connected ? "Đã ghi nhận" : "Chưa có dữ liệu"}</span></div><div className="device-fields"><label>Tên hiển thị<input value={name} onChange={e => setName(e.target.value)} placeholder="Ví dụ: Vòng tay phòng 01"/></label><label>Vị trí<input value={location} onChange={e => setLocation(e.target.value)} placeholder="Ví dụ: Phòng ngủ tầng 2"/></label><label>Người đeo / phụ trách<input value={assigned} onChange={e => setAssigned(e.target.value)} placeholder="Tên người đeo hoặc người chăm sóc"/></label></div><div className="device-stats"><span><b>{n(device.window_count)}</b> cửa sổ đã ghi nhận</span><span>Gần nhất: {fmt(device.last_seen)}</span></div><div className="device-actions"><button className="button secondary" disabled={busy} onClick={() => onSave(device, { display_name: name, location, assigned_to: assigned })}>Lưu thông tin</button><button className={`button ${device.active ? "warning" : "primary"}`} disabled={busy} onClick={() => onSave(device, { active: !device.active })}>{device.active ? "Tạm ngưng" : "Bật thiết bị"}</button></div></article>;
}
function ModelCard({ model, busy, onRegister, onActivate }: { model: Model; busy: boolean; onRegister: (m: Model) => void; onActivate: (m: Model) => void }) {
  const metricsText = JSON.stringify(model.metrics || {}, null, 2);
  const roc = JSON.stringify(model.metrics || {}).match(/"(?:roc_auc|ROC-AUC|roc_auc_score)"\s*:\s*([0-9.]+)/i)?.[1];
  return <article className="panel model-card"><div className="model-card-head"><div className="model-icon">◈</div><div><span className="eyebrow">RANDOM FOREST</span><h3>{model.version}</h3></div>{model.active && <span className="status-chip connected">ACTIVE</span>}</div><p className="model-file">{model.file}</p><div className="model-kpis"><div><small>ROC-AUC</small><b>{roc ? n(roc, 3) : "—"}</b></div><div><small>Trạng thái</small><b>{model.active ? "Đang dùng" : model.registered ? "Đã đăng ký" : "Local artifact"}</b></div><div><small>Đặc trưng</small><b>{model.features?.length ?? 10}</b></div></div><details><summary>Xem metrics / metadata</summary><pre>{metricsText || "Chưa có metrics"}</pre></details><div className="model-actions">{!model.registered ? <button className="button primary" disabled={busy} onClick={() => onRegister(model)}>＋ Đăng ký phiên bản</button> : <button className="button secondary" disabled={busy || model.active} onClick={() => onActivate(model)}>{model.active ? "✓ Phiên bản đang hoạt động" : "Kích hoạt phiên bản"}</button>}</div></article>;
}
