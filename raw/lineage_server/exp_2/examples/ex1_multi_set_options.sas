/* ex1: two SET statements in one step, end=/point= options, options on the
   target, and a second target — none of the option names may leak as tables */
data work.combined(keep=id amount) work.rejects;
    length source $8;
    set raw.txn_2025(where=(status="OK")) raw.txn_2026 end=last_row;
    if amount < 0 then output work.rejects;
    else output work.combined;
    set raw.adjustments point=_n_ nobs=total;
    source = "merged";
run;
