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
  // `next build` (what Vercel runs) always uses Turbopack regardless of this
  // block, so it's already inert in production — the NODE_ENV guard is an
  // explicit belt-and-braces check, not just an implicit consequence of which
  // bundler happens to be invoked, so this can never affect a production build
  // even if a future Next version changes that default.
  webpack: (config) => {
    if (process.env.NODE_ENV !== "production") {
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
};

export default nextConfig;
