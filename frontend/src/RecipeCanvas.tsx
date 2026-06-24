import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
    RecipeSummary,
    RecipeListResponse,
    RecipeItem,
    SlotType,
    NodeSlot,
    RecipeConnection,
    NodeKind,
} from './types/recipe';
import './styles/RecipeCanvas.css';

interface RecipeNode {
    id: string;
    kind: NodeKind;
    recipeId?: string;
    x: number;
    y: number;
    machineName: string;
    inputs: RecipeItem[];
    outputs: RecipeItem[];
}

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
    startX: number;
    startY: number;
    currentX: number;
    currentY: number;
}

type RecipeContextMenu = {
    type: 'recipe';
    contentX: number;
    contentY: number;
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
    sourceNodeId: string;
    sourceSlotType: SlotType;
    sourceItemIndex: number;
    contentX: number;
    contentY: number;
    screenX: number;
    screenY: number;
};

type ContextMenu = RecipeContextMenu | NodeContextMenu | ItemRecipeContextMenu;

type TerminalKind = 'chest' | 'outpost';

const MIN_ITEM_DRAG_DISTANCE = 8;
const SLOT_HIT_RADIUS = 28;

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

const slotKey = (nodeId: string, slotType: SlotType, index: number) =>
    `${nodeId}:${slotType}:${index}`;

const connectionId = (from: NodeSlot, to: NodeSlot) =>
    `${from.nodeId}:${from.slotType}:${from.itemIndex}->${to.nodeId}:${to.slotType}:${to.itemIndex}`;

const tangentLength = (x1: number, x2: number) => Math.max(Math.abs(x2 - x1) * 0.45, 48);

const buildBezierPath = (
    from: { x: number; y: number; side: 'left' | 'right' },
    to: { x: number; y: number; side: 'left' | 'right' },
) => {
    const t = tangentLength(from.x, to.x);
    const cp1x = from.side === 'left' ? from.x - t : from.x + t;
    const cp2x = to.side === 'left' ? to.x - t : to.x + t;
    return `M ${from.x} ${from.y} C ${cp1x} ${from.y}, ${cp2x} ${to.y}, ${to.x} ${to.y}`;
};

const slotSide = (slotType: SlotType): 'left' | 'right' =>
    slotType === 'input' ? 'left' : 'right';

const filterRecipesForItemDrag = (
    recipes: RecipeSummary[],
    itemName: string,
    sourceSlotType: SlotType,
) => {
    if (sourceSlotType === 'input') {
        return recipes.filter((recipe) =>
            recipe.outputs.some((output) => output.name === itemName),
        );
    }
    return recipes.filter((recipe) =>
        recipe.inputs.some((input) => input.name === itemName),
    );
};

const findMatchingSlotIndex = (
    node: RecipeNode,
    slotType: SlotType,
    itemName: string,
) => {
    const items = slotType === 'input' ? node.inputs : node.outputs;
    return items.findIndex((item) => item.name === itemName);
};

const formatRecipeResultLabel = (recipe: RecipeSummary) =>
    recipe.outputs.map((output) => output.name).join(' + ') || 'Без результата';

const filterRecipesByResultName = (recipes: RecipeSummary[], query: string) => {
    const needle = query.trim().toLowerCase();
    if (!needle) return recipes;

    return recipes.filter((recipe) =>
        recipe.outputs.some((output) => output.name.toLowerCase().includes(needle)),
    );
};

const isSlotCompatible = (
    node: RecipeNode,
    slotType: SlotType,
    index: number,
    itemName: string,
) => {
    const slotName = getSlotItemName(node, slotType, index);
    if (!slotName) {
        return isTerminalNode(node);
    }

    return slotName === itemName;
};

