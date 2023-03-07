# SkyDaddy - Minimal, Scalable File Sharing Server

![pylint workflow](https://github.com/Saket-Upadhyay/SkyDaddy//actions/workflows/pylint.yml/badge.svg)

> Tested on Ubuntu 22.04 LTS and MacOS Ventura 13.2.1

## Local Hosting

### Python Setup

##### Ubuntu

```sh
sudo apt-get install python3 python3-pip virtualenv
```

##### MacOS

```sh
brew install python@3.9 virtualenv
```

### Create a virtual env.

```shell
virtualenv -p $(which python3) ~/SkyDaddyEnv
```

### Install required python packages

```shell
source ~/SkyDaddyEnv/bin/activate
pip install -r requirements.txt
deactivate
```

### Hosting

```sh
source ~/SkyDaddyEnv/bin/activate
./serve_local.sh
```

## Docker deployment & Scaling

> By default, the application is scaled to 3 instances of skydaddy servers and 1 instance of nginx.

### Scaling factor

You can change the number of instances you want to run by changing the `replicas: 3` under `deploy:`
in `skydaddy servcice` in `docker-compose.yml`
or you can pass the `--scale skydaddy=x` (where `x` is the number of instances you want to run) to `./serve_docker`
script.

```yml
version: "3.9"

services:
  skydaddy:
    build:
      context: app
  <...>
deploy:
  replicas: 3
  <...>

```

### Composing

```shell
./serve_docker.sh
```

You can also pass [parameters for docker compose](https://docs.docker.com/compose/reference/) by appending them to the
script call:

```shell
./serve_docker.sh --build
```

or

```shell
./serve_docker.sh --build --scale skydaddy=10 ngnix=2
```

