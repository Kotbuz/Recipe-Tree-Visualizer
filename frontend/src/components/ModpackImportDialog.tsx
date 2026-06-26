import type { ModpackInspectResult } from '../hooks/useModpackInspect';
import '../styles/ModpackImportDialog.css';

type ModpackImportDialogProps = {
    open: boolean;
    inspect: ModpackInspectResult | null;
    currentVersion: string;
    modpackLabel: string;
    busy: boolean;
    installing: boolean;
    preparingForge: boolean;
    forgeProgress: number | null;
    forgeMessage: string | null;
    error: string | null;
    success: string | null;
    onConfirm: () => void;
    onCancel: () => void;
};

export default function ModpackImportDialog({
    open,
    inspect,
    currentVersion,
    modpackLabel,
    busy,
    installing,
    preparingForge,
    forgeProgress,
    forgeMessage,
    error,
    success,
    onConfirm,
    onCancel,
}: ModpackImportDialogProps) {
    if (!open || !inspect) {
        return null;
    }

    const needsInstall = !inspect.version_installed;
    const needsSwitch = inspect.minecraft_version !== currentVersion;
    const canProceed = inspect.version_installed || inspect.catalog_available;

    const needsForgePrepare =
        inspect.loader === 'forge' &&
        Boolean(inspect.forge_version) &&
        inspect.forge_installed === false;

    let actionLabel = 'Импортировать';
    if (needsInstall && needsSwitch) {
        actionLabel = `Установить ${inspect.minecraft_version} и импортировать`;
    } else if (needsInstall) {
        actionLabel = `Установить ${inspect.minecraft_version} и импортировать`;
    } else if (needsSwitch) {
        actionLabel = `Переключиться на ${inspect.minecraft_version} и импортировать`;
    } else if (needsForgePrepare) {
        actionLabel = `Подготовить Forge ${inspect.forge_version} и импортировать`;
    }

    const loaderLabel = [inspect.loader, inspect.forge_version].filter(Boolean).join(' ');

    return (
        <div className="modpack-import-overlay" role="presentation" onClick={onCancel}>
            <div
                className="modpack-import-dialog"
                role="dialog"
                aria-modal="true"
                aria-label="Проверка версии модпака"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="modpack-import-header">
                    <h2 className="modpack-import-title">Версия модпака</h2>
                    <button
                        type="button"
                        className="modpack-import-close"
                        aria-label="Закрыть"
                        onClick={onCancel}
                        disabled={busy}
                    >
                        ×
                    </button>
                </div>

                <p className="modpack-import-lead">
                    <strong>{inspect.modpack_name ?? modpackLabel}</strong> предназначен для{' '}
                    <strong>Minecraft {inspect.minecraft_version}</strong>
                    {loaderLabel ? ` (${loaderLabel})` : null}.
                </p>

                {needsSwitch ? (
                    <p className="modpack-import-note">
                        Сейчас выбрана версия <strong>{currentVersion}</strong>. Сборки нельзя
                        смешивать — импорт будет выполнен в профиль {inspect.minecraft_version}.
                    </p>
                ) : null}

                {needsInstall ? (
                    <p className="modpack-import-note">
                        Версия {inspect.minecraft_version} ещё не установлена.
                        {inspect.catalog_available
                            ? ' Программа скачает client.jar из каталога Mojang.'
                            : ' Эта версия недоступна в каталоге — установите её вручную через менеджер версий.'}
                    </p>
                ) : null}

                {needsForgePrepare && !busy ? (
                    <p className="modpack-import-note">
                        Forge {inspect.forge_version} будет скачан перед импортом модов.
                    </p>
                ) : null}

                {busy && (installing || preparingForge || forgeMessage) ? (
                    <div className="modpack-import-progress" aria-live="polite">
                        <div className="modpack-import-progress-label">
                            {installing
                                ? 'Установка Minecraft…'
                                : forgeMessage ?? 'Подготовка Forge…'}
                        </div>
                        {preparingForge || forgeMessage ? (
                            <div className="modpack-import-progress-track" aria-hidden="true">
                                <div
                                    className="modpack-import-progress-fill"
                                    style={{ width: `${forgeProgress ?? 0}%` }}
                                />
                            </div>
                        ) : (
                            <div className="modpack-import-progress-track modpack-import-progress-track--indeterminate" aria-hidden="true">
                                <div className="modpack-import-progress-fill modpack-import-progress-fill--indeterminate" />
                            </div>
                        )}
                    </div>
                ) : null}

                {busy && !installing && !preparingForge && !forgeMessage ? (
                    <p className="modpack-import-note">Импорт модов и конфигов…</p>
                ) : null}

                <p className="modpack-import-meta">
                    Источник: {inspect.detection_source}
                </p>

                {error ? <div className="modpack-import-error">{error}</div> : null}
                {success ? <div className="modpack-import-success">{success}</div> : null}

                <div className="modpack-import-actions">
                    <button
                        type="button"
                        className="modpack-import-btn"
                        onClick={onCancel}
                        disabled={busy}
                    >
                        {success ? 'Закрыть' : 'Отмена'}
                    </button>
                    <button
                        type="button"
                        className="modpack-import-btn modpack-import-btn--primary"
                        onClick={onConfirm}
                        disabled={busy || (!success && !canProceed)}
                    >
                        {success
                            ? 'Готово'
                            : busy
                              ? installing
                                  ? 'Установка Minecraft…'
                                  : preparingForge
                                    ? 'Установка Forge…'
                                    : 'Импорт…'
                              : actionLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
