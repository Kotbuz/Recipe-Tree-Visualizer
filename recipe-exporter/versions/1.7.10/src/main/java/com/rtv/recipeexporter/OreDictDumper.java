package com.rtv.recipeexporter;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import net.minecraftforge.oredict.OreDictionary;
import cpw.mods.fml.common.registry.GameRegistry;

public final class OreDictDumper {
  private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().setPrettyPrinting().create();

  private OreDictDumper() {}

  public static int dump(File outputFile) throws IOException {
    File parent = outputFile.getParentFile();
    if (parent != null && !parent.exists() && !parent.mkdirs()) {
      throw new IOException("Failed to create output directory: " + parent.getAbsolutePath());
    }

    JsonObject root = new JsonObject();
    int exported = 0;

    for (String oreName : OreDictionary.getOreNames()) {
      if (oreName == null || oreName.trim().isEmpty()) {
        continue;
      }

      List<ItemStack> ores = OreDictionary.getOres(oreName);
      if (ores == null || ores.isEmpty()) {
        continue;
      }

      ItemStack canonical = pickCanonical(ores);
      if (canonical == null) {
        continue;
      }

      String itemId = getItemId(canonical);
      int meta = normalizeMeta(canonical.getItemDamage());
      if (meta > 0) {
        JsonObject entry = new JsonObject();
        entry.addProperty("item", itemId);
        entry.addProperty("metadata", meta);
        root.add(oreName, entry);
      } else {
        root.addProperty(oreName, itemId);
      }
      exported++;
    }

    try (Writer writer =
        new OutputStreamWriter(new FileOutputStream(outputFile), StandardCharsets.UTF_8)) {
      GSON.toJson(root, writer);
    }

    return exported;
  }

  private static ItemStack pickCanonical(List<ItemStack> ores) {
    List<ItemStack> stacks = new ArrayList<ItemStack>();
    for (ItemStack stack : ores) {
      if (stack != null && stack.getItem() != null) {
        stacks.add(stack);
      }
    }
    if (stacks.isEmpty()) {
      return null;
    }

    for (ItemStack stack : stacks) {
      if ("minecraft".equals(getModId(stack))) {
        return stack;
      }
    }

    return stacks.get(0);
  }

  private static int normalizeMeta(int meta) {
    if (meta == OreDictionary.WILDCARD_VALUE) {
      return 0;
    }
    return Math.max(meta, 0);
  }

  private static String getModId(ItemStack stack) {
    GameRegistry.UniqueIdentifier uid = GameRegistry.findUniqueIdentifierFor(stack.getItem());
    if (uid != null) {
      return uid.modId;
    }

    Object registered = Item.itemRegistry.getNameForObject(stack.getItem());
    if (registered instanceof String) {
      String value = (String) registered;
      if (value.contains(":")) {
        return value.substring(0, value.indexOf(':'));
      }
      return "minecraft";
    }

    return "unknown";
  }

  private static String getItemId(ItemStack stack) {
    if (stack == null || stack.getItem() == null) {
      return "minecraft:air";
    }

    Item item = stack.getItem();
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
}
