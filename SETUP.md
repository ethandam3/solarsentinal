# SolarSentinel — Build Sequence

Complete 36-hour build checklist. Run each step in order.

---

## Prerequisites (install once)

```bash
pip install boto3 sagemaker pandas scikit-learn xgboost joblib pytz
pip install aws-cdk-lib constructs   # for CDK
npm install -g aws-cdk               # CDK CLI

cd frontend && npm install           # React deps
```

**AWS credentials**: make sure `aws configure` is done with your hackathon account.
Check: `aws sts get-caller-identity`

---

## Step 1 — Process the Scripps data  (~2 min)

```bash
cd C:\Users\ethan\solarsentinel
python scripts/parse_scripps.py
```

Output:
- `data/awn_events.json`    — 1,016 training rows
- `data/demo_replay.json`   — 213 held-out rows (Aug 14-15)

---

## Step 2 — Generate permit data  (~10 sec)

```bash
python scripts/generate_permits.py
```

Output: `data/zenpower_permits.csv`  (50 synthetic San Diego installs)

> ⚠️  If the real ZenPower dataset is released at the hackathon portal,
> overwrite `data/zenpower_permits.csv` with the real file and re-run Steps 3+.

---

## Step 3 — Build training + demo datasets  (~30 sec)

```bash
python scripts/prepare_training_data.py
```

Output:
- `data/training.csv`                — 50,800 rows (1,016 AWN × 50 permits)
- `data/demo_events_with_fault.json` — fault injected into ZP-0014, hours 12–16

---

## Step 4 — Upload to S3 + start SageMaker training  (~2 min to submit)

```bash
python scripts/upload_to_s3.py --account YOUR_ACCOUNT_ID --region us-east-1
```

This submits the training job (async). **While it runs (~5-10 min), do Step 5.**

---

## Step 5 — Deploy CDK infrastructure  (~10 min)

```bash
cd infra
pip install -r requirements.txt
cdk bootstrap
cdk deploy SolarSentinelStack
```

Save the outputs — you'll need them in Step 7:
```
SolarSentinelStack.RestApiUrl  = https://xxx.execute-api...
SolarSentinelStack.WebSocketUrl = wss://yyy.execute-api...
```

---

## Step 6 — Deploy SageMaker endpoint  (~5 min, after training completes)

```bash
cd C:\Users\ethan\solarsentinel
python scripts/deploy_endpoint.py
```

---

## Step 7 — Configure frontend + deploy to Vercel  (~5 min)

Edit `frontend/src/config.js` with the CDK outputs from Step 5:

```js
export const WS_URL  = 'wss://YOUR_WS_ID.execute-api.us-east-1.amazonaws.com/prod'
export const REST_URL = 'https://YOUR_REST_ID.execute-api.us-east-1.amazonaws.com/prod'
```

Deploy:
```bash
cd frontend
npm run build
npx vercel --prod
```

---

## Step 8 — End-to-end test

1. Open the Vercel URL in browser
2. Check WebSocket status pill shows **🟢 Live**
3. Press **▶ Start Replay**
4. Wait ~90 seconds — alert for ZP-0014 should fire
5. Open DevTools → Network → WS → verify real frame arrives

---

## Demo checklist (before presenting)

- [ ] Dashboard loads and WebSocket shows "Live"
- [ ] ▶ Start Replay button kicks off replayer
- [ ] Chart shows blue (expected) and red (actual) lines diverging for ZP-0014
- [ ] Alert card appears in sidebar with correct delta%
- [ ] DevTools WS frame visible for judges
- [ ] CloudWatch dashboard tab open in second window
- [ ] `cdk deploy` output screenshot ready for Devpost

---

## Prizes targeted

| Prize | Evidence |
|---|---|
| **Best Use of AWS** (~$1,000) | CDK stack, SageMaker endpoint, Lambda, API GW REST + WebSocket, DynamoDB, SNS, CloudWatch |
| **Best Solution for ZenPower** (~$500) | ZenPower permit data joined with live solar readings, anomaly detection per install |
| **Scripps Challenge** (~$1,500) | Scripps AWN Solar Radiation data is the primary model feature; real Scripps station data drives all predictions |
