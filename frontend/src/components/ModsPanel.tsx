import { useRef, useState } from 'react';
import type { ModSummary } from '../hooks/useMods';
import '../styles/ModsPanel.css';

type ModsPanelProps = {
    versions: string[];
    version: string;
    onVersionChange: (version: string) => void;
    onSave: () => void;
    onLoad: () => void;
    mods: ModSummary[];
    modsLoading: boolean;
    modsUploading: boolean;
    modsError: string | null;
    onModsUpload: (files: FileList) => void;
    onModsRefresh: () => void;
    gameVersion: string;
};

function formatModVersion(mod: ModSummary): string | null {
    if (mod.minecraft_version) {
        return mod.minecraft_version;
    }
    if (mod.minecraft_version_range) {
        return mod.minecraft_version_range;
    }
    return null;
}

function loaderLabel(loader: string): string {
    switch (loader) {
        case 'neoforge':
            return 'NeoForge';
        case 'fabric':
            return 'Fabric';
        case 'forge':
            return 'Forge';
        default:
            return loader;
    }
}

export default function ModsPanel({
    versions,
    version,
    onVersionChange,
    onSave,
    onLoad,
    mods,
    modsLoading,
    modsUploading,
    modsError,
    onModsUpload,
    onModsRefresh,
    gameVersion,
}: ModsPanelProps) {
    const [expanded, setExpanded] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const compatibleCount = mods.filter((mod) => mod.compatible !== false).length;

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
                <span className="mods-panel-badge">{compatibleCount}/{mods.length}</span>
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
                    <span className="mods-panel-badge">{compatibleCount}/{mods.length}</span>
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

            <p className="mods-panel-hint">
                Для версии <strong>{gameVersion}</strong> активны моды с совпадающим диапазоном
                Minecraft из метаданных JAR. Остальные остаются в каталоге, но их рецепты не
                попадают в поиск и холст.
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

            <div className="mods-panel-catalog">
                <div className="mods-panel-catalog-header">
                    <div className="mods-panel-catalog-title">Подключённые моды</div>
                    <button
                        type="button"
                        className="mods-panel-refresh"
                        onClick={onModsRefresh}
                        disabled={modsLoading || modsUploading}
                    >
                        Обновить
                    </button>
                </div>

                {modsError ? <div className="mods-panel-error">{modsError}</div> : null}

                {modsLoading ? (
                    <div className="mods-panel-status">Загрузка списка…</div>
                ) : mods.length === 0 ? (
                    <div className="mods-panel-status">Нет подключённых модов</div>
                ) : (
                    <ul className="mods-panel-list">
                        {mods.map((mod) => (
                            <li
                                key={mod.mod_id}
                                className={`mods-panel-list-item${mod.compatible === false ? ' mods-panel-list-item--inactive' : ''}`}
                            >
                                <div className="mods-panel-mod-name">{mod.name}</div>
                                <div className="mods-panel-mod-meta">
                                    <span className="mods-panel-mod-loader">
                                        {loaderLabel(mod.loader)}
                                    </span>
                                    {formatModVersion(mod) ? (
                                        <span className="mods-panel-mod-version">
                                            MC {formatModVersion(mod)}
                                        </span>
                                    ) : null}
                                    <span>
                                        {mod.recipe_count} рец. · {mod.item_count} предм.
                                    </span>
                                    {mod.compatible === false ? (
                                        <span className="mods-panel-mod-inactive">
                                            не для {gameVersion}
                                        </span>
                                    ) : (
                                        <span className="mods-panel-mod-active">активен</span>
                                    )}
                                    {mod.skipped_recipe_count > 0 ? (
                                        <span className="mods-panel-mod-skipped">
                                            {mod.skipped_recipe_count} пропущено
                                        </span>
                                    ) : null}
                                </div>
                            </li>
                        ))}
                    </ul>
                )}

                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".jar"
                    multiple
                    className="mods-panel-file-input"
                    onChange={(event) => {
                        const files = event.target.files;
                        if (files && files.length > 0) {
                            onModsUpload(files);
                        }
                        event.target.value = '';
                    }}
                />
                <button
                    type="button"
                    className="mods-panel-button mods-panel-button--upload"
                    disabled={modsUploading}
                    onClick={() => fileInputRef.current?.click()}
                >
                    {modsUploading ? 'Загрузка…' : 'Добавить .jar'}
                </button>
            </div>
        </aside>
    );
}
