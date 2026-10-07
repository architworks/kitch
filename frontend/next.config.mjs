/** @type {import('next').NextConfig} */
const developmentScriptPolicy = process.env.NODE_ENV === "development"
  ? " 'unsafe-eval'"
  : "";

const nextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "cdn.zeptonow.com",
        pathname: "/**"
      },
      {
        protocol: "https",
        hostname: "media-assets.swiggy.com",
        pathname: "/**"
      }
    ]
  },
  async headers() {
    return [{
      source: "/(.*)",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
        { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
        ...(process.env.NODE_ENV === "production" ? [{
          key: "Strict-Transport-Security",
          value: "max-age=63072000; includeSubDomains; preload"
        }] : []),
        { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=()" },
        {
          key: "Content-Security-Policy",
          value: `default-src 'self'; script-src 'self' 'unsafe-inline'${developmentScriptPolicy} https://accounts.google.com; style-src 'self' 'unsafe-inline' https://accounts.google.com; img-src 'self' data: blob: https://cdn.zeptonow.com https://media-assets.swiggy.com https://*.googleusercontent.com; connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 https://accounts.google.com; frame-src https://accounts.google.com; font-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'`
        }
      ]
    }];
  }
};

export default nextConfig;
