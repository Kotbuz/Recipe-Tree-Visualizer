package com.rtv.recipeexporter.neo;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.JsonOps;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.item.crafting.Recipe;
import net.minecraft.world.item.crafting.RecipeHolder;
import net.minecraft.world.item.crafting.RecipeSerializer;
import net.neoforged.neoforge.event.server.ServerStartedEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

public final class RecipeExportHandler {
    private static final Logger LOGGER = LoggerFactory.getLogger(RecipeExportHandler.class);
    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();

    private RecipeExportHandler() {}

    public static void onServerStarted(ServerStartedEvent event) {
        if (!Boolean.getBoolean("rtv.recipe.export")) {
            return;
        }

        String exportDir = System.getProperty("rtv.recipe.export.dir");
        if (exportDir == null || exportDir.isBlank()) {
            LOGGER.error("rtv.recipe.export.dir is not set");
            halt(event.getServer());
            return;
        }

        MinecraftServer server = event.getServer();
        try {
            dumpRecipes(server, Path.of(exportDir));
            LOGGER.info("Recipe export completed");
        } catch (Exception exception) {
            LOGGER.error("Recipe export failed", exception);
        } finally {
            halt(server);
        }
    }

    private static void dumpRecipes(MinecraftServer server, Path outputDir) throws Exception {
        Files.createDirectories(outputDir);

        JsonObject recipes = new JsonObject();
        List<String> skipped = new ArrayList<>();
        var ops = server.registryAccess().createSerializationContext(JsonOps.INSTANCE);

        for (RecipeHolder<?> holder : server.getRecipeManager().getRecipes()) {
            ResourceLocation id = holder.id();
            Recipe<?> recipe = holder.value();
            RecipeSerializer<?> serializer = recipe.getSerializer();
            ResourceLocation typeId = BuiltInRegistries.RECIPE_SERIALIZER.getKey(serializer);

            var encoded = Recipe.CODEC.encodeStart(ops, recipe);
            if (encoded.isError()) {
                String err = encoded.error().map(e -> e.message()).orElse("encode error");
                skipped.add(id + ": " + err);
                continue;
            }

            JsonElement recipeJson = encoded.getOrThrow();
            if (!recipeJson.isJsonObject()) {
                skipped.add(id + ": unexpected json shape");
                continue;
            }

            JsonObject payload = recipeJson.getAsJsonObject();
            if (typeId != null) {
                payload.addProperty("type", typeId.toString());
            }
            recipes.add(id.toString(), payload);
        }

        JsonObject root = new JsonObject();
        root.addProperty("format_version", 1);
        root.addProperty("minecraft_version", System.getProperty("rtv.recipe.export.minecraft", "1.21.1"));
        root.addProperty("loader_version", System.getProperty("rtv.recipe.export.loader", ""));
        root.addProperty("exported_at", Instant.now().toString());
        root.addProperty("recipe_count", recipes.size());
        root.add("recipes", recipes);

        JsonArray skippedArray = new JsonArray();
        for (String entry : skipped) {
            skippedArray.add(entry);
        }
        root.add("skipped", skippedArray);

        Path outputFile = outputDir.resolve("recipes.baked.json");
        Files.writeString(outputFile, GSON.toJson(root), StandardCharsets.UTF_8);
        LOGGER.info("Wrote {} recipes to {}", recipes.size(), outputFile);
    }

    private static void halt(MinecraftServer server) {
        server.execute(() -> server.halt(false));
    }
}
