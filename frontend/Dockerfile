# Use an official Node.js image to build the React app
FROM node:18 AS build

WORKDIR /app

# Copy package.json and install dependencies
COPY package.json package-lock.json ./ 
RUN npm install

# Copy the rest of the frontend code
COPY . . 

# Build the React app
RUN npm run build

# Use Nginx to serve the built files
FROM nginx:alpine AS production

# Copy the custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy React build files to Nginx's HTML folder
COPY --from=build /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
