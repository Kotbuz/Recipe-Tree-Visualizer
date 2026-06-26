import { useState } from 'react';
import { DEFAULT_DURATION_TICKS, TICKS_PER_SECOND } from '../canvas';
import '../styles/ModsPanel.css';

type ModsPanelProps = {
    versions: string[];
    version: string;
    onVersionChange: (version: string) => void;
    onSave: () => void;
    onLoad: () => void;
    modCount?: number;
    defaultDurationTicks: number;
    onDefaultDurationTicksChange: (value: number) => void;
};

export default function ModsPanel({
    versions,
    version,
    onVersionChange,
    onSave,
    onLoad,
    modCount = 0,
    defaultDurationTicks,
    onDefaultDurationTicksChange,
}: ModsPanelProps) {
    const [expanded, setExpanded] = useState(false);

    if (!expanded) {
        return (
            <button
                type="button"
                className="mods-panel-toggle"
                aria-label="Открыть панель модов"
                aria-expanded={false}
                onClick={() => setExpanded(true)}
            >
                <span className="mods-panel-toggle-label">Моды</span>
                <span className="mods-panel-badge">{modCount}</span>
            </button>
        );
    }

    return (
        <aside
            className="mods-panel mods-panel--expanded"
            aria-label="Панель модов"
            aria-expanded={true}
        >
            <div className="mods-panel-header">
                <h2 className="mods-panel-title">Моды</h2>
                <div className="mods-panel-header-actions">
                    <span className="mods-panel-badge">{modCount}</span>
                    <button
                        type="button"
                        className="mods-panel-collapse"
                        aria-label="Свернуть панель модов"
                        onClick={() => setExpanded(false)}
                    >
                        ×
                    </button>
                </div>
            </div>

            <label className="mods-panel-field">
                <span className="mods-panel-field-label">Версия Minecraft</span>
                <select
                    className="mods-panel-select"
                    value={version}
                    onChange={(event) => onVersionChange(event.target.value)}
                >
                    {versions.map((entry) => (
                        <option key={entry} value={entry}>
                            {entry}
                        </option>
                    ))}
                </select>
            </label>

            <div className="mods-panel-section">
                <div className="mods-panel-section-title">Настройки расчёта</div>
                <label className="mods-panel-field">
                    <span className="mods-panel-field-label">Время операции по умолчанию (тиков)</span>
                    <input
                        className="mods-panel-input"
                        type="number"
                        min={1}
                        step={1}
                        value={defaultDurationTicks}
                        onChange={(event) => {
                            const next = Number.parseInt(event.target.value, 10);
                            if (Number.isFinite(next) && next > 0) {
                                onDefaultDurationTicksChange(next);
                            }
                        }}
                    />
                </label>
                <p className="mods-panel-hint">
                    {TICKS_PER_SECOND} тиков = 1 сек. Новые рецепты без времени в jar получают это
                    значение ({DEFAULT_DURATION_TICKS} по умолчанию).
                </p>
            </div>

            <p className="mods-panel-hint">
                Здесь будет список подключённых модов и управление ими. Панель не влияет на размер
                холста.
            </p>

            <div className="mods-panel-actions">
                <button type="button" className="mods-panel-button" onClick={onLoad}>
                    Загрузить схему
                </button>
                <button
                    type="button"
                    className="mods-panel-button mods-panel-button--primary"
                    onClick={onSave}
                >
                    Сохранить схему
                </button>
            </div>

            <div className="mods-panel-placeholder">
                <div className="mods-panel-placeholder-title">Каталог модов</div>
                <div className="mods-panel-placeholder-text">Скоро: импорт .jar и modpack</div>
            </div>
        </aside>
    );
}
