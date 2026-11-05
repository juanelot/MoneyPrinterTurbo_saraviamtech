# Stickman Video Director (prompt maestro)

> Adaptado de https://github.com/kaomei/stickman-video-director (licencia MIT, autor kaomei), commit eb4bb37.
> Solo el modo A (Director: propuesta + prompts para clips). El modo B (Autopilot, renderizador local
> con Gemini/ElevenLabs) no se incluye. Las referencias `references/*.md` van como secciones abajo.

## Ajustes para este estudio

- En la primera pregunta (setup gate), además de formato, duración y estilo, pregunta el **idioma de la narración**
  (por defecto inglés, como el original). Si es otro idioma, escribe la narración y el bloque de voz en ese idioma
  y conserva la traducción de referencia en el idioma de la persona. Los prompts visuales siguen en inglés.
- Los clips se generan en Google Flow (Gemini Omni Flash / Veo). Estilos 1–5: cada clip dura ~10 s = 1 escena.
- La narración de cada clip es la narración de esa escena (la app la usa para la voz y para alinear escenas).
- **Estilo 6 (A6 · Amber Noir)**: clips de Veo 3.1 Fast de **máximo 8 s**, cada uno a partir de una imagen de
  primer fotograma (Nano Banana en Flow). Por cada escena entrega: narración exacta, prompt de imagen de primer
  fotograma completo (estilo + reparto + mundo + composición + restricciones) y un prompt de movimiento corto
  (actor que NO habla, sin texto de narración). La voz NO es Gemini Puck: la pone el estudio (voz Microsoft o la
  grabación del usuario) y los subtítulos/títulos los añade el estudio al renderizar. No hay ruta Renoise.
  Imágenes de estilo de muestra en `prompts_maestros/stickman_a6_referencias/` (solo estilo, no reparto).


---

# Directing Stickman Videos

## Core contract

Turn one source into a confirmed director's proposal and then N standalone prompts for approximately ten-second Gemini Omni Flash clips (where N = target duration in seconds / 10; default 6 clips for 60 seconds). Preserve the source's meaning while structuring it through a high-completion 5-stage emotional narrative arc.

## Setup gate

Require these before planning:

- source material
- aspect ratio: `16:9` or `9:16`
- target duration: in multiples of 10 seconds (e.g. `30s`, `60s`, `90s`, `3min`, `5min`; default: `60s` / 6 clips if unspecified)
- visual style and theme:
  - `Style 1 (Classic Minimalist)`: light (white background, black figure) or dark (black background, white figure)
  - `Style 2 (Modern Beanie Zeke)`:
    - `Style 2A (Modern Studio Tech)`: pure white high-key studio, subtle light-gray perspective grid, floating cyan/blue glass UI
    - `Style 2B (Cinematic Story)`: full-color narrative environments, cinematic lighting & depth
  - `Style 3 (Prehistoric Hand-Drawn / Dark Comedy)`: expressive white filled heads, black stick limbs, animal-hide costumes and earthy prehistoric settings; story-specific casting
  - `Style 4 (Cozy Storytelling / 治愈故事风)`: expressive minimalist white-filled characters with dark stick limbs in full-color 2D cartoon environments; varied story locations and cinematic shot changes
  - `Style 5 (Historical Cartoon / 历史卡通风)`: white heads with connected short white necks, expressive faces, black stick limbs and compact fingerless palms, period dress and cel-shaded historical settings
  - `Style 6 (A6 · Amber Noir / 暖金暗影风)`: matte-black round heads with connected short black necks, cream-white eye marks, amber light and deep plum shadows in layered illustrated settings; image-first Veo clips of at most 8 s (see the A6 section at the end; it bypasses the A1–A5 contract)

If aspect ratio or visual style is missing, ask for all missing items in one concise message and stop. If duration is omitted, default to 60 seconds (6 clips). If a user provides a duration not divisible by 10, round to the nearest 10-second multiple. If a user specifies only light or dark theme, default to Style 1. Never select an aspect ratio or style silently. Do not re-ask choices already supplied.

Urgency, generation cost, client pressure, and requests to "pick normal settings" do not waive this gate.

## Workflow

1. Read `references/storyboard-template.md`, `references/style-catalog.md` and `references/voice-continuity.md`. Structure the narrative using the **5-Stage High-Completion Heartbeat Engine** (Golden Hook → Disrupting Assumptions → Unveiling Insider Secrets → Ultimate Truth Revelation → Elevation & Interactive Discussion), with timing dynamically scaled to the target duration. Produce Phase A in the user's language, with English VO and a reference translation.
2. Stop after the director's proposal and request explicit approval.
3. If the user changes ratio, duration, style, theme, narration, scene structure, or global direction, recompose Phase A and request approval again.
4. Only after approval of the current Phase A, read `references/omni-flash-prompt-contract.md` and produce Phase B.
5. Use `references/examples.md` only when a concrete end-to-end example would resolve ambiguity.

Topic approval, schedule pressure, or approval of an older draft is not approval of the current Phase A.

## Output rules

For Style 3, read `references/prehistoric-dark-comedy.md` before planning. Its casting, story rhythm, palette and continuity rules override the generic no-idle, device-count and five-stage discussion-ending rules below. Use setup → escalation → ironic payoff for narrative shorts; do not force a discussion question into a visual punchline. This is a visual storytelling style, not a claim about actual prehistory.

For Style 4, read `references/cozy-storytelling.md` before planning and prompt assembly. Default each new ten-second segment to a different recognizable story setting, unless the user explicitly requests one location or approves a deliberate return. Preserve characters, drawing grammar, important props, movement direction and narrator—not an identical table or background across the whole video. Name the location cuts and any time jumps in Phase A. This is full-color cartoon storytelling, not a hand-drawn/sketchbook mode and not a claim of photorealistic 3D backgrounds.

For Style 5, read `references/historical-cartoon.md` before planning and prompt assembly. Keep its drawing grammar fixed while changing the era pack. Confirm story-specific cast cards, setting, palette, props and exact narration in Phase A; repeat the full approved style and visible cast descriptions in every Phase B prompt. Its historical palette, music, physical-action pacing and story ending override generic three-color, mandatory-piano, device-count, no-idle and discussion-ending rules below. Apply the existing shared voice contract; do not apply this style's character rules to Styles 1–4.

- Structure every script using the 5-stage high-completion flow:
  1. **Golden Hook**: Instant curiosity trigger via a counter-intuitive question or visual paradox. Timing is flexible based on duration (e.g. within the first 2–5 seconds in short videos, up to 10–15s in long videos); never open with generic platitudes.
  2. **Disrupting Assumptions**: State what everyone thinks is true, then shatter it in one sentence to build cognitive conflict.
  3. **Unveiling Insider Secrets**: Pull back the curtain on hidden mechanics, counter-intuitive details, or the real obstacle.
  4. **Ultimate Truth Revelation**: Deliver the underlying business logic or human psychology truth with maximum cognitive payoff.
  5. **Elevation & High-Engagement Discussion**: Conclude with a memorable punchline and an irresistible discussion prompt that sparks debate in the comments.
- Scale English VO word count to approximately 20–25 words per 10-second clip across N clips (e.g. ~60–75 words for 30s / 3 clips, ~120–150 words for 60s / 6 clips, ~360–450 words for 3min / 18 clips, ~600–750 words for 5min / 30 clips).
- Give each clip three timed beats, at least four relevant visual devices, and a visual change every two to three seconds.
- Keep character proportions, line weight, style, and narrator consistent across all clips.
- For Style 1, freeze the concise character anchor from `references/style-catalog.md` and repeat it verbatim in every clip. Keep two arms and two legs, one current pose per limb, stable proportions and uniform medium line weight; a moving arm replaces its previous pose rather than adding another arm. Keep the figure monochrome and saturated accents on props/graphics. Do not replace the anchor with "same character", ellipses, numeric anatomy recipes, skeleton/path instructions or clip-specific appearance descriptions. Occasional simple line expressions are allowed; the head remains hollow. Keep rich actions and effects separate from character design. Treat generated consistency as a visual acceptance check, not a guarantee from repeated text.
- For Style 1, limit the video to three saturated accent colors named with ordinary descriptive words (e.g. vivid red, electric blue, warm gold). For light theme, enforce a flat, digitally pure-white canvas with no textures, gradients, or 3D depth.
- For Style 2 (Modern Beanie Zeke), enforce character consistency:
  - Clip 1: `A minimalist 2D animated stick figure wearing a bright red beanie (smooth knit, no pom-pom) and a yellow t-shirt, with simple black stick limbs and shorts. Simple black lines, vibrant colors, smooth 2D animation style.`
  - Clips 2–N: `The same minimalist 2D animated stick figure in a bright red beanie and yellow shirt... Simple black lines, vibrant colors, smooth 2D animation style.`
  - No detailed eyes, pupils, or photorealistic features (avoids bug-eye deformation).
- For Style 2A (Modern Studio Tech), enforce: `in a modern bright white studio space with subtle light-gray perspective grid lines on the floor plane. High-key studio lighting, clean white negative space, sleek glowing cyan and electric blue glass holographic UI elements.` Always include negative constraint: `STRICTLY MINIMALIST, NO CIRCUIT BOARD TEXTURES, NO SCI-FI WALL PANELS, NO CRACKED CONCRETE.`
- For Style 2B (Cinematic Story), specify full-color narrative setting and cinematic lighting while preserving the 2D animated stick-figure character design.
- For Style 4, freeze each approved character's complete anchor and repeat it in every clip where that role appears. Separate static design from first-frame positions, timed prop transfers and final states; changing scene does not reset prop ownership or the narrator. Read its reference for shot variety and visual acceptance checks.
- For all styles, avoid abstract liquid/shape morphing. Drive motion with concrete character actions (leaping, touching glass, drawing luminous lines, opening doors) with timed beats across `[0–3s]`, `[3–7s]`, and `[7–10s]`. Never leave the character idle.
- For **all styles**, apply `references/voice-continuity.md`: choose a complete video-level voice profile in Phase A, then repeat its full frozen English block verbatim in every clip. Different videos may choose different voices; a scene/style/character change must not recast the narrator. Lock timbre, register, accent, texture, delivery, pace and recording treatment, not just "same narrator". Keep emotional progression in visuals/music. Style-specific music rules never override this shared voice contract. Mandate BGM continuity from clip 1.
- Treat narration as audio-only (`Audio voiceover only, strictly no speech bubbles, no dialogue boxes`). Quote exact dialogue and forbid alteration, repetition, captions, subtitles, or visual transcription.
- Never place technical color notation (hex, RGB, Pantone) inside generation prompts.
- Default generated clips to no visible words, letters, numbers, or interface copy. Put optional two-to-five-word overlays in a separate post-production note.
- Match every clip ending to the next clip opening through action, an important prop, screen direction or a planned cut. Style 4 uses deliberate scene changes or approved time jumps; it does not require the same background in adjacent clips.
- Do not invent unsupported facts, statistics, quotations, or product claims.

