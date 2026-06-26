import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
    type ReactNode,
} from 'react';
import { DEFAULT_MINECRAFT_VERSION, resolveItemIconFileName } from '../utils/itemIcon';
import type { IngredientIndex } from '../utils/ingredientMatch';

type VersionListResponse = {
    versions: string[];
};

type ItemIconManifestResponse = {
    version: string;
    icons: string[];
    revision?: string;
};

type IngredientIndexResponse = {
    version: string;
    tags: Record<string, string[]>;
    aliases: Record<string, string>;
};

type MinecraftVersionContextValue = {
    version: string;
    versions: string[];
    profileId: string;
    setVersion: (version: string) => void;
    setProfileId: (profileId: string) => void;
    refreshInstalledVersions: () => Promise<string[]>;
    hasIcon: (itemName: string, iconId?: string) => boolean;
    itemIconUrl: (itemName: string, iconId?: string) => string | null;
    iconsReady: boolean;
    iconsRevision: string;
    ingredientIndex: IngredientIndex | null;
    reloadCatalog: () => Promise<void>;
};

const MinecraftVersionContext = createContext<MinecraftVersionContextValue | null>(null);

const profileQuery = (profileId: string | undefined) => {
    if (!profileId || profileId === 'default') {
        return '';
    }
    return `?profile_id=${encodeURIComponent(profileId)}`;
};

export function MinecraftVersionProvider({ children }: { children: ReactNode }) {
    const [version, setVersionState] = useState(DEFAULT_MINECRAFT_VERSION);
    const [profileId, setProfileIdState] = useState('default');
    const [versions, setVersions] = useState<string[]>([DEFAULT_MINECRAFT_VERSION]);
    const [iconNames, setIconNames] = useState<ReadonlySet<string>>(new Set());
    const [iconsRevision, setIconsRevision] = useState('0');
    const [iconsReady, setIconsReady] = useState(false);
    const [ingredientIndex, setIngredientIndex] = useState<IngredientIndex | null>(null);

    const refreshInstalledVersions = useCallback(async () => {
        try {
            const response = await fetch('/versions');
            if (!response.ok) {
                return [];
            }
            const data = (await response.json()) as VersionListResponse;
            const installed = data.versions ?? [];
            setVersions(installed);
            if (installed.length > 0) {
                setVersionState((current) =>
                    installed.includes(current) ? current : installed[0],
                );
            }
            return installed;
        } catch {
            return [];
        }
    }, []);

    useEffect(() => {
        void refreshInstalledVersions();
    }, [refreshInstalledVersions]);

    const loadIcons = useCallback(async (targetVersion: string, targetProfileId: string) => {
        setIconsReady(false);
        const profileSuffix = profileQuery(targetProfileId);
        try {
            void fetch(
                `/versions/${encodeURIComponent(targetVersion)}/render-icons${profileSuffix}`,
                { method: 'POST' },
            );

            const response = await fetch(
                `/versions/${encodeURIComponent(targetVersion)}/item-icons${profileSuffix}`,
            );
            if (!response.ok) {
                setIconNames(new Set());
                return;
            }

            const data = (await response.json()) as ItemIconManifestResponse;
            setIconNames(new Set(data.icons.map((fileName) => fileName.toLowerCase())));
            setIconsRevision(data.revision ?? '0');
        } catch {
            setIconNames(new Set());
        } finally {
            setIconsReady(true);
        }
    }, []);

    useEffect(() => {
        loadIcons(version, profileId);
    }, [version, profileId, loadIcons]);

    const loadIngredientIndex = useCallback(async (targetVersion: string) => {
        const maxAttempts = 5;

        for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
            try {
                const response = await fetch(
                    `/versions/${encodeURIComponent(targetVersion)}/ingredient-index`,
                );
                if (response.ok) {
                    const data = (await response.json()) as IngredientIndexResponse;
                    if (data.tags && Object.keys(data.tags).length > 0) {
                        setIngredientIndex({
                            tags: data.tags,
                            aliases: data.aliases ?? {},
                        });
                        return;
                    }
                }
            } catch {
                // retry
            }

            if (attempt < maxAttempts - 1) {
                await new Promise((resolve) => {
                    window.setTimeout(resolve, 1000 * (attempt + 1));
                });
            }
        }

        setIngredientIndex(null);
    }, []);

    useEffect(() => {
        void loadIngredientIndex(version);
    }, [version, loadIngredientIndex]);

    const pollAttemptsRef = useRef(0);
    const lastIconCountRef = useRef(0);
    const stablePollsRef = useRef(0);

    useEffect(() => {
        pollAttemptsRef.current = 0;
        lastIconCountRef.current = 0;
        stablePollsRef.current = 0;
    }, [version, profileId]);

    useEffect(() => {
        if (!iconsReady) {
            return;
        }

        if (pollAttemptsRef.current >= 48) {
            return;
        }

        const iconCount = iconNames.size;
        if (iconCount > lastIconCountRef.current) {
            lastIconCountRef.current = iconCount;
            stablePollsRef.current = 0;
        } else if (iconCount > 0) {
            stablePollsRef.current += 1;
        }

        if (iconCount > 0 && stablePollsRef.current >= 3) {
            return;
        }

        const timeoutId = window.setTimeout(() => {
            pollAttemptsRef.current += 1;
            void loadIcons(version, profileId);
        }, 5000);

        return () => {
            window.clearTimeout(timeoutId);
        };
    }, [iconsReady, iconNames.size, iconsRevision, version, profileId, loadIcons]);

    const setVersion = useCallback((nextVersion: string) => {
        setVersionState(nextVersion);
    }, []);

    const setProfileId = useCallback((nextProfileId: string) => {
        setProfileIdState(nextProfileId || 'default');
    }, []);

    const hasIcon = useCallback(
        (itemName: string, iconId?: string) =>
            iconNames.has(resolveItemIconFileName(itemName, iconId)),
        [iconNames],
    );

    const itemIconUrl = useCallback(
        (itemName: string, iconId?: string) => {
            const fileName = resolveItemIconFileName(itemName, iconId);
            const profileSuffix = profileQuery(profileId);
            const base = `/versions/${encodeURIComponent(version)}/items/${fileName}${profileSuffix}`;
            return profileSuffix
                ? `${base}&v=${encodeURIComponent(iconsRevision)}`
                : `${base}?v=${encodeURIComponent(iconsRevision)}`;
        },
        [iconsRevision, version, profileId],
    );

    const reloadCatalog = useCallback(async () => {
        await Promise.all([loadIcons(version, profileId), loadIngredientIndex(version)]);
    }, [loadIcons, loadIngredientIndex, version, profileId]);

    const value = useMemo(
        () => ({
            version,
            versions,
            profileId,
            setVersion,
            setProfileId,
            refreshInstalledVersions,
            hasIcon,
            itemIconUrl,
            iconsReady,
            iconsRevision,
            ingredientIndex,
            reloadCatalog,
        }),
        [version, versions, profileId, setVersion, setProfileId, refreshInstalledVersions, hasIcon, itemIconUrl, iconsReady, iconsRevision, ingredientIndex, reloadCatalog],
    );

    return (
        <MinecraftVersionContext.Provider value={value}>
            {children}
        </MinecraftVersionContext.Provider>
    );
}

export function useMinecraftVersion() {
    const context = useContext(MinecraftVersionContext);
    if (!context) {
        throw new Error('useMinecraftVersion must be used within MinecraftVersionProvider');
    }
    return context;
}
