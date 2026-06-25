import { useMemo, useState } from 'react';
import { useVersionCatalog } from '../hooks/useVersionCatalog';
import '../styles/VersionManagerModal.css';

type VersionManagerModalProps = {
    open: boolean;
    onClose: () => void;
    onInstalled: (version: string) => void;
};

export default function VersionManagerModal({
    open,
    onClose,
    onInstalled,
}: VersionManagerModalProps) {
    const { catalog, loading, installingVersion, error, installVersion } = useVersionCatalog();
    const [query, setQuery] = useState('');

    const filtered = useMemo(() => {
        const needle = query.trim().toLowerCase();
        if (!needle) {
            return catalog;
        }
        return catalog.filter((entry) => entry.version.toLowerCase().includes(needle));
    }, [catalog, query]);

    if (!open) {
        return null;
    }

    return (
        <div className="version-manager-overlay" role="presentation" onClick={onClose}>
            <div
                className="version-manager-modal"
                role="dialog"
                aria-modal="true"
                aria-label="Менеджер версий Minecraft"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="version-manager-header">
                    <h2 className="version-manager-title">Менеджер версий</h2>
                    <button
                        type="button"
                        className="version-manager-close"
                        aria-label="Закрыть"
                        onClick={onClose}
                    >
                        ×
                    </button>
                </div>

                <p className="version-manager-hint">
                    Релизы загружаются из каталога Mojang. Установка скачивает client.jar в
                    MinecraftVersions/&#123;версия&#125;/ и сразу запускает рендер иконок.
                </p>

                <input
                    className="version-manager-search"
                    type="search"
                    placeholder="Поиск версии…"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                />

                {error ? <div className="version-manager-error">{error}</div> : null}

                {loading ? (
                    <div className="version-manager-status">Загрузка каталога…</div>
                ) : (
                    <ul className="version-manager-list">
                        {filtered.map((entry) => (
                            <li key={entry.version} className="version-manager-item">
                                <div className="version-manager-item-main">
                                    <span className="version-manager-item-version">
                                        {entry.version}
                                    </span>
                                    <span
                                        className={
                                            entry.installed
                                                ? 'version-manager-item-badge version-manager-item-badge--installed'
                                                : 'version-manager-item-badge'
                                        }
                                    >
                                        {entry.installed ? 'установлена' : 'не установлена'}
                                    </span>
                                </div>
                                <button
                                    type="button"
                                    className="version-manager-install"
                                    disabled={entry.installed || installingVersion !== null}
                                    onClick={() => {
                                        void installVersion(entry.version).then(() => {
                                            onInstalled(entry.version);
                                        });
                                    }}
                                >
                                    {installingVersion === entry.version
                                        ? 'Установка…'
                                        : entry.installed
                                          ? 'Готово'
                                          : 'Установить'}
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}
