import { useState } from 'react';
import { X, ZoomIn, ZoomOut, RotateCcw, Search } from 'lucide-react';

interface PeriodicTableModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ElementInfo {
  num: number;
  sym: string;
  name: string;
  mass: string;
  group: number;
  period: number;
  cat: 'alkali' | 'alkaline' | 'transition' | 'post-trans' | 'metalloid' | 'nonmetal' | 'halogen' | 'noble' | 'lanthanide' | 'actinide';
}

const CATEGORY_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  alkali: { bg: 'rgba(239, 68, 68, 0.2)', border: '#ef4444', text: '#fca5a5' },
  alkaline: { bg: 'rgba(249, 115, 22, 0.2)', border: '#f97316', text: '#fdba74' },
  transition: { bg: 'rgba(234, 179, 8, 0.2)', border: '#eab308', text: '#fde047' },
  'post-trans': { bg: 'rgba(34, 197, 94, 0.2)', border: '#22c55e', text: '#86efac' },
  metalloid: { bg: 'rgba(20, 184, 166, 0.2)', border: '#14b8a6', text: '#5eead4' },
  nonmetal: { bg: 'rgba(59, 130, 246, 0.2)', border: '#3b82f6', text: '#93c5fd' },
  halogen: { bg: 'rgba(168, 85, 247, 0.2)', border: '#a885f7', text: '#d8b4fe' },
  noble: { bg: 'rgba(236, 72, 153, 0.2)', border: '#ec4899', text: '#f472b6' },
  lanthanide: { bg: 'rgba(147, 51, 234, 0.2)', border: '#9333ea', text: '#c084fc' },
  actinide: { bg: 'rgba(219, 39, 119, 0.2)', border: '#db2777', text: '#f472b6' },
};

