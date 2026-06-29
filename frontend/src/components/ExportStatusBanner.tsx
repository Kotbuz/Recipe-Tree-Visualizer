import type { ModDependencyDownloadResponse } from '../hooks/useModDependencyDownload';
import type { RecipeExportStatus } from '../hooks/useRecipeExportStatus';
import '../styles/ExportStatusBanner.css';

type ExportStatusBannerProps = {
    status: RecipeExportStatus | null;
    loading?: boolean;
    downloadingDeps?: boolean;
    depsError?: string | null;
    depsResult?: ModDependencyDownloadResponse | null;
    onDownloadDependencies?: () => void;
};

export default function ExportStatusBanner({
    status,
    loading,
    downloadingDeps = false,
    depsError = null,
    depsResult = null,
    onDownloadDependencies,
}: ExportStatusBannerProps) {
    const hasMissingDeps = (status?.missing_dependencies.length ?? 0) > 0;
    const showBanner =
        !loading &&
        status &&
        status.layout === 'jvm' &&
        (status.warnings.length > 0 || hasMissingDeps || depsResult !== null || depsError);

    if (!showBanner) {
        return null;
    }

    return (
        <div className="export-status-banner" role="status">
            <div className="export-status-banner__title">
                Экспорт рецептов 1.7.x: требуется внимание
            </div>
            {status.warnings.length > 0 && (
                <ul className="export-status-banner__list">
                    {status.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                    ))}
                </ul>
            )}
            {hasMissingDeps && (
                <div className="export-status-banner__deps">
                    <strong>Недостающие зависимости:</strong>
                    <ul>
                        {status.missing_dependencies.map((issue) => (
                            <li key={`${issue.mod_id}-${issue.jar_name}`}>
                                {issue.jar_name}: {issue.requires.join(', ')}
                            </li>
                        ))}
                    </ul>
                    {onDownloadDependencies ? (
                        <button
                            type="button"
                            className="export-status-banner__action"
                            disabled={downloadingDeps}
                            onClick={() => onDownloadDependencies()}
                        >
                            {downloadingDeps
                                ? 'Скачивание и экспорт…'
                                : 'Скачать зависимости и экспортировать'}
                        </button>
                    ) : null}
                </div>
            )}
            {depsError ? (
                <p className="export-status-banner__error">{depsError}</p>
            ) : null}
            {depsResult ? (
                <div className="export-status-banner__result">
                    {depsResult.results.map((item) => (
                        <div key={item.dependency} className="export-status-banner__result-row">
                            <strong>{item.dependency}</strong>: {item.status}
                            {item.jar_name ? ` (${item.jar_name})` : ''}
                            {item.error ? ` — ${item.error}` : ''}
                            {item.manual_url && item.status === 'failed' ? (
                                <>
                                    {' '}
                                    <a href={item.manual_url} target="_blank" rel="noreferrer">
                                        скачать вручную
                                    </a>
                                </>
                            ) : null}
                        </div>
                    ))}
                    {depsResult.export_triggered ? (
                        <p>
                            Экспорт завершён: {depsResult.export_recipe_count ?? 0} рецептов.
                        </p>
                    ) : null}
                    {depsResult.export_error ? (
                        <p className="export-status-banner__error">{depsResult.export_error}</p>
                    ) : null}
                    {!depsResult.all_resolved ? (
                        <p className="export-status-banner__hint">
                            Часть зависимостей не найдена — экспорт не запускался. Скачайте
                            оставшиеся JAR вручную по ссылкам выше.
                        </p>
                    ) : null}
                </div>
            ) : status.warnings.length > 0 || (status.log_errors?.length ?? 0) > 0 ? null : (
                <p className="export-status-banner__hint">
                    Положите JAR-файлы в <code>MinecraftVersions/{status.version}/mods/</code> или
                    используйте кнопку автоматической загрузки.
                </p>
            )}
            {(status.log_errors?.length ?? 0) > 0 && (
                <ul className="export-status-banner__list export-status-banner__log-errors">
                    {status.log_errors!.map((entry) => (
                        <li key={entry}>{entry}</li>
                    ))}
                </ul>
            )}
        </div>
    );
}
