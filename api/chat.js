// Per-mod chat, as a Vercel serverless function: POST /api/chat
// Body: { pack: "atm10", mod: "mekanism", lang: "fr", messages: [{ role, content }, ...] }
// Streams the answer back as plain text. Needs ANTHROPIC_API_KEY in the Vercel project settings.
import Anthropic from "@anthropic-ai/sdk";
import { readFileSync } from "node:fs";

const client = new Anthropic();

// Opus 5.5 by default; set CLAUDE_MODEL=claude-haiku-5-5 in Vercel for a much cheaper chat.
const MODEL = process.env.CLAUDE_MODEL || "claude-opus-5-5";
// Server-side refusal fallback exists for these models only (not Haiku)
const FALLBACK_MODELS = /^claude-(opus-5|fable-5|sonnet-5-5)/;

const MAX_TURNS = 10;
const MAX_CHARS = 1500;
const PACKS = {};

function loadPack(slug) {
  if (!/^[a-z0-9_-]+$/.test(slug)) return null;
  if (!(slug in PACKS)) {
    try {
      PACKS[slug] = JSON.parse(readFileSync(new URL(`./_data/${slug}.json`, import.meta.url), "utf8"));
    } catch {
      PACKS[slug] = null;
    }
  }
  return PACKS[slug];
}

// Best effort: each warm instance keeps its own counts, so this only slows down obvious floods.
const hits = new Map();
function tooMany(ip) {
  const now = Date.now();
  const recent = (hits.get(ip) || []).filter((t) => now - t < 60_000);
  recent.push(now);
  hits.set(ip, recent);
  return recent.length > 8;
}

function cleanMessages(raw) {
  if (!Array.isArray(raw)) return null;
  const msgs = raw
    .slice(-MAX_TURNS)
    .filter((m) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string" && m.content.trim())
    .map((m) => ({ role: m.role, content: m.content.slice(0, MAX_CHARS) }));
  while (msgs.length && msgs[0].role !== "user") msgs.shift();
  // The API needs user/assistant turns to alternate and the last one to be the player's question
  for (let i = 1; i < msgs.length; i++) if (msgs[i].role === msgs[i - 1].role) return null;
  return msgs.length && msgs.at(-1).role === "user" ? msgs : null;
}

function systemBlocks(pack, modId, mod) {
  // Block 1 is the same for every mod of the pack, block 2 changes per mod: both are cached separately
  const packText = `You are the assistant of Modpack Companion, a fan site with guides for Minecraft modpacks.
You answer players' questions about one mod as it is in the ${pack.pack.name} modpack (Minecraft ${pack.pack.minecraft}, ${pack.pack.loader}).

How to answer:
- Answer in the language the player writes in.
- Be concise and practical: a few short paragraphs or a short list, the way a helpful player would answer on Discord.
- When the mod's verified guide below covers the question, base your answer on it and say it comes from the guide.
- When it doesn't, you may use your general knowledge of the mod, but say clearly that it isn't verified for this version or this pack and that recipes and numbers should be checked in JEI/EMI. Modpacks often change recipes.
- Never invent exact recipe quantities, coordinates or config values you are not sure of.
- Stay on Minecraft, this modpack and its mods. Politely decline anything else.

Mods in this pack (name (id) version [type]):
${pack.pack.mods}`;
  const modText = mod.guide
    ? `The player is on the page of ${mod.name} (id ${modId}, version ${mod.version}, type ${mod.category}).

Verified guide for this mod (checked against the mod's source code and the pack's files):
${mod.guide}`
    : `The player is on the page of ${mod.name} (id ${modId}, version ${mod.version}, type ${mod.category}).
There is no verified guide for this mod yet: everything you say about it comes from general knowledge, so say so.`;
  return [
    { type: "text", text: packText, cache_control: { type: "ephemeral" } },
    { type: "text", text: modText, cache_control: { type: "ephemeral" } },
  ];
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "method_not_allowed" });
  }
  const ip = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim() || "unknown";
  if (tooMany(ip)) return res.status(429).json({ error: "rate_limited" });

  const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
  const pack = loadPack(String(body.pack || ""));
  const modId = String(body.mod || "");
  const mod = pack && Object.hasOwn(pack.mods, modId) ? pack.mods[modId] : null;
  const messages = cleanMessages(body.messages);
  if (!mod || !messages) return res.status(400).json({ error: "bad_request" });

  const params = {
    model: MODEL,
    max_tokens: 1500,
    // A chat answer doesn't need deep reasoning; low effort keeps it fast and cheap
    output_config: { effort: "low" },
    system: systemBlocks(pack, modId, mod),
    messages,
  };
  if (FALLBACK_MODELS.test(MODEL)) {
    params.betas = ["server-side-fallback-2026-07-01"];
    params.fallbacks = "default";
  }

  let started = false;
  try {
    const stream = client.beta.messages.stream(params);
    for await (const event of stream) {
      if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
        if (!started) {
          res.writeHead(200, { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" });
          started = true;
        }
        res.write(event.delta.text);
      }
    }
    const final = await stream.finalMessage();
    if (final.stop_reason === "refusal" && !started) {
      return res.status(200).send(body.lang === "fr" ? "Je ne peux pas répondre à cette question." : "I can't answer that question.");
    }
    if (!started) return res.status(502).json({ error: "empty_answer" });
    return res.end();
  } catch (error) {
    if (started) return res.end();
    if (error instanceof Anthropic.RateLimitError) return res.status(429).json({ error: "rate_limited" });
    if (error instanceof Anthropic.AuthenticationError) {
      console.error("chat: ANTHROPIC_API_KEY is missing or invalid");
      return res.status(500).json({ error: "not_configured" });
    }
    if (error instanceof Anthropic.APIError) {
      console.error(`chat: API error ${error.status}`, error.message);
      return res.status(502).json({ error: "upstream" });
    }
    console.error("chat:", error);
    return res.status(500).json({ error: "server" });
  }
}
