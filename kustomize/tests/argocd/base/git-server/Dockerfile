# Pulled Oct 9, 2023
FROM nginx@sha256:32da30332506740a2f7c34d5dc70467b7f14ec67d912703568daff790ab3f755
RUN apt-get update && apt-get install -y git fcgiwrap spawn-fcgi
COPY nginx-default.conf /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf
ENTRYPOINT spawn-fcgi -s /tmp/fcgiwrap.sock -- /usr/sbin/fcgiwrap >> /var/log/nginx/error.log 2>&1 &&\
           nginx -g "daemon off;"
