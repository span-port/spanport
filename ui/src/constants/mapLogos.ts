// Service map logos: which brand a box's name points to (first match wins), and the drawn icon
// for each kind of box when no brand matches. AWS, OpenAI, Azure, Slack and Twilio aren't in
// simple-icons (the brands asked for removal), so their boxes get the drawn icon.
import {
  siAlgolia,
  siAnthropic,
  siApachecassandra,
  siApachekafka,
  siAtlassian,
  siAuth0,
  siClickhouse,
  siCloudflare,
  siCockroachlabs,
  siDatadog,
  siDeepseek,
  siDiscord,
  siElasticsearch,
  siFirebase,
  siGithub,
  siGitlab,
  siGoogle,
  siGooglegemini,
  siHubspot,
  siHuggingface,
  siInfluxdb,
  siMailgun,
  siMariadb,
  siMeilisearch,
  siMeta,
  siMistralai,
  siMongodb,
  siMysql,
  siNeo4j,
  siNetlify,
  siNotion,
  siOkta,
  siOllama,
  siPaypal,
  siPerplexity,
  siPlanetscale,
  siPostgresql,
  siQdrant,
  siRabbitmq,
  siRazorpay,
  siRedis,
  siResend,
  siSentry,
  siShopify,
  siSnowflake,
  siSqlite,
  siStripe,
  siSupabase,
  siTelegram,
  siUpstash,
  siVercel,
  siWhatsapp,
  siZendesk,
  type SimpleIcon,
} from "simple-icons";

/** A brand logo for any box whose name (lower case) contains one of `keywords`. */
export interface MapLogo {
  keywords: readonly string[];
  icon: SimpleIcon;
}

// More specific names first (Gemini's API is on googleapis.com, so it comes before Google).
export const MAP_LOGOS: readonly MapLogo[] = [
  { keywords: ["postgres"], icon: siPostgresql },
  { keywords: ["mariadb"], icon: siMariadb },
  { keywords: ["mysql"], icon: siMysql },
  { keywords: ["redis"], icon: siRedis },
  { keywords: ["mongo"], icon: siMongodb },
  { keywords: ["sqlite"], icon: siSqlite },
  { keywords: ["clickhouse"], icon: siClickhouse },
  { keywords: ["elasticsearch", "elastic-cloud"], icon: siElasticsearch },
  { keywords: ["cassandra"], icon: siApachecassandra },
  { keywords: ["neo4j"], icon: siNeo4j },
  { keywords: ["cockroach"], icon: siCockroachlabs },
  { keywords: ["influx"], icon: siInfluxdb },
  { keywords: ["snowflake"], icon: siSnowflake },
  { keywords: ["supabase"], icon: siSupabase },
  { keywords: ["planetscale", "psdb.cloud"], icon: siPlanetscale },
  { keywords: ["upstash"], icon: siUpstash },
  { keywords: ["qdrant"], icon: siQdrant },
  { keywords: ["kafka"], icon: siApachekafka },
  { keywords: ["rabbitmq", "amqp"], icon: siRabbitmq },
  { keywords: ["anthropic", "claude"], icon: siAnthropic },
  { keywords: ["gemini", "generativelanguage"], icon: siGooglegemini },
  { keywords: ["mistral"], icon: siMistralai },
  { keywords: ["deepseek"], icon: siDeepseek },
  { keywords: ["perplexity"], icon: siPerplexity },
  { keywords: ["ollama"], icon: siOllama },
  { keywords: ["huggingface", "hf.co"], icon: siHuggingface },
  { keywords: ["github"], icon: siGithub },
  { keywords: ["gitlab"], icon: siGitlab },
  { keywords: ["stripe"], icon: siStripe },
  { keywords: ["paypal"], icon: siPaypal },
  { keywords: ["razorpay"], icon: siRazorpay },
  { keywords: ["shopify"], icon: siShopify },
  { keywords: ["mailgun"], icon: siMailgun },
  { keywords: ["resend"], icon: siResend },
  { keywords: ["sentry"], icon: siSentry },
  { keywords: ["datadog"], icon: siDatadog },
  { keywords: ["cloudflare"], icon: siCloudflare },
  { keywords: ["vercel"], icon: siVercel },
  { keywords: ["netlify"], icon: siNetlify },
  { keywords: ["firebase", "firestore"], icon: siFirebase },
  { keywords: ["auth0"], icon: siAuth0 },
  { keywords: ["okta"], icon: siOkta },
  { keywords: ["atlassian", "jira"], icon: siAtlassian },
  { keywords: ["hubspot"], icon: siHubspot },
  { keywords: ["zendesk"], icon: siZendesk },
  { keywords: ["notion.so", "notion.com"], icon: siNotion },
  { keywords: ["algolia"], icon: siAlgolia },
  { keywords: ["meilisearch"], icon: siMeilisearch },
  { keywords: ["discord"], icon: siDiscord },
  { keywords: ["telegram"], icon: siTelegram },
  { keywords: ["whatsapp"], icon: siWhatsapp },
  { keywords: ["facebook", "instagram"], icon: siMeta },
  { keywords: ["google"], icon: siGoogle },
];

// Drawn (stroked, 24 × 24) icons per kind of box: a server, a database, a globe, a sparkle.
export const MAP_KIND_ICONS = {
  service: "M4 4h16v6H4z M4 14h16v6H4z M7.5 7h.01 M7.5 17h.01",
  db: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6 M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  external:
    "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M3 12h18 M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.5-3.5-9s1-6.5 3.5-9z",
  llm: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z M19 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z",
} as const;

// A brand colour darker than this (relative luminance, 0 to 1) is drawn in the text colour
// instead, so black logos (GitHub, Vercel) stay visible on the dark boxes.
export const MIN_LOGO_LUMINANCE = 0.12;
export const HEX_RADIX = 16;
export const MAX_COLOR_CHANNEL = 255;
// Luminance weights of red, green and blue (ITU-R BT.709).
export const LUMINANCE_WEIGHTS = [0.2126, 0.7152, 0.0722] as const;
