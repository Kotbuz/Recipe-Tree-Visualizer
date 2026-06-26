package com.rtv.recipeexporter;

import cpw.mods.fml.common.Mod;
import cpw.mods.fml.common.event.FMLLoadCompleteEvent;

@Mod(
    modid = RecipeExporterMod.MOD_ID,
    name = "RTV Recipe Exporter",
    version = "1.0.0",
    acceptableRemoteVersions = "*")
public final class RecipeExporterMod {
  public static final String MOD_ID = "rtvrecipeexporter";

  @Mod.EventHandler
  public void onLoadComplete(FMLLoadCompleteEvent event) {
    RecipeDumper.onLoadComplete(event);
  }
}