const ELEMENTS: ElementInfo[] = [
  { num: 1, sym: 'H', name: 'Vodorod', mass: '1.008', group: 1, period: 1, cat: 'nonmetal' },
  { num: 2, sym: 'He', name: 'Geliy', mass: '4.0026', group: 18, period: 1, cat: 'noble' },
  { num: 3, sym: 'Li', name: 'Litiy', mass: '6.94', group: 1, period: 2, cat: 'alkali' },
  { num: 4, sym: 'Be', name: 'Berilliy', mass: '9.0122', group: 2, period: 2, cat: 'alkaline' },
  { num: 5, sym: 'B', name: 'Bor', mass: '10.81', group: 13, period: 2, cat: 'metalloid' },
  { num: 6, sym: 'C', name: 'Uglerod', mass: '12.011', group: 14, period: 2, cat: 'nonmetal' },
  { num: 7, sym: 'N', name: 'Azot', mass: '14.007', group: 15, period: 2, cat: 'nonmetal' },
  { num: 8, sym: 'O', name: 'Kislorod', mass: '15.999', group: 16, period: 2, cat: 'nonmetal' },
  { num: 9, sym: 'F', name: 'Ftor', mass: '18.998', group: 17, period: 2, cat: 'halogen' },
  { num: 10, sym: 'Ne', name: 'Neon', mass: '20.180', group: 18, period: 2, cat: 'noble' },
  { num: 11, sym: 'Na', name: 'Natriy', mass: '22.990', group: 1, period: 3, cat: 'alkali' },
  { num: 12, sym: 'Mg', name: 'Magniy', mass: '24.305', group: 2, period: 3, cat: 'alkaline' },
  { num: 13, sym: 'Al', name: 'Alyuminiy', mass: '26.982', group: 13, period: 3, cat: 'post-trans' },
  { num: 14, sym: 'Si', name: 'Kremniy', mass: '28.085', group: 14, period: 3, cat: 'metalloid' },
  { num: 15, sym: 'P', name: 'Fosfor', mass: '30.974', group: 15, period: 3, cat: 'nonmetal' },
  { num: 16, sym: 'S', name: 'Oltingugurt', mass: '32.06', group: 16, period: 3, cat: 'nonmetal' },
  { num: 17, sym: 'Cl', name: 'Xlor', mass: '35.45', group: 17, period: 3, cat: 'halogen' },
  { num: 18, sym: 'Ar', name: 'Argon', mass: '39.948', group: 18, period: 3, cat: 'noble' },
  { num: 19, sym: 'K', name: 'Kaliy', mass: '39.098', group: 1, period: 4, cat: 'alkali' },
  { num: 20, sym: 'Ca', name: 'Kalsiy', mass: '40.078', group: 2, period: 4, cat: 'alkaline' },
  { num: 21, sym: 'Sc', name: 'Skandiy', mass: '44.956', group: 3, period: 4, cat: 'transition' },
  { num: 22, sym: 'Ti', name: 'Titan', mass: '47.867', group: 4, period: 4, cat: 'transition' },
  { num: 23, sym: 'V', name: 'Vanadiy', mass: '50.942', group: 5, period: 4, cat: 'transition' },
  { num: 24, sym: 'Cr', name: 'Xrom', mass: '51.996', group: 6, period: 4, cat: 'transition' },
  { num: 25, sym: 'Mn', name: 'Marganets', mass: '54.938', group: 7, period: 4, cat: 'transition' },
  { num: 26, sym: 'Fe', name: 'Temir', mass: '55.845', group: 8, period: 4, cat: 'transition' },
  { num: 27, sym: 'Co', name: 'Kobalt', mass: '58.933', group: 9, period: 4, cat: 'transition' },
  { num: 28, sym: 'Ni', name: 'Nikel', mass: '58.693', group: 10, period: 4, cat: 'transition' },
  { num: 29, sym: 'Cu', name: 'Mis', mass: '63.546', group: 11, period: 4, cat: 'transition' },
  { num: 30, sym: 'Zn', name: 'Rux', mass: '65.38', group: 12, period: 4, cat: 'transition' },
  { num: 31, sym: 'Ga', name: 'Galliy', mass: '69.723', group: 13, period: 4, cat: 'post-trans' },
  { num: 32, sym: 'Ge', name: 'Germaniy', mass: '72.63', group: 14, period: 4, cat: 'metalloid' },
  { num: 33, sym: 'As', name: 'Mishyak', mass: '74.922', group: 15, period: 4, cat: 'metalloid' },
  { num: 34, sym: 'Se', name: 'Selen', mass: '78.971', group: 16, period: 4, cat: 'nonmetal' },
  { num: 35, sym: 'Br', name: 'Brom', mass: '79.904', group: 17, period: 4, cat: 'halogen' },
  { num: 36, sym: 'Kr', name: 'Kripton', mass: '83.798', group: 18, period: 4, cat: 'noble' },
  { num: 37, sym: 'Rb', name: 'Rubidiy', mass: '85.468', group: 1, period: 5, cat: 'alkali' },
  { num: 38, sym: 'Sr', name: 'Stronsiy', mass: '87.62', group: 2, period: 5, cat: 'alkaline' },
  { num: 47, sym: 'Ag', name: 'Kumush', mass: '107.87', group: 11, period: 5, cat: 'transition' },
  { num: 53, sym: 'I', name: 'Yod', mass: '126.90', group: 17, period: 5, cat: 'halogen' },
  { num: 56, sym: 'Ba', name: 'Bariy', mass: '137.33', group: 2, period: 6, cat: 'alkaline' },
  { num: 79, sym: 'Au', name: 'Oltin', mass: '196.97', group: 11, period: 6, cat: 'transition' },
  { num: 80, sym: 'Hg', name: 'Simob', mass: '200.59', group: 12, period: 6, cat: 'transition' },
  { num: 82, sym: 'Pb', name: 'Qo\'rg\'oshin', mass: '207.2', group: 14, period: 6, cat: 'post-trans' },
];

const ANIONS = ['OH⁻', 'NO₃⁻', 'Cl⁻', 'Br⁻', 'I⁻', 'S²⁻', 'SO₃²⁻', 'SO₄²⁻', 'CO₃²⁻', 'SiO₃²⁻', 'PO₄³⁻'];
const CATIONS = ['H⁺', 'Na⁺', 'K⁺', 'NH₄⁺', 'Ba²⁺', 'Ca²⁺', 'Mg²⁺', 'Al³⁺', 'Zn²⁺', 'Fe²⁺', 'Fe³⁺', 'Cu²⁺', 'Ag⁺', 'Pb²⁺'];

