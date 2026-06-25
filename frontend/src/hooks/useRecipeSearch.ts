import { useEffect, useState } from 'react';
import type { RecipeListResponse, RecipeSummary } from '../types/recipe';
import { RECIPE_SEARCH_DEBOUNCE_MS, RECIPE_SEARCH_LIMIT } from '../utils/itemIcon';

export type RecipeSearchParams = {
    enabled: boolean;
    query: string;
    producesItem?: string;
    usesItem?: string;
};

export function useRecipeSearch(version: string, params: RecipeSearchParams) {
    const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!params.enabled) {
            setRecipes([]);
            setLoading(false);
            return;
        }

        const trimmedQuery = params.query.trim();
        const producesItem = params.producesItem?.trim() ?? '';
        const usesItem = params.usesItem?.trim() ?? '';

        if (!trimmedQuery && !producesItem && !usesItem) {
            setRecipes([]);
            setLoading(false);
            return;
        }

        const controller = new AbortController();
        setLoading(true);

        const timeoutId = window.setTimeout(() => {
            const url = new URL('/recipes', window.location.origin);
            url.searchParams.set('version', version);
            url.searchParams.set('limit', String(RECIPE_SEARCH_LIMIT));
            if (trimmedQuery) {
                url.searchParams.set('q', trimmedQuery);
            }
            if (producesItem) {
                url.searchParams.set('produces_item', producesItem);
            }
            if (usesItem) {
                url.searchParams.set('uses_item', usesItem);
            }

            fetch(url.toString(), { signal: controller.signal })
                .then((response) => response.json())
                .then((data: RecipeListResponse) => {
                    setRecipes(data.recipes ?? []);
                })
                .catch((error: unknown) => {
                    if (error instanceof DOMException && error.name === 'AbortError') {
                        return;
                    }
                    setRecipes([]);
                })
                .finally(() => {
                    if (!controller.signal.aborted) {
                        setLoading(false);
                    }
                });
        }, RECIPE_SEARCH_DEBOUNCE_MS);

        return () => {
            window.clearTimeout(timeoutId);
            controller.abort();
        };
    }, [version, params.enabled, params.query, params.producesItem, params.usesItem]);

    return { recipes, loading };
}
