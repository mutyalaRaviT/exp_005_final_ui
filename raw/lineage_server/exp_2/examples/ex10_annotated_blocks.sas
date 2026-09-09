/*Analyzed: 08/24/2026 11:33:17
Complexity: 3 285.19187081699823 LoC: 24
Errors: 0 in 0/2 Blocks
*/

/*BLOCKID 1:2645661869534515, Proc SQL, Lines: 23 - 7 to 30 : 100%;*/
PROC SQL;

CREATE TABLE work.branch_rollup AS
SELECT
    b.branch_id,
    b.branch_name,
    b.region,
    COUNT(DISTINCT a.acct_id) AS acct_cnt,
    SUM(d.ledger_bal) AS total_ledger_bal
FROM
    work.branches b
    LEFT JOIN work.accounts a ON b.branch_id = a.branch_id
    LEFT JOIN work.daily_bal d ON a.acct_id = d.acct_id
GROUP BY
    b.branch_id,
    b.branch_name,
    b.region;

;

run;
/*ENDBLOCKID 1:2645661869534515, Proc SQL;*/

/*BLOCKID 2:7118293441055627, Data Step, Lines: 6 - 32 to 37 : 100%;*/
data mart.branch_summary;
    set work.branch_rollup(where=(acct_cnt > 0));
    avg_bal = total_ledger_bal / acct_cnt;
run;
/*ENDBLOCKID 2:7118293441055627, Data Step;*/
