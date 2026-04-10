# Mock Message Center

A demo health insurance message center built with Flask, Jinja2, and SQLite.

## Local Development

```bash
cp .env.example .env
# Add your Gemini API key to .env

docker build -t mmc .
docker run -p 8080:8080 mmc
```

Open http://localhost:8080
