# SkyDaddy - Minimal, Scalable File Sharing Server

![pylint workflow](https://github.com/Saket-Upadhyay/SkyDaddy/actions/workflows/pylint.yml/badge.svg) ![function tests workflow](https://github.com/Saket-Upadhyay/SkyDaddy/actions/workflows/functiontests.yml/badge.svg)

> Tested on Ubuntu 22.04 LTS and MacOS Ventura 13.2.1

You can deploy this application without scaling using gunicorn on your local machine/server, or you can utilise docker
to scale the application.
If you intend to use this with more than 3-4 users, it is recommended that you scale it up.

## Local Hosting

To deploy this on your local machine, you will need to install python3. It is suggested that you use a virtual
environment to set up the dependencies.

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
in `skydaddy service` in `docker-compose.yml`
or you can pass the `--scale skydaddy=x` (where `x` is the number of instances you want to run) to `./serve_docker`
script. The later will override the parameters of the compose configuration.

```yml
version: "3.9"

services:
  skydaddy:
    build:
      context: app
#  <...>
    deploy:
      replicas: 3
#  <...>

```

### Composing
You can compose the containers using `./serve_docker.sh` by -

```shell
./serve_docker.sh
```

or

You can manually do it by - 
```shell
docker compose up -d --build --scale skydaddy=3 nginx=1
```

You can also pass [parameters for docker compose](https://docs.docker.com/compose/reference/) by appending them to the
script call:

```shell
./serve_docker.sh --build
```
---

### Pull image from DockerHub
if you don't want to build the image yourself, there are two versions of docker images avaliable at [DockerHub/x64mayhem/skydaddy] (https://hub.docker.com/r/x64mayhem/skydaddy)

#### ARM64 (Mac Mx)
```shell
docker pull x64mayhem/skydaddy:arm64
```

#### AMD64 (Intel/AMD 64-bit)
```shell
docker pull x64mayhem/skydaddy:amd64
```

---

### TODO
- [x] Add linter workflow (Code:Readability)
- [x] Add function tests (Code:Correctness)
- [ ] Improve UI (Design:UI/UX)
- [ ] Add password lock on commands. (Security:Authentication)
- [ ] Implement public key encryption while storing files. (Security:Privacy, Security:Confidentiality)

### License

MIT | [Copyright (c) 2023 Saket Upadhyay](./LICENSE)
