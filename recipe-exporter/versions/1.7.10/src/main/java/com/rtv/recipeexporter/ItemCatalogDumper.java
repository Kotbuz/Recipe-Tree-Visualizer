package com.rtv.recipeexporter;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import cpw.mods.fml.common.registry.GameRegistry;
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
import net.minecraft.util.StatCollector;
import net.minecraftforge.oredict.OreDictionary;

public final class ItemCatalogDumper {
  private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().setPrettyPrinting().create();

  private ItemCatalogDumper() {}

  public static int dump(File outputFile) throws IOException {
    File parent = outputFile.getParentFile();
    if (parent != null && !parent.exists() && !parent.mkdirs()) {
      throw new IOException("Failed to create output directory: " + parent.getAbsolutePath());
    }

    JsonArray items = new JsonArray();
    int exported = 0;

    for (Object entry : Item.itemRegistry) {
      Item item = (Item) entry;
      if (item == null) {
        continue;
      }

      List<ItemStack> stacks = new ArrayList<ItemStack>();
      item.getSubItems(item, null, stacks);
      if (stacks.isEmpty()) {
        stacks.add(new ItemStack(item));
      }

      for (ItemStack stack : stacks) {
        if (stack == null || stack.getItem() == null) {
          continue;
        }

        String itemId = getItemId(stack);
        int meta = normalizeMeta(stack.getItemDamage());
        String displayName = getDisplayName(stack);
        if (displayName == null || displayName.trim().isEmpty()) {
          continue;
        }

        JsonObject payload = new JsonObject();
        payload.addProperty("item", itemId);
        payload.addProperty("metadata", meta);
        payload.addProperty("name", displayName);
        payload.addProperty("mod", getModId(stack));
        items.add(payload);
        exported++;
      }
    }

    try (Writer writer =
        new OutputStreamWriter(new FileOutputStream(outputFile), StandardCharsets.UTF_8)) {
      GSON.toJson(items, writer);
    }

    return exported;
  }

  private static String getDisplayName(ItemStack stack) {
    try {
      return stack.getDisplayName();
    } catch (Throwable ignored) {
      String key = stack.getUnlocalizedName() + ".name";
      return StatCollector.translateToLocal(key);
    }
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
    return "minecraft";
  }

  private static String getItemId(ItemStack stack) {
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
