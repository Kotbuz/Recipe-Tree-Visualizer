FROM node:22-alpine AS build

WORKDIR /app/frontend

COPY frontend/package.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

RUN mkdir -p /usr/share/nginx/minecraft/item-textures /usr/share/nginx/minecraft/block-textures

EXPOSE 80
