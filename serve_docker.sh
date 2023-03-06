#!/usr/bin/env sh

docker volume create sharedUPLOAD
docker volume create sharedPERMA

if [ "$*" != "" ]; then
  docker compose up -d "$*" --scale skydaddy=1
else
  docker compose up -d --scale skydaddy=1
fi

