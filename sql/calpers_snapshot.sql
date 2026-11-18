\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE source_rows (
    program text NOT NULL CHECK (program IN ('private_equity', 'private_debt')),
    source_row integer NOT NULL CHECK (source_row > 0),
    fund text NOT NULL,
    vintage integer NOT NULL,
    commitment_raw text,
    paid_in_raw text,
    distributions_raw text,
    total_value_raw text,
    irr_raw text,
    multiple_raw text,
    PRIMARY KEY (program, source_row)
);

\copy source_rows FROM 'data/source_rows.tsv' WITH (FORMAT csv, DELIMITER E'\t', QUOTE E'\x01', NULL '')

CREATE TEMP TABLE programmes (
    program text PRIMARY KEY,
    programme text NOT NULL,
    expected_count integer NOT NULL,
    early_life_from integer NOT NULL
);
INSERT INTO programmes VALUES
    ('private_equity', 'Private Equity', 485, 2021),
    ('private_debt', 'Private Debt', 66, 2020);

DO $$
BEGIN
    IF EXISTS (
        SELECT p.program
        FROM programmes p LEFT JOIN source_rows s USING (program)
        GROUP BY p.program, p.expected_count
        HAVING count(s.source_row) <> p.expected_count
            OR min(s.source_row) <> 1 OR max(s.source_row) <> p.expected_count
    ) THEN
        RAISE EXCEPTION 'The saved CalPERS snapshot has an unexpected row count or sequence';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM source_rows s
        CROSS JOIN LATERAL unnest(ARRAY[
            commitment_raw, paid_in_raw, distributions_raw, total_value_raw
        ]) AS t(amount)
        WHERE amount !~ '^\$-?([0-9]+|[0-9]{1,3}(,[0-9]{3})+)$'
            AND amount NOT IN ('N/M', 'N/A', '—', '-')
    ) THEN
        RAISE EXCEPTION 'Unrecognised source amount';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM source_rows s
        CROSS JOIN LATERAL (VALUES (irr_raw, '%'), (multiple_raw, 'x')) AS t(raw, suffix)
        CROSS JOIN LATERAL (
            SELECT btrim(regexp_replace(raw, '\s*\[[0-9]+\]', '', 'g')) AS clean
        ) AS parsed
        WHERE clean !~ ('^-?[0-9]+(\.[0-9]+)?' || suffix || '$')
            AND clean NOT IN ('', 'N/M', 'N/A', '—', '-')
    ) THEN
        RAISE EXCEPTION 'Unrecognised reported IRR or multiple';
    END IF;
END $$;

CREATE FUNCTION pg_temp.usd(raw text) RETURNS bigint
LANGUAGE sql IMMUTABLE STRICT AS $$
    SELECT CASE WHEN raw ~ '^\$-?[0-9,]+$' THEN translate(raw, '$,', '')::bigint END
$$;

CREATE FUNCTION pg_temp.reported(raw text, suffix text) RETURNS numeric
LANGUAGE sql IMMUTABLE STRICT AS $$
    SELECT substring(btrim(regexp_replace(raw, '\s*\[[0-9]+\]', '', 'g'))
        FROM ('^(-?[0-9]+(?:\.[0-9]+)?)' || suffix || '$'))::numeric
$$;