// Solubility values: E (eruvchan), Q (kam eruvchan), Ch (cho'kma), B (parchalanadi/mavjud emas), G (gaz)
const SOLUBILITY_DATA: Record<string, Record<string, string>> = {
  'H⁺': { 'OH⁻': '-', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'E', 'S²⁻': 'G', 'SO₃²⁻': 'G', 'SO₄²⁻': 'E', 'CO₃²⁻': 'G', 'SiO₃²⁻': 'Ch', 'PO₄³⁻': 'E' },
  'Na⁺': { 'OH⁻': 'E', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'E', 'S²⁻': 'E', 'SO₃²⁻': 'E', 'SO₄²⁻': 'E', 'CO₃²⁻': 'E', 'SiO₃²⁻': 'E', 'PO₄³⁻': 'E' },
  'K⁺': { 'OH⁻': 'E', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'E', 'S²⁻': 'E', 'SO₃²⁻': 'E', 'SO₄²⁻': 'E', 'CO₃²⁻': 'E', 'SiO₃²⁻': 'E', 'PO₄³⁻': 'E' },
  'NH₄⁺': { 'OH⁻': 'G', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'E', 'S²⁻': 'E', 'SO₃²⁻': 'E', 'SO₄²⁻': 'E', 'CO₃²⁻': 'E', 'SiO₃²⁻': 'B', 'PO₄³⁻': 'E' },
  'Ba²⁺': { 'OH⁻': 'E', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'E', 'S²⁻': 'E', 'SO₃²⁻': 'Ch', 'SO₄²⁻': 'Ch', 'CO₃²⁻': 'Ch', 'SiO₃²⁻': 'Ch', 'PO₄³⁻': 'Ch' },
  'Ca²⁺': { 'OH⁻': 'Q', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'E', 'S²⁻': 'E', 'SO₃²⁻': 'Ch', 'SO₄²⁻': 'Q', 'CO₃²⁻': 'Ch', 'SiO₃²⁻': 'Ch', 'PO₄³⁻': 'Ch' },
  'Mg²⁺': { 'OH⁻': 'Ch', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'E', 'S²⁻': 'B', 'SO₃²⁻': 'E', 'SO₄²⁻': 'E', 'CO₃²⁻': 'Ch', 'SiO₃²⁻': 'Ch', 'PO₄³⁻': 'Ch' },
  'Al³⁺': { 'OH⁻': 'Ch', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'E', 'S²⁻': 'B', 'SO₃²⁻': 'B', 'SO₄²⁻': 'E', 'CO₃²⁻': 'B', 'SiO₃²⁻': 'Ch', 'PO₄³⁻': 'Ch' },
  'Zn²⁺': { 'OH⁻': 'Ch', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'E', 'S²⁻': 'Ch', 'SO₃²⁻': 'Ch', 'SO₄²⁻': 'E', 'CO₃²⁻': 'Ch', 'SiO₃²⁻': 'Ch', 'PO₄³⁻': 'Ch' },
  'Fe²⁺': { 'OH⁻': 'Ch', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'E', 'S²⁻': 'Ch', 'SO₃²⁻': 'Ch', 'SO₄²⁻': 'E', 'CO₃²⁻': 'Ch', 'SiO₃²⁻': 'Ch', 'PO₄³⁻': 'Ch' },
  'Fe³⁺': { 'OH⁻': 'Ch', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'B', 'S²⁻': 'B', 'SO₃²⁻': 'B', 'SO₄²⁻': 'E', 'CO₃²⁻': 'B', 'SiO₃²⁻': 'Ch', 'PO₄³⁻': 'Ch' },
  'Cu²⁺': { 'OH⁻': 'Ch', 'NO₃⁻': 'E', 'Cl⁻': 'E', 'Br⁻': 'E', 'I⁻': 'B', 'S²⁻': 'Ch', 'SO₃²⁻': 'B', 'SO₄²⁻': 'E', 'CO₃²⁻': 'Ch', 'SiO₃²⁻': 'Ch', 'PO₄³⁻': 'Ch' },
  'Ag⁺': { 'OH⁻': 'B', 'NO₃⁻': 'E', 'Cl⁻': 'Ch', 'Br⁻': 'Ch', 'I⁻': 'Ch', 'S²⁻': 'Ch', 'SO₃²⁻': 'Ch', 'SO₄²⁻': 'Q', 'CO₃²⁻': 'Ch', 'SiO₃²⁻': 'Ch', 'PO₄³⁻': 'Ch' },
  'Pb²⁺': { 'OH⁻': 'Ch', 'NO₃⁻': 'E', 'Cl⁻': 'Q', 'Br⁻': 'Q', 'I⁻': 'Ch', 'S²⁻': 'Ch', 'SO₃²⁻': 'Ch', 'SO₄²⁻': 'Ch', 'CO₃²⁻': 'Ch', 'SiO₃²⁻': 'Ch', 'PO₄³⁻': 'Ch' },
};

