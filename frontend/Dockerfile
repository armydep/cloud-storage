# Stage 0, "build-stage", based on Bun, to build and compile the frontend
FROM oven/bun:1 AS build-stage

# Optional, inert unless explicitly invoked: some sandboxed CI/dev environments
# intercept outbound TLS with their own CA, which registry.npmjs.org does not
# trust by default, and bun install fails with SELF_SIGNED_CERT_IN_CHAIN.
# Passing --secret id=sandbox_ca,src=<path-to-that-CA> installs it for this
# build only; without it (every normal build, including CI) this is a no-op.
RUN --mount=type=secret,id=sandbox_ca,required=false \
    if [ -s /run/secrets/sandbox_ca ]; then \
      cp /run/secrets/sandbox_ca /tmp/sandbox-ca.crt; \
    fi
ENV NODE_EXTRA_CA_CERTS=/tmp/sandbox-ca.crt

WORKDIR /app

COPY package.json bun.lock /app/

COPY frontend/package.json /app/frontend/

WORKDIR /app/frontend

RUN bun install

COPY ./frontend /app/frontend
ARG VITE_API_URL

RUN bun run build


# Stage 1, based on Nginx, to have only the compiled app, ready for production with Nginx
FROM nginx:1

COPY --from=build-stage /app/frontend/dist/ /usr/share/nginx/html

COPY ./frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY ./frontend/nginx-backend-not-found.conf /etc/nginx/extra-conf.d/backend-not-found.conf
