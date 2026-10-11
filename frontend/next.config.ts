import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false, // no framework badge on the control-room screen
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
