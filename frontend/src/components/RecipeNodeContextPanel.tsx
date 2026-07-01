import type { CanvasNodeRecord } from '../canvas/canvasSchema';
import type { FlowRateUnit } from '../types/production';
import {
    FLOW_RATE_UNIT_LABELS,
    fromRatePerMinute,
    toRatePerMinute,
} from '../utils/flowRate';
import '../styles/RecipeNodeContextPanel.css';

type RecipeNodeContextPanelProps = {
    node: CanvasNodeRecord;
    screenX: number;
    screenY: number;
    flowRateUnit: FlowRateUnit;
    defaultDurationTicks: number;
    onUpdateNode: (nodeId: string, patch: Partial<CanvasNodeRecord>) => void;
    onOpenFactory: () => void;
    onRenameFactory: () => void;
    onDelete: () => void;
};

export default function RecipeNodeContextPanel({
    node,
    screenX,
    screenY,
    flowRateUnit,
    defaultDurationTicks,
    onUpdateNode,
    onOpenFactory,
    onRenameFactory,
    onDelete,
}: RecipeNodeContextPanelProps) {
    const isRecipe = node.kind === 'recipe';
    const isFactory = node.kind === 'outpost';
    const durationTicks = node.durationTicks ?? defaultDurationTicks;

    const patchMachineLimit = (raw: string) => {
        const trimmed = raw.trim();
        if (!trimmed) {
            onUpdateNode(node.id, { machineLimit: null });
            return;
        }
        const parsed = Number.parseInt(trimmed, 10);
        if (Number.isFinite(parsed) && parsed >= 1) {
            onUpdateNode(node.id, { machineLimit: parsed });
        }
    };

    const patchSpeedPercent = (raw: string) => {
        const parsed = Number.parseFloat(raw);
        if (Number.isFinite(parsed) && parsed > 0) {
            onUpdateNode(node.id, { speedPercent: parsed });
        }
    };

    const patchOutputRateLimit = (raw: string) => {
        const trimmed = raw.trim();
        if (!trimmed) {
            onUpdateNode(node.id, { outputRateLimitPerMinute: null });
            return;
        }
        const parsed = Number.parseFloat(trimmed);
        if (Number.isFinite(parsed) && parsed > 0) {
            onUpdateNode(node.id, {
                outputRateLimitPerMinute: toRatePerMinute(parsed, flowRateUnit),
            });
        }
    };

    const patchDurationTicks = (raw: string) => {
        const parsed = Number.parseInt(raw, 10);
        if (Number.isFinite(parsed) && parsed > 0) {
            onUpdateNode(node.id, { durationTicks: parsed });
        }
    };

    return (
        <div
            className="recipe-node-context-panel recipe-node-context-panel--form"
            style={{ left: screenX, top: screenY }}
            onClick={(event) => event.stopPropagation()}
            onMouseDown={(event) => event.stopPropagation()}
            onWheel={(event) => event.stopPropagation()}
        >
            {isFactory && (
                <div className="recipe-node-context-actions">
                    <button
                        type="button"
                        className="recipe-node-context-item"
                        onClick={onOpenFactory}
                    >
                        Открыть фабрику
                    </button>
                    <button
                        type="button"
                        className="recipe-node-context-item"
                        onClick={onRenameFactory}
                    >
                        Переименовать…
                    </button>
                </div>
            )}

            {isRecipe && (
                <>
                    <div className="recipe-node-context-section-title">Производство</div>
                    <label className="recipe-node-context-field">
                        <span>Лимит машин (целое)</span>
                        <input
                            className="recipe-node-context-input"
                            type="number"
                            min={1}
                            step={1}
                            placeholder="без лимита"
                            value={node.machineLimit ?? ''}
                            onChange={(event) => patchMachineLimit(event.target.value)}
                        />
                    </label>
                    <label className="recipe-node-context-field">
                        <span>Скорость часов %</span>
                        <input
                            className="recipe-node-context-input"
                            type="number"
                            min={0.01}
                            step="any"
                            value={node.speedPercent ?? 100}
                            onChange={(event) => patchSpeedPercent(event.target.value)}
                        />
                    </label>
                    <label className="recipe-node-context-field">
                        <span>Лимит скорости выхода ({FLOW_RATE_UNIT_LABELS[flowRateUnit]})</span>
                        <input
                            className="recipe-node-context-input"
                            type="number"
                            min={0.01}
                            step="any"
                            placeholder="без лимита"
                            value={
                                node.outputRateLimitPerMinute != null
                                    ? fromRatePerMinute(
                                          node.outputRateLimitPerMinute,
                                          flowRateUnit,
                                      )
                                    : ''
                            }
                            onChange={(event) => patchOutputRateLimit(event.target.value)}
                        />
                    </label>
                    <label className="recipe-node-context-toggle">
                        <input
                            type="checkbox"
                            checked={node.autoRound ?? false}
                            onChange={(event) =>
                                onUpdateNode(node.id, { autoRound: event.target.checked })
                            }
                        />
                        <span>Автоматический раунд</span>
                    </label>

                    <div className="recipe-node-context-section-title">Время операции</div>
                    <label className="recipe-node-context-field">
                        <span>Время операции (тиков)</span>
                        <input
                            className="recipe-node-context-input"
                            type="number"
                            min={1}
                            step={1}
                            value={durationTicks}
                            onChange={(event) => patchDurationTicks(event.target.value)}
                        />
                    </label>
                    <p className="recipe-node-context-hint">20 тиков = 1 сек</p>
                </>
            )}

            <button
                type="button"
                className="recipe-node-context-item recipe-node-context-item--danger"
                onClick={onDelete}
            >
                Удалить ноду
            </button>
        </div>
    );
}
