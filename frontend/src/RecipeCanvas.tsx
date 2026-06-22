import { useEffect, useMemo, useRef, useState } from 'react';
import type { RecipeSummary, RecipeListResponse } from './types/recipe';
import './styles/RecipeCanvas.css';

interface RecipeNode {
    id: string;
    x: number;
    y: number;
    machineName: string;
    inputs: string[];
    outputs: string[];
}

interface DragState {
    nodeId: string;
    offsetX: number;
    offsetY: number;
}

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

const mapMachineName = (typeName: string) =>
    machineNameMap[typeName] ??
    typeName
        .replace(/.*:/, '')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c: string) => c.toUpperCase());

export default function RecipeCanvas() {
    const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
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

    const [contextMenu, setContextMenu] = useState<RecipeContextMenu | NodeContextMenu | null>(null);
    const [selectedRecipe, setSelectedRecipe] = useState<RecipeSummary | null>(null);
    const [nodes, setNodes] = useState<RecipeNode[]>([]);
    const [dragState, setDragState] = useState<DragState | null>(null);
    const [scale, setScale] = useState(1);
    const [offsetX, setOffsetX] = useState(0);
    const [offsetY, setOffsetY] = useState(0);
    const [isPanning, setIsPanning] = useState(false);
    const [panStart, setPanStart] = useState<{ x: number; y: number } | null>(null);
    const canvasRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

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
        () => recipes.map((recipe) => ({
            ...recipe,
            machineName: mapMachineName(recipe.machine_type),
        })),
        [recipes],
    );

    const getContentCoordinates = (event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
        if (!canvasRef.current) return null;
        const rect = canvasRef.current.getBoundingClientRect();
        const canvasX = event.clientX - rect.left;
        const canvasY = event.clientY - rect.top;
        return {
            x: (canvasX - offsetX) / scale,
            y: (canvasY - offsetY) / scale,
        };
    };

    const openMenu = (event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
        event.preventDefault();
        setSelectedRecipe(null);

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

    const closeMenu = () => {
        setContextMenu(null);
    };

    const handleRecipeClick = (recipe: RecipeSummary) => {
        if (!contextMenu || contextMenu.type !== 'recipe') return;
        const node: RecipeNode = {
            id: `${recipe.recipe_id}-${nodes.length}`,
            x: contextMenu.contentX,
            y: contextMenu.contentY,
            machineName: mapMachineName(recipe.machine_type),
            inputs: recipe.inputs,
            outputs: recipe.outputs,
        };
        setNodes((current) => [...current, node]);
        setSelectedRecipe(recipe);
        closeMenu();
    };

    const handleNodeMouseDown = (nodeId: string, event: React.MouseEvent<HTMLDivElement>) => {
        event.preventDefault();
        event.stopPropagation();
        const node = nodes.find((n) => n.id === nodeId);
        if (!node) return;

        const contentCoords = getContentCoordinates(event);
        if (!contentCoords) return;

        setDragState({
            nodeId,
            offsetX: contentCoords.x - node.x,
            offsetY: contentCoords.y - node.y,
        });
    };

    const handleNodeContextMenu = (nodeId: string, event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
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

    const handleCanvasMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
        if (!dragState) return;

        const contentCoords = getContentCoordinates(event);
        if (!contentCoords) return;

        setNodes((current) =>
            current.map((node) =>
                node.id === dragState.nodeId
                    ? {
                        ...node,
                        x: contentCoords.x - dragState.offsetX,
                        y: contentCoords.y - dragState.offsetY,
                    }
                    : node,
            ),
        );
    };

    const handleCanvasMouseUp = () => {
        setDragState(null);
    };

    useEffect(() => {
        if (!dragState || !canvasRef.current) return;

        const canvas = canvasRef.current;
        canvas.addEventListener('mousemove', handleCanvasMouseMove as any);
        canvas.addEventListener('mouseup', handleCanvasMouseUp);

        return () => {
            canvas.removeEventListener('mousemove', handleCanvasMouseMove as any);
            canvas.removeEventListener('mouseup', handleCanvasMouseUp);
        };
    }, [dragState]);

    const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
        event.preventDefault();
        const delta = event.deltaY > 0 ? 0.9 : 1.1;
        const newScale = Math.max(0.5, Math.min(3, scale * delta));
        setScale(newScale);
    };

    const handleCanvasMouseDownForPan = (event: React.MouseEvent<HTMLDivElement>) => {
        if (event.button !== 0) return;
        if (dragState) return;
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

    return (
        <div className="recipe-canvas-page">
            <div className="recipe-canvas-toolbar">
                <div>Правый клик по холсту для добавления ноды • Перетащите ноду для перемещения • Колесо мыши для зума • ЛКМ+движение для панинга</div>
            </div>
            <div
                className="recipe-canvas"
                ref={canvasRef}
                onContextMenu={openMenu}
                onWheel={handleWheel}
                onMouseDown={handleCanvasMouseDownForPan}
                onMouseMove={(e) => {
                    handleCanvasMouseMove(e);
                    handleCanvasMouseMoveForPan(e);
                }}
                onMouseUp={() => {
                    handleCanvasMouseUp();
                    handleCanvasMouseUpForPan();
                }}
                onMouseLeave={() => {
                    handleCanvasMouseUp();
                    handleCanvasMouseUpForPan();
                }}
                style={{ cursor: isPanning ? 'grabbing' : 'default' }}
            >
                <div
                    ref={containerRef}
                    style={{
                        transform: `translate(${offsetX}px, ${offsetY}px) scale(${scale})`,
                        transformOrigin: '0 0',
                        transition: isPanning || dragState ? 'none' : 'transform 0.1s ease-out',
                    }}
                >
                    {nodes.map((node) => (
                        <div
                            key={node.id}
                            className={`recipe-node ${contextMenu?.type === 'node' && contextMenu.nodeId === node.id ? 'recipe-node--active' : ''}`}
                            style={{ left: node.x, top: node.y }}
                            onMouseDown={(e) => handleNodeMouseDown(node.id, e)}
                            onContextMenu={(e) => handleNodeContextMenu(node.id, e)}
                        >
                            <div className="recipe-node-column recipe-node-column--inputs">
                                {node.inputs.length > 0 ? (
                                    node.inputs.map((input, index) => (
                                        <div key={index} className="recipe-node-row">
                                            {input}
                                        </div>
                                    ))
                                ) : (
                                    <div className="recipe-node-empty">Нет входов</div>
                                )}
                            </div>
                            <div className="recipe-node-column recipe-node-column--machine">
                                <div className="recipe-node-machine">{node.machineName}</div>
                            </div>
                            <div className="recipe-node-column recipe-node-column--outputs">
                                {node.outputs.length > 0 ? (
                                    node.outputs.map((output, index) => (
                                        <div key={index} className="recipe-node-row">
                                            {output}
                                        </div>
                                    ))
                                ) : (
                                    <div className="recipe-node-empty">Нет результата</div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>

                {contextMenu?.type === 'recipe' && (
                    <div className="recipe-context-modal" onClick={closeMenu}>
                        <div
                            className="recipe-context-panel"
                            style={{ position: 'fixed', left: contextMenu.screenX, top: contextMenu.screenY }}
                            onClick={(event) => event.stopPropagation()}
                        >
                            <div className="recipe-context-header">Выберите рецепт</div>
                            <div className="recipe-context-list">
                                {recipeItems.length > 0 ? (
                                    recipeItems.map((recipe) => (
                                        <button
                                            key={recipe.recipe_id}
                                            className="recipe-context-item"
                                            onClick={() => handleRecipeClick(recipe)}
                                        >
                                            {recipe.outputs[0] ?? 'Без результата'}
                                        </button>
                                    ))
                                ) : (
                                    <div className="recipe-context-empty">Не найдены рецепты</div>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {contextMenu?.type === 'node' && (
                    <div className="recipe-context-modal recipe-context-modal--transparent" onClick={closeMenu}>
                        <div
                            className="recipe-node-context-panel"
                            style={{ position: 'fixed', left: contextMenu.screenX, top: contextMenu.screenY }}
                            onClick={(event) => event.stopPropagation()}
                        >
                            <button className="recipe-node-context-item" onClick={() => {
                                setNodes((current) => current.filter((node) => node.id !== contextMenu.nodeId));
                                closeMenu();
                            }}>
                                Удалить ноду
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