export default function PeriodicTableModal({ isOpen, onClose }: PeriodicTableModalProps) {
  const [tab, setTab] = useState<'periodic' | 'solubility'>('periodic');
  const [zoom, setZoom] = useState(1);
  const [query, setQuery] = useState('');
  const [selectedEl, setSelectedEl] = useState<ElementInfo | null>(null);

  if (!isOpen) return null;

  const filteredElements = query.trim()
    ? ELEMENTS.filter(
        (el) =>
          el.sym.toLowerCase().includes(query.toLowerCase()) ||
          el.name.toLowerCase().includes(query.toLowerCase()) ||
          String(el.num).includes(query)
      )
    : ELEMENTS;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.78)',
        backdropFilter: 'blur(8px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--card-bg, #0f172a)',
          color: 'var(--ink, #f8fafc)',
          borderRadius: 16,
          width: '100%',
          maxWidth: 1100,
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 45px rgba(0,0,0,0.5), 0 0 0 1px rgba(200, 146, 42, 0.3)',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '14px 20px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 24 }}>🧪</span>
            <div>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: '#f59e0b' }}>
                Kimyo Ma'lumotnomasi
              </h3>
              <p style={{ margin: 0, fontSize: 12, opacity: 0.7 }}>
                D.I. Mendeleyev Davriy Jadvali va Eruvchanlik Jadvali
              </p>
            </div>
          </div>

          {/* Tab buttons */}
          <div style={{ display: 'flex', gap: 6, background: 'rgba(255,255,255,0.06)', padding: 4, borderRadius: 10 }}>
            <button
              type="button"
              onClick={() => setTab('periodic')}
              style={{
                padding: '6px 14px',
                borderRadius: 8,
                border: 'none',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                background: tab === 'periodic' ? '#f59e0b' : 'transparent',
                color: tab === 'periodic' ? '#000' : 'inherit',
                transition: 'all 0.15s',
              }}
            >
              🧪 Davriy Jadval
            </button>
            <button
              type="button"
              onClick={() => setTab('solubility')}
              style={{
                padding: '6px 14px',
                borderRadius: 8,
                border: 'none',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                background: tab === 'solubility' ? '#f59e0b' : 'transparent',
                color: tab === 'solubility' ? '#000' : 'inherit',
                transition: 'all 0.15s',
              }}
            >
              💧 Eruvchanlik Jadvali
            </button>
          </div>

          {/* Controls & Close */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 8, padding: 2 }}>
              <button
                type="button"
                onClick={() => setZoom((z) => Math.max(0.7, z - 0.1))}
                title="Kichraytirish"
                style={{ background: 'none', border: 'none', color: 'inherit', padding: 6, cursor: 'pointer', display: 'flex' }}
              >
                <ZoomOut size={16} />
              </button>
              <span style={{ fontSize: 11, minWidth: 32, textAlign: 'center' }}>{Math.round(zoom * 100)}%</span>
              <button
                type="button"
                onClick={() => setZoom((z) => Math.min(1.6, z + 0.1))}
                title="Kattalashtirish"
                style={{ background: 'none', border: 'none', color: 'inherit', padding: 6, cursor: 'pointer', display: 'flex' }}
              >
                <ZoomIn size={16} />
              </button>
              <button
                type="button"
                onClick={() => setZoom(1)}
                title="Asliga qaytarish"
                style={{ background: 'none', border: 'none', color: 'inherit', padding: 6, cursor: 'pointer', display: 'flex' }}
              >
                <RotateCcw size={14} />
              </button>
            </div>

            <button
              type="button"
              onClick={onClose}
              style={{
                background: 'rgba(255,255,255,0.08)',
                border: 'none',
                color: 'inherit',
                padding: 7,
                borderRadius: 8,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {tab === 'periodic' ? (
            <div>
              {/* Search & Filter Bar */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                <div style={{ position: 'relative', flex: 1, maxWidth: 320 }}>
                  <Search size={15} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', opacity: 0.5 }} />
                  <input
                    type="text"
                    placeholder="Element izlash (Fe, Temir, 26)..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '7px 10px 7px 32px',
                      borderRadius: 8,
                      border: '1px solid rgba(255,255,255,0.15)',
                      background: 'rgba(0,0,0,0.25)',
                      color: 'inherit',
                      fontSize: 13,
                    }}
                  />
                </div>
                {selectedEl && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 12px', background: 'rgba(245,158,11,0.15)', borderRadius: 8, border: '1px solid #f59e0b' }}>
                    <span style={{ fontWeight: 800, color: '#f59e0b' }}>{selectedEl.sym}</span>
                    <span style={{ fontSize: 13 }}>{selectedEl.name} (№{selectedEl.num})</span>
                    <span style={{ fontSize: 12, opacity: 0.7 }}>Massa: {selectedEl.mass}</span>
                    <button type="button" onClick={() => setSelectedEl(null)} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 14 }}>×</button>
                  </div>
                )}
              </div>

              {/* Elements Grid */}
              <div
                style={{
                  transform: `scale(${zoom})`,
                  transformOrigin: 'top left',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(88px, 1fr))',
                  gap: 8,
                  transition: 'transform 0.1s ease',
                  paddingBottom: 20,
                }}
              >
                {filteredElements.map((el) => {
                  const colors = CATEGORY_COLORS[el.cat] || { bg: 'rgba(255,255,255,0.1)', border: '#888', text: '#fff' };
                  const isSel = selectedEl?.num === el.num;
                  return (
                    <div
                      key={el.num}
                      onClick={() => setSelectedEl(el)}
                      style={{
                        padding: '6px 8px',
                        borderRadius: 8,
                        background: isSel ? 'rgba(245,158,11,0.25)' : colors.bg,
                        border: `1.5px solid ${isSel ? '#f59e0b' : colors.border}`,
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        minHeight: 74,
                        transition: 'transform 0.1s, box-shadow 0.1s',
                        boxShadow: isSel ? '0 0 12px rgba(245,158,11,0.4)' : 'none',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, opacity: 0.75 }}>
                        <span>{el.num}</span>
                        <span>{el.period}-d</span>
                      </div>
                      <div style={{ textAlign: 'center', fontSize: 20, fontWeight: 900, color: colors.text, lineHeight: 1.1 }}>
                        {el.sym}
                      </div>
                      <div style={{ textAlign: 'center', fontSize: 10.5, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {el.name}
                      </div>
                      <div style={{ textAlign: 'center', fontSize: 9.5, opacity: 0.65 }}>
                        {el.mass}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Solubility Table */
            <div style={{ transform: `scale(${zoom})`, transformOrigin: 'top left', transition: 'transform 0.1s ease' }}>
              <div style={{ overflowX: 'auto', paddingBottom: 16 }}>
                <table
                  style={{
                    borderCollapse: 'collapse',
                    width: '100%',
                    fontSize: 12,
                    textAlign: 'center',
                    background: 'rgba(0,0,0,0.2)',
                  }}
                >
                  <thead>
                    <tr>
                      <th style={{ padding: '8px 10px', border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(245,158,11,0.2)', color: '#f59e0b', fontWeight: 800 }}>
                        Kation \ Anion
                      </th>
                      {ANIONS.map((an) => (
                        <th key={an} style={{ padding: '8px 6px', border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.06)', fontWeight: 700 }}>
                          {an}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {CATIONS.map((cat) => (
                      <tr key={cat}>
                        <td style={{ padding: '6px 10px', border: '1px solid rgba(255,255,255,0.15)', fontWeight: 700, background: 'rgba(255,255,255,0.04)' }}>
                          {cat}
                        </td>
                        {ANIONS.map((an) => {
                          const val = SOLUBILITY_DATA[cat]?.[an] || '-';
                          let cellBg = 'transparent';
                          let cellColor = '#ccc';
                          if (val === 'E') { cellBg = 'rgba(34, 197, 94, 0.18)'; cellColor = '#4ade80'; }
                          else if (val === 'Ch') { cellBg = 'rgba(239, 68, 68, 0.22)'; cellColor = '#f87171'; }
                          else if (val === 'Q') { cellBg = 'rgba(234, 179, 8, 0.2)'; cellColor = '#facc15'; }
                          else if (val === 'G') { cellBg = 'rgba(59, 130, 246, 0.2)'; cellColor = '#60a5fa'; }
                          else if (val === 'B') { cellBg = 'rgba(148, 163, 184, 0.15)'; cellColor = '#94a3b8'; }

                          return (
                            <td
                              key={an}
                              style={{
                                padding: '6px 4px',
                                border: '1px solid rgba(255,255,255,0.12)',
                                background: cellBg,
                                color: cellColor,
                                fontWeight: 800,
                              }}
                            >
                              {val}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Legend */}
              <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 12, padding: '10px 14px', background: 'rgba(255,255,255,0.04)', borderRadius: 10, fontSize: 12 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><strong style={{ color: '#4ade80' }}>E</strong> — Eruvchan</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><strong style={{ color: '#facc15' }}>Q</strong> — Kam eruvchan</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><strong style={{ color: '#f87171' }}>Ch</strong> — Cho'kma</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><strong style={{ color: '#60a5fa' }}>G</strong> — Gaz ajraladi</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><strong style={{ color: '#94a3b8' }}>B</strong> — Parchalanadi / mavjud emas</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
