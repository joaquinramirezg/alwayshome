import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "AlwaysHome",
    short_name: "AlwaysHome",
    description: "Find the fire-safety fixes that move your California home from the FAIR Plan back to affordable private insurance.",
    start_url: "/",
    display: "standalone",
    background_color: "#FAF7F2",
    theme_color: "#111111",
    icons: [
      { src: "/brand/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/brand/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/brand/alwayshome-app-icon.svg", sizes: "any", type: "image/svg+xml" },
    ],
  };
}
