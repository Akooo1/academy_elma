# Phase 1 serves a placeholder page; Phase 6 adds a stage that builds the React app.
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/nginx.conf
COPY security-headers.conf proxy-api.conf /etc/nginx/snippets/
COPY html/ /usr/share/nginx/html/
