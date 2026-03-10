FROM rabbitmq:3-management

# Fix erlang cookie permission issue on Docker Desktop / Windows
# The cookie file needs to be owned by rabbitmq:rabbitmq with mode 400
# Valid cookie must be 32 alphanumeric characters
RUN echo "RABBITMQCOOKIESECRET123456789012" > /var/lib/rabbitmq/.erlang.cookie && \
    chown rabbitmq:rabbitmq /var/lib/rabbitmq/.erlang.cookie && \
    chmod 400 /var/lib/rabbitmq/.erlang.cookie

