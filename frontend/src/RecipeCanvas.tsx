import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
    type RecipeSummary,
    type RecipeItem,
    type SlotType,
    type NodeSlot,
    type RecipeConnection,
    type NodeKind,
} from './types/recipe';
import ModsPanel from './components/ModsPanel';
import ExportStatusBanner from './components/ExportStatusBanner';
import VersionManagerModal from './components/VersionManagerModal';
import ModpackImportDialog from './components/ModpackImportDialog';
import { useModpackInspect, type ModpackInspectResult } from './hooks/useModpackInspect';
import { prepareForgeInstall } from './hooks/useForgePrepare';
import { useVersionCatalog } from './hooks/useVersionCatalog';
import ItemIconView from './components/ItemIconView';
import RecipePickerList from './components/RecipePickerList';
import { mergeRecipeItems } from './utils/mergeRecipeItems';
import { useMinecraftVersion } from './context/MinecraftVersionContext';
import { useModDependencyDownload } from './hooks/useModDependencyDownload';
import { useMods } from './hooks/useMods';
import { useProfiles } from './hooks/useProfiles';
import { useRecipeExportStatus } from './hooks/useRecipeExportStatus';
import { useRecipeSearch } from './hooks/useRecipeSearch';
import { useVersionMaintenance } from './hooks/useVersionMaintenance';
import {
    ingredientsCompatible,
    type IngredientIndex,
    type IngredientRef,
} from './utils/ingredientMatch';
import {
    CANVAS_CONFIG,
    buildCanvasBezierPath,
    buildViewportBezierPath,
    createCanvasDocument,
    downloadCanvasDocument,
    getSlotAnchorCanvas,
    normalizeCanvasPoint,
    pickCanvasDocumentFile,
    slotConnectionSide,
    useCanvasViewport,
    type CanvasNodeRecord,
} from './canvas';
import './styles/RecipeCanvas.css';

type RecipeNode = CanvasNodeRecord;

interface NodeDragState {
    nodeId: string;
    offsetX: number;
    offsetY: number;
}

interface ItemDragState {
    sourceNodeId: string;
    sourceSlotType: SlotType;
    sourceItemIndex: number;
    itemName: string;
    itemId?: string;
    itemMetadata?: number;
    startX: number;
    startY: number;
    startClientX: number;
    startClientY: number;
    currentClientX: number;
    currentClientY: number;
}

type RecipeContextMenu = {
    type: 'recipe';
    screenX: number;
    screenY: number;
};

type NodeContextMenu = {
    type: 'node';
    nodeId: string;
    screenX: number;
    screenY: number;
};

type ItemRecipeContextMenu = {
    type: 'item-recipe';
    itemName: string;
    itemId?: string;
    itemMetadata?: number;
    sourceNodeId: string;
    sourceSlotType: SlotType;
    sourceItemIndex: number;
    screenX: number;
    screenY: number;
};

type ContextMenu = RecipeContextMenu | NodeContextMenu | ItemRecipeContextMenu;

type TerminalKind = 'chest' | 'outpost';

const MIN_ITEM_DRAG_DISTANCE = CANVAS_CONFIG.interaction.minItemDragDistance;
const SLOT_HIT_RADIUS = CANVAS_CONFIG.interaction.slotHitRadius;

const machineNameMap: Record<string, string> = {
    'minecraft:crafting_shaped': 'Верстак',
    'minecraft:crafting_shapeless': 'Верстак',
    'minecraft:smelting': 'Печь',
    'minecraft:smoking': 'Печь',
    'minecraft:blasting': 'Печь',
    'minecraft:campfire_cooking': 'Печь',
    'minecraft:smithing': 'Наковальня',
    'minecraft:smithing_transform': 'Наковальня',
    'minecraft:stonecutting': 'Наковальня',
};

const TERMINAL_LABELS: Record<TerminalKind, string> = {
    chest: 'Сундук',
    outpost: 'Аванпост',
};

const mapMachineName = (typeName: string) =>
    machineNameMap[typeName] ??
    typeName
        .replace(/.*:/, '')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c: string) => c.toUpperCase());

const isTerminalNode = (node: RecipeNode) => node.kind === 'chest' || node.kind === 'outpost';

const getChestPassthroughItem = (node: RecipeNode) =>
    node.inputs[0]?.name || node.outputs[0]?.name || '';

const getSlotItemName = (node: RecipeNode, slotType: SlotType, index: number) => {
    if (node.kind === 'chest') {
        return getChestPassthroughItem(node);
    }

    const items = slotType === 'input' ? node.inputs : node.outputs;
    return items[index]?.name ?? '';
};

const getSlotItemId = (node: RecipeNode, slotType: SlotType, index: number) => {
    if (node.kind === 'chest') {
        const items = node.inputs[0] ?? node.outputs[0];
        return items?.item_id;
    }

    const items = slotType === 'input' ? node.inputs : node.outputs;
    return items[index]?.item_id;
};

const getSlotItemMetadata = (node: RecipeNode, slotType: SlotType, index: number) => {
    if (node.kind === 'chest') {
        const items = node.inputs[0] ?? node.outputs[0];
        return items?.metadata;
    }

    const items = slotType === 'input' ? node.inputs : node.outputs;
    return items[index]?.metadata;
};

const getSlotItemIconId = (node: RecipeNode, slotType: SlotType, index: number) => {
    if (node.kind === 'chest') {
        const items = node.inputs[0] ?? node.outputs[0];
        return items?.icon_id;
    }

    const items = slotType === 'input' ? node.inputs : node.outputs;
    return items[index]?.icon_id;
};

const slotTypesForConnection = (
    sourceSlotType: SlotType,
): SlotType[] => (sourceSlotType === 'input' ? ['output', 'input'] : ['input', 'output']);

const canConnectSlotTypes = (sourceSlotType: SlotType, targetSlotType: SlotType): boolean => {
    if (sourceSlotType === 'output' && targetSlotType === 'input') {
        return true;
    }
    if (sourceSlotType === 'input' && targetSlotType === 'output') {
        return true;
    }
    if (sourceSlotType === 'input' && targetSlotType === 'input') {
        return true;
    }
    return false;
};