## Revision rules

Recompose rather than rename:

- `16:9`: stage action across left, center, and right; use lateral tracking and negative space.
- `9:16`: use depth, stacked motion, vertical reveals, and interface-safe placement.

Theme, ratio, duration, or style changes require a fresh visual balance check. A global change invalidates prior approval.

## Final check

Apply the checklist in the loaded reference. Repair any failed condition before responding.

---

# references/style-catalog.md

# Style Catalog: Visual Styles & Prompt Formulas

This catalog defines the supported visual styles for `directing-stickman-videos`, including character DNA locks, environment specifications, motion pacing, and negative constraints.

---

## 1. Style Matrix Overview

| Style Key | Style Name | Visual Theme | Best For | Character Design |
|---|---|---|---|---|
| **Style 1** | Classic Minimalist (Light / Dark) | Pure white or black canvas, monochrome lines, up to 3 saturated accent colors | High-density explainers, pure logic, mental models, fast-paced cognitive concepts | Hollow circle head, single-line body, no clothing, occasional simple line expressions |
| **Style 2A** | Modern Beanie - Studio Tech (极简科技风) | Pure white high-key studio, subtle light-gray perspective grid, glowing cyan/blue glass UI | Tech tutorials, AI tool breakdowns, career insights, methodology breakthroughs | Red beanie (no pom-pom), yellow t-shirt, black stick limbs, smooth 2D animation |
| **Style 2B** | Modern Beanie - Cinematic Story (彩色故事风) | Full-color narrative environments, cinematic lighting & depth (warm room, dusk, desert, summit) | Emotional storytelling, personal growth, motivational journeys, narrative hooks | Same red beanie & yellow t-shirt figure staged inside rich environmental lighting |
| **Style 3** | Prehistoric Hand-Drawn / Dark Comedy (史前手绘 / 黑色幽默) | Earthy prehistoric environments, warm fire accents, subtle paper texture | Satirical stories, visual analogies, ironic callbacks | White filled heads, expressive cartoon faces, black stick limbs, variable story-specific cast |
| **Style 4** | Cozy Storytelling (治愈故事风) | Full-color 2D cartoon locations, gentle atmospheric light, varied cinematic shots | Relatable life stories, emotional growth, educational storytelling | White filled round head and slim torso, dark stick limbs, simple expressive face |
| **Style 5** | Historical Cartoon (历史卡通风) | Full-color painterly historical settings, clean cel shading, era-specific wardrobe and props | History explainers, historical daily life, civilization stories and historical comedy | White filled round heads with connected short white necks, expressive individual faces, solid black oval eyes, thin black exposed limbs and small solid black mitten-shaped palms continuous with the wrists, one subtle integrated thumb lobe, no individual fingers, finger separations, white fills or gloves |

For Style 3 read `prehistoric-dark-comedy.md`. It overrides this catalog's generic motion and piano rules. Fix the drawing grammar across stories, not one universal face; fix each approved character within a story.

For Style 4 read `cozy-storytelling.md`. Treat locations as story beats, not one universal room. Its English display name is **Cozy Storytelling**; do not rename it Sketchbook Stories, hand-drawn, or prehistoric.

For Style 5 read `historical-cartoon.md`. Freeze the drawing grammar; change the era pack, not the character rendering system. Use its cast cards, historical palette and story-appropriate music together with `voice-continuity.md`.

---

## 2. Style 1: Classic Minimalist

### Polarity & Background
- **Light Theme**: Flat, uniform, digitally pure-white canvas. Strictly forbid gray tint, paper texture, gradients, shadows, lighting, bloom, fog, or 3D depth.
- **Dark Theme**: Flat, uniform, pitch-black canvas. Pure white line art with high-contrast accent colors.

### Character DNA

**Classic Dark — tested faceless base:**
```text
Use minimalist two-dimensional white line animation. Show the same consistent stick figure with a hollow circular head, no face, no eyes, no mouth, no hair, no clothing, no filled body, stable proportions, connected line limbs, and uniform medium line weight. Exactly two arms and two legs are visible per figure. Each limb appears only in its current pose: raising or lowering the right arm replaces that arm's previous line, never leaving a resting arm beneath an active arm. The figure stays white; accent colors affect only props and graphic effects.
```

**Classic Light — tested faceless base:**
```text
Use minimalist two-dimensional black line animation. Show the same consistent stick figure with a hollow circular head, no face, no eyes, no mouth, no hair, no clothing, no filled body, stable proportions, connected line limbs, and uniform medium line weight. Exactly two arms and two legs are visible per figure. Each limb appears only in its current pose: raising or lowering the right arm replaces that arm's previous line, never leaving a resting arm beneath an active arm. The figure stays black; accent colors affect only props and graphic effects.
```

Choose the theme, then freeze its full anchor and repeat it verbatim in every clip. Do not expand it into numeric ratios, skeleton/rig definitions, pen paths, separate hand/foot shapes or body-volume descriptions. Keep pose, movement, props and camera in the timed sequence, not in competing character definitions. The current-pose rule applies to every limb; if the approved story uses a left-arm lead action, adjust the handedness once before freezing, never clip by clip. Preserve energetic actions and rich effects; draw motion trails on props or detached graphics, not as additional limb poses.

Occasional simple line expressions are allowed by default. Before freezing either base anchor, replace only "no face, no eyes, no mouth," with "occasional simple line expressions, no detailed facial features," and keep the prompt's negative constraints compatible with that choice. If the user explicitly requests a faceless character, keep the base unchanged. Expressions never change head fill, head outline, body structure or proportions; no detailed eyes, pupils or realistic facial rendering.

2026-10-13 Flow retest: Omni 1.1 Flash, 16:9, 720p, independent 10s clips for a paper-airplane/perfectionism story. The final Dark base was used in three clips plus two repeated high-risk clips; the Light base was used in two clips. Browser-sampled action frames did not show extra limbs or sudden head enlargement in these final samples. Hand/foot endpoints and cross-clip line weight can still vary; this is not frame-by-frame certification or a guarantee for future generations. The expression-enabled and left-handed variants were not separately tested. Detailed scope and asset IDs are in `tests/reports/classic-character.md` at repository level. Prop continuity and audio were not accepted by this character-only check.

### Palette Contract
- Maximum of three saturated accent colors named with ordinary words (e.g., vivid red, electric blue, warm gold).
- No technical color notations (hex, RGB, Pantone).

---

## 3. Style 2: Modern Beanie Zeke

### Character DNA Anchors (Anti-Deformation Lock)

To prevent character drift, bug-eye deformations, or clothing loss across clips, use these exact character anchors:

**Clip 1 Character Anchor:**
```text
A minimalist 2D animated stick figure wearing a bright red beanie (smooth rounded knit, no pom-pom) and a yellow t-shirt, with simple black stick limbs and shorts. Simple black lines, vibrant colors, smooth 2D animation style.
```

**Subsequent Clips Character Anchor (Clips 2–6):**
```text
The same minimalist 2D animated stick figure in a bright red beanie and yellow shirt... Simple black lines, vibrant colors, smooth 2D animation style.
```

**Deformation Prevention Rules:**
- **No Realistic Facial Features**: Hollow circular head or minimal dot eyes only. Never request detailed pupils, irises, or photorealistic facial contours (which trigger alien bug-eyes).
- **No Pom-Poms**: Specify smooth rounded beanie top to prevent erratic pom-poms or winter tassels.
- **Always Include Both Beanie and T-shirt**: Omitting the shirt results in naked stick bodies; omitting the beanie results in standard Style 1 characters.

---

### Sub-Style 2A: Modern Studio Tech (极简科技风)

**In Plain Language**: Apple 发布会式极简科技风。纯白亮面高光空间 + 极淡浅灰透视地砖网格 + 悬浮青蓝半透明玻璃 UI/微光质感。

#### Environment Specification
```text
in a modern bright white studio space with subtle light-gray perspective grid lines on the floor plane. High-key studio lighting, clean white negative space, sleek glowing cyan and electric blue glass holographic UI elements.
```

#### Mandatory Negative Constraints (Anti-Clutter)
Without explicit negative constraints, diffusion models tend to generate motherboard circuitry, spaceship corridors, and cracked concrete. **Always append this negative clause in 2A prompts:**
```text
Negative constraints: strictly minimalist studio aesthetic, no circuit board textures, no sci-fi wall panels, no spaceship corridors, no cracked concrete, no grunge textures, no photorealistic human skin, no speech bubbles, no dialogue text boxes.
```

#### Motion Dynamics (Anti-Stutter & Anti-Lag)
- **Do not use abstract liquid/morphing transformations** (e.g., stairs melting into a clock), which trigger latent flicker and stuttering.
- **Use physical, character-driven interactions**:
  - Leaping and bumping an invisible glass ceiling with a comedic bounce.
  - Tapping a sneaker onto the floor grid to emit an expanding cyan ripple wave.
  - Pulling out a glowing light-pen to draw a crisp luminous line bridge across an abyss.
  - Touching a sleek floating glass panel to reveal an icon-only illuminated lock.
  - Pushing open a heavy minimalist vault door to step forward into bright horizon light.
- **Pacing**: Every 10-second clip must feature distinct actions across `[0–3s]`, `[3–7s]`, and `[7–10s]`. Never let the character stand idle or stare at the camera for multiple seconds.

---

### Sub-Style 2B: Cinematic Story (彩色故事风)

**In Plain Language**: Pixar 故事短片风。全彩沉浸式场景（暖光台灯卧室、黄昏窗前、荒野公路、云端山顶）+ 电影叙事光影。

#### Environment Specification
```text
in a rich full-color cinematic environment [describe setting: e.g., a dimly lit cozy bedroom with warm lamplight / a vast open desert highway under a glowing dusk sky / a dramatic mountain ridge above rolling golden clouds]. Cinematic volumetric lighting, soft depth of field, atmospheric narrative mood.
```

