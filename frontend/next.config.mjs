/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "cdn.zeptonow.com",
        pathname: "/**"
      }
    ]
  }
};

export default nextConfig;
