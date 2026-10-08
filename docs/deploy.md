# Hosting on Google Cloud Run

_Prepared 8 Oct 2026; not yet deployed. Vikrant chose Cloud Run and is setting up the project, billing, the APIs, the `gemini-api-key` secret and a $5 budget himself. The script is `deploy/cloudrun.sh`._

## Goal: no cost while nobody visits

| Setting | Value | Why |
|---|---|---|
| Minimum instances | **0** | Scale to zero. With no instance running there's no charge; idle instances above the minimum aren't billed. |
| Billing | **request-based** (`--cpu-throttling`) | CPU and memory are billed only while a request is being handled, rounded up to 100 ms. |
| Maximum instances | **1** | Caps the cost. It also keeps the in-memory session and daily message caps correct, since there's only ever one copy of them. |
| CPU and memory | 1 vCPU, **512 MiB** | The app peaks at about 85 MiB locally. The headroom is for visitors' store copies, which live in Cloud Run's memory-backed `/tmp`. |
| Concurrency | **20** | One instance handles up to 20 requests at once. |
| Start-up CPU boost | on | Extra CPU only while starting, to shorten the first visit after idle. |
| Request timeout | 120 s | A live answer takes about 5 s, plus model retries. |
| Region | `us-central1` | A Tier 1 region, the cheapest. |

**Free tier** (request-based billing, from the Cloud Run pricing page, read 8 Oct 2026): 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests a month.
- **Live answers:** about 5 s of one vCPU each, so even 1,000 a month uses about 5,000 vCPU-seconds, under 3% of the free tier.
- **Pages and replays:** these take milliseconds.

**So Cloud Run itself should cost about $0. The real cost is Gemini:**
- About $0.0074 per live conversation.
- At most 400 live messages a day across all visitors (the daily cap), roughly $1 to $3 on a fully used day.
- Sampled grading, capped at $0.50 a day.

The access code keeps casual visitors on free replays. The $5 budget alert catches surprises.

**Smaller items:**
- **Artifact Registry** stores the image, a few hundred MB (`gcloud run deploy --source .` creates the repository).
- **Cloud Build** builds it.
- **Secret Manager** holds three secrets.

Check each against its free tier when billing is set up. I haven't verified their current free tiers.

## Trade-offs of scaling to zero

- **Cold starts.** The first visit after an idle period waits for the container to start (Python plus the Google libraries), probably a few seconds. The start-up boost shortens it. Replays and pages are instant once it's up.
- **Nothing local survives an idle period.** That's acceptable for a demo:
  - the visitors' store copies and sessions
  - the cases on the specialist page
  - the live events on /ops
  - the session and daily message counts

  The daily cap therefore resets on a cold start, so the access code, the per-session cap and the Gemini budget alert are the real spending guards.
- **/ops isn't empty after a cold start.** The image includes `deploy/ops-seed.sqlite`, the release candidate's 84 eval conversations, labelled as eval traffic. It's copied in when an instance starts, and live traffic adds to it until the instance stops. Rebuild the seed with `uv run python -m evals.ops_seed RUN.json...`.
- **Keeping data across restarts** would need a database such as Firestore or Cloud SQL. That's a new dependency and a running cost, so it isn't proposed for the demo.

## Production settings

| Variable | What it is | Where it should live |
|---|---|---|
| `GOOGLE_API_KEY` | The Gemini API key. The Google client reads this name, with `GEMINI_API_KEY` as its fallback. | **Secret Manager** (`gemini-api-key`) |
| `ACCESS_CODE` | The code for live chat. Without it, live chat is off and only replays work. | **Secret Manager** (`access-code`) |
| `OPS_CODE` | The code for /ops. Without it, /ops is off. | **Secret Manager** (`ops-code`) |
| `SPECIALIST_CODE` | The specialist page's demo code, `specialist-demo` by default. The page shows it, because the login exists to separate the personas, not to protect data. | plain variable, or leave the default |
| `MODEL_NAME` | The agent model: `gemini-3.6-flash` | plain variable |
| `GRADER_MODEL` | The grader for sampled live grading: `gemini-3.6-flash` | plain variable |
| `SESSION_CAP` | Live messages per visitor session (default 30) | plain variable |
| `DAILY_CAP` | Live messages per day across everyone (default 400) | plain variable |
| `GRADE_SAMPLE_RATE` | Share of live conversations graded (default 0.1) | plain variable |
| `GRADING_DAILY_BUDGET_USD` | The daily grading budget (default 0.50) | plain variable |
| `SECURE_COOKIES` | `1` on HTTPS, which Cloud Run always uses | plain variable |
| `RUNTIME_DIR` | `/tmp/runtime` (set in the Dockerfile) | image |
| `CAPTURE_PROMPTS` | Leave unset: prompts aren't stored in traces | leave unset |
| `PORT` | Set by Cloud Run; the container listens on it | Cloud Run |

## The container

- **Build.** `gcloud run deploy --source .` builds the repo's `Dockerfile` with Cloud Build. It hasn't been built here, because building and pushing wait for the go-ahead. The Dockerfile's structure is checked by tests: every `evals` module the app imports, the replays and the /ops seed must be copied in, and no secret is baked in.
- **Run.** The container runs as a non-root user and starts `uvicorn merchant_agent.web.api:app --host 0.0.0.0 --port ${PORT}`.
- **Replays.** These are recorded from the release candidate (agent version `60e5bc0b3211`), and a test fails if they go stale.

## Deploying automatically on every push to GitHub

`cloudbuild.yaml` runs on every push to `main`:
1. **Tests and lint.** Model calls are blocked in tests, and a failure stops the deploy.
2. **Build** the image.
3. **Push** it to Artifact Registry.
4. **Deploy** it to Cloud Run, with the same settings as `deploy/cloudrun.sh`. A test keeps the two files in step.

**One-time setup.** Connecting GitHub needs Vikrant's own sign-in, so this is done in the console.

1. **Let the build's service account deploy.** New projects run Cloud Build as the Compute Engine default service account, which already reads the three secrets:

   ```bash
   PROJECT_ID=merchant-agent-demo-vn
   NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
   SA="${NUMBER}-compute@developer.gserviceaccount.com"
   for role in roles/run.admin roles/iam.serviceAccountUser roles/artifactregistry.writer roles/logging.logWriter; do
     gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA" --role=$role --condition=None
   done
   ```

2. **Create the trigger.** In the console, open Cloud Build, then Triggers, then **Create trigger**:
   - **Name:** `deploy-on-push`. **Region:** `us-central1`.
   - **Event:** Push to a branch.
   - **Source:** Repository, then **Connect new repository**. Choose GitHub, authorise it, and pick `BishopSlice/merchant-support-agent`.
   - **Branch:** `^main$`.
   - **Configuration:** Cloud Build configuration file, at `cloudbuild.yaml`.
   - **Service account:** the Compute Engine default service account (`NUMBER-compute@developer.gserviceaccount.com`).
   - Then **Create**.

3. **Test it.** On the trigger, press **Run**, or push any commit. Build history shows the four steps, and the URL stays the same.

**Cost:** each build takes a few minutes of Cloud Build time. Check its free build minutes against your billing account, because I haven't verified the current figure.
