# Production API Gateway & Reverse Proxy Container
FROM nginx:alpine

# Security: Remove default Nginx welcome page
RUN rm -rf /usr/share/nginx/html/*

# Copy custom Nginx routing and proxy configuration
COPY gateway/nginx.conf /etc/nginx/nginx.conf

# Copy Single Page Application frontend assets
COPY frontend /usr/share/nginx/html

EXPOSE 80

# Healthcheck to verify gateway availability
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
