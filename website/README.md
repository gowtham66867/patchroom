# Public evidence demo

Static evidence presentation; it does not execute agents, repositories or Python in the browser. The CLI and actual Switch agents run locally.

The video is a narrated presentation of archived evidence, not a live screen recording.

Serve locally with `python3 -m http.server 4173 --directory dist`. Build the included Dockerfile to serve on port 8080.

The featured film uses Gemini 2.5 Flash TTS (Kore) via Texmed Vertex AI, with
1080p motion graphics, normalized narration and English captions. Rebuild with
`python3 scripts/make_gemini_video.py` from the repository root after signing in
with the authorized cloud account. Credentials are read in memory, not saved.
