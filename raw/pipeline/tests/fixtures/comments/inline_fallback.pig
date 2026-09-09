-- header comment before anything: the prologue bucket
-- second header line

a = LOAD 'x' USING PigStorage(',')
    -- this comment sits inside the LOAD statement's own line span,
    -- but NOT on its last line -- the inline fallback case, which has
    -- zero occurrences anywhere in this project's real corpus
    AS (f:int);

b = FILTER a BY f > 1;  -- trailing, safe on its own line after
