import type { MetadataRoute } from "next";

/** Installable PWA manifest. Lets staff add the portal to the home screen on Android and iOS today. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "IT Service Portal",
    short_name: "IT Desk",
    start_url: "/dashboard",
    display: "standalone",
    background_color: "#f5f7fb",
    theme_color: "#1f4fd8",
    icons: [],
  };
}
