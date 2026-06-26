import type { RecipeExportStatus } from '../hooks/useRecipeExportStatus';
import '../styles/ExportStatusBanner.css';

type ExportStatusBannerProps = {
    status: RecipeExportStatus | null;
    loading?: boolean;
};

export default function ExportStatusBanner({ status, loading }: ExportStatusBannerProps) {
    if (loading || !status || status.layout !== 'jvm' || status.warnings.length === 0) {
        return null;
    }

    return (
        <div className="export-status-banner" role="status">
            <div className="export-status-banner__title">
                Экспорт рецептов 1.7.x: требуется внимание
            </div>
            <ul className="export-status-banner__list">
                {status.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                ))}
            </ul>
            {status.missing_dependencies.length > 0 && (
                <div className="export-status-banner__deps">
                    <strong>Недостающие зависимости:</strong>
                    <ul>
                        {status.missing_dependencies.map((issue) => (
                            <li key={`${issue.mod_id}-${issue.jar_name}`}>
                                {issue.jar_name}: {issue.requires.join(', ')}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
            <p className="export-status-banner__hint">
                Положите JAR-файлы в <code>MinecraftVersions/{status.version}/mods/</code> и
                выполните экспорт заново. Подробности — в консоли браузера и логах backend.
            </p>
        </div>
    );
}
