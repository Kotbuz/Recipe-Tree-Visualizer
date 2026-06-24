from dataclasses import dataclass, field

from app.parser.loaders import ModLoader


@dataclass(frozen=True)
class RawModMeta:
    mod_id: str
    name: str
    loader: ModLoader


@dataclass(frozen=True)
class RawRecipeFile:
    recipe_id: str
    namespace: str
    filename: str
    data: dict[str, object]


@dataclass
class RawModData:
    meta: RawModMeta
    jar_path: str
    recipe_files: list[RawRecipeFile] = field(default_factory=list)
    texture_paths: list[str] = field(default_factory=list)
