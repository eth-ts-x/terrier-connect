# React front-end Dockerfile
FROM node:22-alpine as build

# Set the working directory in the container
WORKDIR /app

# Build-time variables for React
ARG REACT_APP_GOOGLE_MAPS_API_KEY
ARG REACT_APP_API_BASE_URL=/api
ARG REACT_APP_MEDIA_BASE_URL=/media
ENV REACT_APP_GOOGLE_MAPS_API_KEY=$REACT_APP_GOOGLE_MAPS_API_KEY
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL
ENV REACT_APP_MEDIA_BASE_URL=$REACT_APP_MEDIA_BASE_URL

# Copy package.json and install dependencies
COPY package.json package-lock.json ./
RUN npm install

# Copy the rest of the application code
COPY . .

# Build the React app for production
RUN npm run build

# Stage 2: Serve the app using Nginx
FROM nginx:alpine

# Copy the build output to Nginx's default directory
COPY --from=build /app/build /usr/share/nginx/html

# Expose the Nginx port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
