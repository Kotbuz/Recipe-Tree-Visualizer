import { useEffect, useMemo, useState } from 'react';
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
        setContextMenu({ x: event.clientX, y: event.clientY });
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

    return (
        <div className="recipe-canvas-page">
            <div className="recipe-canvas-toolbar">
                <div>Правый клик по холсту для добавления ноды рецепта</div>
            </div>
            <div className="recipe-canvas" onContextMenu={openMenu}>
                {nodes.map((node) => (
                    <div key={node.id} className="recipe-node" style={{ left: node.x, top: node.y }}>
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
