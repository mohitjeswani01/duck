import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  // The dev-mode build-activity badge sits bottom-left and overlaps the
  // Wispr input / sound toggle in screenshots and on-stage demos.
  devIndicators: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // This repo lives on a Windows drive mounted into WSL (/mnt/d). File-change
  // events from drvfs don't propagate to Linux watchers, so hot reload silently
  // stops working without polling. Turbopack doesn't support polling at all, which
  // is why the dev script forces --webpack — this config only takes effect then.
  webpack: (config) => {
    config.watchOptions = {
      poll: 1000,
      aggregateTimeout: 300,
    };
    return config;
  },
};

export default nextConfig;