export default function RecipeCanvas() {
    const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
    const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
    const [selectedRecipe, setSelectedRecipe] = useState<RecipeSummary | null>(null);
    const [nodes, setNodes] = useState<RecipeNode[]>([]);
    const [connections, setConnections] = useState<RecipeConnection[]>([]);
    const [nodeDragState, setNodeDragState] = useState<NodeDragState | null>(null);
    const [itemDragState, setItemDragState] = useState<ItemDragState | null>(null);
    const [scale, setScale] = useState(1);
    const [offsetX, setOffsetX] = useState(0);
    const [offsetY, setOffsetY] = useState(0);
    const [isPanning, setIsPanning] = useState(false);
    const [panStart, setPanStart] = useState<{ x: number; y: number } | null>(null);
    const [recipeSearchQuery, setRecipeSearchQuery] = useState('');
    const [, setLayoutTick] = useState(0);

    const canvasRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map());
    const itemDragRef = useRef<ItemDragState | null>(null);
    const recipeSearchRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        fetch('/recipes?version=26.2')
            .then((response) => response.json())
            .then((data: RecipeListResponse) => {
                setRecipes(data.recipes);
            })
            .catch(() => {
                setRecipes([]);
            });
    }, []);

    const recipeItems = useMemo(
        () =>
            recipes.map((recipe) => ({
                ...recipe,
                machineName: mapMachineName(recipe.machine_type),
            })),
        [recipes],
    );

    const screenToContent = useCallback(
        (clientX: number, clientY: number) => {
            if (!canvasRef.current) return null;
            const rect = canvasRef.current.getBoundingClientRect();
            return {
                x: (clientX - rect.left - offsetX) / scale,
                y: (clientY - rect.top - offsetY) / scale,
            };
        },
        [offsetX, offsetY, scale],
    );

    const getContentCoordinates = useCallback(
        (event: { clientX: number; clientY: number }) =>
            screenToContent(event.clientX, event.clientY),
        [screenToContent],
    );

    const getSlotAnchor = useCallback(
        (nodeId: string, slotType: SlotType, index: number) => {
            const key = slotKey(nodeId, slotType, index);
            const element = itemRefs.current.get(key);
            if (!element) return null;

            const rect = element.getBoundingClientRect();
            const anchorX = slotType === 'input' ? rect.left : rect.right;
            const anchorY = rect.top + rect.height / 2;
            return screenToContent(anchorX, anchorY);
        },
        [screenToContent],
    );

    const bumpLayout = useCallback(() => {
        setLayoutTick((value) => value + 1);
    }, []);

    useEffect(() => {
        bumpLayout();
    }, [nodes, connections, scale, offsetX, offsetY, bumpLayout]);

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
            itemName: string,
            sourceSlotType: SlotType,
            sourceNodeId: string,
        ): NodeSlot | null => {
            const targetSlotType: SlotType = sourceSlotType === 'input' ? 'output' : 'input';

            for (const node of nodes) {
                if (node.id === sourceNodeId) continue;

                const items = targetSlotType === 'input' ? node.inputs : node.outputs;
                for (let index = 0; index < items.length; index += 1) {
                    if (!isSlotCompatible(node, targetSlotType, index, itemName)) {
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
                            itemName,
                        };
                    }
                }
            }

            return null;
        },
        [nodes, getSlotAnchor],
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

            if (sourceSlotType === 'input') {
                addConnection(target, source);
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

        const contentCoords = getContentCoordinates(event);
        if (!contentCoords) return;

        setContextMenu({
            type: 'recipe',
            contentX: contentCoords.x,
            contentY: contentCoords.y,
            screenX: event.clientX,
            screenY: event.clientY,
        });
    };

    const createNodeFromRecipe = (recipe: RecipeSummary, x: number, y: number) => {
        const node: RecipeNode = {
            id: `${recipe.recipe_id}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            kind: 'recipe',
            recipeId: recipe.recipe_id,
            x,
            y,
            machineName: mapMachineName(recipe.machine_type),
            inputs: recipe.inputs,
            outputs: recipe.outputs,
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
        createNodeFromRecipe(recipe, contextMenu.contentX, contextMenu.contentY);
        closeMenu();
    };

    const handleItemRecipeClick = (recipe: RecipeSummary) => {
        if (!contextMenu || contextMenu.type !== 'item-recipe') return;

        const newNode = createNodeFromRecipe(
            recipe,
            contextMenu.contentX,
            contextMenu.contentY,
        );

        const targetSlotType: SlotType =
            contextMenu.sourceSlotType === 'input' ? 'output' : 'input';
        const targetIndex = findMatchingSlotIndex(newNode, targetSlotType, contextMenu.itemName);

        if (targetIndex >= 0) {
            connectSlots(
                contextMenu.sourceNodeId,
                contextMenu.sourceSlotType,
                contextMenu.sourceItemIndex,
                contextMenu.itemName,
                {
                    nodeId: newNode.id,
                    slotType: targetSlotType,
                    itemIndex: targetIndex,
                    itemName: contextMenu.itemName,
                },
            );
        }

        closeMenu();
    };

    const handleTerminalNodeClick = (terminalKind: TerminalKind) => {
        if (!contextMenu || (contextMenu.type !== 'recipe' && contextMenu.type !== 'item-recipe')) {
            return;
        }

        if (contextMenu.type === 'recipe') {
            createTerminalNode(terminalKind, contextMenu.contentX, contextMenu.contentY);
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
            contextMenu.contentX,
            contextMenu.contentY,
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

        event.preventDefault();
        event.stopPropagation();

        const anchor = getSlotAnchor(nodeId, slotType, itemIndex);
        if (!anchor) return;

        const drag: ItemDragState = {
            sourceNodeId: nodeId,
            sourceSlotType: slotType,
            sourceItemIndex: itemIndex,
            itemName,
            startX: anchor.x,
            startY: anchor.y,
            currentX: anchor.x,
            currentY: anchor.y,
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
                drag.currentX - drag.startX,
                drag.currentY - drag.startY,
            );
            if (distance < MIN_ITEM_DRAG_DISTANCE) {
                return;
            }

            const dropPoint = screenToContent(clientX, clientY);
            if (!dropPoint) return;

            const compatibleSlot = findCompatibleSlotAt(
                dropPoint,
                drag.itemName,
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
                sourceNodeId: drag.sourceNodeId,
                sourceSlotType: drag.sourceSlotType,
                sourceItemIndex: drag.sourceItemIndex,
                contentX: dropPoint.x,
                contentY: dropPoint.y,
                screenX: clientX,
                screenY: clientY,
            });
            setRecipeSearchQuery('');
        },
        [screenToContent, findCompatibleSlotAt, connectSlots],
    );

    useEffect(() => {
        if (!nodeDragState) return;

        const handleMouseMove = (event: MouseEvent) => {
            const contentCoords = screenToContent(event.clientX, event.clientY);
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
    }, [nodeDragState, screenToContent]);

    useEffect(() => {
        const handleMouseMove = (event: MouseEvent) => {
            const drag = itemDragRef.current;
            if (!drag) return;

            const contentCoords = screenToContent(event.clientX, event.clientY);
            if (!contentCoords) return;

            const nextDrag = {
                ...drag,
                currentX: contentCoords.x,
                currentY: contentCoords.y,
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
    }, [screenToContent, finishItemDrag]);

    const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
        event.preventDefault();
        const delta = event.deltaY > 0 ? 0.9 : 1.1;
        const newScale = Math.max(0.5, Math.min(3, scale * delta));
        setScale(newScale);
    };

    const handleCanvasMouseDownForPan = (event: React.MouseEvent<HTMLDivElement>) => {
        if (event.button !== 0) return;
        if (nodeDragState || itemDragState) return;
        setIsPanning(true);
        setPanStart({ x: event.clientX - offsetX, y: event.clientY - offsetY });
    };

    const handleCanvasMouseMoveForPan = (event: React.MouseEvent<HTMLDivElement>) => {
        if (!isPanning || !panStart) return;
        setOffsetX(event.clientX - panStart.x);
        setOffsetY(event.clientY - panStart.y);
    };

    const handleCanvasMouseUpForPan = () => {
        setIsPanning(false);
        setPanStart(null);
    };

    const renderConnectionPath = (from: NodeSlot, to: NodeSlot) => {
        const fromAnchor = getSlotAnchor(from.nodeId, from.slotType, from.itemIndex);
        const toAnchor = getSlotAnchor(to.nodeId, to.slotType, to.itemIndex);
        if (!fromAnchor || !toAnchor) return null;

        return buildBezierPath(
            { ...fromAnchor, side: slotSide(from.slotType) },
            { ...toAnchor, side: slotSide(to.slotType) },
        );
    };

    const itemRecipeOptions =
        contextMenu?.type === 'item-recipe'
            ? filterRecipesForItemDrag(
                  recipeItems,
                  contextMenu.itemName,
                  contextMenu.sourceSlotType,
              )
            : [];

    const baseRecipePickerOptions =
        contextMenu?.type === 'recipe'
            ? recipeItems
            : contextMenu?.type === 'item-recipe'
              ? itemRecipeOptions
              : [];

    const filteredRecipePickerOptions = useMemo(
        () => filterRecipesByResultName(baseRecipePickerOptions, recipeSearchQuery),
        [baseRecipePickerOptions, recipeSearchQuery],
    );

    const itemRecipeHeader =
        contextMenu?.type === 'item-recipe'
            ? contextMenu.sourceSlotType === 'input'
                ? `Рецепты с результатом «${contextMenu.itemName}»`
                : `Рецепты с ингредиентом «${contextMenu.itemName}»`
            : '';

    const recipePickerEmptyMessage =
        baseRecipePickerOptions.length === 0
            ? contextMenu?.type === 'item-recipe'
                ? 'Нет подходящих рецептов'
                : 'Не найдены рецепты'
            : 'Ничего не найдено';

    useEffect(() => {
        if (contextMenu?.type === 'recipe' || contextMenu?.type === 'item-recipe') {
            recipeSearchRef.current?.focus();
        }
    }, [contextMenu]);

    const renderItemSlot = (
        node: RecipeNode,
        slotType: SlotType,
        item: RecipeItem,
        index: number,
    ) => {
        const displayName = getSlotItemName(node, slotType, index);
        const isEmpty = !displayName;
        const placeholder = slotType === 'input' ? 'Вход' : 'Выход';

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
            >
                <span className="recipe-node-item-name">{isEmpty ? placeholder : displayName}</span>
                {!isEmpty && (
                    <span className="recipe-node-item-amount">×{item.amount}</span>
                )}
            </div>
        );
    };

    const dragPreviewPath =
        itemDragState &&
        buildBezierPath(
            {
                x: itemDragState.startX,
                y: itemDragState.startY,
                side: slotSide(itemDragState.sourceSlotType),
            },
            {
                x: itemDragState.currentX,
                y: itemDragState.currentY,
                side: itemDragState.currentX >= itemDragState.startX ? 'left' : 'right',
            },
        );

    return (
        <div className="recipe-canvas-page">
            <div className="recipe-canvas-toolbar">
                <div>
                    ПКМ по холсту — добавить ноду • Тяните за блок крафта — перемещение • Тяните
                    за ингредиент/результат — связь • Колесо — зум • ЛКМ+движение — панорама
                </div>
            </div>
            <div
                className="recipe-canvas"
                ref={canvasRef}
                onContextMenu={openMenu}
                onWheel={handleWheel}
                onMouseDown={handleCanvasMouseDownForPan}
                onMouseMove={handleCanvasMouseMoveForPan}
                onMouseUp={handleCanvasMouseUpForPan}
                onMouseLeave={handleCanvasMouseUpForPan}
                style={{ cursor: isPanning ? 'grabbing' : 'default' }}
            >
                <div
                    ref={containerRef}
                    className="recipe-canvas-content"
                    style={{
                        transform: `translate(${offsetX}px, ${offsetY}px) scale(${scale})`,
                        transformOrigin: '0 0',
                        transition: isPanning || nodeDragState ? 'none' : 'transform 0.1s ease-out',
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
                        {dragPreviewPath && (
                            <path
                                className="recipe-connection-line recipe-connection-line--preview"
                                d={dragPreviewPath}
                            />
                        )}
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

                {(contextMenu?.type === 'recipe' || contextMenu?.type === 'item-recipe') && (
                    <div className="recipe-context-modal" onClick={closeMenu}>
                        <div
                            className="recipe-context-panel"
                            style={{
                                position: 'fixed',
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
                                        {filteredRecipePickerOptions.length > 0 ? (
                                            filteredRecipePickerOptions.map((recipe) => (
                                                <button
                                                    key={recipe.recipe_id}
                                                    type="button"
                                                    className="recipe-context-item"
                                                    onClick={() =>
                                                        contextMenu.type === 'recipe'
                                                            ? handleRecipeClick(recipe)
                                                            : handleItemRecipeClick(recipe)
                                                    }
                                                >
                                                    <span className="recipe-context-item-title">
                                                        {formatRecipeResultLabel(recipe)}
                                                    </span>
                                                    <span className="recipe-context-item-meta">
                                                        {mapMachineName(recipe.machine_type)}
                                                    </span>
                                                </button>
                                            ))
                                        ) : (
                                            <div className="recipe-context-empty">
                                                {recipePickerEmptyMessage}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {contextMenu?.type === 'node' && (
                    <div
                        className="recipe-context-modal recipe-context-modal--transparent"
                        onClick={closeMenu}
                    >
                        <div
                            className="recipe-node-context-panel"
                            style={{
                                position: 'fixed',
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
                    </div>
                )}
            </div>
        </div>
    );
}