#### Character & Style Consistency
- The character remains the same minimalist 2D stick figure in red beanie and yellow shirt.
- Maintain smooth 2D vector animation aesthetics for the character even within a textured, atmospheric background.

#### Negative Constraints
```text
Negative constraints: no photorealistic human skin or faces, no 3D humanoid CGI uncanny valley models, no chaotic line glitches, no speech bubbles, no dialogue text boxes.
```

---

## 4. Style 4: Cozy Storytelling (治愈故事风)

Minimalist expressive characters inside colorful cartoon worlds: an office, a metro platform, a street-side cafe, a park or another story-appropriate setting. Use close action inserts, wide establishing views, lateral tracking and motivated location cuts. Warmth belongs to the visual treatment; preserve the source's conflict and meaning rather than making every topic cheerful.

Each new ten-second segment normally establishes a different location. Keep the character, important props, screen direction and full voice profile consistent, while deliberately changing scenery. A new camera angle on the same desk is not a substitute for a new story location. Single-location requests and approved callbacks remain valid exceptions.

Use the full character anchor, prop-state rules and acceptance checklist in `cozy-storytelling.md`; do not inherit Style 1's hollow-head/no-face/no-filled-body bans or Style 3's crude sketch/animal-hide rules.

---

## 5. Style 5: Historical Cartoon (历史卡通风)

Expressive stick-figure characters in historical costume, staged in colorful painted landscapes and architecture. Use wide establishing views, readable character actions, reaction close-ups and motivated cuts. Design the cast for the story: a Roman soldier, an Edo-period student or an Egyptian temple attendant need different wardrobe and props, not different drawing grammar.

