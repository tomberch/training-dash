# TrainingDash

Self-hosted fitness analytics. Analyze your training data with interactive maps, charts, and personal records — with advanced metrics like GoldenCheetah and TrainingPeaks coming soon.

## Features

- **FIT file support** — Upload and parse Garmin FIT files
- **Garmin Connect sync** — Automatic sync from Garmin (with MFA support)
- **Xert sync** — Automatic sync from Xert
- **Interactive maps** — View routes with start/end markers and hover sync
- **Charts** — Speed, heart rate, power, elevation with dynamic scaling
- **Personal records** — Track lifetime and per-route PRs
- **Route matching** — Automatically group activities by route
- **Multi-user** — Each user has isolated data and preferences

## Getting Started

```bash
docker compose up
```

Open http://localhost:3000 and log in with:
- Username: `admin`
- Password: `admin`

To sync activities from Garmin or Xert, go to **Settings** and configure your credentials.

## License

[MIT](LICENSE)
