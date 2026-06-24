import type { RecipeSummary } from '../types/recipe';
import RecipePickerRow from './RecipePickerRow';
import VirtualList from './VirtualList';
import '../styles/RecipePickerList.css';

const RECIPE_ROW_HEIGHT = 56;

type RecipePickerListProps = {
    recipes: RecipeSummary[];
    loading: boolean;
    emptyQuery: boolean;
    emptyMessage: string;
    onRecipeClick: (recipe: RecipeSummary) => void;
};

export default function RecipePickerList({
    recipes,
    loading,
    emptyQuery,
    emptyMessage,
    onRecipeClick,
}: RecipePickerListProps) {
    if (emptyQuery) {
        return (
            <div className="recipe-picker-list recipe-picker-list--hint">
                Начните вводить название результата…
            </div>
        );
    }

    if (loading && recipes.length === 0) {
        return <div className="recipe-picker-list recipe-picker-list--hint">Поиск…</div>;
    }

    if (!loading && recipes.length === 0) {
        return <div className="recipe-picker-list recipe-picker-list--hint">{emptyMessage}</div>;
    }

    return (
        <VirtualList
            className="recipe-picker-list"
            items={recipes}
            itemHeight={RECIPE_ROW_HEIGHT}
            getItemKey={(recipe) => recipe.recipe_id}
            renderItem={(recipe) => (
                <RecipePickerRow recipe={recipe} onClick={() => onRecipeClick(recipe)} />
            )}
        />
    );
}
