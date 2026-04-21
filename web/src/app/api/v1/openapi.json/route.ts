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
      name: "Cyril Leger — CARBON WORLD",
      email: "neousaxis@gmail.com",
      url: "https://carbon-token.xyz",
    },
    license: {
      name: "MIT",
      url: "https://opensource.org/licenses/MIT",
    },
  },
  servers: [
    {
      url: "https://carbon-token.xyz/api/v1",
      description: "Production",
    },
    {
      url: "http://localhost:3000/api/v1",
      description: "Local development",
    },
  ],
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

