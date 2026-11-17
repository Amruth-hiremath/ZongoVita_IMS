FROM alpine:3.22
RUN apk add --no-cache pgbouncer \
    && addgroup -S pooler && adduser -S -G pooler pooler
COPY --chown=pooler:pooler pgbouncer.ini userlist.txt /etc/pgbouncer/
USER pooler
EXPOSE 6432
CMD ["pgbouncer", "/etc/pgbouncer/pgbouncer.ini"]
