-- Engine: PostgreSQL
-- Crypto market schema for the NL2SQL assistant.
-- Data is crawled live from the CoinGecko public API (no key required).
-- Loaded automatically by docker-compose on first container start.

-- One row per coin — slowly-changing metadata, upserted on every crawl.
CREATE TABLE IF NOT EXISTS coins (
  coin_id            VARCHAR(80)  PRIMARY KEY,   -- CoinGecko id, e.g. 'bitcoin'
  symbol             VARCHAR(40)  NOT NULL,      -- e.g. 'btc'
  name               VARCHAR(120) NOT NULL,      -- e.g. 'Bitcoin'
  market_cap_rank    INTEGER,
  circulating_supply NUMERIC(30, 4),
  total_supply       NUMERIC(30, 4),
  max_supply         NUMERIC(30, 4),
  ath                NUMERIC(20, 8),             -- all-time high (USD)
  ath_date           TIMESTAMP,
  updated_at         TIMESTAMP NOT NULL DEFAULT now()
);

-- One row per coin per crawl — the time series that makes the data "realtime".
CREATE TABLE IF NOT EXISTS price_ticks (
  tick_id                     BIGSERIAL PRIMARY KEY,
  coin_id                     VARCHAR(80) NOT NULL REFERENCES coins (coin_id),
  price_usd                   NUMERIC(20, 8) NOT NULL,
  market_cap                  NUMERIC(30, 2),
  total_volume                NUMERIC(30, 2),
  high_24h                    NUMERIC(20, 8),
  low_24h                     NUMERIC(20, 8),
  price_change_24h            NUMERIC(20, 8),
  price_change_pct_24h        NUMERIC(12, 4),
  market_cap_change_pct_24h   NUMERIC(12, 4),
  captured_at                 TIMESTAMP NOT NULL   -- crawl timestamp (UTC)
);

CREATE INDEX IF NOT EXISTS idx_coins_rank          ON coins       (market_cap_rank);
CREATE INDEX IF NOT EXISTS idx_ticks_coin          ON price_ticks (coin_id);
CREATE INDEX IF NOT EXISTS idx_ticks_captured_at   ON price_ticks (captured_at);
CREATE INDEX IF NOT EXISTS idx_ticks_coin_captured ON price_ticks (coin_id, captured_at);
