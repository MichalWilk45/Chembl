#!/bin/bash
docker run -p 9000:9000 --name play-app -d products
sleep 5  # Czekamy, aż aplikacja się uruchomi
ngrok http 9000
