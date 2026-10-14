CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.nndss_weekly (
  year int, week int, label text, states text,
  location1 text, location2 text,
  m1 numeric, m1_flag text, m2 numeric, m2_flag text,
  m3 numeric, m3_flag text, m4 numeric, m4_flag text,
  sort_order text, ingested_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (year, week, label, states)
);

CREATE TABLE IF NOT EXISTS raw.oregon_monthly (
  mmwr_year int, month int, report_period_start date, report_period_end date,
  disease_name text, demographic text, demographic_level text,
  geo_name text, geo_unit text, age_group text, confirmation_status text,
  cases int, is_masked boolean, count_label text,
  population numeric, pop_source text, run_date date,
  ingested_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (mmwr_year, month, disease_name, demographic, demographic_level, confirmation_status)
);

CREATE TABLE IF NOT EXISTS raw.census_population (
  name text, year int, population bigint, region text, division text,
  ingested_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (name, year)
);
