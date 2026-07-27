import type { MetadataRoute } from "next";

/** Web App Manifest — makes Tally installable to a phone home screen or a
 *  desktop dock (Chrome/Edge "Install app", iOS "Add to Home Screen"). */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Tally — Personal Finance OS",
    short_name: "Tally",
    description:
      "Import your bank and UPI statements and see truthfully where your money goes.",
    start_url: "/dashboard",
    scope: "/",
    display: "standalone",
    orientation: "portrait-primary",
    background_color: "#ffffff",
    theme_color: "#2563eb",
    categories: ["finance", "productivity"],
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      {
        src: "/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
    shortcuts: [
      { name: "Ask a question", short_name: "Chat", url: "/chat" },
      { name: "Upload a statement", short_name: "Upload", url: "/upload" },
      { name: "Label spending", short_name: "Triage", url: "/triage" },
    ],
  };
}
