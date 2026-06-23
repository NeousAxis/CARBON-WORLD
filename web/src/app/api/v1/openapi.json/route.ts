/**
 * GET /api/v1/openapi.json — OpenAPI 3.1 specification for Tier 1 public endpoints.
 */

export const dynamic = "force-dynamic";

import { optionsResponse } from "@/lib/api/response";

const SPEC = {
  openapi: "3.1.0",
  info: {
    title: "CARBON WORLD Public API",
    version: "1.0.0",
    description:
      "Real-time ethical impact index of human decisions affecting the living world. " +
      "Scored by an AI pipeline using 7 UN reference frameworks (SDGs, UDHR, ILO, CRC, UNDRIP, " +
      "Animal Rights, Planetary Boundaries) and a 4D analysis model. " +
      "Token CBWD on Solana — scientific instrument, not a speculative asset.",
    contact: {
      name: "Neous Axis — CARBON WORLD",
      email: "hello@carbon-world.xyz",
      url: "https://carbon-world.xyz",
    },
    license: {
      name: "MIT",
      url: "https://opensource.org/licenses/MIT",
    },
  },
  servers: [
    {
      url: "https://carbon-world.xyz/api/v1",
      description: "Production",
    },
    {
      url: "http://localhost:3000/api/v1",
      description: "Local development",
    },
  ],
  components_security_schemes: {
    BearerAuth: {
      type: "http",
      scheme: "bearer",
      description: "Tier 2 Partner API key. Obtain via CLI: python3 worker/generate_api_key.py",
    },
  },
  paths: {
    "/events": {
      get: {
        summary: "List scored events",
        description:
          "Returns a paginated list of ethically scored events. Excludes justification text — use GET /events/:id for full detail.",
        operationId: "listEvents",
        tags: ["Events"],
        parameters: [
          {
            name: "limit",
            in: "query",
            schema: { type: "integer", default: 20, minimum: 1, maximum: 100 },
            description: "Number of events to return (max 100)",
          },
          {
            name: "offset",
            in: "query",
            schema: { type: "integer", default: 0, minimum: 0 },
            description: "Pagination offset",
          },
          {
            name: "decision",
            in: "query",
            schema: { type: "string", enum: ["BURN", "MINT", "NEUTRAL"] },
            description: "Filter by decision type",
          },
          {
            name: "since",
            in: "query",
            schema: { type: "string", format: "date-time" },
            description: "Return events created at or after this ISO8601 timestamp",
          },
          {
            name: "source",
            in: "query",
            schema: { type: "string" },
            description: "Filter by event source (partial match)",
          },
          {
            name: "until",
            in: "query",
            schema: { type: "string", format: "date-time" },
            description: "Return events created at or before this ISO8601 timestamp",
          },
          {
            name: "country",
            in: "query",
            schema: { type: "string" },
            description: "Filter by exact country name (see /countries for the vocabulary)",
          },
          {
            name: "region",
            in: "query",
            schema: {
              type: "string",
              enum: ["North America", "Europe", "Latin America", "Asia", "Oceania", "Africa", "MENA"],
            },
            description: "Filter by world region",
          },
          {
            name: "min_score",
            in: "query",
            schema: { type: "number" },
            description: "Only events with final_score >= this value (signed scale; BURN positive, MINT negative)",
          },
          {
            name: "max_score",
            in: "query",
            schema: { type: "number" },
            description: "Only events with final_score <= this value",
          },
          {
            name: "min_confidence",
            in: "query",
            schema: { type: "integer", minimum: 0, maximum: 10 },
            description: "Only events with confidence >= this value",
          },
          {
            name: "sort",
            in: "query",
            schema: {
              type: "string",
              enum: ["recent", "oldest", "score_desc", "score_asc"],
              default: "recent",
            },
            description: "Result ordering",
          },
        ],
        responses: {
          "200": {
            description: "Successful response",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/EventsResponse" },
              },
            },
          },
          "400": { $ref: "#/components/responses/BadRequest" },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
      post: {
        summary: "Submit an event for scoring",
        description:
          "Partner (Tier 2) submission: push a new event to the CARBON WORLD pipeline. " +
          "The event is queued with source_type=partner_direct, trust_weight=1.0, and scored " +
          "by the full 8-agent pipeline. Returns a submission_id for polling via /submissions/:id. " +
          "Rate-limited to write_quota_daily per key (default 5/day).",
        operationId: "submitEvent",
        tags: ["Events", "Tier2"],
        security: [{ BearerAuth: [] }],
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/SubmitEventRequest" },
            },
          },
        },
        responses: {
          "202": {
            description: "Accepted — submission queued",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/SubmitEventResponse" },
              },
            },
          },
          "401": { $ref: "#/components/responses/Unauthorized" },
          "422": { $ref: "#/components/responses/ValidationError" },
          "429": { $ref: "#/components/responses/WriteQuotaExceeded" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
    },
    "/events/{id}": {
      get: {
        summary: "Get event detail",
        description:
          "Returns full event data including ethical justification text (500-2000 chars).",
        operationId: "getEvent",
        tags: ["Events"],
        parameters: [
          {
            name: "id",
            in: "path",
            required: true,
            schema: { type: "integer" },
            description: "Event ID",
          },
        ],
        responses: {
          "200": {
            description: "Successful response",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/EventDetail" },
              },
            },
          },
          "404": { $ref: "#/components/responses/NotFound" },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
    },
    "/stats": {
      get: {
        summary: "Global stats",
        description:
          "Returns global event counts, CBWD supply breakdown (minted/burned/net), and cache stats.",
        operationId: "getStats",
        tags: ["Stats"],
        responses: {
          "200": {
            description: "Successful response",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/StatsResponse" },
              },
            },
          },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
    },
    "/regions": {
      get: {
        summary: "Per-region geo-economic aggregates",
        description:
          "One entry per world region with the count-based ethical_index (-1..+1), " +
          "decision breakdown, mean_score, CBWD supply, and top countries. " +
          "ethical_index = (burn_count - mint_count) / events — robust, not amount-based.",
        operationId: "listRegions",
        tags: ["Intelligence"],
        parameters: [
          { name: "since", in: "query", schema: { type: "string", format: "date-time" }, description: "Window start" },
          { name: "until", in: "query", schema: { type: "string", format: "date-time" }, description: "Window end" },
          { name: "decision", in: "query", schema: { type: "string", enum: ["BURN", "MINT", "NEUTRAL"] } },
        ],
        responses: {
          "200": { description: "Successful response", content: { "application/json": { schema: { $ref: "#/components/schemas/RegionsResponse" } } } },
          "400": { $ref: "#/components/responses/BadRequest" },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
    },
    "/countries": {
      get: {
        summary: "Per-country geo-economic aggregates + ethical index",
        operationId: "listCountries",
        tags: ["Intelligence"],
        parameters: [
          { name: "region", in: "query", schema: { type: "string" }, description: "Restrict to one world region" },
          { name: "since", in: "query", schema: { type: "string", format: "date-time" } },
          { name: "until", in: "query", schema: { type: "string", format: "date-time" } },
          { name: "decision", in: "query", schema: { type: "string", enum: ["BURN", "MINT", "NEUTRAL"] } },
          { name: "sort", in: "query", schema: { type: "string", enum: ["events", "index_desc", "index_asc"], default: "events" } },
          { name: "limit", in: "query", schema: { type: "integer", default: 50, minimum: 1, maximum: 200 } },
        ],
        responses: {
          "200": { description: "Successful response", content: { "application/json": { schema: { $ref: "#/components/schemas/CountriesResponse" } } } },
          "400": { $ref: "#/components/responses/BadRequest" },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
    },
    "/timeseries": {
      get: {
        summary: "Events / supply / index over time",
        description: "Time-bucketed aggregates (day/week/month), geo- and decision-filterable.",
        operationId: "getTimeseries",
        tags: ["Intelligence"],
        parameters: [
          { name: "interval", in: "query", schema: { type: "string", enum: ["day", "week", "month"], default: "day" } },
          { name: "region", in: "query", schema: { type: "string" } },
          { name: "country", in: "query", schema: { type: "string" } },
          { name: "decision", in: "query", schema: { type: "string", enum: ["BURN", "MINT", "NEUTRAL"] } },
          { name: "since", in: "query", schema: { type: "string", format: "date-time" } },
          { name: "until", in: "query", schema: { type: "string", format: "date-time" } },
        ],
        responses: {
          "200": { description: "Successful response", content: { "application/json": { schema: { $ref: "#/components/schemas/TimeseriesResponse" } } } },
          "400": { $ref: "#/components/responses/BadRequest" },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
    },
    "/frameworks": {
      get: {
        summary: "Aggregates across the 7 UN reference frameworks",
        description:
          "Counts framework hits and sums magnitudes (positive vs negative) across " +
          "SDG, UDHR, ILO, Animal, CRC, UNDRIP, PB — plus an SDG histogram (1-17).",
        operationId: "getFrameworks",
        tags: ["Intelligence"],
        parameters: [
          { name: "region", in: "query", schema: { type: "string" } },
          { name: "country", in: "query", schema: { type: "string" } },
          { name: "decision", in: "query", schema: { type: "string", enum: ["BURN", "MINT", "NEUTRAL"] } },
          { name: "since", in: "query", schema: { type: "string", format: "date-time" } },
          { name: "until", in: "query", schema: { type: "string", format: "date-time" } },
        ],
        responses: {
          "200": { description: "Successful response", content: { "application/json": { schema: { $ref: "#/components/schemas/FrameworksResponse" } } } },
          "400": { $ref: "#/components/responses/BadRequest" },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
    },
    "/index": {
      get: {
        summary: "Synthesized state-of-the-world index",
        description:
          "One call: global count-based ethical index, per-region ranking, and the " +
          "7-day top movers (region index now vs the prior 7-day window). Dashboard-as-API.",
        operationId: "getWorldIndex",
        tags: ["Intelligence"],
        responses: {
          "200": { description: "Successful response", content: { "application/json": { schema: { $ref: "#/components/schemas/WorldIndexResponse" } } } },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
    },
    "/firehose": {
      get: {
        summary: "Raw collected article stream",
        description:
          "Every article the collector fetches, persisted independently of whether it " +
          "survives classification — the full geopolitical/economic stream. Each item " +
          "carries became_event. Forward-only: fills as the pipeline runs (available:false until then).",
        operationId: "getFirehose",
        tags: ["Firehose"],
        parameters: [
          { name: "limit", in: "query", schema: { type: "integer", default: 50, minimum: 1, maximum: 100 } },
          { name: "offset", in: "query", schema: { type: "integer", default: 0, minimum: 0 } },
          { name: "source", in: "query", schema: { type: "string" }, description: "Partial match on source name" },
          { name: "q", in: "query", schema: { type: "string" }, description: "Partial match on title" },
          { name: "since", in: "query", schema: { type: "string", format: "date-time" } },
          { name: "until", in: "query", schema: { type: "string", format: "date-time" } },
          { name: "became_event", in: "query", schema: { type: "string", enum: ["true", "false"] } },
        ],
        responses: {
          "200": { description: "Successful response", content: { "application/json": { schema: { $ref: "#/components/schemas/FirehoseResponse" } } } },
          "400": { $ref: "#/components/responses/BadRequest" },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
    },
    "/external/gdelt": {
      get: {
        summary: "Global news stream (GDELT proxy)",
        description:
          "Cached, timeout-guarded proxy to the GDELT 2.0 Doc API — global geopolitical news. " +
          "Returns 502 upstream_error if GDELT is unreachable.",
        operationId: "getGdelt",
        tags: ["External"],
        parameters: [
          { name: "query", in: "query", required: true, schema: { type: "string", minLength: 2 }, description: "GDELT query expression" },
          { name: "max", in: "query", schema: { type: "integer", default: 25, minimum: 1, maximum: 75 } },
          { name: "timespan", in: "query", schema: { type: "string", default: "3d", example: "1d" } },
        ],
        responses: {
          "200": { description: "Successful response", content: { "application/json": { schema: { $ref: "#/components/schemas/ExternalGdeltResponse" } } } },
          "400": { $ref: "#/components/responses/BadRequest" },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "502": { $ref: "#/components/responses/UpstreamError" },
        },
      },
    },
    "/external/worldbank": {
      get: {
        summary: "Economic indicators (World Bank proxy)",
        description:
          "Cached, timeout-guarded proxy to the World Bank Indicators API — economic / " +
          "development time series. Returns 502 upstream_error if the upstream is unreachable.",
        operationId: "getWorldBank",
        tags: ["External"],
        parameters: [
          { name: "country", in: "query", required: true, schema: { type: "string", example: "US" }, description: "ISO2/ISO3 alpha code" },
          { name: "indicator", in: "query", schema: { type: "string", default: "gdp" }, description: "Friendly key (gdp, gdp_per_capita, gdp_growth, population, co2_per_capita, renewable_energy, unemployment, forest_area) or a raw World Bank code" },
          { name: "from", in: "query", schema: { type: "integer", example: 2010 } },
          { name: "to", in: "query", schema: { type: "integer", example: 2024 } },
        ],
        responses: {
          "200": { description: "Successful response", content: { "application/json": { schema: { $ref: "#/components/schemas/ExternalWorldBankResponse" } } } },
          "400": { $ref: "#/components/responses/BadRequest" },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "502": { $ref: "#/components/responses/UpstreamError" },
        },
      },
    },
    "/sources": {
      get: {
        summary: "List RSS sources",
        description:
          "Returns the full list of RSS sources monitored by the pipeline (~157 worldwide).",
        operationId: "listSources",
        tags: ["Sources"],
        responses: {
          "200": {
            description: "Successful response",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/SourcesResponse" },
              },
            },
          },
          "429": { $ref: "#/components/responses/RateLimitExceeded" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
    },
    "/events/{id}/comment": {
      post: {
        summary: "Annotate an event",
        description: "Attach a partner contextual comment to a scored event. Requires Bearer auth (Tier 2).",
        operationId: "commentEvent",
        tags: ["Events", "Tier2"],
        security: [{ BearerAuth: [] }],
        parameters: [
          {
            name: "id",
            in: "path",
            required: true,
            schema: { type: "integer" },
            description: "Event ID",
          },
        ],
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/CommentRequest" },
            },
          },
        },
        responses: {
          "201": {
            description: "Comment created",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/CommentResponse" },
              },
            },
          },
          "401": { $ref: "#/components/responses/Unauthorized" },
          "404": { $ref: "#/components/responses/NotFound" },
          "422": { $ref: "#/components/responses/ValidationError" },
        },
      },
    },
    "/submissions/{id}": {
      get: {
        summary: "Get submission status",
        description:
          "Polls the status of a partner submission. Public — no auth required. " +
          "Use the callback_url returned by POST /events.",
        operationId: "getSubmission",
        tags: ["Submissions"],
        parameters: [
          {
            name: "id",
            in: "path",
            required: true,
            schema: { type: "string" },
            description: "Submission ID (e.g. sub_20260420_amazonwatch_a1b2c3)",
          },
        ],
        responses: {
          "200": {
            description: "Submission found",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/SubmissionStatus" },
              },
            },
          },
          "404": { $ref: "#/components/responses/NotFound" },
          "500": { $ref: "#/components/responses/InternalError" },
        },
      },
    },
    "/keys/{id}/webhook": {
      post: {
        summary: "Register a webhook URL",
        description:
          "Set or update the webhook URL for the authenticated key. " +
          "CARBON WORLD will POST scored/rejected events to this URL. Requires Bearer auth.",
        operationId: "setWebhook",
        tags: ["Keys", "Tier2"],
        security: [{ BearerAuth: [] }],
        parameters: [
          {
            name: "id",
            in: "path",
            required: true,
            schema: { type: "integer" },
            description: "Key ID (must match authenticated Bearer key)",
          },
        ],
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: {
                type: "object",
                required: ["webhook_url"],
                properties: {
                  webhook_url: {
                    type: "string",
                    format: "uri",
                    example: "https://myorg.example.com/carbon-webhook",
                  },
                },
              },
            },
          },
        },
        responses: {
          "200": {
            description: "Webhook URL updated",
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  properties: {
                    status: { type: "string", example: "updated" },
                    key_id: { type: "integer" },
                    webhook_url: { type: "string", format: "uri" },
                    organization: { type: "string" },
                  },
                },
              },
            },
          },
          "401": { $ref: "#/components/responses/Unauthorized" },
          "403": { $ref: "#/components/responses/Forbidden" },
          "422": { $ref: "#/components/responses/ValidationError" },
        },
      },
    },
    "/health": {
      get: {
        summary: "Health check",
        description:
          "Liveness probe. Returns 200 when DB is reachable, 503 otherwise. Not rate-limited.",
        operationId: "healthCheck",
        tags: ["System"],
        responses: {
          "200": {
            description: "Healthy",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/HealthResponse" },
              },
            },
          },
          "503": {
            description: "Service unavailable — DB unreachable",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/HealthResponse" },
              },
            },
          },
        },
      },
    },
  },
  components: {
    schemas: {
      Event: {
        type: "object",
        properties: {
          id: { type: "integer", example: 50 },
          title: {
            type: "string",
            example: "Why China's decades-long ambition to green the desert could...",
          },
          url: { type: "string", format: "uri" },
          source: { type: "string", example: "South China Morning Post" },
          decision: { type: "string", enum: ["BURN", "MINT", "NEUTRAL"] },
          amount_cbwd: { type: "integer", example: 0 },
          final_score: { type: "number", example: 1.5 },
          confidence: { type: "integer", minimum: 0, maximum: 10, example: 6 },
          created_at: { type: "string", format: "date-time" },
          solana_tx: { type: "string", nullable: true, example: "4BAbn..." },
          link_explorer: {
            type: "string",
            format: "uri",
            nullable: true,
            example: "https://explorer.solana.com/tx/4BAbn...",
          },
          reused_from_event_id: { type: "integer", nullable: true },
        },
      },
      EventDetail: {
        allOf: [
          { $ref: "#/components/schemas/Event" },
          {
            type: "object",
            properties: {
              justification: {
                type: "string",
                description: "Full ethical synthesis (500-2000 chars)",
              },
            },
          },
        ],
      },
      EventsResponse: {
        type: "object",
        properties: {
          events: {
            type: "array",
            items: { $ref: "#/components/schemas/Event" },
          },
          pagination: {
            type: "object",
            properties: {
              limit: { type: "integer" },
              offset: { type: "integer" },
              total: { type: "integer" },
              has_more: { type: "boolean" },
            },
          },
        },
      },
      StatsResponse: {
        type: "object",
        properties: {
          total_events: { type: "integer" },
          by_decision: {
            type: "object",
            properties: {
              BURN: { type: "integer" },
              MINT: { type: "integer" },
              NEUTRAL: { type: "integer" },
            },
          },
          total_supply: {
            type: "object",
            properties: {
              minted: { type: "integer" },
              burned: { type: "integer" },
              net: { type: "integer" },
            },
          },
          last_event_at: { type: "string", format: "date-time", nullable: true },
          cache_stats: {
            type: "object",
            properties: {
              events_with_embedding: { type: "integer" },
              reused_events: { type: "integer" },
            },
          },
        },
      },
      GeoMetrics: {
        type: "object",
        description: "Shared aggregate metrics for a geography or time bucket.",
        properties: {
          events: { type: "integer" },
          by_decision: {
            type: "object",
            properties: {
              BURN: { type: "integer" },
              MINT: { type: "integer" },
              NEUTRAL: { type: "integer" },
            },
          },
          ethical_index: {
            type: "number",
            minimum: -1,
            maximum: 1,
            description: "(burn_count - mint_count) / events. Robust, count-based.",
          },
          burn_ratio: { type: "number" },
          mint_ratio: { type: "number" },
          mean_score: { type: "number", nullable: true, description: "Average signed final_score" },
          supply_cbwd: {
            type: "object",
            description: "On-chain CBWD. net is inflation-prone — do not use as the index.",
            properties: {
              minted: { type: "integer" },
              burned: { type: "integer" },
              net: { type: "integer" },
            },
          },
          last_event_at: { type: "string", format: "date-time", nullable: true },
        },
      },
      RegionsResponse: {
        type: "object",
        properties: {
          regions: {
            type: "array",
            items: {
              allOf: [
                { $ref: "#/components/schemas/GeoMetrics" },
                {
                  type: "object",
                  properties: {
                    region: { type: "string" },
                    top_countries: {
                      type: "array",
                      items: {
                        type: "object",
                        properties: { country: { type: "string" }, events: { type: "integer" } },
                      },
                    },
                  },
                },
              ],
            },
          },
          total_classified: { type: "integer" },
        },
      },
      CountriesResponse: {
        type: "object",
        properties: {
          countries: {
            type: "array",
            items: {
              allOf: [
                { $ref: "#/components/schemas/GeoMetrics" },
                {
                  type: "object",
                  properties: {
                    country: { type: "string" },
                    region: { type: "string", nullable: true },
                  },
                },
              ],
            },
          },
          total_classified: { type: "integer" },
        },
      },
      TimeseriesResponse: {
        type: "object",
        properties: {
          interval: { type: "string", enum: ["day", "week", "month"] },
          buckets: {
            type: "array",
            items: {
              allOf: [
                { $ref: "#/components/schemas/GeoMetrics" },
                { type: "object", properties: { period: { type: "string", example: "2026-06" } } },
              ],
            },
          },
        },
      },
      FrameworksResponse: {
        type: "object",
        properties: {
          frameworks: {
            type: "array",
            items: {
              type: "object",
              properties: {
                framework: { type: "string", enum: ["SDG", "UDHR", "ILO", "Animal", "CRC", "UNDRIP", "PB"] },
                positive_count: { type: "integer" },
                negative_count: { type: "integer" },
                positive_magnitude: { type: "integer" },
                negative_magnitude: { type: "integer" },
                net_magnitude: { type: "integer" },
              },
            },
          },
          sdg_histogram: {
            type: "array",
            items: {
              type: "object",
              properties: {
                sdg: { type: "integer", minimum: 1, maximum: 17 },
                positive: { type: "integer" },
                negative: { type: "integer" },
              },
            },
          },
          events_analyzed: { type: "integer" },
        },
      },
      WorldIndexResponse: {
        type: "object",
        properties: {
          generated_at: { type: "string", format: "date-time" },
          global: { $ref: "#/components/schemas/GeoMetrics" },
          by_region: {
            type: "array",
            items: {
              allOf: [
                { $ref: "#/components/schemas/GeoMetrics" },
                { type: "object", properties: { region: { type: "string" } } },
              ],
            },
          },
          top_movers: {
            type: "array",
            items: {
              type: "object",
              properties: {
                region: { type: "string" },
                index_now: { type: "number" },
                index_prev: { type: "number" },
                delta: { type: "number" },
                events_recent: { type: "integer" },
              },
            },
          },
          window_days: { type: "integer", example: 7 },
        },
      },
      FirehoseResponse: {
        type: "object",
        properties: {
          articles: {
            type: "array",
            items: {
              type: "object",
              properties: {
                url: { type: "string", format: "uri" },
                title: { type: "string" },
                source: { type: "string" },
                published: { type: "string", nullable: true },
                fetched_at: { type: "string", format: "date-time" },
                became_event: { type: "boolean", description: "True if this URL was later scored into carbon_events" },
              },
            },
          },
          pagination: {
            type: "object",
            properties: {
              limit: { type: "integer" },
              offset: { type: "integer" },
              total: { type: "integer" },
              has_more: { type: "boolean" },
            },
          },
          available: { type: "boolean", description: "False until the worker has persisted a batch" },
        },
      },
      ExternalGdeltResponse: {
        type: "object",
        properties: {
          ok: { type: "boolean", example: true },
          source: { type: "string", example: "gdelt" },
          fetched_at: { type: "string", format: "date-time" },
          cached: { type: "boolean" },
          data: {
            type: "object",
            properties: {
              query: { type: "string" },
              timespan: { type: "string" },
              count: { type: "integer" },
              articles: {
                type: "array",
                items: {
                  type: "object",
                  properties: {
                    title: { type: "string" },
                    url: { type: "string", format: "uri" },
                    domain: { type: "string" },
                    seen_date: { type: "string" },
                    language: { type: "string" },
                    source_country: { type: "string" },
                  },
                },
              },
            },
          },
        },
      },
      ExternalWorldBankResponse: {
        type: "object",
        properties: {
          ok: { type: "boolean", example: true },
          source: { type: "string", example: "worldbank" },
          fetched_at: { type: "string", format: "date-time" },
          cached: { type: "boolean" },
          data: {
            type: "object",
            properties: {
              country: { type: "string" },
              country_code: { type: "string" },
              indicator: { type: "string" },
              indicator_code: { type: "string" },
              indicator_name: { type: "string" },
              points: {
                type: "array",
                items: {
                  type: "object",
                  properties: { year: { type: "integer" }, value: { type: "number" } },
                },
              },
              latest: {
                type: "object",
                nullable: true,
                properties: { year: { type: "integer" }, value: { type: "number" } },
              },
            },
          },
          available_indicators: { type: "array", items: { type: "string" } },
        },
      },
      SourcesResponse: {
        type: "object",
        properties: {
          sources: {
            type: "array",
            items: {
              type: "object",
              properties: {
                name: { type: "string" },
                url: { type: "string", format: "uri" },
                region: { type: "string" },
                category: { type: "string" },
                language: { type: "string" },
              },
            },
          },
          count: { type: "integer" },
        },
      },
      HealthResponse: {
        type: "object",
        properties: {
          status: { type: "string", enum: ["ok", "degraded"] },
          version: { type: "string", example: "1.0.0" },
          db_reachable: { type: "boolean" },
          last_event_at: { type: "string", format: "date-time", nullable: true },
        },
      },
      Error: {
        type: "object",
        properties: {
          error: { type: "string" },
        },
      },
    },
    responses: {
      BadRequest: {
        description: "Invalid query parameter",
        content: {
          "application/json": { schema: { $ref: "#/components/schemas/Error" } },
        },
      },
      NotFound: {
        description: "Resource not found",
        content: {
          "application/json": { schema: { $ref: "#/components/schemas/Error" } },
        },
      },
      RateLimitExceeded: {
        description: "Rate limit exceeded (100 req/day/IP)",
        headers: {
          "X-RateLimit-Limit": { schema: { type: "integer" } },
          "X-RateLimit-Remaining": { schema: { type: "integer" } },
          "X-RateLimit-Reset": { schema: { type: "integer" } },
          "Retry-After": { schema: { type: "integer" } },
        },
        content: {
          "application/json": {
            schema: {
              type: "object",
              properties: {
                error: { type: "string", example: "rate_limit_exceeded" },
                retry_after_seconds: { type: "integer" },
              },
            },
          },
        },
      },
      InternalError: {
        description: "Internal server error",
        content: {
          "application/json": { schema: { $ref: "#/components/schemas/Error" } },
        },
      },
      UpstreamError: {
        description: "An external upstream (GDELT / World Bank) was unreachable or returned an error",
        content: {
          "application/json": {
            schema: {
              type: "object",
              properties: {
                error: { type: "string", example: "upstream_error" },
                source: { type: "string", example: "gdelt" },
                detail: { type: "string", example: "upstream timeout" },
              },
            },
          },
        },
      },
      Unauthorized: {
        description: "Invalid or missing Bearer API key",
        content: {
          "application/json": {
            schema: {
              type: "object",
              properties: {
                error: { type: "string", example: "unauthorized" },
                message: { type: "string" },
              },
            },
          },
        },
      },
      Forbidden: {
        description: "Authenticated key does not have permission for this resource",
        content: {
          "application/json": {
            schema: { $ref: "#/components/schemas/Error" },
          },
        },
      },
      ValidationError: {
        description: "Request payload failed schema validation",
        content: {
          "application/json": {
            schema: {
              type: "object",
              properties: {
                error: { type: "string", example: "validation_error" },
                details: {
                  type: "object",
                  additionalProperties: {
                    type: "array",
                    items: { type: "string" },
                  },
                },
              },
            },
          },
        },
      },
      WriteQuotaExceeded: {
        description: "Write quota exceeded for this key today (UTC)",
        content: {
          "application/json": {
            schema: {
              type: "object",
              properties: {
                error: { type: "string", example: "write_quota_exceeded" },
                used: { type: "integer" },
                limit: { type: "integer" },
                reset_at: { type: "string", format: "date-time" },
              },
            },
          },
        },
      },
    },
    schemas_tier2: {
      SubmitEventRequest: {
        type: "object",
        required: ["title", "description", "source_url", "published_at", "organization", "event_type"],
        properties: {
          title: { type: "string", minLength: 10, maxLength: 500, example: "Court victory halts Belo Sun gold mining in the Amazon" },
          description: { type: "string", minLength: 100, maxLength: 3000 },
          source_url: { type: "string", format: "uri" },
          published_at: { type: "string", format: "date-time" },
          organization: { type: "string", minLength: 2, maxLength: 200, example: "Amazon Watch" },
          event_type: {
            type: "string",
            enum: [
              "legal_win", "community_action", "conservation_win",
              "indigenous_rights", "labor_rights", "policy_influence",
              "whistleblower", "corporate_regression", "institutional_decision",
            ],
          },
          region: { type: "string", maxLength: 200, example: "BR / Amazon" },
          sdgs_hint: { type: "array", items: { type: "integer", minimum: 1, maximum: 17 }, maxItems: 17 },
          evidence_urls: { type: "array", items: { type: "string", format: "uri" }, maxItems: 10 },
          language: { type: "string", enum: ["en", "fr", "es", "pt", "ar", "zh"] },
        },
      },
      SubmitEventResponse: {
        type: "object",
        properties: {
          status: { type: "string", example: "accepted" },
          submission_id: { type: "string", example: "sub_20260420_amazonwatch_a1b2c3" },
          queue_position: { type: "integer" },
          estimated_scoring_time_seconds: { type: "integer", example: 180 },
          callback_url: { type: "string", format: "uri" },
        },
      },
      SubmissionStatus: {
        type: "object",
        properties: {
          submission_id: { type: "string" },
          status: {
            type: "string",
            enum: ["pending", "classifying", "scored", "rejected_invalid", "rejected_duplicate"],
          },
          received_at: { type: "string", format: "date-time" },
          processed_at: { type: "string", format: "date-time", nullable: true },
          resulting_event_id: { type: "integer", nullable: true },
          resulting_event_url: { type: "string", format: "uri", nullable: true },
        },
      },
      CommentRequest: {
        type: "object",
        required: ["comment"],
        properties: {
          comment: { type: "string", minLength: 10, maxLength: 1000 },
        },
      },
      CommentResponse: {
        type: "object",
        properties: {
          status: { type: "string", example: "created" },
          comment_id: { type: "integer" },
          event_id: { type: "integer" },
          organization: { type: "string" },
          created_at: { type: "string", format: "date-time" },
        },
      },
    },
  },
};

export async function OPTIONS() {
  return optionsResponse();
}

export async function GET() {
  return new Response(JSON.stringify(SPEC, null, 2), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "public, max-age=3600",
    },
  });
}

