FROM dunglas/frankenphp:1-php8.4

RUN install-php-extensions \
        pdo_mysql \
        intl \
        zip \
        mbstring \
        opcache

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /app

# symfony-flex's auto-scripts run cache:clear, which compiles the container
# and needs a syntactically-valid (not necessarily reachable) DATABASE_URL
# and a non-empty APP_SECRET to do so. These are build-time-only defaults —
# Railway's real runtime env vars override a Dockerfile ENV of the same name.
ENV APP_ENV=prod
ENV APP_SECRET=build-time-placeholder
ENV DATABASE_URL="mysql://user:pass@127.0.0.1:3306/db?serverVersion=8.0&charset=utf8mb4"
# Composer silently disables all plugins (symfony/flex, symfony/runtime) when
# run as root, which is why vendor/autoload_runtime.php was never generated —
# the RUN steps here execute as root since no USER is set.
ENV COMPOSER_ALLOW_SUPERUSER=1

COPY . .

RUN composer install --no-dev --optimize-autoloader --classmap-authoritative \
    && mkdir -p var/cache var/log \
    && chown -R www-data:www-data var

EXPOSE 80

# Railway assigns a dynamic $PORT; frankenphp's built-in server takes it
# directly via --listen, no config-file templating needed.
CMD ["sh", "-c", "frankenphp php-server --listen :${PORT:-80} --root public"]
