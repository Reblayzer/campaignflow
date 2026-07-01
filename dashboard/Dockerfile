FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

# At start: overwrite the committed marts with the fresh pipeline export,
# then build and serve. -H 0.0.0.0 so the published port is reachable.
CMD ["sh", "-c", "cp /marts/marts.json public/data/marts.json && npm run build && npm run start -- -H 0.0.0.0 -p 3000"]
