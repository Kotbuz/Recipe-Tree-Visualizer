import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
    type ReactNode,
} from 'react';
import { DEFAULT_MINECRAFT_VERSION, itemIconFileName } from '../utils/itemIcon';

type VersionListResponse = {
    versions: string[];
};

type ItemIconManifestResponse = {
    version: string;
    icons: string[];
};

type MinecraftVersionContextValue = {
    version: string;
    versions: string[];
    setVersion: (version: string) => void;
    hasIcon: (itemName: string) => boolean;
    itemIconUrl: (itemName: string) => string | null;
    iconsReady: boolean;
};

const MinecraftVersionContext = createContext<MinecraftVersionContextValue | null>(null);

export function MinecraftVersionProvider({ children }: { children: ReactNode }) {
    const [version, setVersionState] = useState(DEFAULT_MINECRAFT_VERSION);
    const [versions, setVersions] = useState<string[]>([DEFAULT_MINECRAFT_VERSION]);
    const [iconNames, setIconNames] = useState<ReadonlySet<string>>(new Set());
    const [iconsReady, setIconsReady] = useState(false);

    useEffect(() => {
        fetch('/versions')
            .then((response) => response.json())
            .then((data: VersionListResponse) => {
                if (data.versions?.length) {
                    setVersions(data.versions);
                }
            })
            .catch(() => {
                // оставляем версию по умолчанию
            });
    }, []);

    const loadIcons = useCallback(async (targetVersion: string) => {
        setIconsReady(false);
        try {
            const response = await fetch(
                `/versions/${encodeURIComponent(targetVersion)}/item-icons`,
            );
            if (!response.ok) {
                setIconNames(new Set());
                return;
            }

            const data = (await response.json()) as ItemIconManifestResponse;
            setIconNames(new Set(data.icons.map((fileName) => fileName.toLowerCase())));
        } catch {
            setIconNames(new Set());
        } finally {
            setIconsReady(true);
        }
    }, []);

    useEffect(() => {
        loadIcons(version);
    }, [version, loadIcons]);

    const setVersion = useCallback((nextVersion: string) => {
        setVersionState(nextVersion);
    }, []);

    const hasIcon = useCallback(
        (itemName: string) => iconNames.has(itemIconFileName(itemName)),
        [iconNames],
    );

    const itemIconUrl = useCallback(
        (itemName: string) => {
            const fileName = itemIconFileName(itemName);
            if (!iconNames.has(fileName)) {
                return null;
            }
            return `/versions/${encodeURIComponent(version)}/items/${fileName}`;
        },
        [iconNames, version],
    );

    const value = useMemo(
        () => ({
            version,
            versions,
            setVersion,
            hasIcon,
            itemIconUrl,
            iconsReady,
        }),
        [version, versions, setVersion, hasIcon, itemIconUrl, iconsReady],
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
