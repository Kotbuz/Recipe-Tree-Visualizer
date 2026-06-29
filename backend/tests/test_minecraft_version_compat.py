from app.parser.minecraft_version import mod_supports_game_version


def test_mod_supports_game_version_ignores_mcmod_placeholders() -> None:
    assert mod_supports_game_version(
        minecraft_version="${mcversion}",
        minecraft_version_range=None,
        jar_path="SomeMod.jar",
        game_version="1.7.10",
    )


def test_mod_supports_game_version_still_checks_real_versions() -> None:
    assert mod_supports_game_version(
        minecraft_version="1.7.10",
        minecraft_version_range=None,
        jar_path="SomeMod-1.7.10-1.0.jar",
        game_version="1.7.10",
    )
    assert not mod_supports_game_version(
        minecraft_version="1.20.1",
        minecraft_version_range=None,
        jar_path="SomeMod-1.20.1-1.0.jar",
        game_version="1.7.10",
    )
