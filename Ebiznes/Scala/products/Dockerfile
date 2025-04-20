# Użyj oficjalnego obrazu OpenJDK jako bazowego
FROM openjdk:17-slim

# Ustaw katalog roboczy
WORKDIR /app

# Kopiuj pliki do kontenera
COPY products-1.0-SNAPSHOT.zip /app/app.zip


# Instalacja unzip i rozpakowanie aplikacji
RUN apt-get update && apt-get install -y unzip && \
    unzip app.zip && rm app.zip && \
    mv products-1.0-SNAPSHOT play-app


# Ustaw port aplikacji Play
EXPOSE 9000

# Uruchomienie aplikacji
CMD ["play-app/bin/products", "-Dhttp.port=9000"]
