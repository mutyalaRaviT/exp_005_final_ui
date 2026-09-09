/* ex6: array/do-loop heavy step — lots of statements that must be ignored,
   including an array named like a keyword-ish thing and nested do blocks */
data work.scores_clean;
    set work.scores_raw(drop=tmp1-tmp9);
    array s{12} score1-score12;
    array m{12} month1-month12;
    do i = 1 to 12;
        if missing(s{i}) then do;
            s{i} = 0;
            m{i} = "imputed";
        end;
        else do;
            s{i} = round(s{i}, 0.01);
        end;
    end;
    drop i;
run;
