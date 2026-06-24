import { useState } from 'react';
import '../styles/ModsPanel.css';

type ModsPanelProps = {
    onSave: () => void;
    onLoad: () => void;
    modCount?: number;
};

export default function ModsPanel({ onSave, onLoad, modCount = 0 }: ModsPanelProps) {
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
