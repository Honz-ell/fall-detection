"use client";

import { useEffect, useRef, useState } from "react";

type Mode = "walk" | "rest" | "wave" | "fall";
type Person = { id: string; name: string; age: number; room: string; wrist: string; mode: Mode; probability: number };
type Sample = { at: number; acc: number; probability: number };
type SimAlert = { id: number; person: string; wrist: string; at: number; probability: number; status: "pending" | "confirmed" | "false_alarm" };
const MODE_LABEL: Record<Mode, string> = { walk: "Đang đi lại", rest: "Đang nghỉ ngơi", wave: "Chuyển động mạnh", fall: "Mô phỏng ngã" };
const initialPeople: Person[] = [
  { id: "wrist-01", name: "Bà Lan", age: 78, room: "Phòng khách", wrist: "WRIST-01", mode: "walk", probability: 0.04 },
  { id: "wrist-02", name: "Ông Hùng", age: 82, room: "Khu vườn", wrist: "WRIST-02", mode: "rest", probability: 0.02 },
  { id: "wrist-03", name: "Bà Mai", age: 75, room: "Phòng ngủ", wrist: "WRIST-03", mode: "rest", probability: 0.01 },
];
const makeInitialSamples = (): Sample[] => Array.from({ length: 30 }, (_, i) => ({ at: Date.now() - (29 - i) * 2000, acc: 11 + (i * 7 % 6) + (i % 9 === 0 ? 5 : 0), probability: 0.02 + (i % 8) * 0.006 }));
const timeLabel = (t: number) => new Date(t).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export default function Simulation() {
  const [people, setPeople] = useState(initialPeople);
  const [selectedId, setSelectedId] = useState(initialPeople[0].id);
  const [samples, setSamples] = useState<Sample[]>(makeInitialSamples);
  const [alerts, setAlerts] = useState<SimAlert[]>([]);
  const [sensitivity, setSensitivity] = useState(70);
  const [windows, setWindows] = useState(30);
  const [confirmed, setConfirmed] = useState(0);
  const [falseAlarms, setFalseAlarms] = useState(0);
  const [paused, setPaused] = useState(false);
  const previousAbove = useRef(false);
  const selected = people.find(p => p.id === selectedId) || people[0];
  const openCount = alerts.filter(a => a.status === "pending").length;

  function emit(mode: Mode = selected.mode) {
    const person = people.find(p => p.id === selectedId) || people[0];
    let acc = 12, probability = 0.04;
    if (mode === "walk") { acc = 10 + Math.random() * 10; probability = 0.02 + Math.random() * 0.12; }
    if (mode === "rest") { acc = 9.7 + Math.random() * 3; probability = 0.01 + Math.random() * 0.06; }
    if (mode === "wave") { acc = 14 + Math.random() * 17; probability = 0.27 + Math.random() * 0.35; }
    if (mode === "fall") { acc = 42 + Math.random() * 34; probability = 0.93 + Math.random() * 0.06; }
    const at = Date.now();
    const above = probability * 100 >= sensitivity;
    setWindows(v => v + 1);
    setSamples(prev => [...prev.slice(-29), { at, acc, probability }]);
    setPeople(prev => prev.map(p => p.id === person.id ? { ...p, mode, probability } : p));
    if (above && !previousAbove.current) {
      setAlerts(prev => [{ id: at + Math.floor(Math.random() * 1000), person: person.name, wrist: person.wrist, at, probability, status: "pending" as const }, ...prev].slice(0, 20));
    }
    previousAbove.current = above;
  }

  useEffect(() => {
    if (paused) return;
    const timer = window.setInterval(() => emit(), 2000);
    return () => window.clearInterval(timer);
  // emit the selected person's scenario every simulated two-second window
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paused, selectedId, selected.mode, sensitivity]);

  function choosePerson(id: string) { previousAbove.current = false; setSelectedId(id); setSamples(makeInitialSamples()); }
  function chooseMode(mode: Mode) { previousAbove.current = false; setPeople(prev => prev.map(p => p.id === selectedId ? { ...p, mode } : p)); emit(mode); }
  function markAlert(alert: SimAlert, status: "confirmed" | "false_alarm") {
    setAlerts(prev => prev.map(a => a.id === alert.id ? { ...a, status } : a));
    if (status === "confirmed") setConfirmed(v => v + 1); else setFalseAlarms(v => v + 1);
  }

  const W = 760, H = 290, L = 45, R = 42, T = 18, B = 32, plotW = W - L - R, plotH = H - T - B;
  const barW = plotW / Math.max(samples.length, 1) * 0.56;
  const yAcc = (v: number) => T + plotH - Math.min(v / 80, 1) * plotH;
  const yProb = (v: number) => T + plotH - v * plotH;
  const probPath = samples.map((s, i) => `${i ? "L" : "M"}${L + (i + .5) * plotW / samples.length},${yProb(s.probability)}`).join(" ");

  return <section className="sim-page">
    <div className="sim-top"><div><div className="eyebrow">INTERACTIVE SCENARIO · LOCAL ONLY</div><h2>Thử nghiệm tình huống chăm sóc</h2><p>Chọn người theo dõi, tạo chuyển động giả lập và quan sát cách ngưỡng cảnh báo ảnh hưởng kết quả.</p></div><div className="demo-warning">DEMO MÔ PHỎNG · số liệu giả lập, không phải cảm biến thật</div></div>
    <div className="sim-pipeline">{["1. Cảm biến / Producer", "2. Kafka", "3. Spark · cửa sổ 2 giây", "4. PostgreSQL", "5. Random Forest", "6. Người chăm sóc"].map((item, i) => <span className={i === 0 || i === 5 ? "pipe-step active" : "pipe-step"} key={item}>{item}</span>)}</div>
    <div className="sim-kpis"><div><b>{windows}</b><span>Cửa sổ 2 giây đã mô phỏng</span></div><div><b>{alerts.length}</b><span>Cảnh báo đã phát</span></div><div><b>{confirmed}</b><span>Xác nhận là ngã thật</span></div><div><b>{falseAlarms}</b><span>Báo nhầm</span></div></div>
    <div className="sim-layout"><aside className="sim-people"><h3>Người được theo dõi <span>{people.length}</span></h3>{people.map(person => <button key={person.id} className={`person-card ${person.id === selectedId ? "chosen" : ""}`} onClick={() => choosePerson(person.id)}><b>{person.name}, {person.age} tuổi</b><small>{person.room} · {person.wrist.toLowerCase()}</small><div className={`person-state ${person.probability * 100 >= sensitivity ? "risk" : "safe"}`}>{person.probability * 100 >= sensitivity ? "Cần kiểm tra" : "Bình thường"}<span>{MODE_LABEL[person.mode]}</span></div><div className="prob-track"><i style={{ width: `${Math.min(100, person.probability * 100)}%` }}/></div><small>Xác suất ngã: {Math.round(person.probability * 100)}%</small></button>)}
      <div className="sensitivity"><b>Độ nhạy cảnh báo: {sensitivity}%</b><input type="range" min="25" max="90" value={sensitivity} onChange={e => { previousAbove.current = false; setSensitivity(Number(e.target.value)); }}/><div className="range-labels"><span>Nhạy hơn · dễ báo nhầm</span><span>Ít báo nhầm · dễ bỏ sót</span></div></div>
    </aside>
    <main className="sim-center"><div className="sim-chart-head"><div><h3>Diễn biến của {selected.name}, {selected.age} tuổi</h3><p>30 cửa sổ gần nhất · mỗi cột tương ứng khoảng 2 giây</p></div><span className="sim-selected">{selected.wrist}</span></div>
      <div className="sim-chart-legend"><span><i className="bar-legend"/> Cường độ chuyển động</span><span><i className="line-legend"/> Xác suất ngã (mô hình)</span><span><i className="dash-legend"/> Ngưỡng {sensitivity}%</span></div>
      <div className="sim-chart"><svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Biểu đồ giả lập chuyển động và xác suất ngã">{[0,25,50,75,100].map(v => { const y = yProb(v / 100); return <g key={v}><line x1={L} y1={y} x2={W-R} y2={y} className="sim-grid"/><text x={L-8} y={y+4} textAnchor="end" className="sim-axis">{Math.round(v * .8)}</text><text x={W-R+8} y={y+4} className="sim-axis">{v}%</text></g>; })}<line x1={L} y1={yProb(sensitivity/100)} x2={W-R} y2={yProb(sensitivity/100)} className="threshold-line"/>{samples.map((s,i) => <rect key={`bar-${s.at}`} x={L+(i+.2)*plotW/samples.length} y={yAcc(s.acc)} width={barW} height={T+plotH-yAcc(s.acc)} rx="2" className="sim-bar"><title>{timeLabel(s.at)} · chuyển động {s.acc.toFixed(1)} m/s²</title></rect>)}<path d={probPath} className="prob-line"/>{samples.map((s,i) => <circle key={`point-${s.at}`} cx={L+(i+.5)*plotW/samples.length} cy={yProb(s.probability)} r={s.probability*100>=sensitivity?4:2.5} className={s.probability*100>=sensitivity?"prob-point-risk":"prob-point"}><title>{timeLabel(s.at)} · xác suất {Math.round(s.probability*100)}%</title></circle>)}<text x={L} y={H-8} className="sim-axis">← cũ</text><text x={W-R} y={H-8} textAnchor="end" className="sim-axis">mới →</text></svg></div>
      <div className="scenario-title"><h3>Thử thao tác <span>(áp dụng cho {selected.name})</span></h3><span>Mỗi lần bấm tạo dữ liệu ngay</span></div><div className="scenario-buttons"><button onClick={() => chooseMode("walk")}>🚶 Đi lại bình thường</button><button onClick={() => chooseMode("rest")}>🪑 Ngồi nghỉ</button><button onClick={() => chooseMode("wave")}>👋 Vẫy tay mạnh <small>(có thể báo nhầm)</small></button><button className="fall-action" onClick={() => chooseMode("fall")}>⚠ Giả lập té ngã</button><button onClick={() => setPaused(v => !v)}>{paused ? "▶ Tiếp tục" : "Ⅱ Tạm dừng"}</button></div>
      <div className="sim-how"><b>Cách demo:</b> chọn một người bên trái → bấm “Giả lập té ngã” → xác suất vượt ngưỡng và xuất hiện cảnh báo bên phải. Thử “Vẫy tay mạnh”, sau đó kéo độ nhạy xuống để thấy cảnh báo giả lập dễ xuất hiện hơn.</div>
    </main>
    <aside className="sim-alerts"><div className="sim-alert-head"><h3>Cảnh báo gần đây</h3><span>{openCount} cần xử lý</span></div>{alerts.length===0?<div className="sim-no-alert">Chưa có cảnh báo.<br/><small>Thử bấm “Giả lập té ngã”.</small></div>:<div className="sim-alert-list">{alerts.slice(0,8).map(alert=><article className={`sim-alert ${alert.status!=="pending"?"resolved":""}`} key={alert.id}><div className="sim-alert-title"><b>{alert.person} · {alert.wrist}</b><span>{alert.status==="confirmed"?"Đã xác nhận":alert.status==="false_alarm"?"Báo nhầm":"FALL"}</span></div><small>{timeLabel(alert.at)} · xác suất {Math.round(alert.probability*100)}%</small>{alert.status==="pending"&&<div className="sim-alert-actions"><button onClick={()=>markAlert(alert,"confirmed")}>✓ Ngã thật</button><button onClick={()=>markAlert(alert,"false_alarm")}>Báo nhầm</button></div>}</article>)}</div>}<div className="sim-note"><b>Demo tách biệt:</b> dữ liệu mô phỏng này chỉ chạy trong trình duyệt, không ghi vào database, không gửi cảnh báo thật.</div></aside></div>
  </section>;
}
