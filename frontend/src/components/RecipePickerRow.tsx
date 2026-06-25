import type { RecipeSummary } from '../types/recipe';
import RecipeItemStrip from './RecipeItemStrip';
import '../styles/RecipePickerRow.css';

const mapMachineName = (recipe: RecipeSummary) =>
    recipe.machine_name ||
    recipe.machine_type
        .replace(/.*:/, '')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());

type RecipePickerRowProps = {
    recipe: RecipeSummary;
    onClick: () => void;
};

export default function RecipePickerRow({ recipe, onClick }: RecipePickerRowProps) {
    const primaryOutput = recipe.outputs[0]?.name ?? 'Без результата';

    return (
        <button type="button" className="recipe-picker-row" onClick={onClick}>
            <RecipeItemStrip items={recipe.inputs} />
            <div className="recipe-picker-row-center">
                <div className="recipe-picker-row-title">{primaryOutput}</div>
                <div className="recipe-picker-row-machine">{mapMachineName(recipe)}</div>
            </div>
            <RecipeItemStrip items={recipe.outputs} />
        </button>
    );
}
