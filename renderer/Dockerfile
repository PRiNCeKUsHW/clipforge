# ClipForge render service: Remotion (React -> video) + headless Chrome.
FROM node:22-bookworm-slim

# Chrome Headless Shell runtime libraries, plus fonts for Devanagari (Hindi) and colour emoji
# so captions in any script render correctly.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 libxrandr2 libxkbcommon-dev \
      libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2 \
      fonts-noto-core fonts-noto-color-emoji ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY tsconfig.json server.mjs ./
COPY src ./src
# Download the headless browser at build time instead of on first render.
RUN npx remotion browser ensure

ENV PORT=3100 WORK_ROOT=/data/work NODE_ENV=production
EXPOSE 3100
CMD ["node", "server.mjs"]
