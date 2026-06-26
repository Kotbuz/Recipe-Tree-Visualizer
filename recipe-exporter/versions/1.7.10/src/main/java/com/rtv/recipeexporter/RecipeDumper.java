package com.rtv.recipeexporter;

import cpw.mods.fml.common.FMLCommonHandler;
import cpw.mods.fml.common.event.FMLServerStartingEvent;
import cpw.mods.fml.relauncher.Side;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.List;
import java.util.Map;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import net.minecraft.item.crafting.CraftingManager;
import net.minecraft.item.crafting.FurnaceRecipes;
import net.minecraft.item.crafting.IRecipe;
import net.minecraft.item.crafting.ShapedRecipes;
import net.minecraft.item.crafting.ShapelessRecipes;
import net.minecraftforge.oredict.OreDictionary;
import net.minecraftforge.oredict.ShapedOreRecipe;
import net.minecraftforge.oredict.ShapelessOreRecipe;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
import cpw.mods.fml.common.registry.GameRegistry;
import java.lang.reflect.Field;

public final class RecipeDumper {
  private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().setPrettyPrinting().create();

  private RecipeDumper() {}

  public static void onServerStarting(FMLServerStartingEvent event) {
    if (!"true".equalsIgnoreCase(System.getProperty("rtv.recipe.export", "false"))) {
      return;
    }

    String outputPath = System.getProperty("rtv.recipe.export.dir");
    if (outputPath == null || outputPath.trim().isEmpty()) {
      System.err.println("[rtvrecipeexporter] rtv.recipe.export.dir is not set");
      return;
    }

    try {
      int count = dump(new File(outputPath));
      int ae2Copied = copyAe2RecipeFiles(new File(outputPath));
      System.out.println("[rtvrecipeexporter] Exported " + count + " recipes to " + outputPath);
      if (ae2Copied > 0) {
        System.out.println(
            "[rtvrecipeexporter] Copied " + ae2Copied + " AE2 recipe file(s) to " + outputPath);
      }

      String oreDictPath = System.getProperty("rtv.ore.dict.export.file");
      if (oreDictPath != null && !oreDictPath.trim().isEmpty()) {
        int oreCount = OreDictDumper.dump(new File(oreDictPath));
        System.out.println(
            "[rtvrecipeexporter] Exported " + oreCount + " ore dict entries to " + oreDictPath);
      }

      String itemCatalogPath = System.getProperty("rtv.item.catalog.export.file");
      if (itemCatalogPath != null && !itemCatalogPath.trim().isEmpty()) {
        int itemCount = ItemCatalogDumper.dump(new File(itemCatalogPath));
        System.out.println(
            "[rtvrecipeexporter] Exported " + itemCount + " item catalog entries to "
                + itemCatalogPath);
      }
    } catch (Exception exception) {
      exception.printStackTrace();
    } finally {
      FMLCommonHandler.instance().exitJava(0, true);
    }
  }

  public static int dump(File outputDir) throws IOException {
    if (!outputDir.exists() && !outputDir.mkdirs()) {
      throw new IOException("Failed to create output directory: " + outputDir.getAbsolutePath());
    }

    int index = 0;
    int exported = 0;

    @SuppressWarnings("unchecked")
    List<IRecipe> recipes = CraftingManager.getInstance().getRecipeList();
    for (IRecipe recipe : recipes) {
      JsonObject payload = serializeCraftingRecipe(recipe);
      if (payload == null) {
        continue;
      }
      String id = buildRecipeId(payload, "crafting", index++);
      if (writeRecipe(outputDir, id, payload)) {
        exported++;
      }
    }

    @SuppressWarnings("unchecked")
    Map<ItemStack, ItemStack> smelting = FurnaceRecipes.smelting().getSmeltingList();
    for (Map.Entry<ItemStack, ItemStack> entry : smelting.entrySet()) {
      JsonObject payload = serializeSmeltingRecipe(entry.getKey(), entry.getValue());
      if (payload == null) {
        continue;
      }
      String id = buildRecipeId(payload, "smelting", index++);
      if (writeRecipe(outputDir, id, payload)) {
        exported++;
      }
    }

    writeManifest(outputDir, exported);
    return exported;
  }

