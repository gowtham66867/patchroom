# Texmed deployment

Public demo: https://patchroom-demo-412542191970.asia-south1.run.app/

Video: https://patchroom-demo-412542191970.asia-south1.run.app/gemini-walkthrough.mp4

Source: https://github.com/gowtham66867/patchroom

## Scope

The Cloud Run service hosts the static evidence walkthrough and media. The Python
CLI and actual coding agents execute locally through Switch Console. No remote
code execution endpoint or model API credential is exposed by the website.

The deployment uses a separate patchroom-demo service account with no project
roles added, min instances 0, max instances 1, 128 MiB memory and port 8080.
Existing Texmed services were not changed. Domain-restricted sharing prevented
an allUsers IAM binding, so the public static service uses Cloud Run's documented
service-scoped invoker-IAM-check setting. No organization policy was changed.

## Reproduce deployment

Run from website/ using an authorized Texmed Google Cloud account:

```sh
gcloud run deploy patchroom-demo --source=. \
  --project=billing-dashboard-505116 --region=asia-south1 \
  --service-account=patchroom-demo@billing-dashboard-505116.iam.gserviceaccount.com \
  --no-invoker-iam-check --ingress=all --port=8080 \
  --cpu=1 --memory=128Mi --min-instances=0 --max-instances=1
```

## Verification

- Cloud Run reported the revision serving 100% of traffic.
- Anonymous GET / returned HTTP 200.
- Anonymous video byte-range request returned HTTP 206.
- Local media probe confirmed a 146.5-second Gemini-narrated 1080p MP4.
- Browser QA confirmed stage switching and loaded video metadata with no error.
- Public source and actual evidence are linked from the deployed page.

No custom texmed.us domain was configured; hosting is in the Texmed account.
