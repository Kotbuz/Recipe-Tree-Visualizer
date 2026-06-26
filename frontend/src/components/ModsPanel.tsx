import { useCallback, useRef, useState, type ReactNode } from 'react';
import type { ModSummary } from '../hooks/useMods';
import type { ProfileSummary } from '../hooks/useProfiles';
import '../styles/ModsPanel.css';

type ModsPanelProps = {
    versions: string[];
    version: string;
    onVersionChange: (version: string) => void;
    onSave: () => void;
    onLoad: () => void;
    profiles: ProfileSummary[];
    activeProfileId: string;
    onProfileChange: (profileId: string) => void;
    onProfileDelete?: (profileId: string) => void;
    deletingProfileId?: string | null;
    profilesLoading?: boolean;
    profileImporting?: boolean;
    profilesError?: string | null;
    onModpackUpload: (file: File) => void;
    onInstancePathImport: (path: string) => void;
    onBrowseInstanceFolder?: () => void;
    browsingInstanceFolder?: boolean;
    mods: ModSummary[];
    modsLoading: boolean;
    modsUploading: boolean;
    modsError: string | null;
    onModsRefresh: () => void;
    onModRemove?: (jarFilename: string) => void;
    removingJarFilename?: string | null;
    onOpenVersionManager: () => void;
    gameVersion: string;
    versionsEmpty: boolean;
    missingDependencyCount?: number;
    onDownloadDependencies?: () => void;
    downloadingDependencies?: boolean;
    onReloadMods?: () => void;
    reloadingMods?: boolean;
    onClearRecipeExport?: () => void;
    clearingRecipeExport?: boolean;
    maintenanceError?: string | null;
    showRecipeMaintenance?: boolean;
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

function zipFilesFromDataTransfer(dataTransfer: DataTransfer): File[] {
    return Array.from(dataTransfer.files).filter((file) =>
        file.name.toLowerCase().endsWith('.zip'),
    );
}

function PanelSection({
    title,
    summary,
    open,
    onToggle,
    children,
}: {
    title: string;
    summary?: string;
    open: boolean;
    onToggle: () => void;
    children: ReactNode;
}) {
    return (
        <section className="mods-panel-section">
            <button
                type="button"
                className="mods-panel-section-toggle"
                aria-expanded={open}
                onClick={onToggle}
            >
                <span className="mods-panel-section-chevron" aria-hidden>
                    {open ? '▾' : '▸'}
                </span>
                <span className="mods-panel-section-title">{title}</span>
                {summary ? <span className="mods-panel-section-summary">{summary}</span> : null}
            </button>
            {open ? <div className="mods-panel-section-body">{children}</div> : null}
        </section>
    );
}

export default function ModsPanel({
    versions,
    version,
    onVersionChange,
    onSave,
    onLoad,
    profiles,
    activeProfileId,
    onProfileChange,
    onProfileDelete,
    deletingProfileId = null,
    profilesLoading = false,
    profileImporting = false,
    profilesError = null,
    onModpackUpload,
    onInstancePathImport,
    onBrowseInstanceFolder,
    browsingInstanceFolder = false,
    mods,
    modsLoading,
    modsUploading,
    modsError,
    onModsRefresh,
    onModRemove,
    removingJarFilename = null,
    onOpenVersionManager,
    gameVersion,
    versionsEmpty,
    missingDependencyCount = 0,
    onDownloadDependencies,
    downloadingDependencies = false,
    onReloadMods,
    reloadingMods = false,
    onClearRecipeExport,
    clearingRecipeExport = false,
    maintenanceError = null,
    showRecipeMaintenance = false,
}: ModsPanelProps) {
    const [expanded, setExpanded] = useState(false);
    const [importOpen, setImportOpen] = useState(versionsEmpty);
    const [modsOpen, setModsOpen] = useState(true);
    const [toolsOpen, setToolsOpen] = useState(false);
    const [isDragOver, setIsDragOver] = useState(false);
    const [instancePath, setInstancePath] = useState('');
    const dragDepthRef = useRef(0);
    const modpackInputRef = useRef<HTMLInputElement>(null);
    const compatibleCount = mods.filter((mod) => mod.compatible !== false).length;
    const importDisabled = profileImporting || versionsEmpty;
    const activeProfile = profiles.find((p) => p.profile_id === activeProfileId);
    const hasTools =
        (missingDependencyCount > 0 && Boolean(onDownloadDependencies)) ||
        Boolean(onReloadMods) ||
        (showRecipeMaintenance && Boolean(onClearRecipeExport));

    const canDeleteActive =
        Boolean(onProfileDelete) && activeProfileId !== 'default' && !versionsEmpty;

    const submitModpackFile = useCallback(
        (file: File | undefined) => {
            if (!file || importDisabled) {
                return;
            }
            onModpackUpload(file);
        },
        [importDisabled, onModpackUpload],
    );

    const handleDragEnter = useCallback(
        (event: React.DragEvent<HTMLDivElement>) => {
            event.preventDefault();
            event.stopPropagation();
            if (importDisabled) {
                return;
            }
            dragDepthRef.current += 1;
            setIsDragOver(true);
        },
        [importDisabled],
    );

    const handleDragLeave = useCallback((event: React.DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        event.stopPropagation();
        dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
        if (dragDepthRef.current === 0) {
            setIsDragOver(false);
        }
    }, []);

    const handleDragOver = useCallback(
        (event: React.DragEvent<HTMLDivElement>) => {
            event.preventDefault();
            event.stopPropagation();
            if (!importDisabled) {
                event.dataTransfer.dropEffect = 'copy';
            }
        },
        [importDisabled],
    );

    const handleDrop = useCallback(
        (event: React.DragEvent<HTMLDivElement>) => {
            event.preventDefault();
            event.stopPropagation();
            dragDepthRef.current = 0;
            setIsDragOver(false);
            if (importDisabled) {
                return;
            }
            const files = zipFilesFromDataTransfer(event.dataTransfer);
            if (files[0]) {
                submitModpackFile(files[0]);
            }
        },
        [importDisabled, submitModpackFile],
    );

    if (!expanded) {
        return (
            <button
                type="button"
                className="mods-panel-toggle"
                aria-label="Открыть панель модпаков"
                aria-expanded={false}
                onClick={() => setExpanded(true)}
            >
                <span className="mods-panel-toggle-label">Модпак</span>
                <span className="mods-panel-badge">
                    {compatibleCount}/{mods.length}
                </span>
            </button>
        );
    }

    return (
        <aside className="mods-panel mods-panel--expanded" aria-label="Панель модпаков">
            <div className="mods-panel-header">
                <h2 className="mods-panel-title">Модпак</h2>
                <div className="mods-panel-header-actions">
                    <span className="mods-panel-badge">
                        {compatibleCount}/{mods.length}
                    </span>
                    <button
                        type="button"
                        className="mods-panel-collapse"
                        aria-label="Свернуть"
                        onClick={() => setExpanded(false)}
                    >
                        ×
                    </button>
                </div>
            </div>

            <div className="mods-panel-toolbar">
                <label className="mods-panel-field mods-panel-field--inline">
                    <span className="mods-panel-field-label">Версия</span>
                    <div className="mods-panel-inline-row">
                        <select
                            className="mods-panel-select"
                            value={version}
                            onChange={(event) => onVersionChange(event.target.value)}
                            disabled={versionsEmpty}
                        >
                            {versions.length === 0 ? (
                                <option value="">—</option>
                            ) : (
                                versions.map((entry) => (
                                    <option key={entry} value={entry}>
                                        {entry}
                                    </option>
                                ))
                            )}
                        </select>
                        <button
                            type="button"
                            className="mods-panel-btn mods-panel-btn--ghost"
                            onClick={onOpenVersionManager}
                        >
                            …
                        </button>
                    </div>
                </label>

                <label className="mods-panel-field mods-panel-field--inline">
                    <span className="mods-panel-field-label">Профиль</span>
                    <div className="mods-panel-inline-row">
                        <select
                            className="mods-panel-select"
                            value={activeProfileId}
                            onChange={(event) => onProfileChange(event.target.value)}
                            disabled={
                                versionsEmpty ||
                                profilesLoading ||
                                profileImporting ||
                                Boolean(deletingProfileId)
                            }
                        >
                            {profiles.length === 0 ? (
                                <option value="default">default</option>
                            ) : (
                                profiles.map((profile) => (
                                    <option key={profile.profile_id} value={profile.profile_id}>
                                        {profile.name}
                                    </option>
                                ))
                            )}
                        </select>
                        {canDeleteActive ? (
                            <button
                                type="button"
                                className="mods-panel-btn mods-panel-btn--danger mods-panel-btn--ghost"
                                disabled={
                                    versionsEmpty ||
                                    profileImporting ||
                                    deletingProfileId === activeProfileId
                                }
                                title="Удалить активный профиль модпака"
                                aria-label="Удалить активный профиль модпака"
                                onClick={() => onProfileDelete?.(activeProfileId)}
                            >
                                {deletingProfileId === activeProfileId ? '…' : 'Удалить'}
                            </button>
                        ) : null}
                    </div>
                </label>
            </div>

            <div className="mods-panel-actions">
                <button type="button" className="mods-panel-btn" onClick={onLoad}>
                    Загрузить
                </button>
                <button
                    type="button"
                    className="mods-panel-btn mods-panel-btn--primary"
                    onClick={onSave}
                >
                    Сохранить
                </button>
            </div>

            {versionsEmpty ? (
                <p className="mods-panel-hint">Установите версию Minecraft, затем импортируйте модпак.</p>
            ) : null}

            {(profilesError || modsError || maintenanceError) && (
                <div className="mods-panel-errors">
                    {profilesError ? <div className="mods-panel-error">{profilesError}</div> : null}
                    {modsError ? <div className="mods-panel-error">{modsError}</div> : null}
                    {maintenanceError ? (
                        <div className="mods-panel-error">{maintenanceError}</div>
                    ) : null}
                </div>
            )}

            <div className="mods-panel-sections">
                <PanelSection
                    title="Импорт"
                    summary={activeProfile ? `${activeProfile.mod_count} мод.` : undefined}
                    open={importOpen}
                    onToggle={() => setImportOpen((v) => !v)}
                >
                    <input
                        ref={modpackInputRef}
                        type="file"
                        accept=".zip,application/zip"
                        className="mods-panel-file-input"
                        onChange={(event) => {
                            const file = event.target.files?.[0];
                            if (file) {
                                submitModpackFile(file);
                            }
                            event.target.value = '';
                        }}
                    />
                    <div
                        className={`mods-panel-dropzone${isDragOver ? ' mods-panel-dropzone--active' : ''}${importDisabled ? ' mods-panel-dropzone--disabled' : ''}`}
                        onDragEnter={handleDragEnter}
                        onDragLeave={handleDragLeave}
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                    >
                        <button
                            type="button"
                            className="mods-panel-btn mods-panel-btn--block"
                            disabled={importDisabled}
                            onClick={() => modpackInputRef.current?.click()}
                        >
                            {profileImporting ? 'Импорт…' : '.zip модпака'}
                        </button>
                    </div>
                    <div className="mods-panel-path-row">
                        <input
                            type="text"
                            className="mods-panel-path-input"
                            placeholder="Папка инстанса Prism…"
                            value={instancePath}
                            onChange={(event) => setInstancePath(event.target.value)}
                            disabled={importDisabled || browsingInstanceFolder}
                        />
                        {onBrowseInstanceFolder ? (
                            <button
                                type="button"
                                className="mods-panel-btn"
                                disabled={importDisabled || browsingInstanceFolder}
                                title="Выбрать папку в проводнике"
                                onClick={onBrowseInstanceFolder}
                            >
                                {browsingInstanceFolder ? '…' : 'Обзор…'}
                            </button>
                        ) : null}
                        <button
                            type="button"
                            className="mods-panel-btn"
                            disabled={
                                importDisabled || browsingInstanceFolder || !instancePath.trim()
                            }
                            onClick={() => {
                                onInstancePathImport(instancePath.trim());
                                setInstancePath('');
                            }}
                        >
                            →
                        </button>
                    </div>
                </PanelSection>

                <PanelSection
                    title="Моды"
                    summary={`${compatibleCount}/${mods.length}`}
                    open={modsOpen}
                    onToggle={() => setModsOpen((v) => !v)}
                >
                    <div className="mods-panel-list-toolbar">
                        <button
                            type="button"
                            className="mods-panel-btn mods-panel-btn--ghost"
                            onClick={onModsRefresh}
                            disabled={modsLoading || modsUploading || profileImporting}
                        >
                            {modsLoading ? '…' : 'Обновить'}
                        </button>
                    </div>
                    {modsLoading ? (
                        <div className="mods-panel-status">Загрузка…</div>
                    ) : mods.length === 0 ? (
                        <div className="mods-panel-status">Пусто</div>
                    ) : (
                        <ul className="mods-panel-list">
                            {mods.map((mod) => {
                                const jarFilename = mod.jar_filename ?? '';
                                const rowKey = jarFilename || mod.mod_id;
                                const isRemoving = removingJarFilename === jarFilename;
                                const mcVer = formatModVersion(mod);
                                return (
                                    <li
                                        key={rowKey}
                                        className={`mods-panel-list-item${mod.compatible === false ? ' mods-panel-list-item--inactive' : ''}`}
                                    >
                                        <div className="mods-panel-mod-row">
                                            <span className="mods-panel-mod-name" title={mod.name}>
                                                {mod.name}
                                            </span>
                                            {jarFilename && onModRemove ? (
                                                <button
                                                    type="button"
                                                    className="mods-panel-mod-remove"
                                                    disabled={
                                                        modsUploading ||
                                                        isRemoving ||
                                                        Boolean(removingJarFilename)
                                                    }
                                                    aria-label={`Удалить jar ${mod.name}`}
                                                    title="Удалить только этот jar (профиль останется)"
                                                    onClick={() => {
                                                        if (
                                                            !window.confirm(
                                                                `Удалить jar «${mod.name}»?\n\nПрофиль модпака не удаляется — только этот файл.`,
                                                            )
                                                        ) {
                                                            return;
                                                        }
                                                        onModRemove(jarFilename);
                                                    }}
                                                >
                                                    {isRemoving ? '…' : '×'}
                                                </button>
                                            ) : null}
                                        </div>
                                        <div className="mods-panel-mod-meta">
                                            <span>{loaderLabel(mod.loader)}</span>
                                            {mcVer ? <span>MC {mcVer}</span> : null}
                                            <span>
                                                {mod.recipe_count}р · {mod.item_count}п
                                            </span>
                                            {mod.compatible === false ? (
                                                <span className="mods-panel-mod-inactive">!</span>
                                            ) : null}
                                        </div>
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </PanelSection>

                {hasTools ? (
                    <PanelSection
                        title="Сервис"
                        summary={missingDependencyCount > 0 ? `деп. ${missingDependencyCount}` : undefined}
                        open={toolsOpen}
                        onToggle={() => setToolsOpen((v) => !v)}
                    >
                        <div className="mods-panel-tools">
                            {missingDependencyCount > 0 && onDownloadDependencies ? (
                                <button
                                    type="button"
                                    className="mods-panel-btn mods-panel-btn--warn mods-panel-btn--block"
                                    disabled={downloadingDependencies || versionsEmpty}
                                    onClick={onDownloadDependencies}
                                >
                                    {downloadingDependencies
                                        ? 'Скачивание…'
                                        : `Зависимости (${missingDependencyCount})`}
                                </button>
                            ) : null}
                            {onReloadMods ? (
                                <button
                                    type="button"
                                    className="mods-panel-btn mods-panel-btn--block"
                                    disabled={reloadingMods || clearingRecipeExport || versionsEmpty}
                                    onClick={onReloadMods}
                                >
                                    {reloadingMods ? 'Перезагрузка…' : 'Перезагрузить рецепты'}
                                </button>
                            ) : null}
                            {showRecipeMaintenance && onClearRecipeExport ? (
                                <button
                                    type="button"
                                    className="mods-panel-btn mods-panel-btn--danger mods-panel-btn--block"
                                    disabled={clearingRecipeExport || reloadingMods || versionsEmpty}
                                    onClick={onClearRecipeExport}
                                >
                                    {clearingRecipeExport ? 'Очистка…' : 'Очистить кэш'}
                                </button>
                            ) : null}
                        </div>
                    </PanelSection>
                ) : null}
            </div>
        </aside>
    );
}