CREATE TEMP VIEW fund_metrics AS
WITH parsed AS (
    SELECT s.program, p.programme, s.source_row, s.fund, s.vintage,
        pg_temp.usd(commitment_raw) AS commitment,
        pg_temp.usd(paid_in_raw) AS paid_in,
        pg_temp.usd(distributions_raw) AS distributions,
        pg_temp.usd(total_value_raw) AS total_value,
        irr_raw, multiple_raw,
        pg_temp.reported(irr_raw, '%') AS reported_irr_pct,
        pg_temp.reported(multiple_raw, 'x') AS reported_multiple,
        vintage >= p.early_life_from OR coalesce(multiple_raw LIKE '%[1]%', false) AS early_life,
        count(*) OVER (PARTITION BY s.program, s.fund, s.vintage) > 1 AS duplicate_fund
    FROM source_rows s JOIN programmes p USING (program)
), ratios AS (
    SELECT *, total_value - distributions AS nav,
        CASE WHEN paid_in > 0 THEN distributions::numeric / paid_in END AS dpi,
        CASE WHEN paid_in > 0 THEN (total_value - distributions)::numeric / paid_in END AS rvpi,
        CASE WHEN paid_in > 0 THEN total_value::numeric / paid_in END AS tvpi,
        CASE WHEN total_value > 0 THEN distributions::numeric / total_value END AS realised_share
    FROM parsed
)
SELECT *,
    tvpi - reported_multiple AS multiple_delta,
    CASE
        WHEN tvpi IS NULL OR reported_multiple IS NULL THEN 'No comparable multiple'
        WHEN abs(tvpi - reported_multiple) <= 0.05000001 THEN 'Within rounding'
        ELSE 'Review difference'
    END AS multiple_check,
    commitment IS NULL OR paid_in IS NULL OR distributions IS NULL OR total_value IS NULL AS missing_amount,
    least(commitment, paid_in, distributions, total_value, nav) < 0 AS negative_amount,
    coalesce(paid_in <= 0, false) AS nonpositive_paid_in,
    coalesce(paid_in > commitment, false) AS paid_in_over_commitment,
    coalesce(reported_irr_pct <= 1 AND reported_multiple >= 1.2, false) AS irr_flag,
    CASE
        WHEN fund LIKE 'Advent International GPE%' THEN 'Advent International'
        WHEN fund LIKE 'Ares Senior Direct Lending Fund%' THEN 'Ares Management'
    END AS manager
FROM ratios;

CREATE TEMP VIEW ranked_funds AS
WITH eligible AS (
    SELECT * FROM fund_metrics
    WHERE NOT early_life AND NOT negative_amount AND NOT duplicate_fund
        AND multiple_check = 'Within rounding'
), peer_summary AS (
    SELECT program, vintage, count(*) AS peer_count,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY tvpi) AS peer_median_tvpi
    FROM eligible GROUP BY program, vintage
), peer_rank AS (
    SELECT program, source_row,
        rank() OVER (PARTITION BY program, vintage ORDER BY tvpi DESC)
            + (count(*) OVER (PARTITION BY program, vintage, tvpi) - 1) / 2.0 AS cohort_rank
    FROM eligible
)
SELECT f.*, p.peer_count, p.peer_median_tvpi, r.cohort_rank,
    CASE WHEN p.peer_count >= 8
        THEN 1 + floor(4 * (r.cohort_rank - 0.5) / p.peer_count)::integer
    END AS quartile
FROM fund_metrics f
LEFT JOIN peer_rank r USING (program, source_row)
LEFT JOIN peer_summary p ON p.program = f.program AND p.vintage = f.vintage AND r.source_row IS NOT NULL;

-- Descriptive cohort statistics include all computed ratios. Peer rankings have stricter eligibility.
CREATE TEMP VIEW cohort_summary AS
SELECT program, vintage, count(*) AS rows, count(dpi) AS dpi_n,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY dpi) AS median_dpi,
    count(tvpi) AS tvpi_n,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY tvpi) AS median_tvpi,
    percentile_cont(0.25) WITHIN GROUP (ORDER BY tvpi) AS p25_tvpi,
    percentile_cont(0.75) WITHIN GROUP (ORDER BY tvpi) AS p75_tvpi
FROM fund_metrics GROUP BY program, vintage;

\copy (SELECT * FROM ranked_funds ORDER BY program, source_row) TO 'powerbi/.build/fund_snapshot.csv' WITH (FORMAT csv, HEADER true)
\copy (SELECT * FROM cohort_summary ORDER BY vintage, program) TO 'powerbi/.build/cohort_summary.csv' WITH (FORMAT csv, HEADER true)
COMMIT;