  private static boolean writeRecipe(File outputDir, String id, JsonObject payload) throws IOException {
    payload.addProperty("id", id);
    String fileName = id.replace(':', '_').replace("/", "__") + ".json";
    File target = new File(outputDir, fileName);
    try (Writer writer =
        new OutputStreamWriter(new FileOutputStream(target), StandardCharsets.UTF_8)) {
      GSON.toJson(payload, writer);
    }
    return true;
  }

  private static void writeManifest(File outputDir, int recipeCount) throws IOException {
    JsonObject manifest = new JsonObject();
    manifest.addProperty("minecraft_version", "1.7.10");
    manifest.addProperty("exporter", "rtv-recipe-exporter");
    manifest.addProperty("recipe_count", recipeCount);
    manifest.addProperty("status", "ok");
    File target = new File(outputDir, "_export_manifest.json");
    try (Writer writer =
        new OutputStreamWriter(new FileOutputStream(target), StandardCharsets.UTF_8)) {
      GSON.toJson(manifest, writer);
    }
  }

  private static String buildRecipeId(JsonObject payload, String category, int index) {
    JsonObject result = payload.getAsJsonObject("result");
    if (result != null && result.has("item")) {
      String itemId = result.get("item").getAsString();
      int colon = itemId.indexOf(':');
      String namespace = colon >= 0 ? itemId.substring(0, colon) : "minecraft";
      return namespace + ":export/" + category + "/" + index;
    }
    return "minecraft:export/" + category + "/" + index;
  }

  private static JsonObject serializeCraftingRecipe(IRecipe recipe) {
    if (recipe instanceof ShapedRecipes) {
      return serializeShaped((ShapedRecipes) recipe);
    }
    if (recipe instanceof ShapelessRecipes) {
      return serializeShapeless((ShapelessRecipes) recipe);
    }
    if (recipe instanceof ShapedOreRecipe) {
      return serializeShapedOre((ShapedOreRecipe) recipe);
    }
    if (recipe instanceof ShapelessOreRecipe) {
      return serializeShapelessOre((ShapelessOreRecipe) recipe);
    }
    return null;
  }

  private static JsonObject serializeShaped(ShapedRecipes recipe) {
    ItemStack output = recipe.getRecipeOutput();
    if (output == null) {
      return null;
    }
    return buildShapedPayloadFromObjects(
        recipe.recipeWidth, recipe.recipeHeight, recipe.recipeItems, output, "crafting_shaped");
  }

  private static JsonObject serializeShapedOre(ShapedOreRecipe recipe) {
    ItemStack output = recipe.getRecipeOutput();
    if (output == null) {
      return null;
    }
    return buildShapedPayloadFromObjects(
        getOreRecipeWidth(recipe),
        getOreRecipeHeight(recipe),
        recipe.getInput(),
        output,
        "forge:ore_shaped");
  }

  private static JsonObject serializeShapeless(ShapelessRecipes recipe) {
    ItemStack output = recipe.getRecipeOutput();
    if (output == null) {
      return null;
    }

    JsonObject payload = new JsonObject();
    payload.addProperty("type", "crafting_shapeless");
    JsonArray ingredients = new JsonArray();
    @SuppressWarnings("unchecked")
    List<ItemStack> inputs = recipe.recipeItems;
    for (ItemStack input : inputs) {
      if (input == null) {
        continue;
      }
      ingredients.add(stackToIngredient(input));
    }
    payload.add("ingredients", ingredients);
    payload.add("result", stackToResult(output));
    return payload;
  }

