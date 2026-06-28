package com.rtv.recipeexporter.neo;

import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;

@Mod(RecipeExporterNeoMod.MOD_ID)
public final class RecipeExporterNeoMod {
    public static final String MOD_ID = "rtvrecipeexporterneo";

    public RecipeExporterNeoMod(IEventBus modEventBus) {
        NeoForge.EVENT_BUS.addListener(RecipeExportHandler::onServerStarted);
    }
}