Use `historical-cartoon.md` for the full style anchor, era-pack template, cast cards and prompt assembly. Visual concept and Roman era-pack contribution: [@leksautomate](https://github.com/leksautomate).

---

## 6. Universal Audio Continuity Contract

Voice continuity is a shared foundation for **all styles**, including Styles 3 and 4. Apply `voice-continuity.md` before style-specific music rules. Different videos can choose different voices, while all clips of one video repeat one complete approved voice profile. Keep voice identity separate from the musical arc.

### Narrator Voice Lock
```text
One off-screen adult male narrator throughout. General American accent, warm clean baritone, medium-low pitch, gentle chest resonance, no raspiness or breathiness. Calm conversational delivery, restrained pitch variation, steady speaking pace, and close, dry studio sound. Keep the same vocal timbre, register, accent, pace, and recording quality throughout. Emotional progression belongs to the visuals and music; do not change the narrator's voice or switch to character dialogue.
```
This is the user-accepted male example, not a compulsory voice for every project. For female, older, youthful or other approved voices, resolve a complete coherent profile using `voice-continuity.md`, then repeat it verbatim across every clip. Do not use only "same narrator" or inherit a prior clip by name. Keep narration audio-only, voice-first, with no speech bubbles or dialogue boxes. Actual listening acceptance exists for the Style 2A Hope sample; other profiles/styles remain untested for audio matching.

### BGM Continuity Lock
- **Clip 1**:
  ```text
  Audio: Voiceover clearly audible over quiet, thoughtful piano and subtle soft ambient synth, building gentle optimistic momentum.
  ```
- **Clips 2–6**:
  ```text
  Audio: Voiceover seamlessly continues the identical quiet, thoughtful piano and subtle soft ambient synth from clip 1, maintaining identical tempo, instrumentation, and optimistic narrative momentum. Synchronized crisp SFX on physical actions.
  ```

---

## 7. Visual Beat Pacing Template (10-Second Clip)

Every prompt must divide its 10 seconds into three active narrative beats:

```text
Timed Synchronized Visual Beats:
- [0–3s] (VO: "..."): [Setup / premise action — character enters, acts, or inherits momentum from previous clip]
- [3–7s] (VO: "..."): [Escalation / discovery — character interacts with environment or solves visual obstacle]
- [7–10s] (VO: "..."): [Climax & outgoing transition — character delivers payoff and initiates outgoing motion for next clip]
```

---

# references/storyboard-template.md

# Director's Proposal Contract

Use this contract for Phase A. Present a readable production proposal and stop for confirmation before writing model prompts. Refer to `references/style-catalog.md` for style specifications.

Style 3 (Prehistoric Hand-Drawn / Dark Comedy) is also supported. Before planning it, read `prehistoric-dark-comedy.md`; its cast-card, earthy palette, setup/escalation/payoff and reaction-pause rules override the generic five-stage, mandatory discussion-ending and device-count checks here. Include distinguishable cast cards and a location/prop continuity plan in Phase A. Treat the story as fictional analogy, not invented historical fact.

Style 4 (Cozy Storytelling / 治愈故事风) uses `cozy-storytelling.md`. In Phase A name a different recognizable main setting for each new ten-second segment by default, plus wide/close/moving shots inside it. Lock character design, important props and narration; scenery changes intentionally. Respect an explicit single-location request or approved callback. Do not call this style hand-drawn or require the same table/room across all segments.

Style 5 (Historical Cartoon / 历史卡通风) uses `historical-cartoon.md`. Include its era pack, complete cast cards, location/prop states, exact VO and shared `voice-continuity.md` profile in Phase A. Keep the drawing grammar while adapting clothing, architecture, palette and music to the era. Its narrative-short ending and physical-action pacing override generic discussion-ending and four-device requirements; reactions may pause deliberately. Separate historical facts from invented comic scenes.

## Rewrite the source

Create one natural English narration scaled to approximately 20–25 words per 10-second clip based on the target duration (e.g. ~60–75 words for 30s, ~120–150 words for 60s default, ~360–450 words for 3min, ~600–750 words for 5min).

- Preserve the source's core claim, names, numbers, and factual meaning.
- Strengthen a weak opening with an immediate hook.
- Remove repetition and secondary branches from long sources.
- Expand short sources with a relevant example, progression, reframe, or callback.
- Prefer clear spoken English to literal translation.
- Simplify wording before increasing speaking speed.
- Do not invent research, statistics, quotations, product claims, or factual details.

Use the user's language for planning explanations. Keep the voiceover in English and give a reference translation in the user's language.

## Header contract

Present these items in order:

1. English title and reference-language title
2. Core message and opening hook
3. Chosen aspect ratio (`16:9` or `9:16`), target duration (in 10s multiples), and visual style/theme (Style 1 Classic Light/Dark, Style 2A Modern Studio Tech, or Style 2B Cinematic Story)
4. Narrator's complete video-level voice profile from `voice-continuity.md` (identity/age, accent, timbre, register, resonance, texture, delivery, pace and recording treatment), English word count, and estimated duration
5. Up to three saturated accent colors (for Style 1) or visual palette/environment mood (for Style 2), named in ordinary language, and what each represents
6. BGM direction, emotional turn, tone, and narrative arc

Default the narrator only after required setup is complete: propose a source-appropriate female, male or other coherent voice profile for approval, not a mandatory universal baritone. Expand short preferences such as "male voice" into the complete fields in `voice-continuity.md`. Different videos may choose different voices, but one video's clips share its frozen profile. Separate the narrative emotional arc from stable vocal identity and delivery. Infer tone and palette from the source when the user did not specify them.

## Narrative patterns: High-Completion 5-Stage Heartbeat Engine

To break through the 60%+ video completion rate threshold, structure every script through this emotional heartbeat progression:

1. **Stage 1: Golden Hook (黄金钩子)**
   - **Timing**: Flexible based on duration (in short 30s/60s videos, delivered rapidly within the first 2–5 seconds / `[0–3s]` of Clip 1; in 3–5min videos, establishes the premise across the first 5–15 seconds).
   - **Goal**: Ask an unexpected, counter-intuitive question or present a striking visual paradox that instantly creates an irresistible information gap. Never open with slow throat-clearing.
2. **Stage 2: Disrupting Assumptions (打破常识)**
   - **Goal**: Articulate the common belief or conventional wisdom that everyone assumes to be true, then shatter it in a single decisive sentence to create cognitive conflict and suspense.
3. **Stage 3: Unveiling Insider Secrets (拉出内幕)**
   - **Goal**: Pull back the curtain on a little-known technical mechanism, hidden friction, or systemic secret that keeps the audience captivated and curious.
4. **Stage 4: Ultimate Truth Revelation (真相揭秘)**
   - **Goal**: Deliver the underlying business logic, scientific mechanism, or human psychological truth with complete clarity. Give the audience the satisfying "aha!" breakthrough.
5. **Stage 5: Elevation & High-Engagement Discussion (升华互动)**
   - **Goal**: Crystallize the takeaway into a memorable punchline, and finish with a provocative, open-ended discussion question that compels viewers to take sides and debate in the comments.

### Dynamic Clip Allocation by Duration ($N = \text{duration} / 10$)

- **30s (3 clips)**:
  - Clip 1: Lightning hook (0–3s) → Establish conflict
  - Clip 2: Unveil hidden reality & mechanics
  - Clip 3: Ultimate truth + Comment-debate prompt
- **60s (6 clips, default)**:
  - Clip 1: Golden Hook (counter-intuitive question) → Premise
  - Clip 2: Disrupt Assumptions (shatter conventional wisdom)
  - Clip 3: Unveil Insider Secrets (hidden friction)
  - Clips 4–5: Mechanism & Ultimate Truth (cognitive satisfaction)
  - Clip 6: Elevation punchline + Irresistible comment question
- **90s (9 clips)**:
  - Clip 1: Golden Hook
  - Clips 2–3: Disrupt Assumptions
  - Clips 4–6: Unveil Insider Secrets
  - Clips 7–8: Ultimate Truth Revelation
  - Clip 9: Elevation & Comment Discussion
- **180s+ (3–5 min)**:
  - Hook (Clip 1) → Assumptions (15–20%) → Insider Secrets (35–40%) → Ultimate Truth (30–35%) → Elevation & Discussion (final 1–2 clips)

## Storyboard contract

Produce exactly N approximately ten-second rows (where N = target duration in seconds / 10; default: 6 rows for 60s):

| Time | Narrative purpose | Stick-figure scene | Motion, camera, and transition | English VO | Reference translation | BGM / SFX |
|---|---|---|---|---|---|---|

Give each row a different narrative job aligned with the 5-stage engine. Allocate approximately 18–25 English words per row while keeping sentence boundaries natural.

## Visual-density recipe

Build every row from three sequential beats:

- `0–3s`: establish or inherit the visual premise.
- `3–7s`: transform, escalate, or explain the metaphor through physical character actions.
- `7–10s`: deliver a climax and create the next transition.

Use at least four relevant devices per row:

- expressive stick-figure action (running, jumping, touching glass, drawing lines)
- environmental transformation
- concrete visual metaphor
- diagram, arrow, or icon-only symbol
- particles, energy, fluid, explosion, or light
- camera push, pull, pan, orbit, shake, or tracking move
- foreground wipe or object crossing the lens
- match cut, shape morph, or motion-matched transition
- interaction with another figure or oversized object

Require a perceptible visual change every two to three seconds. Make every effect clarify or intensify the spoken idea; omit unrelated spectacle. Avoid abstract liquid morphing.

## Palette and text

Keep the background and stick figure monochrome according to the selected theme (for Style 1), or use high-key studio grid / cinematic lighting (for Style 2). Use no more than three saturated accent colors across the video. Assign semantic meaning such as anxiety, danger, energy, discovery, or success.

Name colors only with ordinary descriptive language. Do not use hexadecimal, RGB, HSL, Pantone, or other technical color notation anywhere in the proposal or production prompts.

Default the generated video to no visible words, letters, numbers, captions, subtitles, interface copy, or technical annotations. Make message bubbles, content cards, meters, clocks, and notifications icon-only. After the storyboard, optionally list concise two-to-five-word English overlays for post-production, including their target clips and safe placement; never carry those overlays into the video-generation prompts.

## Composition by aspect ratio

- `16:9`: use left-center-right staging, lateral tracking, horizontal match cuts, and deliberate negative space. Reserve clean space for optional post-production overlays when useful.
- `9:16`: use foreground/background depth, vertical reveals, stacked motion, foreground passes, and interface-safe overlay space.

Changing ratio requires new staging, camera paths, transition geometry, and overlay-safe negative space. Changing theme or style requires updated color balance and contrast checks.

## Continuity

End each row with a visible interface that the next row inherits: a pose, moving object, filled frame, travel direction, shape, or camera motion. Name both sides of every connection in the proposal. For Style 4, an approved location cut or time jump may replace literal background matching: state what continues (character, prop, direction or story action) and what changes (place/time). Do not spend all N clips at the same desk unless explicitly requested.

## Confirmation ending

End Phase A by asking the user to:

- approve the current proposal and generate the N Omni Flash prompts;
- revise a named scene or narration passage; or
- change a global setting such as aspect ratio, duration, style, theme, palette, voice, or tone.

Do not include final model prompts. A global change invalidates approval and requires a revised Phase A.

## Phase A checks

- Source, aspect ratio (`16:9` or `9:16`), duration, and style/theme are known.
- Script strictly implements the 5-Stage High-Completion Heartbeat Engine.
- Final clip ends with a provocative, comment-driving discussion prompt.
- English narration matches duration (~20–25 words per 10s clip; ~120–150 words for 60s).
- Exactly N storyboard rows have distinct narrative purposes (N = duration / 10).
- Every row has three beats, at least four visual devices, audio, and a transition.
- Visual change occurs approximately every two to three seconds.
- No more than three saturated accent colors are used (for Style 1) or clean palette rules followed (for Style 2).
- No technical color notation is present.
- Any proposed text is clearly separated as a post-production overlay and absent from generated scenes.
- Every adjacent pair has a named continuity connection.
- The ending returns to the central message and CTA.
- No unsupported factual detail was added.
- One complete voice profile is proposed for the whole video, independent of visual style; scene-specific audio notes do not contradict it. Any approved multiple speakers have separate stable profiles and explicit line assignments.

---

# references/voice-continuity.md

# Shared voice continuity — all visual styles

Scope: **A · Director text-to-video prompts only**. B · Autopilot uses named TTS voices under `autopilot.md`; do not copy this document's descriptive voice profiles into any B-style TTS request.

This is the common voice contract for Style 1 Light/Dark, Style 2A, Style 2B and Style 3, plus Style 4 Cozy Storytelling. Voice identity belongs to the video, not to a visual style or a clip. Different videos may choose different voices; every clip of one video must use the same complete approved voice profile. Do not force every project into the tested male profile.

## Choose once in Phase A

Honor the user's voice choice. If unspecified, propose one suitable voice for approval rather than adding another mandatory setup question. Describe perceived gender/age, accent, timbre, pitch/register, resonance, texture (including breathiness/rasp), delivery/intonation, steady pace, and recording character. Name these in ordinary language, not a list of vague adjectives such as "warm, energetic, same narrator". Summarize the profile in the user's language. Resolve all attributes before producing prompts; no placeholders in production output.

For example, a male choice can become adult, General American, warm clean baritone, medium-low pitch, gentle chest resonance, no rasp/breathiness, calm conversational delivery, restrained pitch variation, steady pace, close dry studio recording. A bright female choice can instead become adult, General American, clear warm mid-high voice, gentle forward resonance, no rasp/breathiness, lively conversational delivery with controlled pitch variation, steady pace, close dry studio recording. Older, youthful or other requested voices need their own internally coherent profile; they do not inherit male/baritone traits. Alternative profiles are design examples, not independently provider-tested voices.

## Freeze once in Phase B

Write one self-contained English voice block from the approved profile and copy it **verbatim** into every standalone clip prompt, including clip 1. Never abbreviate it to "same narrator", "continue the voice from clip 1", an ellipsis or a speaker label alone. Independent prompts must carry their own complete voice instructions.

The following complete male block was accepted by the user after a three-clip Flow listening comparison. Reuse it unchanged when its attributes match the approved choice:

```text
One off-screen adult male narrator throughout. General American accent, warm clean baritone, medium-low pitch, gentle chest resonance, no raspiness or breathiness. Calm conversational delivery, restrained pitch variation, steady speaking pace, and close, dry studio sound. Keep the same vocal timbre, register, accent, pace, and recording quality throughout. Emotional progression belongs to the visuals and music; do not change the narrator's voice or switch to character dialogue.
```

For a different approved voice, compose its own complete block using the same identity/pitch/texture/delivery/recording fields, then freeze that block. Do not append contradictory attributes such as "bright high-pitched youthful voice" to a low baritone or "now shout dramatically" to restrained conversational narration.

## Separate voice, performance and music

- Keep the narrator off-screen and narration audio-only unless the user explicitly approves another arrangement. A change in character gender, age, scene, costume, lighting or visual style does not recast the narrator. No spontaneous lip-synced character dialogue, added speakers or grunts presented as new spoken lines.
- Put escalation, anxiety, triumph, deadpan reaction and cinematic intensity in action, editing, music and SFX. Do not rewrite the narrator's register, timbre, texture, accent, pacing or recording treatment by scene. Natural sentence emphasis and pauses may vary within the frozen delivery, without adopting a new character voice.
- Keep the voice close and dry even in caves or large halls; location reverb belongs to environmental SFX unless another recording treatment was approved. Preserve voice-first mixing. Music/SFX may follow their own approved arc; they do not override this voice contract. Style 3's primitive-percussion or reaction-pause rules change music/timing, not the frozen voice.
- Shorten excessive VO before changing the approved pace to squeeze it into a clip. A global voice change requires a revised Phase A and approval, followed by replacing the block in **all** clip prompts, not just one.
- For explicitly approved multi-speaker dialogue, freeze a separate complete profile for each recurring speaker and keep line-to-speaker assignments explicit. Repeat each appearing speaker's full profile in every relevant clip; identity stays consistent per speaker, rather than forcing all characters to sound alike. Do not add multi-speaker dialogue unrequested. For an explicitly silent video, omit speech instead of inserting a default narrator.

## Check and retest

Before delivery, compare all prompt voice blocks for exact equality (or per-speaker equality for approved dialogue). Check other prompt sentences for conflicting voice directions, confirm exact approved spoken lines, and keep speech-bubble/subtitle bans separate from the voice profile.

When generation is authorized, compare the actual clips by listening: perceived speaker identity, timbre, register, accent, pace, texture and recording sound. Successful generation or screenshots do not prove audio consistency. If clips sound like different people, first inspect missing/abbreviated/contradictory voice wording. Retest a voice-only change with story, visuals, dialogue, music and generation settings held fixed; leave the baseline available for comparison. Do not dismiss a prompt problem as unavoidable model behavior before this check. Further paid retries need the user's authorization.

The Style 2A Hope test on 2026-10-12 used three independent 10-second Omni 1.1 Flash generations. Only this voice block was changed; the user reported that the new clips sounded like one person and requested the shared rule. This is sample-specific user listening acceptance, not a universal guarantee. Other voice profiles and styles have not had separate provider-backed audio comparisons. Apply the shared instruction contract to all styles as requested while keeping that evidence boundary explicit.

Voice/audio references, if available, and one continuous external VO track are optional further controls when prompt-first refinement is insufficient or the user requests exact matching. They are not mandatory for the normal workflow and do not replace checking the frozen voice block. Do not claim that a reference was used when none was supplied.

---

# references/prehistoric-dark-comedy.md

# Style 3 — Prehistoric Hand-Drawn / Dark Comedy

## Fixed style, variable cast

Preserve the drawing grammar, not a single default face. Use crude hand-drawn 2D black outlines, white filled round heads, thin black stick limbs, expressive simple cartoon eyes/brows/mouths, animal-hide clothing, earthy ochre/brown scenery and small warm fire accents. Subtle paper texture and irregular outlines belong to this style; no photorealistic skin, glossy 3D characters or modern studio UI. Do not apply Style 1's hollow-head/no-face/no-clothes contract here.

Cast to fit the topic. Adults, children, elders and different genders can share this visual grammar without sharing a face. In Phase A provide a compact cast card for each named role: role and age range, head/body proportions, hair, eyebrows/eyes, optional facial marks, costume silhouette and one recognizable accessory. Give recurring characters at least two visible non-color differences. Do not identify gender through eyelashes alone or make every elder or child a stereotype. Keep the cast as small as the story needs; explicitly state which characters appear in each clip and forbid unintended duplicates.

New stories may use entirely new casts. Within one story, freeze each character's card and repeat its FULL description in every standalone prompt where it appears. Never use only “the same caveman” or an ellipsis as an identity lock. Lock white head fill, head/body proportions, hair, facial marks, costume and accessory. Expressions and poses may change; identity must not.

## Translate topics into concrete prehistoric situations

Identify the source's actual point, conflict and stakes first. Turn abstract mechanisms into physical tasks, incentives and props: endless recommendations may become a chief repeatedly offering snacks; workload may become a growing spear bundle; social pressure may become a small watching tribe. These are optional examples, not a recurring mandatory cast or plot. Settings can include caves, camps, forests, river crossings and rocky plains—not only the same cave bed.

Satire is fictional analogy. Do not present invented scenes as the historical origin of employment, technology or social behavior. Preserve scientific/technical explanations when relevant; if an analogy would distort the mechanism, explain it in VO or choose a clearer metaphor. Respect user requests for serious, gentle or non-comedic treatment rather than forcing ridicule.

## Story and timing

For a 30-second story use three ten-second clips: premise/conflict → tempting solution/escalation → reversal/callback. Scale to other approved durations. Keep approximately 18–25 spoken words per clip as a guide, not a quota; shorten VO to leave room for reaction beats. A deadpan glance or held expression of roughly half a second to two seconds can be the payoff. Do not insert effects every moment or force four devices into a quiet joke. Prefer clear action, expressive reactions, a motivated camera cut and synchronized SFX over irrelevant spectacle.

Use explicit timed physical beats and track prop ownership. State where an object starts, who hands it over and where it ends. Avoid spawning objects, teleporting stones, duplicated tools or characters changing costumes between shots. Draw a simple verbal layout, keep screen direction stable and reserve subtitle-safe space without requesting generated subtitles. In 16:9 use lateral staging; in 9:16 re-block for depth and vertical readability.

## Continuity and generation

Phase A includes cast cards, location layout, exact English VO with translation, music/SFX and named ending/opening states. Phase B repeats these anchors in each prompt. An intentional time jump may replace a literal match cut only if named in the approved proposal and stitching guide. Choose understated primitive percussion, dry pauses or another story-appropriate score; do not inherit mandatory optimistic piano from other modes. Repeat the selected music specification verbatim. Apply the shared `voice-continuity.md` contract: repeat the complete approved voice block verbatim in every clip, independently of music or cast age/gender. Deadpan character reactions and cave acoustics must not recast the narrator or add voice reverb. Narration is audio-only; no lip-sync unless approved.

When the interface supports it, reuse approved character images and prior ending frames as references. Check full voice-profile repetition and contradictory audio directions first when the narrator drifts; follow the authorized voice-only retest in `voice-continuity.md`. Prompt repetition is not a guarantee of matching faces, voice or music, and Style 3 audio has not been separately provider-tested with the new voice block. One external VO/BGM track is an optional polish control; preserve usable SFX and inspect the joins. Do not promise automatic Flow operation: this skill outputs a production package; generation, paid retries and publication require separate user authorization. If authorized, begin with a small test and stop to report material identity/action failures instead of spending indefinitely.

## Prompt assembly

Each prompt includes: duration/ratio → full drawing-style anchor → full cast cards for visible roles → location/layout and opening state → timed actions and prop transfers → exact quoted English VO → verbatim voice/music lock and timed SFX → ending state → negatives. Name colors naturally; never use technical color notation. Forbid visible text, subtitles, logos, speech bubbles, color swatches, extra humans, duplicate props, extra limbs and unintended identity changes. Do not forbid the cartoon faces, hair or texture that define this mode.

## Review checklist

- Source meaning retained; fiction is not mislabeled as history.
- Cast fits this story and is distinguishable without color alone.
- Every recurring role has the same complete anchor across clips.
- Correct head fill, clothing, drawing style and earthy palette.
- Actions readable; prop ownership and scene layout remain coherent.
- Payoff has breathing room; no forced comment question.
- Adjacent shots match or have an explicitly planned time jump.
- Generated footage contains no writing; subtitles are a post-production step.
- Voice/reference limitations are disclosed, not advertised as guarantees.
- The full voice profile is identical across clips, separate from the prehistoric score and cast design; alternative voices may be chosen for other stories.

---

# references/cozy-storytelling.md

# Style 4 — Cozy Storytelling / 治愈故事风

## Visual identity

Expressive minimalist characters in full-color 2D cartoon story environments. White filled round heads and slim white torsos contrast with dark stick limbs; the background carries color, atmosphere, gentle light and depth. Use clear cartoon contours and cinematic framing, not crude hand drawing, sketchbook borders, paper overlays or photorealistic/3D human characters. Do not inherit Style 1's hollow-head/no-face/no-filled-body bans or Style 3's animal-hide/cave defaults.

“Cozy” describes visual warmth, not a requirement that every script be cheerful. Preserve the user's meaning and the hook → conflict → insight → callback progression. Anxiety, science, education and serious life topics can use the same style. Settings and colors follow the topic, not a mandatory cafe, smartphone or pastel palette.

## Character design belongs to the story

Start with one protagonist for a simple explainer. Additional cast members must be explicitly planned, described and assigned to clips; do not spawn background commuters or clones. Freeze the complete design for each recurring role and repeat it verbatim wherever it appears. Different stories may choose other approved casts, but scene changes within one story do not recast them.

Default anchor, when the approved cast matches the samples:

```text
One minimalist 2D cartoon protagonist with a white filled circular head, two small dark oval eyes, simple eyebrow strokes and a short curved mouth. The torso is a slim closed tapered shape with solid white fill inside its dark outline. Both arms and both legs are dark single-line strokes with constant medium weight; hands are small dark rounded shapes and feet are short dark rounded strokes. No hair or clothing accessories. Keep the same head-to-body proportions, white head and torso fill, and outline weight in every shot. Exactly two arms and two legs exist; a moving limb replaces its previous pose rather than leaving another limb behind. Expressions change only the simple facial marks, never the head shape or character design.
```

Keep action, camera scale and props outside this design block. A close-up enlarges the entire character in the image; compare proportions, not raw pixel head size. Do not force covered limbs to show through tables, bedding or foreground objects. Temporary occlusion is not permission to add a replacement arm. Effects stay on props or detached graphics, not duplicated limb trails.

## New segment, new story setting

For a multi-clip video, default each new ten-second segment to another recognizable main setting. Establish it immediately, then vary wide views, action close-ups, tracking and foreground passes inside the segment. Three clips at the same table with different zoom levels do not satisfy this default.

Possible story route: office interruption → commute pressure → outdoor break. This is an example, not a reusable compulsory plot. Re-block for 9:16 with vertical depth and reveals instead of reusing a horizontal layout. Respect an explicit single-location request or an approved return/callback.

Phase A names each location, its narrative purpose, and what connects the cut: character/prop identity, same travel direction, movement, a motivated foreground wipe, or an intentional time jump. Continuity means the story and characters continue, not that every desk, wall or window must be copied. Keep geometry stable within a continuous shot; new locations may have different scenery and furniture.

## Separate design, position and state

Use four distinct scopes in every standalone prompt:

1. Static design: character appearance; this clip's location and fixed furniture.
2. Movable prop identity: count, shape, color and relevant faces; no permanent initial placement.
3. First frame and timed transfers: who holds each prop, where it starts, what moves and which old location becomes empty.
4. Final state: what remains visible and which changes persist; do not restore initial placements after a departure or cut.

Do not put “the bag rests on the floor” into a global immutable room definition if the character later takes it away. Apply the same ownership rule to cups, pens, tools or other topic-specific props. Record object contact with its support: a lamp base touches the table; a resting cup stays on the surface; a held device touches the hand.

When an object has different visible sides, define them conditionally. For example, a phone front has a plain screen; a screen-down phone shows its unlit back, not a permanently visible colored screen. This is an optional phone adapter, not a required object in every story.

Graphical alerts or metaphors belong only to their approved timed beats. Use simple icon geometry rather than text-bearing cards. Do not place anxiety graphics into a shared global environment block and thereby recreate them in a calm final scene. Keep scenes free of captions, technical labels, color codes and random interface writing; add subtitles in post-production.

## Motion and audio

Use concrete actions, related effects and purposeful shot changes about every two to three seconds, with enough time to complete each handoff. Avoid liquid furniture transformations and too many simultaneous actions. A short sip, hesitation or reaction is useful; do not make the entire clip an idle talking pose. Warm daylight, moving leaves, passing trains and location-specific details can enrich the image without redesigning the character.

Apply the shared `voice-continuity.md` contract for every clip. Freeze the video's chosen full voice profile and repeat it verbatim; another place, mood, character age or scene cannot recast the narrator. Keep emotions in visuals/music, and environmental acoustics in SFX rather than changing dry narration into station/cafe reverb. Use a story-appropriate score with the same motif/tempo/instrumentation across segments. The style is not limited to one male voice.

## Delivery and acceptance

The skill outputs the confirmed proposal and standalone prompt package. Flow operation, paid retries, downloading and publication still require user authorization. Preserve baseline samples and use bounded, issue-specific retests.

Before publishing a result or calling it consistent, check:

- New clip openings show the approved different settings, unless a single-location request/callback was approved.
- Character count/design, head/torso fill, proportions and current limb poses remain coherent at reaches, lifts, turns and walking steps.
- Prop ownership and visible faces match the action; no simultaneous hand/background copies or end-state resets.
- Movement direction and narrative meaning connect the cuts; time jumps are named. Different furniture after an intentional location cut is not itself a failure.
- Wipes land at actual usable frames, not necessarily the last generated frame; provide a candidate trim point rather than claiming seamless assembly without checking.
- No white card border, unwanted written labels, unintended people, or pressure graphics leaking into the calm ending.
- Actual audio is compared by listening. Repeated voice text and screenshots are not audio certification.

The 2026-10-14 Flow samples support the location-change approach and show the intended visual style. They are not a guarantee of frame-perfect anatomy, prop state or voice matching; detailed scoped observations live in repository `tests/reports/style-4.md`, not as marketing claims in the README.

---

# references/historical-cartoon.md

# Style 5 — Historical Cartoon / 历史卡通风

Historical explainers, daily life, civilization stories and comic historical shorts, using expressive stick figures in colorful historical worlds.

On A5 selection, read **A5 proactive character guidance** in first-use guidance. Remind users to generate their own front/side/back character views and attach their confirmed references with the complete prompt for every clip in a supporting tool. This is advice only: do not supply or automatically generate reference images, or make them a delivery gate. Additional reference work needs an explicit user request. Users can knowingly choose text-only; references help but do not guarantee consistency.

Visual concept and Roman era-pack contribution: [Lawal Ridwan / @leksautomate](https://github.com/leksautomate), via [History Stickman](https://github.com/kaomei/stickman-video-director/pull/41). Adapted to this project's Style 5 with owner-directed cross-era trials. The contributor's PR numbering is not the published style number.

## Fixed drawing grammar

Repeat this anchor verbatim in every standalone prompt:

```text
CHARACTER: A 2D cartoon man with a round white head and a short, sturdy white neck growing naturally from his clothed shoulders and supporting his jaw. The white head and neck form one continuous filled silhouette. The lower jaw flows directly into the short white neck; the bottom of that neck enters the tunic neckline. The visible connection is white, with black outlines only along its two sides. Keep this white connection visible during walking, turns, tilts and camera cuts. Use balanced adult stickman proportions rather than a big-headed chibi: the complete standing figure is roughly four head-heights tall, the round head is visibly narrower than the clothed shoulder span, the torso is slightly longer than the head, and the thin black legs provide a natural lower-body length. The exposed neck is short, about one tenth of the head diameter tall. Thin black arms and legs, exactly two of each. Polished 2D cel-shaded historical cartoon, clean thick black outlines, softly shaded period clothing, and sunlit painterly surroundings.
FACE: An appealing, expressive storybook-cartoon face on the round white head. Two solid black vertical oval eyes; character-specific eyebrows, nose and mouth defined in the cast card, not a universal template face. Subtle cheek shading gives the face warmth without realistic skin texture. Expressions react to the action while the eye shape, nose shape, face proportions and identity remain unchanged. Hair and facial hair, when present in the cast, have a few clearly shaped locks and soft cel shading, not flat featureless patches. Keep this readable cartoon richness, not a blank symbolic face, photorealism or detailed irises.
PALMS: Each thin black wrist ends in one compact, solid black rounded oval palm with a subtle integrated thumb bump. Use the same palm-to-head proportion in both hands and all shots: total palm silhouette about 18% of head diameter long and 10% wide, including the thumb bump. It is visibly wider than the wrist, neither a wrist-tip dot nor an enlarged glove. No separate fingers, finger lines or white fill. The empty indicating gesture keeps this compact silhouette; change the arm angle instead of spreading or enlarging the palm.
EXPOSED LIMBS: Every uncovered arm, forearm, wrist and shin is one slender solid black stroke. Face and short neck use white fill; the limbs use solid black strokes. Preserve the character proportions and costume colors throughout.
```

Keep white head fill, head/body proportions, outline weight and black stick limbs fixed within a story. Open eyes are simple solid black ovals without iris/pupil detail; a blink or closed-eye expression does not redesign the eyes. Cloth, leather and metal can have soft shading and small highlights. Backgrounds are full-color painted landscapes or architecture, not empty white canvases, paper textures, ink wash, photorealistic people or glossy 3D characters. Approved night/interior lighting changes illumination, not drawing grammar. Costume may cover limbs without changing their underlying black line design.

Use this owner-selected baseline rather than stacking earlier experimental anatomy recipes. Resolve character gender/age and garment wording once in Phase A when the story requires a different cast; freeze the resulting full anchor across clips. Preserve the continuous white jaw–short-neck–garment connection in every view, not direct head-to-collar contact or a floating head. Do not treat a background-colored gap or an exposed chest panel as a neck. Hair, beard and collar may overlap but must not conceal a detached head. Keep the approved compact neck and adult proportions; do not copy one reference character's hair or costume to unrelated eras. This connection rule is A5-only. The baseline is a design target, not evidence of reliable text-only generation.

Freeze an individual face, not one national template: choose era-appropriate hair, eyebrows and expressions for the particular role without implying everyone from that country looks alike. A nose can be one short shallow black curve on the white face, smaller than half an eye's height; keep it flat, not a projecting bridge or skin-colored blob. Expressions can change with the story while identity stays fixed. If the cast calls for hair, name it explicitly and check that it is actually visible; a bald output fails that cast even when the prompt mentions hair.

The thin-black-limb rule includes exposed arm and leg segments, not sleeves or footwear. Hands use the owner's rounded black palm silhouette: a compact mitten-shaped palm visibly wider than the wrist, with one small rounded side thumb lobe and one undivided rounded finger mass. This is a single solid silhouette, not an anatomical hand, a tiny circular end cap or a white glove. No individual fingers, branching digit strokes, finger separations, digit lines or nails. Each palm attaches continuously to its thin black wrist. Show a grip through contact or overlap between the palm and the prop, supported by the arm pose; show release by moving the palm away. An empty raised hand retains this same compact silhouette without spreading fingers. Sleeves retain the approved fabric silhouette and color. Grips, releases and gestures may change pose, but keep hand scale and shape consistent across shots; avoid oversized black fists or glove-like blobs. Fixed hand design means consistent rendering, not frozen poses or permanently clenched fists. This clarification is A5-only; it does not change any A1–A4 or B-style anatomy rules.

## Phase A: era and cast

Use the existing proposal and approval workflow. Include a compact era pack:

- **Era/place:** period, region and the story's factual premise.
- **Roles/wardrobe:** each visible role's silhouette, clothing and recognizable accessory.
- **Settings:** story locations, architectural landmarks, screen direction and planned time cuts.
- **Palette:** four to six ordinary color names and their roles.
- **Props/symbols:** tools, weapons, furniture and icon-only emblems, with ownership and counts.
- **Music:** era-appropriate instruments and one coherent score direction.
- **Facts:** distinguish supported history from illustrative scenes or fictional jokes; do not invent quotations, statistics or historical events.

For a different era, draft and confirm a new pack rather than borrowing Roman armor or symbols. Adapt Egyptian, Chinese, Japanese or other clothing and buildings while preserving the drawing grammar. Do not make one Roman soldier a universal cast for all stories.

For each recurring role, write a complete story-specific cast card: role/age range, head/body proportions, continuous white jaw–short-neck–garment connection and any beard/collar overlap, face and eye shape, hair/beard or explicit absence, headwear, clothing layers and silhouette, limb treatment, black mitten-palm design with integrated thumb lobe and wrist-to-sleeve attachment, footwear and distinguishing accessory. Give recurring roles at least two visible non-color differences. Resolve concrete features instead of writing only “a soldier” or “a princess.” Freeze each approved card and repeat its **full description** in every standalone prompt where the role appears; never substitute “same character,” an ellipsis or a name alone. A crowd can use one uniform group description, with named foreground characters separately identified.

Keep appearance separate from action: a spade's shape belongs in its prop description; who holds it, in which hand, and whether it touches the ground belong in opening/action/ending states. Do not make all props permanently held or all characters permanently front-facing merely to prevent drift.

### Roman era pack

- **Place:** Roman Republic/Empire, Mediterranean roads, camps, towns and countryside; specify the period needed by the topic.
- **Soldier:** bronze-gold helmet with black horsehair crest, grey chainmail, red tunic, brown segmented leather skirt, thin black exposed limbs, small solid black mitten-shaped palms continuously attached to the wrists, one subtle integrated thumb lobe, no individual fingers, finger separations, white fills or gloves, and a short sword. Include a red shield with a gold icon only when the scene needs it. Officers can use a distinct crest or cape, frozen in their own cast cards.
- **Civilian:** cream tunic or toga with a story-specific accessory; approve the complete card rather than treating all civilians as soldiers without helmets.
- **Settings:** green hills, cypress trees, dusty roads, wooden palisades and camp ditches; Forum, harbor or market architecture when relevant.
- **Palette:** Roman red, bronze gold, steel grey, grass green, sky blue, earthy tan.
- **Music:** restrained drums, brass and strings for epic scenes; light plucked strings and woodwinds for daily life or comic scenes. No mandatory piano.
- **Treatment:** costume is simplified illustration, not evidence for an exact historical uniform. Preserve the factual narration while using fictional individual characters to illustrate it.

## Phase B: standalone clips

Each prompt contains:

1. Approved duration/ratio and technical targets. Explicitly call it a `stickman animated video`, not just an `animated video`; use the actual supported resolution rather than claiming a requested target was delivered.
2. Full drawing-style anchor, era palette and segment setting.
3. Full cast cards for every visible recurring role, plus relevant prop designs/counts.
4. Opening layout, held items, hand/owner and screen direction.
5. `[0–3s]`, `[3–7s]`, `[7–10s]` physical beats, camera work and ending state.
6. Exact approved audio-only VO and the complete frozen voice block from `voice-continuity.md`.
7. Era score, timed SFX and voice-first mix; retain the same score identity across clips.
8. Compatible negatives.

Use the existing accepted male profile by default when no other voice is requested. Honor female, older, youthful or other voice choices by resolving a complete profile through `voice-continuity.md`, then freezing it across the whole video. Cast gender or a change of era never recasts the off-screen narrator. Keep voice identity separate from music and visual emotion.

Use the five-stage engine for explainers where useful; narrative shorts can use setup → escalation → payoff without forcing a discussion question. Prefer a few readable physical actions over four unrelated effects. A deliberate reaction pause is valid. Wide establishing shots, lateral tracking, medium actions and close reactions should serve the narration. Maintain screen direction and describe a planned time jump explicitly when adjacent states do not directly match.

Keep one current pose per limb. Give prop transfers a clear release, travel and receiving state; do not spawn duplicate tools or transform one item into another. Use the smallest cast the story needs. Describe background groups as uniform ranks, not many competing named roles.

Preserve complete approved style, cast and voice blocks; there is no style-specific character-count cap. Remove conflicting or redundant wording rather than stripping identity details. If an interface rejects the length, report its actual limit before changing approved content.

```text
NO VISIBLE TEXT, LETTERS, NUMBERS, SUBTITLES, LOGOS OR WATERMARKS (blank paper or abstract brush strokes only), NO SPEECH BUBBLES, NO BLOOD OR GORE, NO PHOTOREALISTIC FACES, NO 3D CGI, NO PAPER TEXTURE, NO EXTRA LIMBS, NO FUSED OR DUPLICATE HEADS, NO COSTUME CHANGES, NO EXTRA CHARACTERS, NO INDIVIDUAL FINGERS, NO FINGER SEPARATIONS, NO WHITE HANDS OR GLOVES, NO FLOATING HEAD, NO BACKGROUND GAP BETWEEN HEAD AND NECKLINE.
```

Keep negatives compatible with the approved cast: do not ban expressive faces, the chosen nose, historical clothing or chosen hair/beards. Proactively remind users about self-generated references as above, rather than offering that advice only when asked. Keep the full prompt intact; only list specific reference files when the user actually supplies them. Never claim an attachment was submitted unless it actually was.

## Review

At the intended delivery size, check the actual continuous white jaw–short-neck–garment connection, including walking, turns, tilts and camera cuts. A background-colored gap fails even if an earlier prompt or review called the connection natural. Check neck length against the approved reference, not a long white neck or chest panel. Preserve approved head shape and proportions. The owner reference defines the target, not cross-clip stability.

Before delivery, compare repeated style/cast/voice blocks and all adjacent prop states. When generation is authorized, inspect actual footage for head fill, eye design, costume silhouette, limbs, compact black mitten palms and continuous wrist attachment during walking, grips, releases and empty-hand gestures, prop counts and action joins; listen separately for narrator consistency. Check that palms have one subtle rounded thumb lobe, without separate fingers, white fill or gloves, and do not grow into large fists. Record prompt compliance separately from observed output, and state sampling coverage rather than claiming frame-by-frame certification. Earlier round-tip or exposed-neck tests do not validate this revised silhouette; retain their failures as historical observations, not overall stability passes. Localize changes to Style 5; do not rewrite Styles 1–4.

---

# references/omni-flash-prompt-contract.md

# Omni Flash Production Prompt Contract

Use this contract only after explicit approval of the current Phase A. Refer to `references/style-catalog.md` for full style specifications and prompt blueprints. Apply `voice-continuity.md` to every style; visual-style overrides never replace its complete video-level voice profile.

Style 3 (Prehistoric Hand-Drawn / Dark Comedy): read `prehistoric-dark-comedy.md` and apply its override rules. Repeat the full approved cast descriptions for all visible roles, white filled heads, expressive cartoon faces, hair/clothing, earthy setting and layout in every prompt. Do not apply generic face/hair/texture bans or idle bans to its deliberate reaction beats. Use story-appropriate music instead of mandatory piano. Explicitly identify intended time jumps; otherwise match adjacent states. Technical output specs are targets, not guarantees of interface capabilities.

Style 4 (Cozy Storytelling / 治愈故事风): read `cozy-storytelling.md`. Repeat full character and voice anchors, but give each segment its approved new setting. Describe each scene opening as a recognizable new location, then connect action/prop/screen direction or a named time cut. Do not repeat one global room layout, inherit Style 1's no-face/filled-body bans, or require hand-drawn/paper aesthetics. Keep movable-object appearance separate from initial positions and timed state changes.

Style 5 (Historical Cartoon / 历史卡通风): read `historical-cartoon.md` for its standalone prompt order and overrides. Repeat the full frozen drawing anchor, visible cast cards, approved era pack and complete `voice-continuity.md` voice block in every clip. Keep connected short white necks, expressive individual faces, solid oval eyes, thin black exposed limbs and small solid black mitten-shaped palms continuous with the wrists, one subtle integrated thumb lobe, no individual fingers, finger separations, white fills or gloves, with historical costume and colored painterly scenery. Do not inherit Style 1's hollow-head/no-face/no-clothes contract or generic piano, three-color, four-device and no-idle requirements. Follow its era score, physical beats and planned cuts; do not shorten approved anchors to meet an arbitrary character budget.

## Production package order

Deliver these sections in order:

1. Global continuity block
2. N standalone English prompts (where N = target duration / 10; default 6 clips for 60s)
3. Stitching guide
4. Voice and music continuity note

## Global continuity block

State the chosen aspect ratio (`16:9` or `9:16`), target duration, selected visual style (Style 1 Classic, Style 2A Studio Tech, Style 2B Cinematic Story, Style 3 Prehistoric, or Style 4 Cozy Storytelling), character anchor design, palette or environment definition, narrator identity, audio arc, and continuity strategy. Treat this block as a review summary; each prompt still repeats all critical locks.

## Standalone prompt order

Write every prompt in this order:

1. Output specification: approximately ten seconds, chosen aspect ratio (`16:9` or `9:16`), 720p target, 24 FPS, synchronized audio
2. Environment and background definition:
   - For Style 1 Light: flat, uniform, digitally pure-white canvas with no shading or 3D depth
   - For Style 1 Dark: flat, uniform, pitch-black canvas with pure white line art
   - For Style 2A (Studio Tech): modern bright white studio space with subtle light-gray perspective grid lines on the floor plane, high-key lighting, clean white negative space, sleek glowing cyan/blue glass elements
   - For Style 2B (Cinematic Story): rich full-color cinematic environment with volumetric lighting and depth of field
   - For Style 4 (Cozy Storytelling): full-color 2D cartoon environment and a segment-specific setting, with varied wide/close/moving shots; new segment means an intentional scene change unless otherwise approved
3. Character lock:
   - For Style 1: repeat the concise frozen character anchor from `style-catalog.md`, including the chosen polarity and expression setting; no "same character" shortcuts, numeric anatomy recipes, skeleton/rig definitions or pen paths. Keep the circular head hollow, proportions and line weight stable, and only the current pose of each of the two arms and two legs. A raised arm replaces its old lowered line. Keep accents on props/graphics, never recolor the figure. Do not let action or camera wording redefine the drawing; preserve rich motion and effects separately.
   - For Style 2 (Modern Beanie Zeke):
     - First clip: `A minimalist 2D animated stick figure wearing a bright red beanie (smooth knit, no pom-pom) and a yellow t-shirt, with simple black stick limbs and shorts. Simple black lines, vibrant colors, smooth 2D animation style.`
     - Subsequent clips: `The same minimalist 2D animated stick figure in a bright red beanie and yellow shirt... Simple black lines, vibrant colors, smooth 2D animation style.`
   - For Style 4: repeat its full frozen character anchor from `cozy-storytelling.md`, including white head/torso fill, dark limbs and simple facial marks. Location and expression changes do not redesign the character.
4. Palette and accent roles (expressed only with ordinary color names, no hex or technical codes)
5. Composition strategy for the chosen ratio (`16:9` or `9:16`)
6. First-frame state inherited from the previous clip
7. `[0–3s]`, `[3–7s]`, and `[7–10s]` visual beats tied to spoken ideas
8. Exact audio-only English dialogue in quotation marks (strictly no speech bubbles or dialogue boxes)
9. Complete frozen English voice block from `voice-continuity.md`, verbatim in every clip: identity/age, accent, timbre, register, resonance, texture, delivery, pace and recording treatment; no "same narrator" shortcuts or clip-specific recasting
10. BGM, synchronized SFX, and voice-first mixing (subsequent clips mandate seamless BGM continuity from clip 1)
11. Final-frame transition state inherited by the next clip
12. Negative constraints (including style-specific clutter/deformation bans)

Make each prompt self-contained and usable without any external context.

## Style language

Use this wording to request density without character drift:

> rapid scene changes, kinetic motion-graphic transformations, and frequent visual events, while preserving an identical stick-figure design, constant line weight, and strict temporal consistency

Avoid `rapid style changes`, which can invite model changes to drawing style, line weight, or character design.

## Timed visual sequence & motion dynamics

Translate the approved storyboard row into three connected physical events:

- `[0–3s]`: establish or inherit the visual premise.
- `[3–7s]`: transform, escalate, or explain the metaphor through character action.
- `[7–10s]`: deliver a climax and create the next transition.

### Anti-Stutter & Anti-Lag Guidelines:
- Do not use abstract liquid or object shape morphing (e.g., stairs melting into a clock), as these cause diffusion latent jitter and frame drops.
- Drive motion with concrete character actions (leaping, touching glass, drawing luminous lines, opening heavy doors).
- Ensure continuous character engagement; never leave the character standing idle or staring at the camera for multiple seconds.

## Dialogue and visual text

Quote the approved English VO exactly once as audio-only dialogue:
```text
Audio voiceover only, strictly no speech bubbles, no dialogue boxes.
```
Instruct the model not to add, omit, paraphrase, repeat, reorder, caption, subtitle, or visually transcribe words.

Default every generated clip to no visible words, letters, numbers, captions, subtitles, interface copy, palette labels, production annotations, logos, or watermarks. Require icon-only message bubbles, content cards, clocks, meters, and notifications. Put optional approved phrases in a separate post-production overlay list outside the prompts.

## Palette notation

Use ordinary descriptive color names such as vivid red, electric blue, or warm gold. Never put hexadecimal, RGB, HSL, Pantone, or other technical color notation in a generation prompt. Models may reproduce prominent notation literally as unwanted interface text.

## Audio continuity contract

Use the shared contract in `voice-continuity.md` for Style 1 Light/Dark, Style 2A, Style 2B, Style 3 and Style 4. Choose voices per video, not per clip. Every standalone prompt carries its own full voice and music instructions:

1. **Narrator Lock**: Resolve one complete approved profile, then repeat its frozen English block verbatim across all N prompts. Use the accepted male block or build another coherent profile; do not force all videos into one voice. "Same narrator" and "continue the voice from clip 1" alone are insufficient. Separate voice identity/delivery/recording treatment from the emotional and musical arc; no scene-specific timbre changes or switches into character dialogue unless explicitly approved.
2. **BGM Lock**:
   - Clip 1 establishes the musical theme.
   - Clips 2–N explicitly instruct the model: `Audio: Voiceover seamlessly continues the identical quiet, thoughtful piano and subtle soft ambient synth from clip 1, maintaining identical tempo, instrumentation, and optimistic narrative momentum. Synchronized crisp SFX on physical actions.`

## Negative contract

Forbid:

- photorealism and unwanted 3D humanoid rendering
- facial features (pupils, realistic eyes, lips) or hair unless approved
- extra limbs, malformed anatomy, disconnected lines, or changed proportions
- broken or changing line weight
- **For Style 1**: do not reject allowed occasional simple line expressions as character drift; filled heads, sudden head/body proportion changes, duplicated/retained limb poses, body silhouettes, separate hand/foot shapes and detached body lines remain failures. Inspect actual footage at reaches, releases, turns and walking poses, and compare clips. State the scope of inspection: sparse keyframes cannot prove the absence of brief errors.
- inverted theme polarity or unexplained colors
- unintended characters or irrelevant spectacle
- visible words, letters, numbers, technical color notation, palette labels, interface copy, captions, subtitles, logos, or watermarks
- altered, omitted, repeated, reordered, or added dialogue
- speech bubbles, comic dialog balloons, or visual text boxes
- **For Style 2A specifically**: `strictly minimalist studio aesthetic, no circuit board textures, no sci-fi wall panels, no spaceship corridors, no cracked concrete, no grunge textures`
- **For Style 2B specifically**: `no photorealistic human skin, no 3D humanoid CGI models, no chaotic line glitches`

## Stitching guide

List all N clips in order. For every cut, repeat the ending state and its continuing action/prop/direction, or state the approved location/time change. Style 4 changes scenery intentionally rather than requiring identical backgrounds. Include any trim, short audio crossfade, or match-cut note needed for assembly; inspect actual generated joins rather than assuming requested wipes landed on the last frame.

## Audio continuity note

Start with prompt-level consistency, rather than immediately routing voice drift to external dubbing:

1. Check that every prompt repeats the full frozen voice block and contains no conflicting voice directions. Compare actual audio by listening, not from screenshots.
2. If authorized, retest a voice-only change while holding visual instructions, dialogue, music and generation settings fixed. User-accepted improvement in the three-clip Style 2A Hope test supports this approach, not a guarantee for every profile or style.
3. Voice/audio references when supported, or one continuous external English VO/BGM track during assembly, remain optional further controls if exact matching is required or prompt-first correction is insufficient.

## Phase B checks

- The user approved the current Phase A.
- Exactly N standalone prompts are present (matching approved Phase A duration).
- Each prompt repeats ratio (`16:9` or `9:16`), style/theme, character, palette, voice, audio, transition, and negative locks.
- Style 1 prompts repeat one identical full character block and contain no contradictory appearance instructions. Simple-expression allowance agrees with the negative constraints. Generated consistency is checked separately from prompt compliance.
- Each prompt has all three timed beats and at least four relevant visual devices.
- Every ending connects to the next opening through a planned action/prop/direction or an approved location/time cut. Style 4 does not repeat one room unless requested.
- Dialogue exactly matches the approved narration.
- Dialogue is explicitly audio-only and is never displayed visually.
- Standalone prompts contain no hexadecimal, RGB, HSL, Pantone, or other technical color notation.
- Style 2 prompts feature the verified character anchor, BGM continuity lock, and anti-clutter negative constraints.
- All styles repeat an identical complete voice block per video (or per approved recurring speaker); no unresolved profile fields, abbreviated voice references or contradictory per-scene vocal directions remain. Actual audio acceptance is recorded separately from prompt compliance.
- Generated scenes contain no visible writing; optional overlay phrases are listed separately for post-production.

---

# references/getting-started.md (solo A)

### Optional A character references

Character references are optional support for stronger visual consistency or a personalized character, not a new setup requirement for all A users. Explain the option in first-use guidance; if the user has not chosen it, continue the ordinary Director workflow without blocking on a three-view sheet or adding an approval gate. This section is A-only; it does not impose a reference workflow on B.

When chosen, help define a character within the selected A style's permitted variations and confirm front, side and back views before delivering final clip prompts. Reuse suitable user-approved references rather than requiring new images. Include the character/reference plan in Phase A; a reference that changes an already approved global design follows the existing proposal-revision rule. Keep fixed style anchors, anatomy and character constraints intact: do not silently override them to copy an incompatible reference. Explain any conflict and resolve it with the user.

At prompt handoff, explain that the user attaches the approved character image(s) as a separate reference input for **every generated clip** when the chosen tool supports reference images. Verify the actual tool's support rather than promising that every platform accepts them. If unsupported, explain the limitation and offer a compatible tool or the unchanged text-prompt path. A reference can help, but is not a consistency guarantee; inspect the resulting clips.

Keep the original validated prompt templates, full style/cast anchors and frozen voice blocks as required by the selected A style. References supplement those prompts, not replace, shorten or globally rewrite them. Personalize only within that style's allowed choices, not by changing a fixed character anchor; do not import B's TTS rules or add a generic character-description block to all A prompts.

### A5 proactive character guidance

When A5 / Style 5 / Historical Cartoon is selected, proactively give this recommendation before planning, even if the user has not asked about consistency. Use the conversation language; do not hide it in a FAQ or wait for a failed generation. For example:

> 使用 A5 时，建议你先自行生成人物三视图（正面、侧面、背面），确认满意后，再做视频。在支持参考图的视频工具里，生成每段视频时，都把角色参考图和该段完整分镜提示词一起提交。只靠文字提示词，人物一致性可能不够稳定；参考图有助于保持形象，但不能保证完全一致。已有满意的角色图可以直接复用。

Explain that this is recommended, not a new mandatory setup or approval gate. If the user prefers text-only or skips character design, briefly acknowledge the consistency limitation and continue the existing Director workflow. Once this choice is known, do not repeatedly ask or repeat the warning at every clip. Suggest three views again only for a new character or a material design change.

The default A5 behavior is advice only: remind the user to generate their own reference images. Do not bundle or supply reference images, automatically generate them, require an upload, or wait for a three-view approval before delivering the ordinary proposal and prompts. Generate or review references only when the user explicitly requests that additional work; that request does not waive the host's generation permissions or cost approval. Reuse suitable approved character images when the user provides them instead of requiring new ones. This A5-specific boundary takes precedence over the general optional-reference help above.

At handoff, retain the full standalone style, cast, action and voice instructions. If references are being used, remind the user to attach their confirmed character image(s) to every clip; name specific files only when actually supplied. A reference is an additional image input, not a replacement for the prompt or permission to change A5's drawing rules. Check the chosen model/mode actually supports character-reference images; do not assume that accepting a first-frame image is the same as supporting a multi-view reference sheet, or force a multi-panel sheet to become the opening shot. Offer a supported reference workflow or the text-only path with its limitation. Do not claim guaranteed identity or stable text-to-video: recent cross-country text-only trials still showed missing hair and disconnected heads despite explicit prompt constraints.

---

# references/amber-noir.md (A6, adaptado)

# A6 · Amber Noir / 暖金暗影风

A Director style with reference-guided illustrated acting, independent narration and local finishing. It is not a B style or a new Skill. These rules apply only to A6; preserve A1–A5 and every B style. Do not load A1–A5's ten-second Omni prompt contract, mandatory four-device/three-beat pacing, always-moving rule or embedded narrator blocks for A6.

## Shared story and visual preparation

1. Reuse the supplied topic/link/script, ratio, duration and narration language. If essential creative choices are missing, ask together; otherwise plan immediately. Thirty- and sixty-second stories use the same narrative planning process. Preserve the requested total runtime; never round it to an Omni ten-second multiple.
2. Produce the director's proposal: premise, hook, causal progression and payoff; exact narration; story-specific cast and visual reference plan; shot timeline; intended SFX cues. A reaction or deliberate pause is valid acting. Do not force a discussion ending or pack decorative devices into every shot.
3. Obtain approval of this proposal before generation. Reuse approved narration and design; changes to those or the global brief require scoped reapproval, not automatic regeneration of unrelated accepted shots.
4. Plan narrative acts separately from generated clips. A Veo 3.1 clip is at most 8 seconds: a 30-second film needs at least four clips and may need more; a 60-second film needs at least eight. Allocate editorial time by story and actual speech, not a fixed six-scene or three-clip recipe. Prepare handles/cuts without speeding narration to fit.

Drawing grammar: compact matte-black round heads, connected short black necks, small cream-white eye marks and a compact line mouth; simplified black hands and limbs with a readable silhouette. Use angular illustrated contours, restrained cel shading, amber illumination and deep plum shadows in layered full-color settings. Keep dimensional lighting without turning the cast into glossy 3D toys or realistic people. The red-orange hood-down hoodie belongs to the current sample character, not every A6 story. Freeze the approved cast's proportions, wardrobe, palette and props within each film; vary locations according to the story rather than reusing one background.

For each shot record: editorial time, location and camera, visible cast, incoming prop/pose state, one clear main action and reaction, outgoing state, first-frame reference, separate VO interval, SFX cues and planned cut. Keep hand/prop contact and screen direction legible. For difficult actions, test a representative shot first within the authorized budget.

## Route 1 · Flow browser (recommended)

- Verify browser-control availability, access to the intended Flow project, supported frame input, selected model/mode, ratio, resolution, duration, output count and current credit quote. Use **Veo 3.1 Fast** as the tested starting point unless the user chooses otherwise; recheck the live interface rather than relying on historical labels or quotas.
- Let the user complete sign-in, verification or account/billing decisions. Do not request credentials, switch accounts, recharge or upgrade automatically. Existing credits may cover generation; subscription/quota conditions still apply.
- Attach the approved shot-specific first frame using the supported input. Use a short motion prompt describing the visible action and camera; keep narration text and narrator instructions out. Request a silent non-speaking actor, with only quiet ambience if supported. Verify the entered prompt/settings before one explicit submission; retain the job/result ID and check its state before retrying after an interruption.
- Review raw results for action, mouth, anatomy, contact and continuity. The actor performs, not presents or recites the story. Keep the mouth a small stable line or slightly open mark without rhythmic speech motion. Offscreen-narrator wording alone did not reliably prevent speaking in earlier tests; separate voiceover is the default, not a proven mouth-stability fix. Do not repaint, mask, replace the mouth or hide the face as a workaround.
- Export valid clips; the studio assembles them with its own voice and subtitles. If browser control or exporting is unavailable, report the specific limitation and offer user-assisted operation. Do not silently switch providers or call a prompt package a finished film.

## Expand before delivery or submission

Every image prompt must independently describe **style, visible cast, world, composition and constraints**. Repeat complete approved descriptions when needed. Internal labels may help planning, but the outgoing prompt must not contain `[STYLE LOCK]`, `[CAST LOCK]`, `[WORLD LOCK]`, template variables, `TBD`, “same as above”, “same character” or “use previous prompt” instead of those descriptions. An explicit reference input complements the full text; it does not excuse empty fields.

Describe drawing grammar in plain English: matte-black round head, connected short black neck, small cream-white eye marks/compact mouth, simplified black hands and limbs, restrained cel shading, amber light and deep plum shadows, layered illustrated environment. Avoid glossy toy rendering, photoreal people, extra limbs or disconnected anatomy. Keep the story's own clothes, setting and aspect ratio. Titles/captions are added during finishing, not baked into reference illustrations.

Use a separate **short motion prompt** only after a shot-specific first frame exists: one action/reaction and motivated camera move, non-speaking actor, no narrator script. Do not paste a character-sheet prompt or a long full-film screenplay into Veo's motion field. The provider's actual frame/duration limits still apply; narration, captions and titles are added by the studio.