  private static JsonObject serializeShapelessOre(ShapelessOreRecipe recipe) {
    ItemStack output = recipe.getRecipeOutput();
    if (output == null) {
      return null;
    }

    JsonObject payload = new JsonObject();
    payload.addProperty("type", "forge:ore_shapeless");
    JsonArray ingredients = new JsonArray();
    for (Object input : recipe.getInput()) {
      ingredients.add(objectToIngredient(input));
    }
    payload.add("ingredients", ingredients);
    payload.add("result", stackToResult(output));
    return payload;
  }

  private static JsonObject serializeSmeltingRecipe(ItemStack input, ItemStack output) {
    if (input == null || output == null) {
      return null;
    }

    JsonObject payload = new JsonObject();
    payload.addProperty("type", "smelting");
    payload.add("ingredient", stackToIngredient(input));
    payload.add("result", stackToResult(output));
    return payload;
  }

  private static JsonObject buildShapedPayloadFromObjects(
      int width, int height, Object[] matrix, ItemStack output, String type) {
    JsonObject payload = new JsonObject();
    payload.addProperty("type", type);

    JsonArray pattern = new JsonArray();
    JsonObject key = new JsonObject();
    java.util.Map<String, Character> signatureToSymbol = new java.util.HashMap<String, Character>();
    char nextSymbol = 'A';

    for (int row = 0; row < height; row++) {
      StringBuilder line = new StringBuilder();
      for (int col = 0; col < width; col++) {
        Object cell = matrix[row * width + col];
        if (isEmptyIngredient(cell)) {
          line.append(' ');
          continue;
        }

        String signature = ingredientSignature(cell);
        Character symbol = signatureToSymbol.get(signature);
        if (symbol == null) {
          symbol = nextSymbol++;
          if (nextSymbol > 'Z') {
            symbol = '#';
          }
          signatureToSymbol.put(signature, symbol);
          key.add(String.valueOf(symbol), objectToIngredient(cell));
        }
        line.append(symbol);
      }
      pattern.add(new JsonPrimitive(line.toString()));
    }

    payload.add("pattern", pattern);
    payload.add("key", key);
    payload.add("result", stackToResult(output));
    return payload;
  }

  private static boolean isEmptyIngredient(Object cell) {
    if (cell == null) {
      return true;
    }
    if (cell instanceof ItemStack) {
      ItemStack stack = (ItemStack) cell;
      return stack.getItem() == null || stack.stackSize <= 0;
    }
    if (cell instanceof List) {
      return ((List<?>) cell).isEmpty();
    }
    return false;
  }

  private static String ingredientSignature(Object ingredient) {
    if (ingredient instanceof ItemStack) {
      ItemStack stack = (ItemStack) ingredient;
      return "stack:" + getItemId(stack) + ":" + normalizeMeta(stack.getItemDamage());
    }
    if (ingredient instanceof String) {
      return "ore:" + ingredient;
    }
    if (ingredient instanceof List) {
      List<?> list = (List<?>) ingredient;
      if (list.isEmpty()) {
        return "empty";
      }
      return ingredientSignature(list.get(0));
    }
    return String.valueOf(ingredient);
  }

  private static JsonObject objectToIngredient(Object ingredient) {
    if (ingredient instanceof ItemStack) {
      return stackToIngredient((ItemStack) ingredient);
    }
    if (ingredient instanceof String) {
      JsonObject ore = new JsonObject();
      ore.addProperty("ore", (String) ingredient);
      ore.addProperty("type", "forge:ore_dict");
      return ore;
    }
    if (ingredient instanceof List) {
      List<?> list = (List<?>) ingredient;
      if (list.isEmpty()) {
        return unknownIngredient();
      }
      Object first = list.get(0);
      if (first instanceof String) {
        JsonObject ore = new JsonObject();
        ore.addProperty("ore", (String) first);
        ore.addProperty("type", "forge:ore_dict");
        return ore;
      }
      if (first instanceof ItemStack) {
        ItemStack stack = (ItemStack) first;
        int[] oreIds = OreDictionary.getOreIDs(stack);
        if (oreIds != null && oreIds.length > 0) {
          JsonObject ore = new JsonObject();
          ore.addProperty("ore", OreDictionary.getOreName(oreIds[0]));
          ore.addProperty("type", "forge:ore_dict");
          return ore;
        }
        return stackToIngredient(stack);
      }
    }
    return unknownIngredient();
  }

