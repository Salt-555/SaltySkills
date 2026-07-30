# SaltySkills

A public collection of fun creative skills for the [Hermes agent](https://github.com/Salt-555/hermes-agent).

## What are skills?

Skills are modular instruction sets that extend what Hermes can do. Each skill lives in its own directory with a `SKILL.md` (the instructions/workflow) and a `references/` folder for any supporting scripts or configs.

## Skills

### video/cinematic-beats

Cinematic video style with short punchy TTS (one sentence max), visuals given full runtime to breathe, hard cuts, and user-provided music with ducking during speech. Check-in gates after each production phase for user review before proceeding. Includes VHS filter and vibey audio mixing scripts.

**Tags:** `video` `cinematic` `tts` `storyboard` `creative`

### video/deep-fry

Multi-phase ASCII video pipeline. Turns source video into glitch-art with ASCII color variants (vidcolors, bw, matrix, rainbow), YAML-driven segment stitching with slow-mo, and VHS/analog artifact post-processing.

**Tags:** `ascii` `glitch` `vhs` `ffmpeg` `pipeline`

### video/moshpit

Datamoshing and video glitch effects pipeline. Takes a video, produces multiple glitched variations via I-frame removal, P-frame duplication, FFglitch motion vectors, and FFmpeg lagfun trails. Real codec manipulation — not simulated filters.

**Tags:** `datamosh` `glitch` `ffglitch` `ffmpeg` `codec`

### video/video-clip-captions

Extract short clips from long videos with burned-in social-media captions. Downloads YouTube auto-captions (VTT) or transcribes local files via faster-whisper, deduplicates overlapping blocks, and creates vertical 9:16 clips with verbatim word-level synced subtitles for TikTok/Reels/Shorts.

**Tags:** `clips` `captions` `social-media` `whisper` `ffmpeg`
