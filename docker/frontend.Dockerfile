FROM node:18-alpine

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .

# Disable Next.js telemetry during build
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
