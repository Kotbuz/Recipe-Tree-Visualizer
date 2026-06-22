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
    const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
    const [selectedRecipe, setSelectedRecipe] = useState<RecipeSummary | null>(null);
    const [nodes, setNodes] = useState<RecipeNode[]>([]);
    const [dragState, setDragState] = useState<DragState | null>(null);
    const canvasRef = useRef<HTMLDivElement>(null);

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

    const openMenu = (event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
        event.preventDefault();
        setSelectedRecipe(null);
        setContextMenu({ x: event.nativeEvent.offsetX, y: event.nativeEvent.offsetY });
    };

    const closeMenu = () => {
        setContextMenu(null);
    };

    const handleRecipeClick = (recipe: RecipeSummary) => {
        if (!contextMenu) return;
        const node: RecipeNode = {
            id: `${recipe.recipe_id}-${nodes.length}`,
            x: contextMenu.x,
            y: contextMenu.y,
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
        const node = nodes.find((n) => n.id === nodeId);
        if (!node) return;

        setDragState({
            nodeId,
            offsetX: event.clientX - node.x,
            offsetY: event.clientY - node.y,
        });
    };

    const handleCanvasMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
        if (!dragState) return;

        setNodes((current) =>
            current.map((node) =>
                node.id === dragState.nodeId
                    ? {
                        ...node,
                        x: event.clientX - dragState.offsetX,
                        y: event.clientY - dragState.offsetY,
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


    return (
        <div className="recipe-canvas-page">
            <div className="recipe-canvas-toolbar">
                <div>Правый клик по холсту для добавления ноды рецепта • Перетащите ноду для перемещения</div>
            </div>
            <div
                className="recipe-canvas"
                ref={canvasRef}
                onContextMenu={openMenu}
                onMouseMove={handleCanvasMouseMove}
                onMouseUp={handleCanvasMouseUp}
                onMouseLeave={handleCanvasMouseUp}
            >
                {nodes.map((node) => (
                    <div
                        key={node.id}
                        className="recipe-node"
                        style={{ left: node.x, top: node.y }}
                        onMouseDown={(e) => handleNodeMouseDown(node.id, e)}
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

                {contextMenu && (
                    <div className="recipe-context-modal" onClick={closeMenu}>
                        <div
                            className="recipe-context-panel"
                            style={{ left: contextMenu.x, top: contextMenu.y }}
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
            </div>
        </div>
    );
}
