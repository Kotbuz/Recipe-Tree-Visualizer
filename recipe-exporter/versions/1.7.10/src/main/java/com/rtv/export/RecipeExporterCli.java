package com.rtv.export;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;

@Command(
    name = "recipe-exporter",
    mixinStandardHelpOptions = true,
    description = "Export Minecraft recipes to JSON files for Recipe Tree Visualizer"
)
public final class RecipeExporterCli implements Runnable {
  @Option(names = "--minecraft-version", required = true)
  private String minecraftVersion;

  @Option(names = "--client-jar", required = true)
  private Path clientJar;

  @Option(names = "--mods-dir", required = true)
  private Path modsDir;

  @Option(names = "--output-dir", required = true)
  private Path outputDir;

  public static void main(String[] args) {
    int exitCode = new CommandLine(new RecipeExporterCli()).execute(args);
    System.exit(exitCode);
  }

  @Override
  public void run() {
    if (!Files.isRegularFile(clientJar)) {
      throw new IllegalStateException("client.jar not found: " + clientJar);
    }

    try {
      Files.createDirectories(outputDir);
      StringBuilder manifest = new StringBuilder();
      manifest.append("{\n");
      manifest.append("  \"minecraft_version\": \"").append(minecraftVersion).append("\",\n");
      manifest.append("  \"status\": \"forge-runtime-required\",\n");
      manifest.append(
          "  \"message\": \"Bootstrap exporter. Forge runtime build required for live recipe dump.\"\n");
      manifest.append("}\n");
      Path manifestPath = outputDir.resolve("_export_manifest.json");
      Files.writeString(manifestPath, manifest);
      System.out.println("Wrote export manifest to " + manifestPath);

      if (Files.isDirectory(modsDir)) {
        try (var stream = Files.list(modsDir)) {
          long modCount =
              stream
                  .filter(
                      path ->
                          path.getFileName().toString().toLowerCase(Locale.ROOT).endsWith(".jar"))
                  .count();
          System.out.println("Detected " + modCount + " mod jar(s) in " + modsDir);
        }
      }
    } catch (IOException exception) {
      throw new IllegalStateException("Failed to write export manifest", exception);
    }
  }
}
