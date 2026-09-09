/* ============================================================
   03_seed_branches.sas
   Creates : work.branches
   Reads   : (none)
   ============================================================ */

data work.branches;
  length branch_id $6 branch_name $40 region $12;
  infile datalines dsd dlm='|' truncover;
  input branch_id branch_name region;
  datalines;
B01|Downtown|WEST
B02|Airport|WEST
B03|Midtown|EAST
B04|Harbor|EAST
B05|Central|CENTRAL
;
run;
