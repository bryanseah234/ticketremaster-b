FROM kong:3.6

# Copy declarative config
COPY kong.yml /etc/kong/kong.yml

ENV KONG_DECLARATIVE_CONFIG=/etc/kong/kong.yml
ENV KONG_DATABASE=off