  private static JsonObject unknownIngredient() {
    JsonObject unknown = new JsonObject();
    unknown.addProperty("item", "minecraft:air");
    return unknown;
  }

  private static JsonObject stackToIngredient(ItemStack stack) {
    JsonObject ingredient = new JsonObject();
    ingredient.addProperty("item", getItemId(stack));
    int meta = normalizeMeta(stack.getItemDamage());
    ingredient.addProperty("metadata", meta);
    return ingredient;
  }

  private static JsonObject stackToResult(ItemStack stack) {
    JsonObject result = new JsonObject();
    result.addProperty("item", getItemId(stack));
    int meta = normalizeMeta(stack.getItemDamage());
    result.addProperty("metadata", meta);
    int count = stack.stackSize;
    if (count > 1) {
      result.addProperty("count", count);
    }
    return result;
  }

  private static int normalizeMeta(int meta) {
    if (meta == OreDictionary.WILDCARD_VALUE) {
      return 0;
    }
    return Math.max(meta, 0);
  }

  private static String getItemId(ItemStack stack) {
    if (stack == null || stack.getItem() == null) {
      return "minecraft:air";
    }

    Item item = stack.getItem();
    int meta = normalizeMeta(stack.getItemDamage());
    GameRegistry.UniqueIdentifier uid = GameRegistry.findUniqueIdentifierFor(item);
    if (uid != null) {
      return uid.modId + ":" + uid.name;
    }

    Object registered = Item.itemRegistry.getNameForObject(item);
    if (registered instanceof String) {
      String value = (String) registered;
      if (value.contains(":")) {
        return value;
      }
      return "minecraft:" + value;
    }
    return "minecraft:unknown";
  }

  private static int getOreRecipeWidth(ShapedOreRecipe recipe) {
    return readOreRecipeDimension(recipe, "width");
  }

  private static int getOreRecipeHeight(ShapedOreRecipe recipe) {
    return readOreRecipeDimension(recipe, "height");
  }

  private static int readOreRecipeDimension(ShapedOreRecipe recipe, String fieldName) {
    try {
      Field field = ShapedOreRecipe.class.getDeclaredField(fieldName);
      field.setAccessible(true);
      return field.getInt(recipe);
    } catch (ReflectiveOperationException exception) {
      Object[] input = recipe.getInput();
      int size = input == null ? 0 : input.length;
      return size <= 3 ? size : 3;
    }
  }

  private static int copyAe2RecipeFiles(File outputDir) throws IOException {
    File sourceRoot = new File("config/AppliedEnergistics2/recipes/generated");
    if (!sourceRoot.isDirectory()) {
      return 0;
    }

    File targetRoot = new File(outputDir, "ae2-recipes");
    if (!targetRoot.exists() && !targetRoot.mkdirs()) {
      throw new IOException("Failed to create AE2 recipe directory: " + targetRoot.getAbsolutePath());
    }

    final int[] copied = {0};
    Path sourcePath = sourceRoot.toPath();
    Path targetPath = targetRoot.toPath();
    Files.walkFileTree(
        sourcePath,
        new SimpleFileVisitor<Path>() {
          @Override
          public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
            if (!file.getFileName().toString().endsWith(".recipe")) {
              return FileVisitResult.CONTINUE;
            }
            Path relative = sourcePath.relativize(file);
            Path destination = targetPath.resolve(relative);
            if (destination.getParent() != null) {
              Files.createDirectories(destination.getParent());
            }
            Files.copy(file, destination, StandardCopyOption.REPLACE_EXISTING);
            copied[0]++;
            return FileVisitResult.CONTINUE;
          }
        });
    return copied[0];
  }
}