const slotKey = (nodeId: string, slotType: SlotType, index: number) =>
    `${nodeId}:${slotType}:${index}`;

const connectionId = (from: NodeSlot, to: NodeSlot) =>
    `${from.nodeId}:${from.slotType}:${from.itemIndex}->${to.nodeId}:${to.slotType}:${to.itemIndex}`;

const getSlotIngredientRef = (
    node: RecipeNode,
    slotType: SlotType,
    index: number,
): IngredientRef => ({
    name: getSlotItemName(node, slotType, index),
    itemId: getSlotItemId(node, slotType, index),
    metadata: getSlotItemMetadata(node, slotType, index),
});

const findCompatibleSlotOnNode = (
    node: RecipeNode,
    sourceSlotType: SlotType,
    dragged: IngredientRef,
    ingredientIndex: IngredientIndex | null,
): NodeSlot | null => {
    for (const targetSlotType of slotTypesForConnection(sourceSlotType)) {
        if (!canConnectSlotTypes(sourceSlotType, targetSlotType)) {
            continue;
        }

        const items = targetSlotType === 'input' ? node.inputs : node.outputs;
        for (let index = 0; index < items.length; index += 1) {
            if (!isSlotCompatible(node, targetSlotType, index, dragged, ingredientIndex)) {
                continue;
            }

            return {
                nodeId: node.id,
                slotType: targetSlotType,
                itemIndex: index,
                itemName: dragged.name,
            };
        }
    }

    return null;
};

const findMatchingSlotIndex = (
    node: RecipeNode,
    slotType: SlotType,
    dragged: IngredientRef,
    ingredientIndex: IngredientIndex | null,
) => {
    const items = slotType === 'input' ? node.inputs : node.outputs;
    return items.findIndex((item) =>
        ingredientsCompatible(
            dragged,
            { name: item.name, itemId: item.item_id, metadata: item.metadata },
            ingredientIndex,
        ),
    );
};

const isSlotCompatible = (
    node: RecipeNode,
    slotType: SlotType,
    index: number,
    dragged: IngredientRef,
    ingredientIndex: IngredientIndex | null,
) => {
    const slotName = getSlotItemName(node, slotType, index);
    if (!slotName) {
        return isTerminalNode(node);
    }

    return ingredientsCompatible(
        dragged,
        getSlotIngredientRef(node, slotType, index),
        ingredientIndex,
    );
};

