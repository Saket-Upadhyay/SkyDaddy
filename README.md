# SkyDaddy

A minimal self-hosted file sharing app. Upload a file, get a SHA1 code, share the code so anyone can download it.

## Requirements

- Python 3.14+
- [uv](https://github.com/astral-sh/uv)

## Setup

```bash
uv sync
```

## Running

**Development** (auto-reloads on file changes):
```bash
uv run dev
```

**Production** (waitress WSGI server):
```bash
uv run prod
```

The server starts on `http://0.0.0.0:8000`.

## Configuration

All options are set via environment variables.

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | random (changes on restart) | Flask session secret — set a fixed value in production |
| `UPLOAD_FOLDER` | `./UPLOADS` | Where uploaded files are stored |
| `PERMA_FOLDER` | `./PERMA` | Destination for the SAVELOCAL command |
| `MAP_FILE` | `./file_map.json` | Persisted SHA1 → filename mapping |
| `ADMIN_TOKEN` | _(empty — no auth)_ | Token required for admin commands |

## Usage

1. Open `http://localhost:8000`
2. Pick a file and click **Upload** — you'll receive a SHA1 code
3. Share the code; recipients enter it in the download box to retrieve the file

## Admin commands

Hit these endpoints as `GET /uploads/<command>?token=<ADMIN_TOKEN>`:

| Command | Effect |
|---|---|
| `RESETCACHE` | Deletes all files in `UPLOAD_FOLDER` and clears the map |
| `SAVELOCAL` | Copies all uploaded files to `PERMA_FOLDER` |

If `ADMIN_TOKEN` is not set, these commands are open to anyone. Set it in production.

## Supported file types

`txt` `pdf` `png` `jpg` `jpeg` `gif` `h` `cpp` `zip` `tar` `xz` `7z` `iso`
`doc` `docx` `xls` `xlsx` `ppt` `pptx` `csv` `json` `xml` `md`
`mkv` `mp4` `avi` `mov` `mp3` `wav` `flac` `ogg`
