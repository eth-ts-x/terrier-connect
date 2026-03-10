# React front-end Dockerfile
FROM node:22-alpine AS build

WORKDIR /app

# Build-time variables for React
ARG REACT_APP_GOOGLE_MAPS_API_KEY
ARG REACT_APP_API_BASE_URL=/api
ARG REACT_APP_MEDIA_BASE_URL=/media
ARG REACT_APP_GRAPHQL_URL=/graphql
ARG REACT_APP_GOOGLE_CLIENT_ID
ENV REACT_APP_GOOGLE_MAPS_API_KEY=$REACT_APP_GOOGLE_MAPS_API_KEY
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL
ENV REACT_APP_MEDIA_BASE_URL=$REACT_APP_MEDIA_BASE_URL
ENV REACT_APP_GRAPHQL_URL=$REACT_APP_GRAPHQL_URL
ENV REACT_APP_GOOGLE_CLIENT_ID=$REACT_APP_GOOGLE_CLIENT_ID

COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps

COPY . .
RUN npm run build

# Serve via Nginx
FROM nginx:alpine

COPY --from=build /app/build /usr/share/nginx/html

# Use production Nginx config with SPA fallback (try_files)
COPY nginx_conf/nginx_prod.conf /etc/nginx/nginx.conf

# Expose the Nginx port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
