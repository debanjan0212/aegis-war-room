# Voices

Every folder here is one voice the assistant can speak in. The **Voice** menu on screen lists them.

| Folder | What it is |
|---|---|
| `butler/` | Calm British male. A stock voice that ships with the browser |
| `aria/` | Clear female. A stock voice that ships with the browser |
| `_template/` | Copy this to add a voice. Folders starting with `_` are not shown in the menu |

Stock voices are free and work offline. Which exact voice you hear depends on the browser: `voice.yaml` lists several names in `prefer`, and the first one your browser has is used.

No film or TV character's voice is included, and none should be added: those are real actors' voices and they belong to them and the studios.

## Add a stock voice

1. Copy `butler/` to a new folder, for example `voices/narrator/`.
2. Edit `voice.yaml`: the name, the `lang` (for example `en-IN`), the voices to `prefer`, and the `rate` and `pitch`.
3. Restart `aegis serve`. The new voice is in the menu.

To see which voice names your browser has, open its console and run `speechSynthesis.getVoices().map(v => v.name)`.

## Add a real person's voice

Only do this with a recording the person made themselves, for this purpose.

1. Copy `_template/` to a new folder, for example `voices/my-voice/`.
2. Record the script below and save it in that folder as `sample.wav`.
3. In `voice.yaml`, the speaker writes the `consent` line in their own words, for example:
   `consent: "I recorded this myself on 16 Nov 2026 and I agree to it being used as the Aegis assistant voice."`
4. Restart `aegis serve`.

The voice shows in the menu as "not ready" until the cloning engine is installed. That is the next step in [`docs/PLAN.md`](../docs/PLAN.md). A cloned voice with no consent line is never loaded.

Personal voice folders are kept out of Git by `.gitignore`, so a recording cannot be pushed by accident. Keep it that way. If you use an online cloning service, delete the voice from it when you are done.

### How to record

- A quiet room. Fan, TV and music off.
- The phone about a hand's length from the mouth.
- A calm, steady tone: the way you want the assistant to sound.
- Read the script twice in one go. That gives about two minutes.
- Save in the highest quality the phone allows. Do not edit the recording.

### The script

> Good morning. I've gone through everything that came in overnight, and there are three things you should know. First, the payment service is slow again. Error rate crossed forty percent at 9:15, and it started four minutes after a config change. Second, I checked the logs, the metrics and the traces, and they all point to the same place. Third, I have a fix ready, but I won't touch anything until you say so.
>
> Should I roll it back, or do you want to look at the evidence first? It's your call. Go, or no-go?
>
> Done. The rollback is complete, errors are back under one percent, and the dashboard is green. I've drafted the update for the team. Would you like to hear it, or shall I just send it?
>
> By the way, it's past two o'clock, your next meeting is in thirty minutes, and you still haven't had lunch. Just saying.