export default function RecipeCanvas() {
    const { version, versions, setVersion, ingredientIndex, reloadCatalog, refreshInstalledVersions } =
        useMinecraftVersion();
    const {
        profiles,
        activeProfileId,
        activateProfile,
        deleteProfile,
        importModpackZip,
        importFromPath,
        importing: profileImporting,
        deletingProfileId,
        error: profilesError,
        refresh: refreshProfiles,
    } = useProfiles(version);
    const { mods, loading: modsLoading, uploading: modsUploading, removingJar, error: modsError, refresh: refreshMods, remove: removeMod } = useMods(version, activeProfileId);
    const { status: exportStatus, loading: exportStatusLoading, refresh: refreshExportStatus } = useRecipeExportStatus(version, activeProfileId);
    const {
        reloading: maintenanceReloading,
        clearing: maintenanceClearing,
        error: maintenanceError,
        reloadMods,
        clearRecipeExport,
    } = useVersionMaintenance(version, activeProfileId);
    const handleReloadMods = useCallback(async () => {
        try {
            const result = await reloadMods();
            await refreshMods();
            if (result.export_status) {
                await refreshExportStatus();
            }
            await reloadCatalog();
        } catch {
            // ошибка уже в maintenanceError
        }
    }, [reloadMods, refreshMods, refreshExportStatus, reloadCatalog]);

    const handleClearRecipeExport = useCallback(async () => {
        const confirmed = window.confirm(
            'Удалить все JSON-файлы рецептов и ore_dict.json для этой версии?\n\n' +
                'После очистки потребуется повторный JVM-экспорт (вручную или через «Скачать зависимости»).',
        );
        if (!confirmed) {
            return;
        }

        try {
            await clearRecipeExport();
            await refreshExportStatus();
            await refreshMods();
            await reloadCatalog();
        } catch {
            // ошибка уже в maintenanceError
        }
    }, [clearRecipeExport, refreshExportStatus, refreshMods, reloadCatalog]);

    const handleModRemove = useCallback(
        async (jarFilename: string) => {
            try {
                await removeMod(jarFilename);
                await refreshExportStatus();
            } catch {
                // ошибка уже в modsError
            }
        },
        [removeMod, refreshExportStatus],
    );

    const handleDepsDownloadComplete = useCallback(async () => {
        await refreshMods();
        await refreshExportStatus();
        await reloadCatalog();
    }, [refreshMods, refreshExportStatus, reloadCatalog]);

    const {
        download: downloadMissingDeps,
        downloading: depsDownloading,
        error: depsError,
        lastResult: depsResult,
    } = useModDependencyDownload(version, activeProfileId, handleDepsDownloadComplete);
    const [versionManagerOpen, setVersionManagerOpen] = useState(false);
    const [pendingModpackImport, setPendingModpackImport] = useState<
        | {
              kind: 'zip';
              file: File;
              label: string;
              inspect: ModpackInspectResult;
          }
        | {
              kind: 'path';
              path: string;
              label: string;
              inspect: ModpackInspectResult;
          }
        | null
    >(null);
    const [importFlowBusy, setImportFlowBusy] = useState(false);
    const [importFlowError, setImportFlowError] = useState<string | null>(null);
    const [importFlowSuccess, setImportFlowSuccess] = useState<string | null>(null);
    const [installingMinecraft, setInstallingMinecraft] = useState(false);
    const [forgePrepareProgress, setForgePrepareProgress] = useState<number | null>(null);
    const [forgePrepareMessage, setForgePrepareMessage] = useState<string | null>(null);
    const [preparingForge, setPreparingForge] = useState(false);
    const { inspectZip, inspectPath, pickFolder, inspecting: modpackInspecting, error: modpackInspectError } =
        useModpackInspect();
    const { installVersion, installingVersion } = useVersionCatalog();
    const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
    const [selectedRecipe, setSelectedRecipe] = useState<RecipeSummary | null>(null);
    const [nodes, setNodes] = useState<RecipeNode[]>([]);
    const [connections, setConnections] = useState<RecipeConnection[]>([]);
    const [nodeDragState, setNodeDragState] = useState<NodeDragState | null>(null);
    const [itemDragState, setItemDragState] = useState<ItemDragState | null>(null);
    const [recipeSearchQuery, setRecipeSearchQuery] = useState('');
    const [, setLayoutTick] = useState(0);

    const recipeSearchParams = useMemo(() => {
        if (contextMenu?.type !== 'recipe' && contextMenu?.type !== 'item-recipe') {
            return {
                enabled: false,
                query: '',
            };
        }

        if (contextMenu.type === 'item-recipe') {
            const focusItem = contextMenu.itemId ?? contextMenu.itemName;
            const focusRole =
                contextMenu.sourceSlotType === 'input' ? ('output' as const) : ('input' as const);
            return {
                enabled: true,
                query: recipeSearchQuery,
                focusItem,
                focusRole,
                focusMetadata: contextMenu.itemMetadata,
                includeMods: true,
            };
        }

        return {
            enabled: true,
            query: recipeSearchQuery,
        };
    }, [contextMenu, recipeSearchQuery]);

    const { recipes: searchedRecipes, loading: recipesLoading } = useRecipeSearch(
        version,
        activeProfileId,
        recipeSearchParams,
    );

    const {
        viewportRef,
        contentRef,
        transform,
        transformStyle,
        coords,
        isPanning,
        setViewportTransform,
        handleWheel,
        handlePanMouseDown,
        handlePanMouseMove,
        handlePanMouseUp,
    } = useCanvasViewport();

    const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map());
    const itemDragRef = useRef<ItemDragState | null>(null);
    const recipeSearchRef = useRef<HTMLInputElement>(null);

    const handleVersionChange = useCallback(
        (nextVersion: string) => {
            setVersion(nextVersion);
            setNodes([]);
            setConnections([]);
            setContextMenu(null);
            setRecipeSearchQuery('');
            setSelectedRecipe(null);
            setNodeDragState(null);
            setItemDragState(null);
            itemDragRef.current = null;
        },
        [setVersion],
    );

    const screenToCanvas = coords.screenToCanvas;

    const canvasPointFromScreen = useCallback(
        (clientX: number, clientY: number) => {
            const point = screenToCanvas(clientX, clientY);
            return point ? normalizeCanvasPoint(point) : null;
        },
        [screenToCanvas],
    );

    const getContentCoordinates = useCallback(
        (event: { clientX: number; clientY: number }) =>
            canvasPointFromScreen(event.clientX, event.clientY),
        [canvasPointFromScreen],
    );

    const getSlotAnchor = useCallback(
        (nodeId: string, slotType: SlotType, index: number) => {
            const key = slotKey(nodeId, slotType, index);
            const element = itemRefs.current.get(key);
            const node = nodes.find((entry) => entry.id === nodeId);
            if (!element || !node) return null;

            return getSlotAnchorCanvas({
                nodeX: node.x,
                nodeY: node.y,
                slotType,
                itemElement: element,
                scale: transform.scale,
            });
        },
        [nodes, transform.scale],
    );

    const bumpLayout = useCallback(() => {
        setLayoutTick((value) => value + 1);
    }, []);

    useEffect(() => {
        bumpLayout();
    }, [nodes, connections, transform, bumpLayout]);

    const syncChestPassthrough = useCallback((nodeId: string, itemName: string) => {
        setNodes((current) =>
            current.map((node) => {
                if (node.id !== nodeId || node.kind !== 'chest') return node;

                return {
                    ...node,
                    inputs: node.inputs.map((item, index) =>
                        index === 0 ? { ...item, name: itemName } : item,
                    ),
                    outputs: node.outputs.map((item, index) =>
                        index === 0 ? { ...item, name: itemName } : item,
                    ),
                };
            }),
        );
    }, []);

    const populateTerminalSlot = useCallback(
        (nodeId: string, slotType: SlotType, itemIndex: number, itemName: string) => {
            setNodes((current) =>
                current.map((node) => {
                    if (node.id !== nodeId || node.kind !== 'outpost') return node;

                    const items = slotType === 'input' ? node.inputs : node.outputs;
                    const item = items[itemIndex];
                    if (!item || item.name) return node;

                    const updatedItem = { ...item, name: itemName };
                    if (slotType === 'input') {
                        const inputs = [...node.inputs];
                        inputs[itemIndex] = updatedItem;
                        return { ...node, inputs };
                    }

                    const outputs = [...node.outputs];
                    outputs[itemIndex] = updatedItem;
                    return { ...node, outputs };
                }),
            );
        },
        [],
    );

    const addConnection = useCallback((from: NodeSlot, to: NodeSlot) => {
        const id = connectionId(from, to);
        setConnections((current) => {
            if (current.some((connection) => connection.id === id)) {
                return current;
            }
            return [...current, { id, from, to }];
        });
    }, []);

    const removeNode = useCallback((nodeId: string) => {
        setNodes((current) => current.filter((node) => node.id !== nodeId));
        setConnections((current) =>
            current.filter(
                (connection) =>
                    connection.from.nodeId !== nodeId && connection.to.nodeId !== nodeId,
            ),
        );
    }, []);

    const findCompatibleSlotAt = useCallback(
        (
            point: { x: number; y: number },
            dragged: IngredientRef,
            sourceSlotType: SlotType,
            sourceNodeId: string,
        ): NodeSlot | null => {
            for (const node of nodes) {
                if (node.id === sourceNodeId) continue;

                for (const targetSlotType of slotTypesForConnection(sourceSlotType)) {
                    if (!canConnectSlotTypes(sourceSlotType, targetSlotType)) {
                        continue;
                    }

                    const items = targetSlotType === 'input' ? node.inputs : node.outputs;
                    for (let index = 0; index < items.length; index += 1) {
                        if (
                            !isSlotCompatible(
                                node,
                                targetSlotType,
                                index,
                                dragged,
                                ingredientIndex,
                            )
                        ) {
                            continue;
                        }

                        const anchor = getSlotAnchor(node.id, targetSlotType, index);
                        if (!anchor) continue;

                        const distance = Math.hypot(anchor.x - point.x, anchor.y - point.y);
                        if (distance <= SLOT_HIT_RADIUS) {
                            return {
                                nodeId: node.id,
                                slotType: targetSlotType,
                                itemIndex: index,
                                itemName: dragged.name,
                            };
                        }
                    }
                }
            }

            return null;
        },
        [nodes, getSlotAnchor, ingredientIndex],
    );

    const connectSlots = useCallback(
        (
            sourceNodeId: string,
            sourceSlotType: SlotType,
            sourceItemIndex: number,
            itemName: string,
            target: NodeSlot,
        ) => {
            const source: NodeSlot = {
                nodeId: sourceNodeId,
                slotType: sourceSlotType,
                itemIndex: sourceItemIndex,
                itemName,
            };

            if (sourceSlotType === 'input' && target.slotType === 'output') {
                addConnection(target, source);
            } else if (sourceSlotType === 'input' && target.slotType === 'input') {
                addConnection(source, target);
            } else {
                addConnection(source, target);
            }

            syncChestPassthrough(target.nodeId, itemName);
            syncChestPassthrough(source.nodeId, itemName);
            populateTerminalSlot(target.nodeId, target.slotType, target.itemIndex, itemName);
            populateTerminalSlot(source.nodeId, source.slotType, source.itemIndex, itemName);
        },
        [addConnection, syncChestPassthrough, populateTerminalSlot],
    );

    const closeMenu = () => {
        setContextMenu(null);
        setRecipeSearchQuery('');
    };

    const openMenu = (event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
        event.preventDefault();
        setSelectedRecipe(null);
        setRecipeSearchQuery('');

        if (!canvasPointFromScreen(event.clientX, event.clientY)) return;

        setContextMenu({
            type: 'recipe',
            screenX: event.clientX,
            screenY: event.clientY,
        });
    };

    const placeNodeAtScreen = useCallback(
        (clientX: number, clientY: number) => canvasPointFromScreen(clientX, clientY),
        [canvasPointFromScreen],
    );

    const createNodeFromRecipe = (recipe: RecipeSummary, x: number, y: number) => {
        const node: RecipeNode = {
            id: `${recipe.recipe_id}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            kind: 'recipe',
            recipeId: recipe.recipe_id,
            x,
            y,
            machineName: mapMachineName(recipe.machine_type),
            inputs: mergeRecipeItems(recipe.inputs).map((item) => ({
                name: item.name,
                amount: item.amount,
                item_id: item.item_id,
                icon_id: item.icon_id,
                metadata: item.metadata,
            })),
            outputs: mergeRecipeItems(recipe.outputs).map((item) => ({
                name: item.name,
                amount: item.amount,
                item_id: item.item_id,
                icon_id: item.icon_id,
                metadata: item.metadata,
            })),
        };
        setNodes((current) => [...current, node]);
        setSelectedRecipe(recipe);
        return node;
    };

    const createTerminalNode = (
        terminalKind: TerminalKind,
        x: number,
        y: number,
        prefilledSlot?: { slotType: SlotType; itemName: string },
    ) => {
        const node: RecipeNode = {
            id: `${terminalKind}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            kind: terminalKind,
            x,
            y,
            machineName: TERMINAL_LABELS[terminalKind],
            inputs: [
                {
                    name:
                        prefilledSlot?.slotType === 'input' ? prefilledSlot.itemName : '',
                    amount: 1,
                },
            ],
            outputs: [
                {
                    name:
                        prefilledSlot?.slotType === 'output' ? prefilledSlot.itemName : '',
                    amount: 1,
                },
            ],
        };
        setNodes((current) => [...current, node]);
        return node;
    };

    const connectItemDragToTerminal = (
        menu: ItemRecipeContextMenu,
        terminalNode: RecipeNode,
    ) => {
        const targetSlotType: SlotType =
            menu.sourceSlotType === 'input' ? 'output' : 'input';
        const targetIndex = 0;

        connectSlots(
            menu.sourceNodeId,
            menu.sourceSlotType,
            menu.sourceItemIndex,
            menu.itemName,
            {
                nodeId: terminalNode.id,
                slotType: targetSlotType,
                itemIndex: targetIndex,
                itemName: menu.itemName,
            },
        );
    };

    const handleRecipeClick = (recipe: RecipeSummary) => {
        if (!contextMenu || contextMenu.type !== 'recipe') return;
        const coords = placeNodeAtScreen(contextMenu.screenX, contextMenu.screenY);
        if (!coords) return;
        createNodeFromRecipe(recipe, coords.x, coords.y);
        closeMenu();
    };

    const handleItemRecipeClick = (recipe: RecipeSummary) => {
        if (!contextMenu || contextMenu.type !== 'item-recipe') return;

        const coords = placeNodeAtScreen(contextMenu.screenX, contextMenu.screenY);
        if (!coords) return;

        const newNode = createNodeFromRecipe(recipe, coords.x, coords.y);

        const dragged: IngredientRef = {
            name: contextMenu.itemName,
            itemId: contextMenu.itemId,
            metadata: contextMenu.itemMetadata,
        };
        const compatibleSlot = findCompatibleSlotOnNode(
            newNode,
            contextMenu.sourceSlotType,
            dragged,
            ingredientIndex,
        );

        if (compatibleSlot) {
            connectSlots(
                contextMenu.sourceNodeId,
                contextMenu.sourceSlotType,
                contextMenu.sourceItemIndex,
                contextMenu.itemName,
                compatibleSlot,
            );
        }

        closeMenu();
    };

    const handleTerminalNodeClick = (terminalKind: TerminalKind) => {
        if (!contextMenu || (contextMenu.type !== 'recipe' && contextMenu.type !== 'item-recipe')) {
            return;
        }

        const coords = placeNodeAtScreen(contextMenu.screenX, contextMenu.screenY);
        if (!coords) return;

        if (contextMenu.type === 'recipe') {
            createTerminalNode(terminalKind, coords.x, coords.y);
            closeMenu();
            return;
        }

        const prefilledSlot =
            terminalKind === 'outpost'
                ? {
                      slotType: (contextMenu.sourceSlotType === 'input'
                          ? 'output'
                          : 'input') as SlotType,
                      itemName: contextMenu.itemName,
                  }
                : undefined;

        const terminalNode = createTerminalNode(
            terminalKind,
            coords.x,
            coords.y,
            prefilledSlot,
        );
        connectItemDragToTerminal(contextMenu, terminalNode);
        closeMenu();
    };

    const handleMachineMouseDown = (nodeId: string, event: React.MouseEvent<HTMLDivElement>) => {
        event.preventDefault();
        event.stopPropagation();

        const node = nodes.find((entry) => entry.id === nodeId);
        if (!node) return;

        const contentCoords = getContentCoordinates(event);
        if (!contentCoords) return;

        setNodeDragState({
            nodeId,
            offsetX: contentCoords.x - node.x,
            offsetY: contentCoords.y - node.y,
        });
    };

    const handleItemMouseDown = (
        nodeId: string,
        slotType: SlotType,
        itemIndex: number,
        event: React.MouseEvent<HTMLDivElement>,
    ) => {
        const node = nodes.find((entry) => entry.id === nodeId);
        if (!node) return;

        const itemName = getSlotItemName(node, slotType, itemIndex);
        if (!itemName) return;

        const itemId = getSlotItemId(node, slotType, itemIndex);
        const itemMetadata = getSlotItemMetadata(node, slotType, itemIndex);

        event.preventDefault();
        event.stopPropagation();

        const anchor = getSlotAnchor(nodeId, slotType, itemIndex);
        if (!anchor) return;

        const drag: ItemDragState = {
            sourceNodeId: nodeId,
            sourceSlotType: slotType,
            sourceItemIndex: itemIndex,
            itemName,
            itemId,
            itemMetadata,
            startX: anchor.x,
            startY: anchor.y,
            startClientX: event.clientX,
            startClientY: event.clientY,
            currentClientX: event.clientX,
            currentClientY: event.clientY,
        };
        itemDragRef.current = drag;
        setItemDragState(drag);
    };

    const handleNodeContextMenu = (
        nodeId: string,
        event: React.MouseEvent<HTMLDivElement, MouseEvent>,
    ) => {
        event.preventDefault();
        event.stopPropagation();
        setSelectedRecipe(null);
        setContextMenu({
            type: 'node',
            nodeId,
            screenX: event.clientX,
            screenY: event.clientY,
        });
    };

    const finishItemDrag = useCallback(
        (drag: ItemDragState, clientX: number, clientY: number) => {
            const distance = Math.hypot(
                clientX - drag.startClientX,
                clientY - drag.startClientY,
            );
            if (distance < MIN_ITEM_DRAG_DISTANCE) {
                return;
            }

            const dropPoint = canvasPointFromScreen(clientX, clientY);
            if (!dropPoint) return;

            const compatibleSlot = findCompatibleSlotAt(
                dropPoint,
                { name: drag.itemName, itemId: drag.itemId, metadata: drag.itemMetadata },
                drag.sourceSlotType,
                drag.sourceNodeId,
            );

            if (compatibleSlot) {
                connectSlots(
                    drag.sourceNodeId,
                    drag.sourceSlotType,
                    drag.sourceItemIndex,
                    drag.itemName,
                    compatibleSlot,
                );
                return;
            }

            setContextMenu({
                type: 'item-recipe',
                itemName: drag.itemName,
                itemId: drag.itemId,
                itemMetadata: drag.itemMetadata,
                sourceNodeId: drag.sourceNodeId,
                sourceSlotType: drag.sourceSlotType,
                sourceItemIndex: drag.sourceItemIndex,
                screenX: clientX,
                screenY: clientY,
            });
            setRecipeSearchQuery('');
        },
        [canvasPointFromScreen, findCompatibleSlotAt, connectSlots],
    );

    useEffect(() => {
        if (!nodeDragState) return;

        const handleMouseMove = (event: MouseEvent) => {
            const contentCoords = canvasPointFromScreen(event.clientX, event.clientY);
            if (!contentCoords) return;

            setNodes((current) =>
                current.map((node) =>
                    node.id === nodeDragState.nodeId
                        ? {
                              ...node,
                              x: contentCoords.x - nodeDragState.offsetX,
                              y: contentCoords.y - nodeDragState.offsetY,
                          }
                        : node,
                ),
            );
        };

        const handleMouseUp = () => {
            setNodeDragState(null);
        };

        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);

        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [nodeDragState, canvasPointFromScreen]);

    useEffect(() => {
        const handleMouseMove = (event: MouseEvent) => {
            const drag = itemDragRef.current;
            if (!drag) return;

            const nextDrag = {
                ...drag,
                currentClientX: event.clientX,
                currentClientY: event.clientY,
            };
            itemDragRef.current = nextDrag;
            setItemDragState(nextDrag);
        };

        const handleMouseUp = (event: MouseEvent) => {
            const drag = itemDragRef.current;
            if (!drag) return;

            itemDragRef.current = null;
            setItemDragState(null);
            finishItemDrag(drag, event.clientX, event.clientY);
        };

        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);

        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [finishItemDrag]);

    const handleCanvasMouseDownForPan = (event: React.MouseEvent<HTMLDivElement>) => {
        if (event.button !== 0) return;
        if (nodeDragState || itemDragState) return;
        handlePanMouseDown(event);
    };

    const handleSaveCanvas = useCallback(() => {
        const document = createCanvasDocument({
            nodes,
            connections,
            viewport: transform,
            name: 'recipe-tree',
            minecraftVersion: version,
            profileId: activeProfileId,
        });
        downloadCanvasDocument(document);
    }, [activeProfileId, connections, nodes, transform, version]);

    const handleLoadCanvas = useCallback(async () => {
        try {
            const document = await pickCanvasDocumentFile();
            if (document.minecraftVersion && document.minecraftVersion !== version) {
                setVersion(document.minecraftVersion);
            }
            if (document.profileId && document.profileId !== activeProfileId) {
                await activateProfile(document.profileId);
            }
            setNodes(document.nodes);
            setConnections(document.connections);
            if (document.viewport) {
                setViewportTransform(document.viewport);
            }
            setContextMenu(null);
            setRecipeSearchQuery('');
        } catch {
            // пользователь отменил выбор или файл некорректен
        }
    }, [activeProfileId, activateProfile, setVersion, setViewportTransform, version]);

    const handleProfileChange = useCallback(
        async (profileId: string) => {
            if (!profileId || profileId === activeProfileId) {
                return;
            }
            try {
                await activateProfile(profileId);
                await refreshMods();
                await refreshExportStatus();
                await reloadCatalog();
            } catch {
                // ошибка в profilesError
            }
        },
        [activeProfileId, activateProfile, refreshMods, refreshExportStatus, reloadCatalog],
    );

    const handleProfileDelete = useCallback(
        async (profileId: string) => {
            const profile = profiles.find((entry) => entry.profile_id === profileId);
            const label = profile?.name ?? profileId;
            if (
                !window.confirm(
                    `Удалить профиль «${label}»?\n\nБудут удалены mods/, config/, scripts/ и кэш рецептов этого профиля.`,
                )
            ) {
                return;
            }
            try {
                await deleteProfile(profileId);
                await refreshMods();
                await refreshExportStatus();
                await reloadCatalog();
            } catch {
                // ошибка в profilesError
            }
        },
        [
            deleteProfile,
            profiles,
            refreshMods,
            refreshExportStatus,
            reloadCatalog,
        ],
    );

    const runModpackImport = useCallback(
        async (
            inspect: ModpackInspectResult,
            source:
                | { kind: 'zip'; file: File }
                | { kind: 'path'; path: string },
        ) => {
            const targetVersion = inspect.minecraft_version;
            setImportFlowBusy(true);
            setImportFlowError(null);
            setImportFlowSuccess(null);
            setForgePrepareProgress(null);
            setForgePrepareMessage(null);
            setPreparingForge(false);
            setInstallingMinecraft(false);
            try {
                setVersion(targetVersion);

                if (!inspect.version_installed) {
                    if (!inspect.catalog_available) {
                        throw new Error(
                            `Версия ${targetVersion} недоступна в каталоге Mojang. Установите её через менеджер версий.`,
                        );
                    }
                    setInstallingMinecraft(true);
                    await installVersion(targetVersion);
                    await refreshInstalledVersions();
                    setInstallingMinecraft(false);
                }
                if (
                    inspect.loader === 'forge' &&
                    inspect.forge_version &&
                    inspect.forge_installed === false
                ) {
                    setPreparingForge(true);
                    await prepareForgeInstall(
                        targetVersion,
                        inspect.forge_version,
                        (status) => {
                            setForgePrepareProgress(status.progress);
                            setForgePrepareMessage(status.message);
                        },
                    );
                    setPreparingForge(false);
                }
                let importResult;
                if (source.kind === 'zip') {
                    importResult = await importModpackZip(source.file, { targetVersion });
                } else {
                    importResult = await importFromPath(source.path, { targetVersion });
                }

                await refreshProfiles(targetVersion);
                await reloadCatalog();
                await refreshMods();
                await refreshExportStatus();

                const profileName = importResult?.profile?.name ?? 'модпак';
                const jarCount = importResult?.jars_imported ?? 0;
                setImportFlowSuccess(
                    `Готово: импортировано ${jarCount} модов в профиль «${profileName}».`,
                );
            } catch (flowError) {
                const message =
                    flowError instanceof Error ? flowError.message : 'Ошибка импорта модпака';
                setImportFlowError(message);
                throw flowError;
            } finally {
                setImportFlowBusy(false);
                setInstallingMinecraft(false);
                setPreparingForge(false);
                setForgePrepareProgress(null);
                setForgePrepareMessage(null);
            }
        },
        [
            importFromPath,
            importModpackZip,
            installVersion,
            refreshExportStatus,
            refreshInstalledVersions,
            refreshMods,
            refreshProfiles,
            reloadCatalog,
            setVersion,
        ],
    );

    const handleModpackUpload = useCallback(
        async (file: File) => {
            try {
                const inspect = await inspectZip(file);
                if (inspect.minecraft_version === version && inspect.version_installed) {
                    await importModpackZip(file, { targetVersion: inspect.minecraft_version });
                    await refreshMods();
                    await refreshExportStatus();
                    await reloadCatalog();
                    return;
                }
                setImportFlowError(null);
                setPendingModpackImport({
                    kind: 'zip',
                    file,
                    label: file.name,
                    inspect,
                });
            } catch {
                // ошибка в useModpackInspect.error
            }
        },
        [
            importModpackZip,
            inspectZip,
            refreshMods,
            refreshExportStatus,
            reloadCatalog,
            version,
        ],
    );

    const handleInstancePathImport = useCallback(
        async (path: string) => {
            try {
                const inspect = await inspectPath(path);
                if (inspect.minecraft_version === version && inspect.version_installed) {
                    await importFromPath(path, { targetVersion: inspect.minecraft_version });
                    await refreshMods();
                    await refreshExportStatus();
                    await reloadCatalog();
                    return;
                }
                setImportFlowError(null);
                setPendingModpackImport({
                    kind: 'path',
                    path,
                    label: path,
                    inspect,
                });
            } catch {
                // ошибка в useModpackInspect.error
            }
        },
        [
            importFromPath,
            inspectPath,
            refreshMods,
            refreshExportStatus,
            reloadCatalog,
            version,
        ],
    );

    const handleBrowseInstanceFolder = useCallback(async () => {
        try {
            const path = await pickFolder();
            if (path) {
                await handleInstancePathImport(path);
            }
        } catch {
            // ошибка в modpackInspectError
        }
    }, [handleInstancePathImport, pickFolder]);

    const renderConnectionPath = (from: NodeSlot, to: NodeSlot) => {
        const fromAnchor = getSlotAnchor(from.nodeId, from.slotType, from.itemIndex);
        const toAnchor = getSlotAnchor(to.nodeId, to.slotType, to.itemIndex);
        if (!fromAnchor || !toAnchor) return null;

        return buildCanvasBezierPath(
            { ...fromAnchor, side: slotConnectionSide(from.slotType) },
            { ...toAnchor, side: slotConnectionSide(to.slotType) },
        );
    };

    const itemRecipeHeader =
        contextMenu?.type === 'item-recipe'
            ? contextMenu.sourceSlotType === 'input'
                ? `Рецепты с результатом «${contextMenu.itemName}»`
                : `Рецепты с ингредиентом «${contextMenu.itemName}»`
            : '';

    const recipePickerEmptyQuery =
        contextMenu?.type === 'recipe' && recipeSearchQuery.trim().length === 0;

    const recipePickerEmptyMessage =
        contextMenu?.type === 'item-recipe' ? 'Нет подходящих рецептов' : 'Ничего не найдено';

    useEffect(() => {
        if (contextMenu?.type === 'recipe' || contextMenu?.type === 'item-recipe') {
            recipeSearchRef.current?.focus();
        }
    }, [contextMenu]);

    const renderItemSlot = (
        node: RecipeNode,
        slotType: SlotType,
        _item: RecipeItem,
        index: number,
    ) => {
        const displayName = getSlotItemName(node, slotType, index);
        const iconId = getSlotItemIconId(node, slotType, index);
        const isEmpty = !displayName;

        return (
            <div
                key={slotKey(node.id, slotType, index)}
                ref={(element) => {
                    const key = slotKey(node.id, slotType, index);
                    if (element) {
                        itemRefs.current.set(key, element);
                    } else {
                        itemRefs.current.delete(key);
                    }
                }}
                className={`recipe-node-item recipe-node-item--${slotType}${
                    isEmpty ? ' recipe-node-item--empty' : ''
                }`}
                onMouseDown={(event) =>
                    handleItemMouseDown(node.id, slotType, index, event)
                }
                title={isEmpty ? (slotType === 'input' ? 'Вход' : 'Выход') : displayName}
            >
                {isEmpty ? (
                    <span className="item-icon-view item-icon-view--chip recipe-node-item-placeholder">
                        {slotType === 'input' ? 'IN' : 'OUT'}
                    </span>
                ) : (
                    <ItemIconView itemName={displayName} iconId={iconId} />
                )}
            </div>
        );
    };

    const dragPreviewPath = useMemo(() => {
        if (!itemDragState) return null;

        const start = coords.canvasToViewportLocal({
            x: itemDragState.startX,
            y: itemDragState.startY,
        });
        const end = coords.viewportLocalFromScreen(
            itemDragState.currentClientX,
            itemDragState.currentClientY,
        );
        if (!start || !end) return null;

        return buildViewportBezierPath(
            { ...start, side: slotConnectionSide(itemDragState.sourceSlotType) },
            {
                ...end,
                side: end.x >= start.x ? 'left' : 'right',
            },
        );
    }, [coords, itemDragState]);

    const isJvmExportVersion = exportStatus?.layout === 'jvm';
    const missingDependencyCount =
        isJvmExportVersion && exportStatus
            ? exportStatus.missing_dependencies.reduce(
                  (count, issue) => count + issue.requires.length,
                  0,
              )
            : 0;

    const canvasStyle = {
        '--canvas-svg-offset': `${CANVAS_CONFIG.layers.connectionsSvgOffset}px`,
        '--canvas-svg-size': `${CANVAS_CONFIG.layers.connectionsSvgSize}px`,
    } as React.CSSProperties;

    return (
        <div className="recipe-canvas-page" style={canvasStyle}>
            <ExportStatusBanner
                status={exportStatus}
                loading={exportStatusLoading}
                downloadingDeps={depsDownloading}
                depsError={depsError}
                depsResult={depsResult}
                onDownloadDependencies={
                    isJvmExportVersion && missingDependencyCount > 0
                        ? () => void downloadMissingDeps()
                        : undefined
                }
            />
            <div
                className="recipe-canvas"
                ref={viewportRef}
                onContextMenu={openMenu}
                onWheel={handleWheel}
                onMouseDown={handleCanvasMouseDownForPan}
                onMouseMove={handlePanMouseMove}
                onMouseUp={handlePanMouseUp}
                onMouseLeave={handlePanMouseUp}
                style={{ cursor: isPanning ? 'grabbing' : 'default' }}
            >
                <div className="recipe-canvas-toolbar">
                    <div>
                        ПКМ по холсту — добавить ноду • Тяните за блок крафта — перемещение •
                        Тяните за ингредиент/результат — связь • Колесо — зум • ЛКМ+движение —
                        панорама
                    </div>
                </div>

                {dragPreviewPath && (
                    <svg className="recipe-connections-screen-layer" aria-hidden="true">
                        <path
                            className="recipe-connection-line recipe-connection-line--preview"
                            d={dragPreviewPath}
                        />
                    </svg>
                )}
                <div
                    ref={contentRef}
                    className="recipe-canvas-content"
                    style={{
                        transform: transformStyle,
                        transformOrigin: '0 0',
                    }}
                >
                    <svg className="recipe-connections-layer" aria-hidden="true">
                        {connections.map((connection) => {
                            const path = renderConnectionPath(connection.from, connection.to);
                            if (!path) return null;
                            return (
                                <path
                                    key={connection.id}
                                    className="recipe-connection-line"
                                    d={path}
                                />
                            );
                        })}
                    </svg>

                    {nodes.map((node) => (
                        <div
                            key={node.id}
                            className={`recipe-node ${
                                contextMenu?.type === 'node' && contextMenu.nodeId === node.id
                                    ? 'recipe-node--active'
                                    : ''
                            }`}
                            style={{ left: node.x, top: node.y }}
                            onContextMenu={(event) => handleNodeContextMenu(node.id, event)}
                        >
                            <div className="recipe-node-column recipe-node-column--inputs">
                                {node.inputs.map((input, index) =>
                                    renderItemSlot(node, 'input', input, index),
                                )}
                            </div>
                            <div className="recipe-node-column recipe-node-column--machine">
                                <div
                                    className={`recipe-node-machine recipe-node-machine--${node.kind}`}
                                    onMouseDown={(event) =>
                                        handleMachineMouseDown(node.id, event)
                                    }
                                >
                                    {node.machineName}
                                </div>
                            </div>
                            <div className="recipe-node-column recipe-node-column--outputs">
                                {node.outputs.map((output, index) =>
                                    renderItemSlot(node, 'output', output, index),
                                )}
                            </div>
                        </div>
                    ))}
                </div>

                {(contextMenu?.type === 'recipe' || contextMenu?.type === 'item-recipe') &&
                    createPortal(
                        <div className="recipe-context-modal" onClick={closeMenu}>
                            <div
                                className="recipe-context-panel"
                                style={{
                                    left: contextMenu.screenX,
                                    top: contextMenu.screenY,
                                }}
                                onClick={(event) => event.stopPropagation()}
                            >
                                <div className="recipe-context-header">
                                    {contextMenu.type === 'recipe'
                                        ? 'Добавить на холст'
                                        : itemRecipeHeader}
                                </div>
                                <div className="recipe-context-body">
                                    <div className="recipe-context-sidebar">
                                        <div className="recipe-context-sidebar-title">Блоки</div>
                                        <button
                                            type="button"
                                            className="recipe-context-terminal recipe-context-terminal--chest"
                                            onClick={() => handleTerminalNodeClick('chest')}
                                        >
                                            Сундук
                                        </button>
                                        <button
                                            type="button"
                                            className="recipe-context-terminal recipe-context-terminal--outpost"
                                            onClick={() => handleTerminalNodeClick('outpost')}
                                        >
                                            Аванпост
                                        </button>
                                    </div>
                                    <div className="recipe-context-main">
                                        <div className="recipe-context-main-title">Рецепты</div>
                                        <input
                                            ref={recipeSearchRef}
                                            className="recipe-context-search"
                                            type="search"
                                            placeholder="Поиск по результату..."
                                            value={recipeSearchQuery}
                                            onChange={(event) =>
                                                setRecipeSearchQuery(event.target.value)
                                            }
                                        />
                                        <div className="recipe-context-list">
                                            <RecipePickerList
                                                recipes={searchedRecipes}
                                                loading={recipesLoading}
                                                emptyQuery={recipePickerEmptyQuery}
                                                emptyMessage={recipePickerEmptyMessage}
                                                onRecipeClick={(recipe) =>
                                                    contextMenu.type === 'recipe'
                                                        ? handleRecipeClick(recipe)
                                                        : handleItemRecipeClick(recipe)
                                                }
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>,
                        document.body,
                    )}

                {contextMenu?.type === 'node' &&
                    createPortal(
                        <div
                            className="recipe-context-modal recipe-context-modal--transparent"
                            onClick={closeMenu}
                        >
                            <div
                                className="recipe-node-context-panel"
                                style={{
                                    left: contextMenu.screenX,
                                    top: contextMenu.screenY,
                                }}
                                onClick={(event) => event.stopPropagation()}
                            >
                                <button
                                    type="button"
                                    className="recipe-node-context-item"
                                    onClick={() => {
                                        removeNode(contextMenu.nodeId);
                                        closeMenu();
                                    }}
                                >
                                    Удалить ноду
                                </button>
                            </div>
                        </div>,
                        document.body,
                    )}
            </div>

            <ModsPanel
                versions={versions}
                version={version}
                onVersionChange={handleVersionChange}
                onSave={handleSaveCanvas}
                onLoad={handleLoadCanvas}
                profiles={profiles}
                activeProfileId={activeProfileId}
                onProfileChange={(profileId) => void handleProfileChange(profileId)}
                onProfileDelete={(profileId) => void handleProfileDelete(profileId)}
                deletingProfileId={deletingProfileId}
                profilesLoading={false}
                profileImporting={profileImporting || modpackInspecting || importFlowBusy}
                profilesError={profilesError ?? modpackInspectError}
                onModpackUpload={(file) => void handleModpackUpload(file)}
                onInstancePathImport={(path) => void handleInstancePathImport(path)}
                onBrowseInstanceFolder={() => void handleBrowseInstanceFolder()}
                browsingInstanceFolder={modpackInspecting}
                mods={mods}
                modsLoading={modsLoading}
                modsUploading={modsUploading}
                modsError={modsError}
                onModsRefresh={refreshMods}
                onModRemove={(jarFilename) => void handleModRemove(jarFilename)}
                removingJarFilename={removingJar}
                onOpenVersionManager={() => setVersionManagerOpen(true)}
                gameVersion={version}
                versionsEmpty={versions.length === 0}
                missingDependencyCount={missingDependencyCount}
                onDownloadDependencies={
                    isJvmExportVersion && missingDependencyCount > 0
                        ? () => void downloadMissingDeps()
                        : undefined
                }
                downloadingDependencies={depsDownloading}
                onReloadMods={() => void handleReloadMods()}
                reloadingMods={maintenanceReloading}
                onClearRecipeExport={() => void handleClearRecipeExport()}
                clearingRecipeExport={maintenanceClearing}
                maintenanceError={maintenanceError}
                showRecipeMaintenance={isJvmExportVersion}
            />

            <VersionManagerModal
                open={versionManagerOpen}
                onClose={() => setVersionManagerOpen(false)}
                onInstalled={async (installedVersion) => {
                    const installed = await refreshInstalledVersions();
                    if (installed.includes(installedVersion)) {
                        setVersion(installedVersion);
                    }
                    await reloadCatalog();
                    await refreshMods();
                    setVersionManagerOpen(false);
                }}
            />

            <ModpackImportDialog
                open={pendingModpackImport !== null}
                inspect={pendingModpackImport?.inspect ?? null}
                currentVersion={version}
                modpackLabel={pendingModpackImport?.label ?? 'Модпак'}
                busy={importFlowBusy || profileImporting}
                installing={installingVersion !== null || installingMinecraft}
                preparingForge={preparingForge}
                forgeProgress={forgePrepareProgress}
                forgeMessage={forgePrepareMessage}
                error={importFlowError}
                success={importFlowSuccess}
                onCancel={() => {
                    if (importFlowBusy) {
                        return;
                    }
                    setPendingModpackImport(null);
                    setImportFlowError(null);
                    setImportFlowSuccess(null);
                }}
                onConfirm={() => {
                    if (importFlowSuccess) {
                        setPendingModpackImport(null);
                        setImportFlowSuccess(null);
                        setImportFlowError(null);
                        return;
                    }
                    if (!pendingModpackImport || importFlowBusy) {
                        return;
                    }
                    const { inspect, ...source } = pendingModpackImport;
                    void runModpackImport(inspect, source).catch(() => {
                        // ошибка в importFlowError
                    });
                }}
            />
        </div>
    );
}
