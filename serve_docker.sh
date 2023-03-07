#!/usr/bin/env sh

if [ "$*" != "" ]; then
  docker compose up -d "$*"
else
  docker compose up -d
fi

